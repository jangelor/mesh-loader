# Heltec V4 Companion v0.5 experimental builds

Two precompiled options are offered for **Heltec WiFi LoRa 32 V4/V4.3 with ESP32-S3 and 16 MB flash**. This is a community modification of MeshCore and is not an official firmware release.

| Build | File | Flash offset | Validation |
|---|---|---|---|
| Mesh Loader dual-boot application | `heltec-v4-companion-v05-dualboot-app.bin` | `0xA0000` (only with compatible existing Mesh Loader partition layout) | Compiled and **hardware-tested by the maintainer** |
| Standalone single-boot complete installer | `heltec-v4-companion-v0.5-standalone-merged-UNTESTED.bin` | `0x0` (full, destructive fresh install) | **Compiled and format-checked only; not hardware-tested** |

These builds provide Quick Actions, inbox access, 15 Quick Message presets, on-device replies and send-confirmation UI. The standalone build omits Mesh Loader and Meshtastic; it is not for the dual-boot application slot.

**Standalone SHA-256:** `3708864cb3659a9edfe5e17dea8a087418a418f77809ce537cd9d0f8fd0f24a1`.

**Important:** `0x0` and `0xA0000` are not interchangeable. Writing the standalone merged image at `0x0` replaces the existing bootloader, partition table and firmware and may erase device identity, contacts, private keys and settings. Back up first. Do not flash a deployed/irreplaceable node. The standalone build needs physical testing on a spare Heltec V4 before a stable release can be claimed.

Firmware and source code: https://github.com/jangelor/mesh-loader/releases/tag/heltec-v4-companion-v05-test1
