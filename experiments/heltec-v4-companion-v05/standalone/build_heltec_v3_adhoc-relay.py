#!/usr/bin/env python3
"""Isolated, conservative Heltec V4 v0.5 standalone build and merged-image verifier.

The dual-boot compatibility patch and partition override are intentionally NEVER
applied. Outputs are clearly labeled UNTESTED until independently field-tested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import build_companion_v05 as v05

HERE = Path(__file__).resolve().parent
ENV = 'Heltec_v3_companion_radio_ble'
TARGET_REL = 'build/heltec-v3-companion-v05-adhoc-relay'
DIST_NAME = 'heltec-v3-companion-v05-adhoc-relay-merged-UNTESTED.bin'
MANIFEST_NAME = '.heltec-v3-adhoc-relay-manifest.json'


def assert_board_config(source: Path) -> None:
    ini = (source / "variants/heltec_v3/platformio.ini").read_text()

    section = "[env:Heltec_v3_companion_radio_ble]"

    if ini.count(section) != 1:
        raise RuntimeError("Missing native Heltec V3 BLE target")

    if "board = esp32-s3-devkitc-1" not in ini:
        raise RuntimeError("Unexpected Heltec V3 board definition")

    segment = ini.split(section, 1)[1].split("\n[", 1)[0]

    if "board_build.partitions" in segment:
        raise RuntimeError("Unexpected partition override")

    if "build/loader" in ini or "0xA0000" in ini:
        raise RuntimeError("Unexpected Mesh Loader configuration")

    print("Native Heltec V3 board configuration verified.")


def inspect_merged_image(binary: Path, flash_limit: int = 16 * 1024 * 1024) -> dict:
    """Recognize ESP32 bootloader, partition magic, and app at standalone offsets.

    Checks are format/packaging validation, never a substitute for physical testing.
    """
    if not binary.is_file():
        raise RuntimeError(f'Missing merged standalone binary: {binary}')
    size = binary.stat().st_size
    if not 0x10100 <= size <= flash_limit:
        raise RuntimeError(f'Unexpected merged size ({size} bytes); refusing release')
    with binary.open('rb') as file:
        def get(at: int, n: int) -> bytes:
            file.seek(at)
            return file.read(n)
        boot = get(0x0, 1)
        table = get(0x8000, 2)
        app = get(0x10000, 1)
    if boot != b'\xe9':
        raise RuntimeError('Merged image lacks ESP32 bootloader magic at 0x0')
    if table != b'\xaa\x50':
        raise RuntimeError('Merged image lacks partition table magic at 0x8000')
    if app != b'\xe9':
        raise RuntimeError('Merged image lacks standalone MeshCore app magic at 0x10000')
    return {'size': size, 'bootloader_offset': '0x0', 'partition_offset': '0x8000',
            'app_offset': '0x10000', 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}


def prepare(root: Path) -> Path:
    source = root / 'modules/meshcore'
    if not (source / 'platformio.ini').is_file():
        raise RuntimeError('MeshCore submodule missing. Use your existing ~/mesh-loader-blefix checkout.')
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != v05.UPSTREAM_SHA:
        raise RuntimeError('MeshCore submodule SHA unexpected: ' + actual + '\nExpected: ' + v05.UPSTREAM_SHA)
    assert_board_config(source)
    presets = v05.load_presets()
    manifest_data = {'feature': 'heltec-v4-companion-v05', 'flavor': 'v3-adhoc-relay',
                     'upstream': v05.UPSTREAM_SHA, 'presets': presets,
                     'boot': 'standalone', 'app_offset': '0x10000'}
    target = root / TARGET_REL
    manifest = target / MANIFEST_NAME
    if target.exists():
        if not manifest.is_file() or json.loads(manifest.read_text(encoding='utf-8')) != manifest_data:
            raise RuntimeError('Existing standalone build directory differs; not overwriting: ' + str(target))
        if v05.MARKER not in (target/'examples/companion_radio/ui-new/UITask.cpp').read_text(encoding='utf-8'):
            raise RuntimeError('Existing standalone source lacks v0.5 UI marker')
        assert_board_config(target)
        print('Reusing prepared v0.5 standalone source:', target)
        return target

    # Import the exact same v3 UI and reply hooks used for the user-tested v0.5 dualboot.
    v3 = v05.load_v3()
    print('Preparing an isolated standalone source copy:', target, flush=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git', '.pio', '__pycache__'))
    try:
        # Deliberately DO NOT call git apply common.patch or v3.insert_partition_setting.
        v3.install_ui(target, presets)
        v3.install_receive_replies(target)
        v05.patch_v05_ui(target)

        relay_patch = HERE.parent / "patches/ad-hoc-relay.patch"

        cmd = ["git", "apply", "--directory=" + TARGET_REL]

        subprocess.run(
            cmd + ["--check", str(relay_patch)],
            cwd=root, check=True
        )

        subprocess.run(
            cmd + [str(relay_patch)],
            cwd=root, check=True
        )

        # Local Companion CLI relay control.
        cpp = target / "examples/companion_radio/MyMesh.cpp"
        code = cpp.read_text()

        anchor = '  if (_prefs.getRadioPrefs()->handleCommand('

        if code.count(anchor) != 1:
            raise RuntimeError("CLI handler anchor not unique")

        cli = """
  if (strcmp(command, "get relay") == 0 ||
      strcmp(command, "set relay on") == 0 ||
      strcmp(command, "set relay off") == 0 ||
      strncmp(command, "set relay ", 10) == 0) {

    if (sender_timestamp != 0) {
      strcpy(reply, "Error: local CLI only");
      return true;
    }

    if (strcmp(command, "set relay on") == 0) {
      setAdHocRelayEnabled(true);
    } else if (strcmp(command, "set relay off") == 0) {
      setAdHocRelayEnabled(false);
    } else if (strcmp(command, "get relay") != 0) {
      strcpy(reply, "Usage: set relay on/off");
      return true;
    }

    sprintf(reply, "> ad hoc relay %s; off-grid repeat %s",
            isAdHocRelayEnabled() ? "ON" : "OFF",
            _prefs.isRepeatEn() ? "ON" : "OFF");
    return true;
  }

