import io
import os
import struct
import tempfile
import unittest
from contextlib import redirect_stdout

from tic_preproc.pipeline import RunOptions, run


def chunk_header(chunk_type: int, size: int) -> bytes:
    return struct.pack('<I', chunk_type | (size << 8))


class PipelineTests(unittest.TestCase):
    def write_cartridge(self, path: str, code: str):
        data = code.encode('utf-8')
        with open(path, 'wb') as f:
            f.write(chunk_header(5, len(data)))
            f.write(data)

    def test_dry_run_prints_preprocessed_code_without_backup_or_write(self):
        with tempfile.TemporaryDirectory(prefix='tic-80-') as tmp:
            project = os.path.join(tmp, 'game')
            os.makedirs(project)
            cartridge = os.path.join(project, 'game.tic')
            include = os.path.join(project, 'main.lua')
            self.write_cartridge(cartridge, '-- #include main.lua')
            with open(include, 'w', encoding='utf-8') as f:
                f.write('print("hi")')

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                run(RunOptions(file=include, dry_run=True, backup=True))

            self.assertEqual(
                '-- #include main.lua\nprint("hi")\n-- #endinclude main.lua\n',
                stdout.getvalue(),
            )
            self.assertFalse(os.path.exists(cartridge + '.bak'))

    def test_run_writes_preprocessed_code_and_creates_backup(self):
        with tempfile.TemporaryDirectory(prefix='tic-80-') as tmp:
            project = os.path.join(tmp, 'game')
            os.makedirs(project)
            cartridge = os.path.join(project, 'game.tic')
            include = os.path.join(project, 'main.lua')
            self.write_cartridge(cartridge, '-- #include main.lua')
            with open(include, 'w', encoding='utf-8') as f:
                f.write('print("hi")')

            run(RunOptions(file=include, backup=True))

            self.assertTrue(os.path.exists(cartridge + '.bak'))
            with open(cartridge, 'rb') as f:
                data = f.read()
            size = struct.unpack('<I', data[:4])[0] >> 8
            self.assertEqual(len('-- #include main.lua\nprint("hi")\n-- #endinclude main.lua'.encode('utf-8')), size)
            self.assertIn(b'print("hi")', data)


if __name__ == '__main__':
    unittest.main()
