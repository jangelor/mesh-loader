#!/usr/bin/env python3
"""Build Heltec V4 MeshCore companion v0.5 (Quick Actions, messages, v3 dual boot).

Uses the pinned v3 source preparer, prepares a NEW isolated source tree, then
performs conservative source substitutions before optionally running PlatformIO.
It never flashes the radio or mutates existing v3 build folders.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
UPSTREAM_SHA = "81dbae592ffad40b4212bc0b37e82b38da08f4bc"
V3_PROJECT_SHA = "32d102fe7dd2398225f2f551a7f30d999131c5af"
V3_URL = (
    "https://raw.githubusercontent.com/jangelor/mesh-loader/"
    + V3_PROJECT_SHA
    + "/experiments/heltec-v4-quick-replies-v3/prepare_quick_messages.py"
)
ENV = "heltec_v4_companion_radio_ble"
TARGET_REL = "build/heltec-v4-companion-v05-dualboot"
OUTPUT_NAME = "heltec-v4-companion-v05-dualboot-app.bin"
MARKER = "// HELTEC_V4_COMPANION_V05_QUICK_ACTIONS"


def only(text: str, before: str, after: str, label: str) -> str:
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {n}. Stopping safely.")
    return text.replace(before, after, 1)


def section_replace(text: str, begin: str, end: str, callback, label: str) -> str:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError(f"Could not uniquely locate {label}")
    start = text.index(begin)
    finish = text.index(end, start)
    return text[:start] + callback(text[start:finish]) + text[finish:]


def patch_quick_messages(seg: str) -> str:
    seg = only(seg, "  bool send_selected = false; // confirmation defaults to CANCEL",
               "  uint8_t confirm_choice = 2; // 0=tag, 1=SEND, 2=CANCEL (safe default)\n"
               "  bool quick_tag = false; // session-only; reset on reboot", "confirmation state")
    seg = only(seg, "if (phase == 2) { phase = 1; send_selected = false; }",
               "if (phase == 2) { phase = 1; confirm_choice = 2; }", "confirmation back")
    seg = only(seg,
               "    const char* msg = QUICK_PRESETS[preset_idx];\n"
               "    if (the_mesh.sendGroupMessage(timestamp, channel.channel,\n"
               "                                  the_mesh.getNodeName(), msg, strlen(msg))) {",
               "    char msg[144];\n"
               "    snprintf(msg, sizeof(msg), \"%s%s\", QUICK_PRESETS[preset_idx],\n"
               "             quick_tag ? \" [Quick Msg]\" : \"\");\n"
               "    if (the_mesh.sendGroupMessage(timestamp, channel.channel,\n"
               "                                  the_mesh.getNodeName(), msg, strlen(msg))) {", "optional tag on sent message")
    seg = only(seg, "      send_selected = false;", "      confirm_choice = 2;", "reset after transmit")
    seg = only(seg,
               "      display.setColor(send_selected ? UIColor::warning_txt : UIColor::primary_txt);\n"
               "      display.drawTextCentered(display.width()/2, 43,\n"
               "                               send_selected ? \"SEND\" : \"CANCEL\");\n"
               "      display.drawTextCentered(display.width()/2, 55, \"Tap toggle|Hold OK\");",
               "      display.setColor(UIColor::primary_txt);\n"
               "      display.drawTextCentered(display.width()/2, 40,\n"
               "          quick_tag ? \"[Quick Msg] ON\" : \"[Quick Msg] OFF\");\n"
               "      display.setColor(confirm_choice == 1 ? UIColor::warning_txt : UIColor::primary_txt);\n"
               "      display.drawTextCentered(display.width()/2, 53,\n"
               "          confirm_choice == 0 ? \"TOGGLE TAG\" :\n"
               "          confirm_choice == 1 ? \"SEND\" : \"CANCEL\");",
               "confirmation OLED display")
    seg = only(seg, "else send_selected = !send_selected;",
               "else confirm_choice = (confirm_choice + 1) % 3;", "confirmation cycling")
    seg = only(seg,
               "      else if (phase == 1) { phase = 2; send_selected = false; }\n"
               "      else if (send_selected) sendSelected();\n"
               "      else back();",
               "      else if (phase == 1) { phase = 2; confirm_choice = 2; }\n"
               "      else if (confirm_choice == 0) quick_tag = !quick_tag;\n"
               "      else if (confirm_choice == 1) sendSelected();\n"
               "      else back();", "explicit confirmation handling")
    if "send_selected" in seg:
        raise RuntimeError("Stale v3 confirmation variable remained")
    return seg


ACTION_RENDER = r'''    if (_quick_actions) {
      display.setTextSize(1);
      display.setColor(UIColor::title_txt);
      display.drawTextCentered(display.width()/2, 0, "QUICK ACTIONS");
      static const char* labels[] = {
        "Inbox", "Quick Msgs", "Find repeaters", "Advertise", "Radio status", "Back"
      };
      int top = _action_index > 2 ? _action_index - 2 : 0;
      if (top > 3) top = 3;
      for (int row = 0; row < 3; ++row) {
        int i = top + row;
        char line[30];
        snprintf(line, sizeof(line), "%c %s", i == _action_index ? '>' : ' ', labels[i]);
        display.setColor(i == _action_index ? UIColor::title_txt : UIColor::primary_txt);
        display.drawTextLeftAlign(2, 16 + row*12, line);
      }
      display.setColor(UIColor::secondary_txt);
      display.drawTextCentered(display.width()/2, 55, "Tap next / Hold OK");
      return 500;
    }
'''
ACTION_INPUT = r'''    if (_quick_actions) {
      // A double-click/previous signal advances while inside this menu.
      if (c == KEY_NEXT || c == KEY_RIGHT || c == KEY_PREV || c == KEY_LEFT) {
        _action_index = (_action_index + 1) % 6;
        return true;
      }
      if (c == KEY_ENTER) {
        _quick_actions = false;
        switch (_action_index) {
          case 0:
            _task->openInbox();
            break;
          case 1:
            _task->gotoQuickMessagesScreen();
            break;
          case 2:
#if UI_DISCOVER_SCREEN
            _page = HomePage::DISCOVERY;
            if (millis() > discovery_req_time + 5000) sendDiscoverRequest();
#else
            _task->showAlert("Discovery unavailable", 1200);
#endif
            break;
          case 3:
            _task->showAlert(the_mesh.advert() ? "Advert queued" : "Advert failed", 1200);
            break;
          case 4:
            _page = HomePage::RADIO;
            break;
          default:
            break;  // Back
        }
        return true;
      }
      return true;
    }
    if (c == KEY_ENTER && (_page == HomePage::FIRST ||
        _page == HomePage::RECENT || _page == HomePage::RADIO)) {
      _quick_actions = true;
      _action_index = 0;
      return true;
    }
'''


def patch_home(seg: str) -> str:
    if MARKER in seg:
        raise RuntimeError("Home menu is already patched; stopping safely")
    seg = only(seg, "  uint8_t _page;", "  uint8_t _page;\n"
               "  bool _quick_actions = false;\n  uint8_t _action_index = 0;\n  " + MARKER,
               "home menu state")
    seg = only(seg, "  int render(DisplayDriver& display) override {\n",
               "  int render(DisplayDriver& display) override {\n" + ACTION_RENDER,
               "home menu rendering")
    seg = only(seg, "  bool handleInput(char c) override {\n",
               "  bool handleInput(char c) override {\n" + ACTION_INPUT,
               "home menu input")
    return seg


def patch_v05_ui(target: Path) -> None:
    cpp = target / "examples/companion_radio/ui-new/UITask.cpp"
    header = target / "examples/companion_radio/ui-new/UITask.h"
    src = cpp.read_text(encoding="utf-8")
    hdr = header.read_text(encoding="utf-8")
    if MARKER in src:
        raise RuntimeError("Source already has v0.5 modifications; refusing double patch")
    src = section_replace(src, "// === BEGIN HELTEC V4 QUICK MESSAGES",
                          "// === END HELTEC V4 QUICK MESSAGES", patch_quick_messages,
                          "Quick Messages screen")
    src = section_replace(src, "class HomeScreen : public UIScreen {",
                          "#ifndef UI_MSG_PREVIEW_SIZE", patch_home, "HomeScreen")
    # All 15 presets work both as channel quick messages and direct/channel replies.
    src = only(src,
               '    static const char* replies[] = {"Yes", "No", "Will reply in app later"};\n'
               '    return replies[index % 3];',
               '    return QUICK_PRESETS[index % QUICK_PRESETS_COUNT];',
               "incoming reply preset list")
    src = only(src, 'reply_index = (reply_index + 1) % 3;',
               'reply_index = (reply_index + 1) % QUICK_PRESETS_COUNT;',
               "incoming reply cycling")
    # The stock MsgPreviewScreen stores received text in a 32-entry RAM queue.
    src = only(src, '  MsgPreviewScreen(UITask* task, mesh::RTCClock* rtc)',
               '  bool hasUnread() const { return num_unread > 0; }\n'
               '  MsgPreviewScreen(UITask* task, mesh::RTCClock* rtc)',
               "unread inbox accessor")
    src = only(src, "void UITask::showAlert(const char* text, int duration_millis) {",
               "void UITask::openInbox() {\n"
               "  if (static_cast<MsgPreviewScreen*>(msg_preview)->hasUnread()) {\n"
               "    setCurrScreen(msg_preview);\n"
               "  } else {\n"
               "    showAlert(\"No unread messages\", 1400);\n"
               "  }\n"
               "}\n\n"
               "void UITask::showAlert(const char* text, int duration_millis) {",
               "openInbox implementation")
    hdr = only(hdr, '  void gotoHomeScreen() { setCurrScreen(home); }',
               '  void gotoHomeScreen() { setCurrScreen(home); }\n'
               '  void openInbox();',
               "openInbox declaration")
    cpp.write_text(src, encoding="utf-8")
    header.write_text(hdr, encoding="utf-8")


def load_v3():
    cache = HERE / ".pinned_v3_preparer.py"
    if not cache.exists():
        print("Downloading pinned v3 preparer from the verified mesh-loader commit...")
        req = urllib.request.Request(V3_URL, headers={"User-Agent":"Heltec-V4-v05-builder"})
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
        if b"def install_receive_replies" not in content or b"def insert_partition_setting" not in content:
            raise RuntimeError("Unexpected v3 preparer content; aborting")
        cache.write_bytes(content)
    spec = importlib.util.spec_from_file_location("mesh_loader_v3_preparer", cache)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import the v3 preparer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_presets() -> list[str]:
    path = HERE / "quick_messages.json"
    msgs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(msgs, list) or not 1 <= len(msgs) <= 20:
        raise RuntimeError("Provide between one and 20 preset strings")
    if any(not isinstance(x, str) or not x.isascii() or not 1 <= len(x) <= 80
           or "\n" in x or "\r" in x for x in msgs):
        raise RuntimeError("Each preset must be ASCII and between 1 and 80 chars")
    return msgs


def do_build(root: Path, *, build: bool, ad_hoc_relay: bool = False) -> Path:
    v3 = load_v3()
    msgs = load_presets()
    submodule = root / "modules/meshcore"
    if not (submodule / "platformio.ini").is_file():
        raise RuntimeError("Missing initialized modules/meshcore; git submodule update --init --recursive")
    actual = subprocess.check_output(["git", "-C", str(submodule), "rev-parse", "HEAD"], text=True).strip()
    if actual != UPSTREAM_SHA:
        raise RuntimeError(f"Unexpected MeshCore SHA {actual}. Need {UPSTREAM_SHA}. No source changes made")
    patch = root / "patches/meshcore/common.patch"
    target_rel = TARGET_REL
    output_name = OUTPUT_NAME
    relay_patch = HERE / "patches/ad-hoc-relay.patch"
    if ad_hoc_relay:
        patch = HERE / "patches/meshcore-1.18-mesh-loader.patch"
        target_rel += "-adhoc-relay"
        output_name = "heltec-v4-companion-v05-adhoc-relay-dualboot-app-UNTESTED.bin"
    if not patch.exists():
        raise RuntimeError(f"Missing existing dual-boot patch {patch}")
    target = root / target_rel
    manifest_data = {"feature":"heltec-companion-v05", "flavor":"dualboot", "upstream":UPSTREAM_SHA, "presets":msgs}
    if ad_hoc_relay:
        manifest_data["ad_hoc_relay"] = True
    manifest = target / ".companion-v05-manifest.json"
    apply_patch = ["git", "apply", f"--directory={target_rel}"]
    if target.exists():
        if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8")) != manifest_data:
            raise RuntimeError(f"Existing v0.5 folder differs: {target}; rename it before regenerating")
        if MARKER not in (target / "examples/companion_radio/ui-new/UITask.cpp").read_text(encoding="utf-8"):
            raise RuntimeError("v0.5 marker missing from existing prepared folder")
        if ad_hoc_relay:
            subprocess.run(apply_patch + ["--reverse", "--check", str(relay_patch)], cwd=root, check=True)
        print("Reusing prepared v0.5 source:", target)
    else:
        print("Copying pinned MeshCore source to isolated v0.5 build directory...")
        shutil.copytree(submodule, target, ignore=shutil.ignore_patterns(".git", ".pio", "__pycache__"))
        try:
            # Use the exact same loader return, BLE MAC and filesystem patches as v3.
            subprocess.run(apply_patch + ["--check", str(patch)], cwd=root, check=True)
            subprocess.run(apply_patch + [str(patch)], cwd=root, check=True)
            for p, marker in {
                "examples/companion_radio/main.cpp": "esp_ota_set_boot_partition(loader_partition)",
                "src/helpers/esp32/SerialBLEInterface.cpp": "setDeviceAddress("
            }.items():
                if marker not in (target / p).read_text(encoding="utf-8"):
                    raise RuntimeError(f"Loader/BLE patch missing marker: {marker}")
            v3.insert_partition_setting(target, root)
            v3.install_ui(target, msgs)
            v3.install_receive_replies(target)
            patch_v05_ui(target)
            if ad_hoc_relay:
                subprocess.run(apply_patch + ["--check", str(relay_patch)], cwd=root, check=True)
                subprocess.run(apply_patch + [str(relay_patch)], cwd=root, check=True)
            manifest.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")
        except Exception:
            shutil.rmtree(target)
            raise
        print("Prepared v0.5 companion source:", target)
    if build:
        cmd = [sys.executable, "-m", "platformio", "run", "-d", str(target), "-e", ENV]
        print("Compiling:", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)
        compiled = target / ".pio/build" / ENV / "firmware.bin"
        if not compiled.is_file() or compiled.open("rb").read(1) != b"\xe9":
            raise RuntimeError("No valid ESP32 application image produced")
        if compiled.stat().st_size > 0x300000:
            raise RuntimeError("Application exceeds dual-boot 3 MiB partition")
        dist = root / "build/companion-v05-dist"
        dist.mkdir(parents=True, exist_ok=True)
        dest = dist / output_name
        shutil.copy2(compiled, dest)
        checksum = hashlib.sha256(dest.read_bytes()).hexdigest()
        (dist / (output_name + ".sha256")).write_text(checksum + "  " + output_name + "\n", encoding="ascii")
        print("\nSUCCESS: compiled application-only firmware")
        print(dest)
        print("SHA256", checksum)
        print("NOT flashed. Only compatible verified Mesh Loader layouts use offset 0xA0000.")
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.home()/"mesh-loader-blefix")
    ap.add_argument("--build", action="store_true", help="Compile the MeshCore companion application")
    ap.add_argument("--ad-hoc-relay", action="store_true", help="Include the OLED relay toggle in an isolated build")
    args = ap.parse_args()
    root = args.repo.expanduser().resolve()
    do_build(root, build=args.build, ad_hoc_relay=args.ad_hoc_relay)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.exit("STOP: " + str(exc))
