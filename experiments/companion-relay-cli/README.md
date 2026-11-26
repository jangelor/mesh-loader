# Custom MeshCore Companion Ad Hoc Relay

Experimental community firmware based on
MeshCore 1.18.

## Supported devices

- Heltec WiFi LoRa 32 V3 standalone
- Heltec WiFi LoRa 32 V4 standalone
- SenseCAP T1000-E BLE companion

The Heltec editions include the enhanced Quick
Actions interface and OLED relay toggle.

The SenseCAP edition retains the standard
screenless companion interface.

## Companion CLI

    get relay
    set relay on
    set relay off

Custom relay defaults to OFF after reboot.

The custom relay inherits the current radio
configuration and operates independently of
the official Off-Grid Repeat functionality.

## Build targets

Heltec V3:
    Heltec_v3_companion_radio_ble

Heltec V4:
    heltec_v4_companion_radio_ble

SenseCAP T1000-E:
    t1000e_companion_radio_ble

## Base MeshCore commit

81dbae592ffad40b4212bc0b37e82b38da08f4bc

## Intended use

Camping, hiking, temporary off-grid meshes,
disaster response and contingency communications.

## Cautions

Mobile or temporary relays may invalidate
previously learned MeshCore message paths.

Additional relaying may increase airtime
utilization and battery consumption.

Avoid unnecessary relaying in established meshes.

Experimental firmware. Consult the individual
release notes for hardware validation status.
