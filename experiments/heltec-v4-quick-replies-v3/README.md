# Heltec V4 Quick Messages + On-device Quick Replies — experimental v3

**Source prototype only. Python preparation tests passed; not yet compiled with PlatformIO or hardware-tested.** These source changes target **Heltec V4 / V4.3 ESP32-S3, MeshCore 1.18 source at commit `81dbae592ffad40b4212bc0b37e82b38da08f4bc`.** They prepare two separate builds from the same feature code.

## How channel broadcasts work

Outgoing **Quick Messages** (including `CQ CQ CQ - anyone copying?`) prompt for a configured channel; the firmware initially highlights channel 0 if configured, otherwise the first configured channel. You deliberately select the target channel, select the preset, toggle the confirmation to SEND, and hold the device button again. **It does not automatically select Public; Public only if you explicitly select your configured Public channel.** These are channel-wide messages, not private messages. Receipt is not guaranteed.

## Replying to a message shown on the device

Incoming MeshCore channel and contact/private messages already appear on the Heltec V4 OLED even with no phone connected. This version extends the existing message preview:

- **Short press** the user button to skip/cycle unread messages (existing behavior).
- **Long press** on the displayed incoming message to open the Quick Reply menu. This replaces the previous hold-to-dismiss action.
- Select `Yes`, `No`, or `Will reply in app later` by short presses; **long press** to confirm the choice.
- On the final confirmation screen, `CANCEL` is the default. **Short press** to change it to `SEND`, then **long press** to transmit.
- **Double-click** backs out one screen, or dismisses the incoming preview from the normal read screen.

**Correct destination:** The original message stores metadata when received. For a *direct/private message*, the feature stores the sender's complete public key and attempts a **private reply to that same contact**. For a *channel message*, the feature stores the configured channel index and broadcasts the reply **to that same channel**; it does not infer a private sender from the channel's displayed text. The OLED labels the reply type. If the sender contact or channel no longer exists, the send fails rather than guessing a recipient.

A status such as `Queued; not delivered` means the transmission was accepted, **not** acknowledged by the other radio or guaranteed delivered. Private-message ACK tracking is integrated in the outgoing helper, but the initial OLED prototype does not show later ACK/timeout confirmation. Outgoing replies initiated on the device may not appear as outgoing history in the phone app when you later reconnect. Initial firmware requires the device's time to be synchronized (usually by connecting a companion app at least once after power-up) before it sends.

**Important:** This does not turn the companion into a standalone LoRa repeater. It only allows using its physical UI without the phone attached.

## Two separate variants

| Variant | Source | Output after build | Installation |
|---|---|---|---|
| **Standalone** | Stock MeshCore 1.18 plus both quick message features | `build/quick-replies-dist/heltec-v4-quick-reply-standalone-merged.bin` | Fresh **destructive full install** at address `0x0` |
| **Mesh Loader dual-boot** | Same features plus the prior BLE address split and return-to-Mesh-Loader compatibility patches | `build/quick-replies-dist/heltec-v4-quick-reply-dualboot-app.bin` | Only at `0xA0000` on the validated matching 16 MB dual-boot layout, after backup |

Neither should be flashed yet. Compile and review the results first. The standalone merged image and dual-boot application-only image **are not interchangeable**.

## Prepare and compile on your Mac

The builder reads your existing `~/mesh-loader-blefix` checkout and its pinned MeshCore submodule. It only writes **new, versioned build folders**, preserving the earlier `build/canned-*` experiment and existing public GitHub releases.

```bash
cd ~/Downloads
unzip heltec-v4-quick-replies-v3.zip
cd heltec-v4-quick-replies-v3
python -m unittest -v test_prepare.py
python prepare_quick_messages.py --repo ~/mesh-loader-blefix
```

Expected new source folders:

- `~/mesh-loader-blefix/build/canned-standalone-replies-v3/`
- `~/mesh-loader-blefix/build/canned-dualboot-replies-v3/`

If preparation passes, attempt both builds:

```bash
python prepare_quick_messages.py --repo ~/mesh-loader-blefix --build
```

Output (only upon successful PlatformIO compilation) goes into:

`~/mesh-loader-blefix/build/quick-replies-dist/`

The preparation script checks source-code anchors against the pinned MeshCore version and stops rather than modifying unexpected upstream code. It doesn't flash devices, edit your tracked Git repository, or publish releases.

**Build caveat:** The Python unit tests validate source transformations and destination selection logic, not the C++ toolchain, radio transmission, BLE connection, screen rendering, delivery, or acknowledgments. Real-device testing on a spare Heltec V4 is essential before sharing firmware.

## Edit preset broadcasts

Edit `quick_messages.json` before first preparation. This version embeds the broadcast message presets at build time. The three **reply presets** are currently hardcoded in the source-rewriter's reply UI; they're separate from broadcast presets. Messages initiated from the phone app are unaffected.

## Attribution

This independently written experiment targets [MeshCore](https://github.com/meshcore-dev/MeshCore) and the user's experimental [Mesh Loader dual-boot fork](https://github.com/jangelor/mesh-loader), including the upstream [BLE fix pull request](https://github.com/clausefoto/mesh-loader/pull/1). The proof of concept is not an official MeshCore release.
