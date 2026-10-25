#!/usr/bin/env python3
"""Prepare a NEW-INSTALL Heltec V4 Mesh Loader image from public firmware assets.

This never connects to hardware and never flashes any device. The result must be
hardware-tested before being advertised as a validated fresh installer.
"""
import argparse
import hashlib
import struct
from pathlib import Path

FLASH_SIZE = 0x1000000
CORE_ADDR = 0xA0000
CORE_SIZE = 0x300000
APP_CHECKSUM = "24ac8687995376314d6d2488fe36d7becfb0125e5a790475e97c59df69ad11d7"
PARTITIONS = {
    "nvs": (1, 2, 0x9000, 0x6000),
    "otadata": (1, 0, 0xF000, 0x2000),
    "loader": (0, 0, 0x20000, 0x7D000),
    "meshcore": (0, 0x10, CORE_ADDR, CORE_SIZE),
    "meshtas": (0, 0x11, 0x3A0000, 0x300000),
    "core_fs": (1, 0x82, 0x6A0000, 0x4B0000),
    "tastic_fs": (1, 0x82, 0xB50000, 0x4B0000),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check_partition_table(image):
    raw = image[0x8000:0x9000]
    found = {}
    for i in range(0, len(raw), 32):
        item = raw[i:i+32]
        marker = int.from_bytes(item[:2], "little")
        if marker in (0xFFFF, 0xEBEB):
            break
        if marker != 0x50AA:
            raise ValueError(f"Invalid partition-table entry at 0x{0x8000+i:X}")
        _, typ, subtype, addr, size, name, _ = struct.unpack("<HBBII16sI", item)
        key = name.split(b"\0", 1)[0].decode("ascii")
        if key in found:
            raise ValueError(f"Duplicate partition: {key}")
        found[key] = (typ, subtype, addr, size)
    if found != PARTITIONS:
        raise ValueError(f"Unexpected flash layout. Refusing to compose image.\nFound: {found}")


def build(base, companion):
    if len(base) != FLASH_SIZE:
        raise ValueError(f"Base is not a 16 MiB full merged image ({len(base):,} bytes)")
    if not (64 <= len(companion) <= CORE_SIZE) or companion[0] != 0xE9:
        raise ValueError("MeshCore input is not a correctly sized ESP32 application image")
    if sha256(companion) != APP_CHECKSUM:
        raise ValueError("MeshCore SHA-256 differs from the designated BLE-fix test1 release")
    check_partition_table(base)
    for name, offset in (("ESP bootloader", 0x0), ("Mesh Loader", 0x20000),
                         ("Meshtastic", 0x3A0000)):
        if base[offset] != 0xE9:
            raise ValueError(f"Missing {name} image at 0x{offset:X}")
    for name, start, end in (("NVS", 0x9000, 0xF000),
                             ("OTA selection", 0xF000, 0x11000),
                             ("MeshCore filesystem", 0x6A0000, 0xB50000)):
        if any(x != 0xFF for x in base[start:end]):
            raise ValueError(f"{name} is not blank in base image; refusing to distribute it")
    result = bytearray(base)
    result[CORE_ADDR:CORE_ADDR+CORE_SIZE] = b"\xff" * CORE_SIZE
    result[CORE_ADDR:CORE_ADDR+len(companion)] = companion
    check_partition_table(result)
    if result[CORE_ADDR:CORE_ADDR+len(companion)] != companion:
        raise ValueError("Internal error: MeshCore mismatch")
    if (result[:CORE_ADDR] != base[:CORE_ADDR] or
            result[CORE_ADDR+CORE_SIZE:] != base[CORE_ADDR+CORE_SIZE:]):
        raise ValueError("Internal error: changed data outside MeshCore application slot")
    return bytes(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True,
                   help="Clausefoto's public 16 MiB full merged Heltec V4 prerelease")
    p.add_argument("--meshcore", type=Path, required=True,
                   help="Published heltec-v4-meshcore-v1.18.0-blefix-test1.bin")
    p.add_argument("--output", type=Path, required=True,
                   help="Output complete 16 MiB fresh-install image")
    a = p.parse_args()
    if a.output.resolve() in (a.base.resolve(), a.meshcore.resolve()):
        p.error("Output must not overwrite either input")
    if a.output.exists():
        p.error("Output already exists; refusing to overwrite")
    base = a.base.read_bytes()
    core = a.meshcore.read_bytes()
    result = build(base, core)
    a.output.write_bytes(result)
    checksum = sha256(result)
    checksums_path = a.output.parent / (a.output.name + ".sha256")
    checksums_path.write_text(f"{checksum}  {a.output.name}\n", encoding="utf-8")
    print(f"PASS: {a.output} ({len(result):,} bytes)")
    print(f"SHA-256: {checksum}")
    print("CAUTION: EXPERIMENTAL fresh installer. Destructive at 0x0; NOT hardware-tested.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"STOP: {exc}")
