# Heltec V4 Companion v0.5 source build kit

This is an **uncompiled, locally reproducible source build kit** for a **separate Heltec V4/V4.3 ESP32-S3 companion**, not the Room Server. It prepares a fresh dual-boot-compatible MeshCore v1.18.0 application from the source used by the earlier v3 Quick Messages experiment. It preserves the Meshtastic/MeshCore loader return patches, BLE address adjustment, and isolated MeshCore SPIFFS partition. It does **not** include the loader, Meshtastic, or a full merged firmware image.

## Features

- Existing MeshCore OLED home pages retained, including recent adverts, radio status, BLE, advert, and discovery.
- **Quick Actions** overlay from the Home, Recent Adverts, or Radio Status pages: Inbox, Quick Msgs, Find repeaters, Advertise, Radio status, Back.
- Short press to advance, long press to select. Double-click/previous while inside Quick Actions advances instead of closing the menu.
- **Inbox** opens the existing unread-message RAM queue. It is not a durable 12-message history, and messages that have already been dismissed cannot be retrieved from this menu.
- **Quick Msgs** offers 15 editable presets. Explicitly confirm a configured channel; the first configured channel (often Public) is initially highlighted but is not sent to without selection and SEND confirmation. Outgoing channel broadcasts require deliberate SEND confirmation.
- Optional `[Quick Msg]` suffix, initially OFF after every reboot. On the confirmation screen, short presses cycle CANCEL > TOGGLE TAG > SEND. Long hold on TOGGLE TAG changes it for the current boot session; long hold on SEND requests transmission.
- When reading an incoming **channel or private message**, long hold allows a quick reply using the same preset list. Direct replies use the preserved full public key of the sender; channel replies use the original channel. Safety confirmation defaults to CANCEL.
- Existing BLE protocol, existing dual-boot loader switching, and radio configuration remain unmodified by this script.

## Preparation on macOS

The script expects the established local `~/mesh-loader-blefix` checkout, with its MeshCore submodule pinned to commit `81dbae592ffad40b4212bc0b37e82b38da08f4bc`, and your existing virtual environment containing PlatformIO. It stops if the checkout or source version does not match. It downloads a pinned copy of the previously published v3 source preparer (Git commit `32d102fe7dd2398225f2f551a7f30d999131c5af`) on first run.

Unzip this kit into Downloads and run:

```bash
cd ~/Downloads/heltec-v4-companion-v05
source ~/meshcore-flash/bin/activate
python -m platformio --version
python build_companion_v05.py --repo ~/mesh-loader-blefix --build
```

If you prefer to inspect the patched source before compiling, omit `--build` and review `~/mesh-loader-blefix/build/heltec-v4-companion-v05-dualboot`.

A successful compilation produces:

```
~/mesh-loader-blefix/build/companion-v05-dist/heltec-v4-companion-v05-dualboot-app.bin
~/mesh-loader-blefix/build/companion-v05-dist/heltec-v4-companion-v05-dualboot-app.bin.sha256
```

The script will never flash hardware, replace existing v3 builds, modify submodules, or upload code to GitHub. It refuses to overwrite a v0.5 prepared directory if its manifest no longer matches. To edit the 15 presets before your *first* build, change `quick_messages.json` before running the script.

## Flashing (only after a successful build and partition verification)

**Do not flash this binary at `0x0` or onto the Room Server.** This is an application-only image for a Heltec V4 already running the **matching 16 MiB Mesh Loader dual-boot layout**, where MeshCore is the `ota_0` app at `0xA0000`. Check the actual board first, and back up its identity and filesystem. It should have the following expected entries:

| Partition | Offset | Size |
| --- | --- | --- |
| loader | `0x20000` | `0x7D000` |
| meshcore | `0xA0000` | `0x300000` |
| meshtas | `0x3A0000` | `0x300000` |
| core_fs | `0x6A0000` | `0x4B0000` |
| tastic_fs | `0xB50000` | `0x4B0000` |

An example **only for a verified matching dual-boot device** (substitute your current port):

```bash
PORT=/dev/cu.usbmodem14101
python -m esptool --chip esp32s3 --port "$PORT" write_flash 0xA0000 \
  ~/mesh-loader-blefix/build/companion-v05-dist/heltec-v4-companion-v05-dualboot-app.bin
```

The Mesh Loader upgrade guide in `jangelor/mesh-loader` documents partition checks and backups. If the target radio currently runs a standalone MeshCore image or if its partition table is unknown, do **not** use this flashing command.

## Status and caveats

- The Python file passes static syntax checking and source-pattern unit tests. **The firmware has not been compiled or tested on physical hardware by this package's authoring environment**, which does not have a copy of your local checkout or network access to download its dependencies. A successful `platformio run` on your Mac is the next gate.
- Display layouts target the Heltec's 128×64 OLED, and should be checked in person. Font and button timing depend on the pinned firmware.
- Queued messages are not proof of delivery. BLE app history need not include on-device transmissions.
- Quick Messages require the companion's clock to be synchronized before attempting a send, as in the v3 prototype.
- The existing input handling still governs incoming preview dismissals and cannot serve as durable message storage after power loss.

## Sources

- Heltec dual-boot source: https://github.com/jangelor/mesh-loader
- Existing experimental v3 release: https://github.com/jangelor/mesh-loader/releases/tag/heltec-v4-quick-replies-v3-test1
- MeshCore 1.18: https://github.com/meshcore-dev/MeshCore
