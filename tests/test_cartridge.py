import os
import struct
import tempfile
import unittest

from tic_preproc.cartridge import TicCartridge


def chunk_header(chunk_type: int, size: int, bank: int = 0, temp: int = 0) -> bytes:
    pack = chunk_type | (bank << 5) | (size << 8) | (temp << 24)
    return struct.pack('<I', pack)


class CartridgeTests(unittest.TestCase):
    def test_loads_and_replaces_code_chunk_while_preserving_rest(self):
        original_code = 'print("old")'.encode('utf-8')
        new_code = 'print("new")'
        rest = chunk_header(1, 3) + b'abc'

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'game.tic')
            with open(path, 'wb') as f:
                f.write(chunk_header(5, len(original_code)))
                f.write(original_code)
                f.write(rest)

            cartridge = TicCartridge.load(path)
            self.assertEqual('print("old")', cartridge.code_text)

            cartridge.replace_code(new_code)
            cartridge.write(path)

            reloaded = TicCartridge.load(path)
            self.assertEqual(new_code, reloaded.code_text)
            with open(path, 'rb') as f:
                data = f.read()
            self.assertTrue(data.endswith(rest))

    def test_rejects_invalid_chunk_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'game.tic')
            with open(path, 'wb') as f:
                f.write(chunk_header(20, 0))

            with self.assertRaisesRegex(ValueError, 'invalid type 20'):
                TicCartridge.load(path)

    def test_rejects_png_cartridges(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'game.tic')
            with open(path, 'wb') as f:
                f.write(b'\x89PNG')

            with self.assertRaisesRegex(ValueError, 'PNG'):
                TicCartridge.load(path)


if __name__ == '__main__':
    unittest.main()
