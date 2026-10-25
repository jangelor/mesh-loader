# Heltec V4 Mesh Loader: installation, upgrades, and recovery

**Status:** Experimental community instructions for the **Heltec WiFi LoRa 32 V4 / V4.3 with ESP32-S3 and 16 MB flash**. This is **not** for Heltec V3, RAK4631, or arbitrary ESP32 boards. **Read the differences below before flashing.**

## Choose your installation type

| Situation | File | Flash offset | Preserves current identities/settings? |
| --- | --- | --- | --- |
| Already running compatible Mesh Loader dual-boot; want BLE fix | `heltec-v4-meshcore-v1.18.0-blefix-test1.bin` | `0xA0000` | Intended to, provided partitions and storage formats match. Back up first. |
| Fresh/empty board, or willing to reset **everything** | `heltec-v4-full-dualboot-blefix-experimental.bin` (assemble below) | `0x0` | **NO.** The entire 16 MB image overwrites previous firmware, identities, keys, contacts, and settings. |
| Only want a MeshCore repeater | Official MeshCore **repeater** firmware | Not covered here | Mesh Loader's MeshCore build is a **BLE companion**, not a repeater. |

### What exactly is the “bootloader”?

There are **two distinct programs**:

- The **ESP32-S3 second-stage bootloader** lives in flash at offset `0x0` and reads the partition table at `0x8000`. The chip also has a built-in ROM download bootloader, which is permanent and is **not** something you flash.
- **Mesh Loader** is the **factory app** at `0x20000`. It displays the two-second selection screen and chooses the MeshCore or Meshtastic application.

A **complete merged image written at `0x0`** installs both, plus the partition table, MeshCore companion, Meshtastic, and its initial filesystem. You do **not** need a separate bootloader flash if using the merged image. The MeshCore `.bin` from the BLE-fix release is **only an application**; writing it at `0x0` is wrong.

Expected Heltec V4 16 MB layout:

| Partition | Address | Size |
| --- | --- | --- |
| ESP bootloader | `0x0` | Included in full image |
| Partition table | `0x8000` | `0x1000` reserved for table |
| NVS | `0x9000` | `0x6000` |
| OTA selection | `0xF000` | `0x2000` |
| Mesh Loader factory app | `0x20000` | `0x7D000` |
| MeshCore companion (`ota_0`) | `0xA0000` | `0x300000` |
| Meshtastic (`ota_1`) | `0x3A0000` | `0x300000` |
| MeshCore filesystem | `0x6A0000` | `0x4B0000` |
| Meshtastic filesystem | `0xB50000` | `0x4B0000` |

## Prerequisites (Mac, Windows, or Linux)

1. Use a **data-capable USB cable** and reliable power. Connect **only the target board** when possible.
2. Install Python and **esptool 4.12.0**. In a Python environment run `python -m pip install "esptool==4.12.0"`; use `py -m` rather than `python -m` on Windows if necessary.
3. Identify the actual serial port. Mac: `ls /dev/cu.usb*`; Linux: `ls /dev/ttyACM* /dev/ttyUSB*`; Windows: Device Manager → Ports (COM & LPT), e.g. `COM5`.
4. Put the Heltec V4 into ESP **download mode**: **hold PRG → tap RST → release PRG**. If a command fails to connect, recheck the port and repeat the sequence.
5. Keep the computer awake and don't interrupt flash reads/writes. On macOS you can prepend `caffeinate -di` to commands.

The commands below use **esptool 4.x** command names with underscores (`read_flash`, `write_flash`). Esptool 5.x uses hyphens; don't mix them.

## A. Update an existing compatible Mesh Loader installation (non-destructive to other partitions)

**Stop if the board is running standalone MeshCore, a different loader, or an unknown partition layout.** You must verify the **connected device** before using address `0xA0000`.

