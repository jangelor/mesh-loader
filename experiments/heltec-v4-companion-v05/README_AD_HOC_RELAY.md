# Heltec V4 Companion ad hoc relay

See the [release notes](RELEASE_NOTES_AD_HOC_RELAY.md) for controls, intended use, and hardware status.

To build the application-only image, use a Mesh Loader checkout with `modules/meshcore` at `81dbae592ffad40b4212bc0b37e82b38da08f4bc` and an active Python environment with PlatformIO. The current branch’s default submodule revision is different. For a fresh checkout, pin the source with:

```sh
git -c submodule.modules/meshcore.url=https://github.com/meshcore-dev/MeshCore.git submodule update --init modules/meshcore
git -C modules/meshcore fetch https://github.com/meshcore-dev/MeshCore.git 81dbae592ffad40b4212bc0b37e82b38da08f4bc
git -C modules/meshcore checkout --detach 81dbae592ffad40b4212bc0b37e82b38da08f4bc
```

From the Mesh Loader repository root:

```sh
python3 experiments/heltec-v4-companion-v05/build_companion_v05.py --repo . --ad-hoc-relay --build
```

The builder prepares a separate tree at `build/heltec-v4-companion-v05-dualboot-adhoc-relay`. It produces the app binary and its SHA-256 in `build/companion-v05-dist`. Use the partition and backup instructions in the [v0.5 build guide](README.md) before flashing the application slot on a matching device.
