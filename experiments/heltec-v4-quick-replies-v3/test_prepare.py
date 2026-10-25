import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('quick', HERE/'prepare_quick_messages.py')
quick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick)

class TestQuickMessages(unittest.TestCase):
    def test_valid_config(self):
        msgs=quick.validate_presets(HERE/'quick_messages.json')
        self.assertEqual(len(msgs),7)
        self.assertIn("CQ CQ CQ - anyone copying?", msgs)
    def test_reject_too_long_message(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'quick_messages.json'
            p.write_text('["'+('A'*41)+'"]')
            with self.assertRaises(ValueError): quick.validate_presets(p)
    def test_reject_unicode_for_small_oled(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'quick_messages.json'
            p.write_text('["Kamusta 👋"]')
            with self.assertRaises(ValueError): quick.validate_presets(p)
    def test_strict_anchors_stop_unexpected_source(self):
        with self.assertRaises(RuntimeError):
            quick.exactly_replace('hello','no matching anchor','new','test')
    def test_cpp_contains_explicit_confirmation(self):
        self.assertIn('bool send_selected = false;', quick.QUICK_UI_CPP)
        self.assertIn('send_selected = false;', quick.QUICK_UI_CPP)
        self.assertIn('the_mesh.sendGroupMessage(', quick.QUICK_UI_CPP)
        self.assertIn('rtc_clock.getCurrentTime()', quick.QUICK_UI_CPP)
        self.assertIn('Sync clock via app', quick.QUICK_UI_CPP)
        self.assertIn('#include "QuickMessagePresets.h"', quick.QUICK_UI_CPP)
    def test_ui_transforms_on_known_anchor_sample(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'examples/companion_radio/ui-new'
            src.mkdir(parents=True)
            (src/'UITask.cpp').write_text('''class HomeScreen : public UIScreen {
#ifndef UI_NO_HIBERNATE
    SHUTDOWN,
#ifndef UI_NO_HIBERNATE
    } else if (_page == HomePage::SHUTDOWN) {
#ifndef UI_NO_HIBERNATE
    if (c == KEY_ENTER && _page == HomePage::SHUTDOWN) {
  msg_preview = new MsgPreviewScreen(this, &rtc_clock);
''')
            (src/'UITask.h').write_text('''  UIScreen* msg_preview;
  void gotoHomeScreen() { setCurrScreen(home); }
''')
            quick.install_ui(Path(d), ['All OK','Checking in'])
            actual=(src/'UITask.cpp').read_text()
            self.assertIn('class QuickMessagesScreen',actual)
            self.assertIn('QUICK_MESSAGES',actual)
            self.assertIn('the_mesh.sendGroupMessage(',actual)
            self.assertIn('"All OK"', (src/'QuickMessagePresets.h').read_text())
            self.assertIn('gotoQuickMessagesScreen()', (src/'UITask.h').read_text())
            self.assertIn('msg_preview = new MsgPreviewScreen(this, &rtc_clock);', actual)
            self.assertIn('quick_messages = new QuickMessagesScreen(this);', actual)
    def test_failed_preparation_removes_only_new_working_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            origin = root/'modules/meshcore'
            origin.mkdir(parents=True)
            (origin/'platformio.ini').write_text('[platformio]\n')
            with self.assertRaises(FileNotFoundError):
                quick.prepare(root, 'standalone', ['All OK'])
            self.assertFalse((root/'build/canned-standalone-replies-v3').exists())
            self.assertTrue((origin/'platformio.ini').exists())

    def test_no_duplicate_source_patches(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'examples/companion_radio/ui-new'
            src.mkdir(parents=True)
            (src/'UITask.cpp').write_text('HELTEC V4 QUICK MESSAGES')
            (src/'UITask.h').write_text('')
            with self.assertRaises(RuntimeError): quick.install_ui(Path(d),['Yes'])

if __name__ == '__main__': unittest.main()

class TestIncomingReplies(unittest.TestCase):
    def test_quick_reply_choices_include_later(self):
        self.assertIn('"Yes", "No", "Will reply in app later"', quick.REPLY_LOGIC)
        self.assertIn('reply_target = unread[head]', quick.REPLY_INPUT)
        self.assertIn('sendQuickReplyToContact(reply_target.sender_key', quick.REPLY_LOGIC)
        self.assertIn('sendGroupMessage(', quick.REPLY_LOGIC)
        self.assertIn('confirm_send = false;', quick.REPLY_INPUT)
    def test_exact_pinned_1_18_message_preview_transformation(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            f=target/'examples/companion_radio/ui-new'
            f.mkdir(parents=True)
            fcpp=f/'UITask.cpp'
            fcpp.write_text('''class MsgPreviewScreen : public UIScreen {
  UITask* _task;
  mesh::RTCClock* _rtc;
  struct MsgEntry {
    uint32_t timestamp;
    char origin[62];
    char msg[UI_MSG_PREVIEW_SIZE];
  };
  #define MAX_UNREAD_MSGS   32
  int num_unread;
  int head = MAX_UNREAD_MSGS - 1;
  MsgEntry unread[MAX_UNREAD_MSGS];
public:
  MsgPreviewScreen(UITask* task, mesh::RTCClock* rtc) : _task(task), _rtc(rtc) { num_unread = 0; }
  void addPreview(uint8_t path_len, const char* from_name, const char* msg) {
    head = (head + 1) % MAX_UNREAD_MSGS;
    if (num_unread < MAX_UNREAD_MSGS) num_unread++;
    auto p = &unread[head];
    p->timestamp = _rtc->getCurrentTime();
  }
  int render(DisplayDriver& display) override {
    char tmp[16];
    return 1000;
  }
  bool handleInput(char c) override {
    if (c == KEY_ENTER) { num_unread = 0; _task->gotoHomeScreen(); return true; }
    return false;
  }
};

void UITask::begin(DisplayDriver* display, SensorManager* sensors, NodePrefs* node_prefs) {}
void UITask::onMessageRecv() {
  ((MsgPreviewScreen *) msg_preview)->addPreview(path_len, from.name, text);
}
void UITask::onChannelMessageRecv() {
  ((MsgPreviewScreen *) msg_preview)->addPreview(path_len, channel_details.name, text);
}
''')
            (target/'examples/companion_radio/MyMesh.h').write_text('  bool advert();\n')
            (target/'examples/companion_radio/MyMesh.cpp').write_text('void MyMesh::onContactPathUpdated(const ContactInfo &contact) {}\n')
            quick.install_receive_replies(target)
            u=fcpp.read_text()
            m=(target/'examples/companion_radio/MyMesh.cpp').read_text()
            self.assertIn('sender->id.pub_key',u)
            self.assertIn('the_mesh.findChannelIdx(channel_details.channel)',u)
            self.assertIn('const ContactInfo* sender, int channel_idx',u)
            self.assertIn('sendQuickReplyToContact(reply_target.sender_key',u)
            self.assertIn('expected_ack_table[next_ack_idx].ack = expected_ack;',m)
            self.assertIn('bool sendQuickReplyToContact', (target/'examples/companion_radio/MyMesh.h').read_text())
    def test_transform_fail_closed_on_changed_source(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            f=target/'examples/companion_radio/ui-new'
            f.mkdir(parents=True)
            (f/'UITask.cpp').write_text('not the expected 1.18 source')
            (target/'examples/companion_radio/MyMesh.h').write_text('  bool advert();\n')
            (target/'examples/companion_radio/MyMesh.cpp').write_text('void MyMesh::onContactPathUpdated(const ContactInfo &contact) {}\n')
            with self.assertRaises(RuntimeError): quick.install_receive_replies(target)
            self.assertEqual((f/'UITask.cpp').read_text(),'not the expected 1.18 source')
