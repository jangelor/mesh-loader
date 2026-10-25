#!/usr/bin/env python3
"""Verify a partition-table backup READ FROM A CONNECTED Heltec V4 device.

Read first: python -m esptool --chip esp32s3 --port PORT read_flash 0x8000 0x1000 partitions.bin
This script never connects to hardware or flashes it.
"""
import argparse
import struct
from pathlib import Path

EXPECTED = {
    "nvs": (1, 2, 0x9000, 0x6000),
    "otadata": (1, 0, 0xF000, 0x2000),
    "loader": (0, 0, 0x20000, 0x7D000),
    "meshcore": (0, 0x10, 0xA0000, 0x300000),
    "meshtas": (0, 0x11, 0x3A0000, 0x300000),
    "core_fs": (1, 0x82, 0x6A0000, 0x4B0000),
    "tastic_fs": (1, 0x82, 0xB50000, 0x4B0000),
}


def check(data):
    if len(data) != 0x1000:
        raise ValueError("Not a 4096-byte ESP32 partition-table backup")
    found = {}
    for i in range(0, len(data), 32):
        entry = data[i:i+32]
        magic = int.from_bytes(entry[:2], "little")
        if magic in (0xFFFF, 0xEBEB):
            break
        if magic != 0x50AA:
            raise ValueError(f"Bad entry at byte {i}: 0x{magic:04X}")
        _, typ, subtype, addr, size, name, _flags = struct.unpack("<HBBII16sI", entry)
        label = name.split(b"\0", 1)[0].decode("ascii")
        if label in found:
            raise ValueError(f"Duplicate partition: {label}")
        found[label] = (typ, subtype, addr, size)
    for name, expect in EXPECTED.items():
        actual = found.get(name)
        print(f"{name:<12} {'OK' if actual == expect else 'MISMATCH'}  {actual}")
    if found != EXPECTED:
        raise ValueError("Partition table is not the expected Mesh Loader Heltec V4 layout. STOP.")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("partition_backup", type=Path)
    a = p.parse_args()
    try:
        check(a.partition_backup.read_bytes())
    except (ValueError, OSError) as exc:
        p.exit(1, f"STOP: {exc}\n")
    print("PASS: Connected-device partition layout matches. Back up the device before any write.")


if __name__ == "__main__":
    main()
