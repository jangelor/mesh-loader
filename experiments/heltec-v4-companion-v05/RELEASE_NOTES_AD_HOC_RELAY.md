# Heltec V4 Companion v0.5 ad hoc relay preview

A Heltec V4/V4.3 OLED companion running Mesh Loader can temporarily forward MeshCore packets on its active LoRa settings while using BLE and Quick Messages. Hold the user button to open **Quick Actions**, tap to **Ad hoc relay**, then hold to toggle it. **RLY** shows when the local relay is active. The toggle starts off after reboot.

## Intended use

This prerelease is for testing and ad hoc use only. Our local mesh is growing, and some areas still have sparse repeater coverage. The feature is best suited to truly off-grid use away from the usual mesh, or to a small group with few nearby nodes that needs its companions to forward packets for one another. On an established mesh, other nodes can learn routes through a temporary companion relay. Those routes may fail when the companion moves away or turns forwarding off. Keep the toggle off during ordinary use on an established repeater mesh.

## Hardware and status

This app-only binary targets the OLED Heltec V4/V4.3 with the 16 MiB Mesh Loader dual-boot layout and a MeshCore app slot at `0xA0000`. The ESP32-S3 image and checksum were verified. The relay feature still needs physical testing on a Heltec. Companion relays do not respond to dedicated Repeater Discovery requests.