"""

        code = code.replace(anchor, cli + anchor, 1)
        cpp.write_text(code)

        print("Ad hoc relay and CLI controls applied.")
        assert_board_config(target)
        main_src = (target/'examples/companion_radio/main.cpp').read_text(encoding='utf-8')
        if 'esp_ota_set_boot_partition(loader_partition)' in main_src:
            raise RuntimeError('Unexpected dualboot loader-return patch in standalone main.cpp')
        manifest.write_text(json.dumps(manifest_data, indent=2) + '\n', encoding='utf-8')
    except Exception:
        shutil.rmtree(target)
        raise
    return target


def build(root: Path, target: Path) -> Path:
    cmd = [sys.executable, '-m', 'platformio', 'run', '-d', str(target), '-e', ENV]
    print('Compiling standalone companion v0.5:', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    app = target / '.pio/build' / ENV / 'firmware.bin'
    if not app.is_file() or app.open('rb').read(1) != b'\xe9':
        raise RuntimeError('Missing valid standalone ESP32 app image')
    print('Merging bootloader, partitions, and standalone app...', flush=True)
    subprocess.run(cmd + ['-t', 'mergebin'], check=True)
    merged = app.with_name('firmware-merged.bin')
    meta = inspect_merged_image(merged)
    dist = root / 'build/heltec-v3-adhoc-relay-dist'
    dist.mkdir(parents=True, exist_ok=True)
    output = dist / DIST_NAME
    shutil.copy2(merged, output)
    sha_file = dist / (DIST_NAME + '.sha256')
    sha_file.write_text(meta['sha256'] + '  ' + DIST_NAME + '\n', encoding='ascii')
    status = {
        'version': 'v0.5', 'hardware': 'Heltec WiFi LoRa 32 V3 ESP32S3 OLED',
        'variant': 'standalone', 'physical_hardware_test': 'NOT TESTED',
        'firmware_build': 'BUILT on user Mac when this script succeeds',
        'full_flash_offset': '0x0', 'app_offset': '0x10000',
        'dualboot_compatible': False, 'destructive_full_flash': True,
        'source_meshcore_sha': v05.UPSTREAM_SHA, 'file': DIST_NAME,
        'sha256': meta['sha256'], 'bytes': meta['size'],
    }
    (dist / 'BUILD_STATUS_adhoc-relay.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    release = Path.home() / 'Downloads/heltec-v3-custom-release'
    release.mkdir(parents=True, exist_ok=True)
    for p in (output, sha_file, dist / 'BUILD_STATUS_adhoc-relay.json'):
        shutil.copy2(p, release / p.name)
    print('\nSUCCESS: standalone source compiled and merged image verified.', flush=True)
    print('Standalone full installer:', release / DIST_NAME)
    print('SHA256:', meta['sha256'])
    print('STATUS: COMPILED / FORMAT-CHECKED, NOT HARDWARE-TESTED')
    print('NO DEVICE FLASHED. Never write this merged image at 0xA0000.')
    return output


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, default=Path.home() / 'mesh-loader-blefix')
    ap.add_argument('--prepare-only', action='store_true', help='Do not compile, inspect patches only')
    args = ap.parse_args()
    root = args.repo.expanduser().resolve()
    target = prepare(root)
    if not args.prepare_only:
        build(root, target)
    else:
        print('Prepared source without compiling:', target)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit('STOP: ' + str(exc))
