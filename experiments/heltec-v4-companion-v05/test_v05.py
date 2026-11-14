import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('builder', HERE/'build_companion_v05.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class StaticPatchTests(unittest.TestCase):
    def test_presets(self):
        messages = b.load_presets()
        self.assertEqual(len(messages), 15)
        self.assertEqual(messages[0], 'OK/Tnx/Acknowledged')
        self.assertTrue(all(len(x) <= 80 for x in messages))

    def test_anchor_mismatch_stops(self):
        with self.assertRaises(RuntimeError):
            b.only('abc','missing','new','safety')
        with self.assertRaises(RuntimeError):
            b.only('aa','a','b','not unique')

    def test_quick_messages_confirmation_patch(self):
        sample = r'''// === BEGIN HELTEC V4 QUICK MESSAGES (experimental) ===
  bool send_selected = false; // confirmation defaults to CANCEL
  void back() {
    if (phase == 2) { phase = 1; send_selected = false; }
  }
  void sendSelected() {
    const char* msg = QUICK_PRESETS[preset_idx];
    if (the_mesh.sendGroupMessage(timestamp, channel.channel,
                                  the_mesh.getNodeName(), msg, strlen(msg))) {
      send_selected = false;
    }
  }
  int render() {
      display.setColor(send_selected ? UIColor::warning_txt : UIColor::primary_txt);
      display.drawTextCentered(display.width()/2, 43,
                               send_selected ? "SEND" : "CANCEL");
      display.drawTextCentered(display.width()/2, 55, "Tap toggle|Hold OK");
  }
  bool handleInput(char key) {
    if (key == KEY_NEXT) {
      else send_selected = !send_selected;
    }
    if (key == KEY_ENTER) {
      else if (phase == 1) { phase = 2; send_selected = false; }
      else if (send_selected) sendSelected();
      else back();
    }
  }
'''
        patched = b.patch_quick_messages(sample)
        self.assertNotIn('send_selected', patched)
        self.assertIn('confirm_choice == 1', patched)
        self.assertIn('quick_tag ? " [Quick Msg]"', patched)
        self.assertIn('confirm_choice = 2;', patched)

    def test_menu_render_and_input_injection(self):
        s = '''class HomeScreen : public UIScreen {
  uint8_t _page;
  int render(DisplayDriver& display) override {
    return 5000;
  }
  bool handleInput(char c) override {
    return false;
  }
};'''
        changed = b.patch_home(s)
        self.assertIn('QUICK ACTIONS', changed)
        self.assertIn('_task->openInbox()', changed)
        self.assertIn('gotoQuickMessagesScreen()',changed)
        self.assertIn('the_mesh.advert()', changed)
        self.assertIn('sendDiscoverRequest()', changed)
        with self.assertRaises(RuntimeError):
            b.patch_home(changed)


if __name__ == '__main__':
    unittest.main()
