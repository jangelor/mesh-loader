"""Offline static and image-format checks. Does not compile or test hardware."""
import json
import tempfile
import unittest
from pathlib import Path
import build_standalone_v05 as b

class StandaloneV05Checks(unittest.TestCase):
    def test_environment_and_variant_name(self):
        self.assertEqual(b.ENV, 'heltec_v4_companion_radio_ble')
        self.assertIn('standalone', b.TARGET_REL)
        self.assertNotIn('dualboot', b.TARGET_REL)
        self.assertIn('UNTESTED', b.DIST_NAME)

    def test_presets_same_as_v05(self):
        self.assertEqual(len(b.v05.load_presets()), 15)

    def test_board_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'boards').mkdir()
            (p/'variants/heltec_v4').mkdir(parents=True)
            (p/'boards/heltec_v4.json').write_text(json.dumps({'build': {'mcu':'esp32s3'}, 'upload': {'flash_size':'16MB'}}))
            ini = p/'variants/heltec_v4/platformio.ini'
            ini.write_text('[env:heltec_v4_companion_radio_ble]\nbuild_flags=foo\n\n[env:other]\n')
            b.assert_board_config(p)
            ini.write_text('[env:heltec_v4_companion_radio_ble]\nboard_build.partitions=partitions.csv\n')
            with self.assertRaisesRegex(RuntimeError, 'partition override'):
                b.assert_board_config(p)

    def test_merged_magic_and_offsets(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'merged.bin'
            data=bytearray(0x10150)
            data[0] = 0xe9
            data[0x8000:0x8002] = b'\xaa\x50'
            data[0x10000] = 0xe9
            p.write_bytes(data)
            self.assertEqual(b.inspect_merged_image(p)['app_offset'], '0x10000')
            data[0x10000] = 0x00
            p.write_bytes(data)
            with self.assertRaisesRegex(RuntimeError,'app magic'):
                b.inspect_merged_image(p)

    def test_no_dualboot_patch_applied(self):
        script=(Path(__file__).parent/'build_standalone_v05.py').read_text()
        self.assertNotIn('v3.insert_partition_setting(target, root)',script.replace('# Deliberately DO NOT call git apply common.patch or v3.insert_partition_setting.',''))
        self.assertIn('v3.install_receive_replies(target)',script)
        self.assertIn('v05.patch_v05_ui(target)',script)
        self.assertIn("'physical_hardware_test': 'NOT TESTED'",script)

if __name__ == '__main__':
    unittest.main()
