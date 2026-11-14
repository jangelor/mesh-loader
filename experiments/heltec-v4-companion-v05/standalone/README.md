# Heltec V4/V4.3 MeshCore Companion v0.5, standalone (single-boot)

**Release status as of 14 November 2026**

| Build | Compilation | Physical testing |
|---|---|---|
| v0.5 Mesh Loader dual-boot | Completed | **Tested successfully by the project maintainer on a Heltec V4** |
| v0.5 standalone single-boot | **Compiled successfully, merged image verified**, 14 November 2026 | **Not hardware-tested**. No spare Heltec V4 currently available |

This kit builds the same **v0.5 companion features** as the tested dual-boot variant: Quick Actions, Inbox, Quick Messages, on-device replies, and confirmation screen, using the same 15 preset messages. The standalone image intentionally **does not** include Mesh Loader, Meshtastic, or the dual-boot loader return/partition modifications.

## One-command build on macOS

Extract the ZIP to `~/Downloads`, then run:

```bash
bash ~/Downloads/heltec-v4-v05-standalone-kit/build-heltec-v05-standalone.sh
```

The script reuses the existing `~/mesh-loader-blefix` source checkout and `~/meshcore-flash` virtual environment. It downloads the pinned v3 source preparer only if a local copy is unavailable; an internet connection may be needed for that and PlatformIO dependencies. If your checkout is elsewhere, set `HELTEC_MESH_LOADER_REPO=/path/to/checkout` before the command.

The build creates a **new isolated source tree** at `~/mesh-loader-blefix/build/heltec-v4-companion-v05-standalone`, then compiles and merges the ESP32-S3 bootloader, partition table, and application. It checks the pinned upstream MeshCore commit, the Heltec V4 16 MB board definition, ESP32 image headers, partition table magic, app offset, image size, and SHA-256. It will **not flash a radio, change the existing dual-boot source, or publish anything**.

Successful output:

```text
~/Downloads/heltec-release/heltec-v4-companion-v0.5-standalone-merged-UNTESTED.bin
~/Downloads/heltec-release/heltec-v4-companion-v0.5-standalone-merged-UNTESTED.bin.sha256
~/Downloads/heltec-release/BUILD_STATUS.json
```

The filename deliberately says **UNTESTED**. Passing the build and image-format checks does not demonstrate that BLE, messaging, OLED, or LoRa work on a standalone device. The existing dual-boot hardware test does not prove the standalone variant will boot or work correctly.

## Flashing guidance, for later hardware testing

**Do not flash an in-service or irreplaceable device.** This image is intended for a Heltec WiFi LoRa 32 **V4 / V4.3 with ESP32-S3, 16 MB flash, and OLED**. It is **not** for Heltec V3, FakeTec/nRF52840, RAK, or Mesh Loader's dual-boot application partition.

A full merged **standalone** installer is written to offset **`0x0`**, not `0xA0000`. Flashing at `0x0` is **destructive**, replacing the bootloader, partition table, firmware, and potentially identity keys/configurations/filesystems. Back up the device and private keys before any future test. Do not flash this binary until a test board is available.

When a spare board arrives, first confirm boot, OLED layout/navigation, BLE pairing, correct Quick Msg destination and send confirmations, LoRa RX/TX, on-device replies, and reboot/persistence. Only then consider describing the standalone variant as hardware-tested.

## GitHub release-note wording

> **Heltec V4 Companion v0.5 experimental builds**
>
> - **Dual-boot v0.5 (Mesh Loader):** Successfully compiled and hardware-tested on a Heltec V4 by the project maintainer.
> - **Standalone v0.5 (single-boot):** Source/build and merged-image checks only. **Not hardware-tested**, as no spare Heltec V4 is currently available. Use only on an appropriate test device and at your own risk.
> - The builds use different flash layouts. Do not interchange them or their flash offsets. Existing, tested dual-boot installations should remain on the dual-boot build.

Project release: https://github.com/jangelor/mesh-loader/releases/tag/heltec-v4-companion-v05-test1

Based on MeshCore source commit `81dbae592ffad40b4212bc0b37e82b38da08f4bc` and the existing v0.5 / v3 source preparers. This is an independent experimental community modification, not an official MeshCore release.


## Standalone compilation report (14 November 2026)

The project maintainer compiled the standalone v0.5 image successfully using the build kit. PlatformIO reported `heltec_v4_companion_radio_ble SUCCESS`; the standalone merged-image format checks passed. No physical device was flashed or tested.

Binary filename: `heltec-v4-companion-v0.5-standalone-merged-UNTESTED.bin`

Reported SHA-256: `3708864cb3659a9edfe5e17dea8a087418a418f77809ce537cd9d0f8fd0f24a1`

The GitHub publisher independently verifies this checksum before upload. The binary is produced on the maintainer's Mac, not included in this source archive.