Download the [BLE-fix application and checksum](https://github.com/jangelor/mesh-loader/releases/tag/heltec-v4-blefix-test1). The application checksum is:

```
24ac8687995376314d6d2488fe36d7becfb0125e5a790475e97c59df69ad11d7
```

With the board in download mode, set your port. Replace the examples with yours:

**macOS/Linux** (Terminal):

```sh
PORT=/dev/cu.usbmodem14101            # Replace with your actual device path
python -m esptool --chip esp32s3 --port "$PORT" read_flash 0x8000 0x1000 partitions-from-device.bin
```

**Windows** (PowerShell):

```powershell
$Port = 'COM5'                        # Replace with your actual port
python -m esptool --chip esp32s3 --port $Port read_flash 0x8000 0x1000 partitions-from-device.bin
```

Check the actual board partition table with the included **read-only verifier** (from the repository root):

```sh
python scripts/verify_heltec_v4_partitions.py /path/to/partitions-from-device.bin
```

Windows example: `python scripts/verify_heltec_v4_partitions.py .\partitions-from-device.bin`. The tool checks *all* entries, including `ota_0`/`ota_1` subtype, offsets, and sizes. **Do not flash unless it prints `PASS`.**

Before updating, back up at least NVS, OTA selection, the MeshCore app, and **both** application filesystems. A full 16 MB read is the simplest complete backup (but can be slow):

**macOS/Linux:**

```sh
python -m esptool --chip esp32s3 --port "$PORT" read_flash 0x0 0x1000000 original-device-private-backup.bin
```

**Windows:**

```powershell
python -m esptool --chip esp32s3 --port $Port read_flash 0x0 0x1000000 original-device-private-backup.bin
```

Check that the backup is **16,777,216 bytes**. Store it privately; it can contain device private keys. Do not upload it to GitHub.

Only after verifying the board layout and backup, flash the MeshCore **application-only** image in your downloaded folder:

**macOS/Linux:**

```sh
python -m esptool --chip esp32s3 --port "$PORT" --baud 115200 write_flash 0xA0000 heltec-v4-meshcore-v1.18.0-blefix-test1.bin
```

**Windows:**

```powershell
python -m esptool --chip esp32s3 --port $Port --baud 115200 write_flash 0xA0000 heltec-v4-meshcore-v1.18.0-blefix-test1.bin
```

Look for `Hash of data verified`. Reset normally; test MeshCore → reset → Mesh Loader → Meshtastic → reset → Mesh Loader → MeshCore. Forget the **old MeshCore** Bluetooth bond on the phone once if needed, then pair again. Meshtastic should keep its own pairing.

## B. Fresh dual-boot installation, including both bootloaders (DESTRUCTIVE)

**This path erases existing MeshCore/Meshtastic identities, keys, and configuration.** Export app identities/settings **and** take a private full-flash backup first, exactly as described above. Even if the board seems blank, treat it as potentially configured.

As of this guide, the full merged image incorporating the BLE fix is **not yet hardware-tested**. Do not distribute it as a production/stable release. Start with a spare Heltec V4 and verify both applications before inviting wider testing.

### Prepare the complete fresh-install image (without compiling Meshtastic)

Download two **public distribution binaries** into one folder (never use another device's flash readback as a release input):

1. The `heltec-v4-full-merged.bin` from [clausefoto's Heltec V4 pre1 prerelease](https://github.com/clausefoto/mesh-loader/releases/tag/heltec-v4-mc1.18.0-mt2.8.1-pre1). This includes the ESP32 bootloader, Mesh Loader, partition table, Meshtastic 2.8.1 and its initial filesystem. Its *full-image* installation has not been independently hardware-tested by that maintainer.
2. `heltec-v4-meshcore-v1.18.0-blefix-test1.bin` from [jangelor's BLE-fix prerelease](https://github.com/jangelor/mesh-loader/releases/tag/heltec-v4-blefix-test1). This is the MeshCore companion update.

Use the published `SHA256SUMS.txt` for **each** source release to verify downloaded files. Then use the script [`scripts/compose_heltec_v4_fresh.py`](../scripts/compose_heltec_v4_fresh.py) in this repository:

```sh
python scripts/compose_heltec_v4_fresh.py \
  --base /path/to/heltec-v4-full-merged.bin \
  --meshcore /path/to/heltec-v4-meshcore-v1.18.0-blefix-test1.bin \
  --output /path/to/heltec-v4-full-dualboot-blefix-experimental.bin
```

On Windows PowerShell, put this on **one line** (or use PowerShell backticks for continuation):

```powershell
python scripts/compose_heltec_v4_fresh.py --base .\heltec-v4-full-merged.bin --meshcore .\heltec-v4-meshcore-v1.18.0-blefix-test1.bin --output .\heltec-v4-full-dualboot-blefix-experimental.bin
```

The script validates the **complete 16 MB** layout; ESP bootloader, Mesh Loader, and Meshtastic headers; blank initial NVS/OTA selection/MeshCore filesystem; checks the BLE-fix application SHA-256; replaces only the MeshCore `ota_0` slot; and generates a new checksum file. It does **not** flash hardware.

### Flash the full image at address `0x0`

Make the full private backup **first**, enter download mode, then (only on the spare/test device initially):

**macOS/Linux:**

```sh
python -m esptool --chip esp32s3 --port "$PORT" --baud 115200 write_flash 0x0 heltec-v4-full-dualboot-blefix-experimental.bin
```

**Windows:**

```powershell
python -m esptool --chip esp32s3 --port $Port --baud 115200 write_flash 0x0 heltec-v4-full-dualboot-blefix-experimental.bin
```

This full image **already includes** the ESP bootloader and factory Mesh Loader. Do **not** flash the application-only file at `0x0` or try to combine different firmware versions/partition layouts. The write can overwrite the entire 16 MB flash; previous identities and settings are not preserved.

Check `Hash of data verified`, press RST, then test the loader menu, MeshCore and Meshtastic, and reset back into the loader from both apps. After that, verify BLE connections, RF transmit/receive, and cold-start/power cycling. Record failures before calling the full installer tested.

## Recovery and troubleshooting

- **Only MeshCore boots / loader menu disappears:** The running app may lack the `esp_ota_set_boot_partition(factory)` return-to-loader patch. Reflashing the *verified compatible MeshCore application* at `0xA0000` can restore the next-reset selection. Reset twice if the first boot goes straight into the app. Don't start with `erase_flash`.
- **BLE cannot pair:** Forget the old MeshCore pairing once. Check in a BLE scanner that MeshCore and Meshtastic advertise **different** addresses. If not, stop and confirm you installed the BLE-fixed application.
- **Port missing:** Use a data USB cable, close serial monitors, repeat PRG+RST download-mode sequence, and enumerate ports again.
- **Checksum/format mismatch or unexpected partitions:** **STOP. Do not flash.**
- **Reverting:** Keep the private full-flash backup and device identity exports. Restoring a full backup is itself destructive and should be done only for that same board, with the correct size and a deliberate recovery plan; never share full backups.

**Do not use this BLE companion dual-boot image for an unattended MeshCore repeater.** Use a dedicated MeshCore repeater build for repeater installations.

## Credits and status

- Original project: [eliahreeves/mesh-loader](https://github.com/eliahreeves/mesh-loader)
- Heltec V4 dual-boot pre1 source image and work: [clausefoto/mesh-loader](https://github.com/clausefoto/mesh-loader)
- Bluetooth fix and build reliability changes: [jangelor PR #1](https://github.com/clausefoto/mesh-loader/pull/1)
- Experimental BLE-fix application binary: [jangelor release test1](https://github.com/jangelor/mesh-loader/releases/tag/heltec-v4-blefix-test1)

This procedure is community guidance, not an official firmware update. The BLE fix and return-to-loader behavior were tested on hardware; the composed full image needs its own hardware validation. AI tools assisted in development; the user/contributor performed hands-on testing.
