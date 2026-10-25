#!/usr/bin/env python3
"""Prepare/build *separate* Heltec V4 1.18 quick-message variants, without flashing.

Run from this script's directory. Requires a local Mesh Loader checkout with its
pinned MeshCore submodule. The script copies source into ignored build paths.
It does not alter the upstream submodule, tracked Mesh Loader files, or devices.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ENV = "heltec_v4_companion_radio_ble"
SECTION = "[env:" + ENV + "]"
# Mesh Loader's exact pinned v1.18.0 submodule; reject surprises by default.
PINNED_MESHCORE = "81dbae592ffad40b4212bc0b37e82b38da08f4bc"

# Inserted into MeshCore examples/companion_radio/ui-new/UITask.cpp.
# No filesystem operations or persistent config changes in this first prototype.
QUICK_UI_CPP = '''
// === BEGIN HELTEC V4 QUICK MESSAGES (experimental) ===
#include "QuickMessagePresets.h"
class QuickMessagesScreen : public UIScreen {
  UITask* task;
  int phase = 0;         // 0 channel, 1 preset, 2 explicit confirmation
  int channel_idx = 0;
  int preset_idx = 0;
  bool send_selected = false; // confirmation defaults to CANCEL
  uint32_t last_transmit_ms = 0;

  bool validChannel(int idx) {
    ChannelDetails ch;
    return idx >= 0 && idx < MAX_GROUP_CHANNELS &&
           the_mesh.getChannel(idx, ch) && ch.name[0] != 0;
  }
  int nextChannel(int after) {
    for (int step = 1; step <= MAX_GROUP_CHANNELS; ++step) {
      const int idx = (after + step) % MAX_GROUP_CHANNELS;
      if (validChannel(idx)) return idx;
    }
    return -1;
  }
  bool ensureChannel() {
    if (validChannel(channel_idx)) return true;
    channel_idx = nextChannel(MAX_GROUP_CHANNELS - 1);
    return channel_idx >= 0;
  }
  void back() {
    if (phase == 2) { phase = 1; send_selected = false; }
    else if (phase == 1) phase = 0;
    else task->gotoHomeScreen();
  }
  void sendSelected() {
    // Prevent accidental or rapid transmissions (only after explicit confirmation).
    const uint32_t now_ms = millis();
    if (last_transmit_ms && (uint32_t)(now_ms - last_transmit_ms) < 10000) {
      task->showAlert("10s between TX", 1600);
      return;
    }
    const uint32_t timestamp = rtc_clock.getCurrentTime();
    if (timestamp < 1700000000UL) {
      task->showAlert("Sync clock via app", 2000);
      return;
    }
    ChannelDetails channel;
    if (!ensureChannel() || !the_mesh.getChannel(channel_idx, channel)) {
      task->showAlert("No channel", 1600);
      return;
    }
    const char* msg = QUICK_PRESETS[preset_idx];
    if (the_mesh.sendGroupMessage(timestamp, channel.channel,
                                  the_mesh.getNodeName(), msg, strlen(msg))) {
      last_transmit_ms = now_ms;
      task->showAlert("Queued for TX", 1600);
      phase = 1;
      send_selected = false;
    } else {
      task->showAlert("TX rejected", 1600);
    }
  }
public:
  explicit QuickMessagesScreen(UITask* t) : task(t) {}
  int render(DisplayDriver& display) override {
    display.setTextSize(1);
    display.setColor(UIColor::title_txt);
    display.drawTextCentered(display.width()/2, 1, "QUICK MESSAGES");
    display.setColor(UIColor::primary_txt);
    if (!ensureChannel()) {
      display.drawTextCentered(display.width()/2, 26, "No channels set");
      display.drawTextCentered(display.width()/2, 52, "Long: back");
      return 1000;
    }
    ChannelDetails ch;
    the_mesh.getChannel(channel_idx, ch);
    if (phase == 0) {
      display.drawTextCentered(display.width()/2, 16, "Choose channel");
      display.drawTextEllipsized(2, 30, display.width()-4, ch.name);
      display.drawTextCentered(display.width()/2, 52, "Tap next | Hold OK");
    } else if (phase == 1) {
      display.drawTextEllipsized(2, 14, display.width()-4, ch.name);
      char number[20];
      snprintf(number, sizeof(number), "%d/%d", preset_idx+1, QUICK_PRESETS_COUNT);
      display.drawTextCentered(display.width()/2, 27, number);
      display.drawTextEllipsized(2, 40, display.width()-4, QUICK_PRESETS[preset_idx]);
      display.drawTextCentered(display.width()/2, 55, "Tap next | Hold OK");
    } else {
      display.drawTextCentered(display.width()/2, 14, "Transmit to channel?");
      display.drawTextEllipsized(2, 28, display.width()-4, QUICK_PRESETS[preset_idx]);
      display.setColor(send_selected ? UIColor::warning_txt : UIColor::primary_txt);
      display.drawTextCentered(display.width()/2, 43,
                               send_selected ? "SEND" : "CANCEL");
      display.drawTextCentered(display.width()/2, 55, "Tap toggle|Hold OK");
    }
    return 1000;
  }
  bool handleInput(char key) override {
    if (key == KEY_PREV || key == KEY_LEFT) { back(); return true; }
    if (key == KEY_NEXT || key == KEY_RIGHT) {
      if (!ensureChannel()) return true;
      if (phase == 0) channel_idx = nextChannel(channel_idx);
      else if (phase == 1) preset_idx = (preset_idx + 1) % QUICK_PRESETS_COUNT;
      else send_selected = !send_selected;
      return true;
    }
    if (key == KEY_ENTER) {
      if (!ensureChannel()) { task->gotoHomeScreen(); return true; }
      if (phase == 0) phase = 1;
      else if (phase == 1) { phase = 2; send_selected = false; }
      else if (send_selected) sendSelected();
      else back();
      return true;
    }
    return false;
  }
};
// === END HELTEC V4 QUICK MESSAGES ===

'''


def exactly_replace(text, before, after, what):
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f"Unexpected upstream {what} (expected once, saw {n}); STOP without guessing")
    return text.replace(before, after, 1)


def install_ui(target, presets):
    cpp = target / "examples/companion_radio/ui-new/UITask.cpp"
    h = target / "examples/companion_radio/ui-new/UITask.h"
    src = cpp.read_text(encoding="utf-8")
    if "HELTEC V4 QUICK MESSAGES" in src:
        raise RuntimeError("Quick Messages already installed in source")
    src = exactly_replace(src, "class HomeScreen : public UIScreen {", QUICK_UI_CPP + "class HomeScreen : public UIScreen {", "HomeScreen class")
    src = exactly_replace(src, "#ifndef UI_NO_HIBERNATE\n    SHUTDOWN,", "    QUICK_MESSAGES,\n#ifndef UI_NO_HIBERNATE\n    SHUTDOWN,", "page enum")
    src = exactly_replace(src, "#ifndef UI_NO_HIBERNATE\n    } else if (_page == HomePage::SHUTDOWN) {", "    } else if (_page == HomePage::QUICK_MESSAGES) {\n      display.setTextSize(1);\n      display.setColor(UIColor::primary_txt);\n      display.drawTextCentered(display.width()/2, 24, \"Quick Messages\");\n      display.drawTextCentered(display.width()/2, 48, \"Hold to open\");\n#ifndef UI_NO_HIBERNATE\n    } else if (_page == HomePage::SHUTDOWN) {", "home page rendering")
    src = exactly_replace(src, "#ifndef UI_NO_HIBERNATE\n    if (c == KEY_ENTER && _page == HomePage::SHUTDOWN) {", "    if (c == KEY_ENTER && _page == HomePage::QUICK_MESSAGES) {\n      _task->gotoQuickMessagesScreen();\n      return true;\n    }\n#ifndef UI_NO_HIBERNATE\n    if (c == KEY_ENTER && _page == HomePage::SHUTDOWN) {", "home input")
    src = exactly_replace(src, "  msg_preview = new MsgPreviewScreen(this, &rtc_clock);", "  msg_preview = new MsgPreviewScreen(this, &rtc_clock);\n  quick_messages = new QuickMessagesScreen(this);", "UI construction")
    hdr = h.read_text(encoding="utf-8")
    hdr = exactly_replace(hdr, "  UIScreen* msg_preview;", "  UIScreen* msg_preview;\n  UIScreen* quick_messages;", "UI pointer")
    hdr = exactly_replace(hdr, "  void gotoHomeScreen() { setCurrScreen(home); }", "  void gotoHomeScreen() { setCurrScreen(home); }\n  void gotoQuickMessagesScreen() { setCurrScreen(quick_messages); }", "UI navigation")
    cpp.write_text(src, encoding="utf-8")
    h.write_text(hdr, encoding="utf-8")
    def esc(msg):
        return msg.replace("\\", "\\\\").replace('"', '\\"')
    lines = ["// Generated from quick_messages.json -- no persistent storage", "#pragma once", "#define QUICK_PRESETS_COUNT %d" % len(presets), "static const char* const QUICK_PRESETS[] = {"]
    lines.extend('  "%s",' % esc(msg) for msg in presets)
    lines.append("};\n")
    (cpp.parent / "QuickMessagePresets.h").write_text("\n".join(lines), encoding="utf-8")
    # Enable OLED status page in the same compilation environment.
    return cpp



# === BEGIN HELTEC V4 INCOMING QUICK REPLIES v3 ===
# A private reply retains the original contact's full public key; a channel reply
# retains its local channel index. Neither infers a recipient from display text.
REPLY_FIELDS = '''
    bool is_channel;
    int channel_idx;
    uint8_t sender_key[PUB_KEY_SIZE];
'''
REPLY_LOGIC = r'''
  enum ReplyState : uint8_t { PREVIEW, CHOOSE_REPLY, CONFIRM_REPLY };
  ReplyState reply_state = PREVIEW;
  int reply_index = 0;
  bool confirm_send = false;
  uint32_t last_reply_tx_ms = 0;
  MsgEntry reply_target = {};

  static const char* quickReplyText(int index) {
    static const char* replies[] = {"Yes", "No", "Will reply in app later"};
    return replies[index % 3];
  }

  void queueSelectedReply() {
    const uint32_t now = millis();
    if (last_reply_tx_ms && (uint32_t)(now - last_reply_tx_ms) < 10000UL) {
      _task->showAlert("10s between TX", 1500);
      return;
    }
    if (_rtc->getCurrentTime() < 1700000000UL) {
      _task->showAlert("Sync clock via app", 2000);
      return;
    }
    const char* response = quickReplyText(reply_index);
    bool queued = false;
    if (reply_target.is_channel) {
      ChannelDetails channel;
      if (reply_target.channel_idx >= 0 &&
          the_mesh.getChannel(reply_target.channel_idx, channel) && channel.name[0]) {
        queued = the_mesh.sendGroupMessage(_rtc->getCurrentTimeUnique(), channel.channel,
                                           the_mesh.getNodeName(), response, strlen(response));
      }
    } else {
      queued = the_mesh.sendQuickReplyToContact(reply_target.sender_key, response);
    }
    if (queued) {
      last_reply_tx_ms = now;
      _task->showAlert("Queued; not delivered", 1600);
      reply_state = PREVIEW;
    } else {
      _task->showAlert("Reply failed", 1600);
      reply_state = PREVIEW;
    }
  }
'''
REPLY_RENDER = r'''
    if (reply_state != PREVIEW) {
      display.setTextSize(1);
      display.setColor(UIColor::title_txt);
      display.drawTextCentered(display.width()/2, 1, "REPLY TO MESSAGE");
      display.setColor(UIColor::primary_txt);
      display.drawTextEllipsized(0, 14, display.width()-1,
        reply_target.is_channel ? "CHANNEL REPLY" : "PRIVATE REPLY");
      display.drawTextEllipsized(0, 25, display.width()-1, reply_target.origin);
      if (reply_state == CHOOSE_REPLY) {
        display.drawTextEllipsized(0, 39, display.width()-1, quickReplyText(reply_index));
        display.drawTextCentered(display.width()/2, 54, "Tap next | Hold OK");
      } else {
        display.drawTextEllipsized(0, 35, display.width()-1, quickReplyText(reply_index));
        display.setColor(confirm_send ? UIColor::warning_txt : UIColor::primary_txt);
        display.drawTextCentered(display.width()/2, 49, confirm_send ? "SEND" : "CANCEL");
        display.drawTextCentered(display.width()/2, 59, "Tap toggle | Hold OK");
      }
      return 1000;
    }
'''
REPLY_INPUT = r'''  bool handleInput(char c) override {
    if (c == KEY_PREV || c == KEY_LEFT) { // Double-click: cancel/back
      if (reply_state == CONFIRM_REPLY) reply_state = CHOOSE_REPLY;
      else if (reply_state == CHOOSE_REPLY) reply_state = PREVIEW;
      else { num_unread = 0; _task->gotoHomeScreen(); }
      return true;
    }
    if (reply_state == CHOOSE_REPLY) {
      if (c == KEY_NEXT || c == KEY_RIGHT) {
        reply_index = (reply_index + 1) % 3;
        return true;
      }
      if (c == KEY_ENTER) {
        reply_state = CONFIRM_REPLY;
        confirm_send = false;  // Never default to transmitting
        return true;
      }
      return false;
    }
    if (reply_state == CONFIRM_REPLY) {
      if (c == KEY_NEXT || c == KEY_RIGHT) { confirm_send = !confirm_send; return true; }
      if (c == KEY_ENTER) {
        if (confirm_send) queueSelectedReply();
        else reply_state = CHOOSE_REPLY;
        return true;
      }
      return false;
    }
    if (c == KEY_NEXT || c == KEY_RIGHT) {
      head = (head + MAX_UNREAD_MSGS - 1) % MAX_UNREAD_MSGS;
      num_unread--;
      if (num_unread == 0) _task->gotoHomeScreen();
      return true;
    }
    if (c == KEY_ENTER && num_unread > 0) { // Long press: reply to THIS message
      reply_target = unread[head];  // Snapshot avoids recipient changes on new arrivals
      reply_state = CHOOSE_REPLY;
      reply_index = 0;
      confirm_send = false;
      return true;
    }
    return false;
  }
'''

def install_receive_replies(target):
    cpp = target / "examples/companion_radio/ui-new/UITask.cpp"
    src = cpp.read_text(encoding="utf-8")
    header = target / "examples/companion_radio/MyMesh.h"
    impl = target / "examples/companion_radio/MyMesh.cpp"
    hsrc = header.read_text(encoding="utf-8")
    isrc = impl.read_text(encoding="utf-8")
    start_mark = "class MsgPreviewScreen : public UIScreen {"
    end_mark = "\n};\n\nvoid UITask::begin("
    if src.count(start_mark) != 1 or src.count(end_mark) != 1:
        raise RuntimeError("Unexpected pinned message preview class layout")
    start = src.index(start_mark)
    end = src.index(end_mark, start)
    before = src[:start]
    part = src[start:end]
    after = src[end:]
    part = exactly_replace(part, "    char msg[UI_MSG_PREVIEW_SIZE];\n", "    char msg[UI_MSG_PREVIEW_SIZE];\n"+REPLY_FIELDS, "preview message metadata")
    part = exactly_replace(part, "  MsgEntry unread[MAX_UNREAD_MSGS];\n", "  MsgEntry unread[MAX_UNREAD_MSGS];\n"+REPLY_LOGIC, "reply state")
    part = exactly_replace(part,
        "  void addPreview(uint8_t path_len, const char* from_name, const char* msg) {",
        "  void addPreview(uint8_t path_len, const char* from_name, const char* msg,\n"+
        "                  const ContactInfo* sender, int channel_idx) {",
        "preview add recipient signature")
    part = exactly_replace(part, "    p->timestamp = _rtc->getCurrentTime();",
        "    p->is_channel = sender == nullptr;\n"+
        "    p->channel_idx = channel_idx;\n"+
        "    if (sender) memcpy(p->sender_key, sender->id.pub_key, PUB_KEY_SIZE);\n"+
        "    else memset(p->sender_key, 0, PUB_KEY_SIZE);\n"+
        "    p->timestamp = _rtc->getCurrentTime();", "preview recipient snapshot")
    part = exactly_replace(part, "  int render(DisplayDriver& display) override {\n    char tmp[16];",
        "  int render(DisplayDriver& display) override {\n"+REPLY_RENDER+"    char tmp[16];",
        "reply rendering")
    input_start = part.index("  bool handleInput(char c) override {")
    if part[input_start:].count("  bool handleInput(char c) override {") != 1:
        raise RuntimeError("Unexpected preview handleInput count")
    part = part[:input_start]+REPLY_INPUT
    src = before + part + after
    src = exactly_replace(src,
        "((MsgPreviewScreen *) msg_preview)->addPreview(path_len, from.name, text);",
        "((MsgPreviewScreen *) msg_preview)->addPreview(path_len, from.name, text, &from, -1);",
        "private preview callback")
    src = exactly_replace(src,
        "((MsgPreviewScreen *) msg_preview)->addPreview(path_len, channel_details.name, text);",
        "((MsgPreviewScreen *) msg_preview)->addPreview(path_len, channel_details.name, text,\n"+
        "    nullptr, the_mesh.findChannelIdx(channel_details.channel));",
        "channel preview callback")
    hsrc = exactly_replace(hsrc, "  bool advert();\n", "  bool advert();\n  bool sendQuickReplyToContact(const uint8_t* pub_key, const char* text);\n", "quick direct-send declaration")
    reply_method = r'''
bool MyMesh::sendQuickReplyToContact(const uint8_t* pub_key, const char* text) {
  if (!pub_key || !text || !*text) return false;
  ContactInfo* recipient = lookupContactByPubKey(pub_key, PUB_KEY_SIZE);
  if (!recipient) return false;
  uint32_t expected_ack = 0, est_timeout = 0;
  const uint32_t timestamp = getRTCClock()->getCurrentTimeUnique();
  const int result = sendMessage(*recipient, timestamp, 0, text, expected_ack, est_timeout);
  if (result == MSG_SEND_FAILED) return false;
  if (expected_ack) {
    expected_ack_table[next_ack_idx].msg_sent = _ms->getMillis();
    expected_ack_table[next_ack_idx].ack = expected_ack;
    expected_ack_table[next_ack_idx].contact = recipient;
    next_ack_idx = (next_ack_idx + 1) % EXPECTED_ACK_TABLE_SIZE;
  }
  return true;  // Enqueued/sent, NOT proof of receipt
}

'''
    isrc = exactly_replace(isrc, "void MyMesh::onContactPathUpdated(const ContactInfo &contact) {",
        reply_method+"void MyMesh::onContactPathUpdated(const ContactInfo &contact) {", "DM reply helper insertion")
    # All exact-anchor transformations succeed before replacing source on disk.
    cpp.write_text(src, encoding="utf-8")
    header.write_text(hsrc, encoding="utf-8")
    impl.write_text(isrc, encoding="utf-8")
# === END HELTEC V4 INCOMING QUICK REPLIES v3 ===

def insert_partition_setting(target, root):
    ini = target / "variants/heltec_v4/platformio.ini"
    cfg = ini.read_text(encoding="utf-8")
    start = cfg.find(SECTION)
    if start < 0 or cfg.count(SECTION) != 1:
        raise RuntimeError("Wrong BLE companion PlatformIO environment")
    start += len(SECTION)
    end = cfg.find("\n[", start)
    if end < 0: end = len(cfg)
    if "board_build.partitions" in cfg[start:end]:
        raise RuntimeError("Unexpected existing partition override")
    cfg = cfg[:start] + "\nboard_build.partitions = partitions.csv" + cfg[start:]
    ini.write_text(cfg, encoding="utf-8")
    shutil.copy2(root / "partitions/16mb_default/partitions-meshcore.csv", target / "partitions.csv")


def run(*args, cwd=None):
    print("+", " ".join(str(s) for s in args), flush=True)
    subprocess.run([str(s) for s in args], cwd=str(cwd) if cwd else None, check=True)


def validate_presets(path):
    msgs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(msgs, list) or not 1 <= len(msgs) <= 20:
        raise ValueError("quick_messages.json must contain 1-20 strings")
    for index, msg in enumerate(msgs):
        if not isinstance(msg, str) or not 1 <= len(msg) <= 40 or not msg.isascii() or "\n" in msg:
            raise ValueError("Preset #%d: ASCII string of 1-40 characters required" % (index+1))
    return msgs


def prepare(root, flavor, msgs):
    origin = root / "modules/meshcore"
    target = root / "build" / ("canned-" + flavor + "-replies-v3")
    if target.exists():
        manifest = target / ".quick-messages-manifest.json"
        if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8")) != {"flavor": flavor, "presets": msgs, "upstream": PINNED_MESHCORE, "feature": "quick-reply-v3"}:
            raise RuntimeError(f"Existing target differs from current presets/source: {target}. Preserve or move it aside first.")
        if "HELTEC V4 QUICK MESSAGES" not in (target/"examples/companion_radio/ui-new/UITask.cpp").read_text(encoding="utf-8") or "REPLY TO MESSAGE" not in (target/"examples/companion_radio/ui-new/UITask.cpp").read_text(encoding="utf-8"):
            raise RuntimeError("Prepared UI marker missing from existing target")
        print(f"REUSE: {target} (preset manifest verified)")
        return target
    print(f"Preparing {flavor} from pinned MeshCore 1.18 source...")
    shutil.copytree(origin, target, ignore=shutil.ignore_patterns(".git", ".pio", "__pycache__"))
    try:
        if flavor == "dualboot":
            patch = root / "patches/meshcore/common.patch"
            run("git", "apply", "--check", "--directory=build/canned-dualboot-replies-v3", str(patch), cwd=root)
            run("git", "apply", "--directory=build/canned-dualboot-replies-v3", str(patch), cwd=root)
            expected = {"examples/companion_radio/main.cpp": "esp_ota_set_boot_partition(loader_partition)",
                        "src/helpers/esp32/SerialBLEInterface.cpp": "setDeviceAddress("}
            for path, marker in expected.items():
                if marker not in (target/path).read_text(encoding="utf-8"):
                    raise RuntimeError(f"Required dual-boot source marker missing: {marker}")
            insert_partition_setting(target, root)
        install_ui(target, msgs)
        install_receive_replies(target)
        (target/".quick-messages-manifest.json").write_text(
            json.dumps({"flavor": flavor, "presets": msgs, "upstream": PINNED_MESHCORE, "feature": "quick-reply-v3"}, indent=2),
            encoding="utf-8")
    except Exception:
        # Only remove a working copy created by THIS invocation, never a pre-existing tree.
        # A failed prepare must not strand another incomplete directory for the next run.
        shutil.rmtree(target)
        raise
    print(f"PREPARED: {target}")
    return target


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True, help="Local Mesh Loader checkout path")
    p.add_argument("--build", action="store_true", help="Compile both variants with PlatformIO (never flash)")
    p.add_argument("--flavor", choices=("both", "standalone", "dualboot"), default="both")
    a = p.parse_args()
    root = a.repo.expanduser().resolve()
    msgs = validate_presets(Path(__file__).with_name("quick_messages.json"))
    origin = root / "modules/meshcore"
    if not (origin / "platformio.ini").is_file():
        p.error("Initialize the MeshCore submodule in the given repo first")
    sha = subprocess.check_output(["git", "-C", str(origin), "rev-parse", "HEAD"], text=True).strip()
    if sha != PINNED_MESHCORE:
        p.error(f"MeshCore submodule commit unexpected ({sha}); expected {PINNED_MESHCORE}; STOP")
    targets = []
    for flavor in (("standalone", "dualboot") if a.flavor == "both" else (a.flavor,)):
        targets.append((flavor, prepare(root, flavor, msgs)))
    if a.build:
        for flavor, target in targets:
            run(sys.executable, "-m", "platformio", "run", "-d", target, "-e", ENV)
            out = target / ".pio/build" / ENV / "firmware.bin"
            if not out.exists() or out.read_bytes()[:1] != b"\xe9":
                raise RuntimeError(f"Missing valid {flavor} ESP32 application image: {out}")
            print(f"BUILT {flavor}: {out} ({out.stat().st_size:,} bytes)")
            dist = root / "build/quick-replies-dist"
            dist.mkdir(parents=True, exist_ok=True)
            if flavor == "dualboot":
                if out.stat().st_size > 0x300000:
                    raise RuntimeError("Dual-boot MeshCore app exceeds 3 MiB slot")
                dest = dist / "heltec-v4-quick-reply-dualboot-app.bin"
                shutil.copy2(out, dest)
                print("Dualboot APPLICATION ONLY: requires matching loader partitions at 0xA0000")
            else:
                # Build a standard standalone complete ESP32 installation image.
                # The stock MeshCore merge-bin.py includes the native bootloader,
                # partitions, boot_app0, and app at the normal ESP32 app offset.
                run(sys.executable, "-m", "platformio", "run", "-d", target, "-e", ENV, "-t", "mergebin")
                merged = out.with_name("firmware-merged.bin")
                if not merged.is_file() or merged.stat().st_size < 0x10100:
                    raise RuntimeError("No standalone merged image produced; do not flash app image at 0x0")
                with merged.open("rb") as f:
                    f.seek(0); boot = f.read(1)
                    f.seek(0x8000); partition = f.read(2)
                    f.seek(0x10000); app = f.read(1)
                if boot != b"\xe9" or partition != b"\xaa\x50" or app != b"\xe9":
                    raise RuntimeError("Unexpected merged standalone bootloader/partition/app offsets")
                dest = dist / "heltec-v4-quick-reply-standalone-merged.bin"
                shutil.copy2(merged, dest)
                print("Standalone FULL INSTALL at 0x0: DESTRUCTIVE; no Mesh Loader")
            digest = sha256_file(dest)
            (dist / (dest.name + ".sha256")).write_text(f"{digest}  {dest.name}\n", encoding="ascii")
            print(f"OUTPUT: {dest} ({dest.stat().st_size:,} bytes) SHA256 {digest}")
    print("PASS: variants prepared" + (" and compiled" if a.build else "") + "; no device flashed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.exit(f"STOP: {exc}")
