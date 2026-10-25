import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

composer = module("composer", "scripts/compose_heltec_v4_fresh.py")
verifier = module("verifier", "scripts/verify_heltec_v4_partitions.py")


def partition_table():
    result = bytearray([0xff]) * 4096
    for i, (name, (typ, subtype, offset, size)) in enumerate(composer.PARTITIONS.items()):
        result[i * 32:(i+1) * 32] = struct.pack('<HBBII16sI', 0x50aa, typ, subtype,
                                                offset, size, name.encode().ljust(16, b'\0'), 0)
    return result


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.table = partition_table()
        self.base = bytearray([0xff]) * composer.FLASH_SIZE
        self.base[0x8000:0x9000] = self.table
        for pos in (0x0, 0x20000, 0x3A0000):
            self.base[pos] = 0xe9
        self.app = b'\xe9' + b'\0' * 128
        self.previous_hash = composer.APP_CHECKSUM
        composer.APP_CHECKSUM = hashlib.sha256(self.app).hexdigest()

    def tearDown(self):
        composer.APP_CHECKSUM = self.previous_hash

    def test_known_layout(self):
        self.assertTrue(verifier.check(bytes(self.table)))

    def test_wrong_layout(self):
        self.table[3 * 32 + 4] ^= 1
        with self.assertRaises(ValueError):
            verifier.check(bytes(self.table))

    def test_composition_only_meshcore_slot_changes(self):
        result = composer.build(bytes(self.base), self.app)
        self.assertEqual(len(result), composer.FLASH_SIZE)
        self.assertEqual(result[:composer.CORE_ADDR], self.base[:composer.CORE_ADDR])
        self.assertEqual(result[0x3A0000:], self.base[0x3A0000:])
        self.assertEqual(result[composer.CORE_ADDR:composer.CORE_ADDR+len(self.app)], self.app)

    def test_reject_unexpected_nvs_contents(self):
        self.base[0x9000] = 0
        with self.assertRaises(ValueError):
            composer.build(bytes(self.base), self.app)

    def test_reject_wrong_app_hash(self):
        with self.assertRaises(ValueError):
            composer.build(bytes(self.base), b'\xe9' + b'X' * 128)


if __name__ == '__main__':
    unittest.main()
