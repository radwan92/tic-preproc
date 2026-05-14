import os
import tempfile
import unittest

from tic_preproc.project import find_tic_file


class ProjectDiscoveryTests(unittest.TestCase):
    def test_finds_project_cartridge_from_nested_file(self):
        with tempfile.TemporaryDirectory(prefix='tic-80-') as tmp:
            project = os.path.join(tmp, 'game')
            nested = os.path.join(project, 'src', 'core')
            os.makedirs(nested)
            cartridge = os.path.join(project, 'game.tic')
            script = os.path.join(nested, 'main.lua')
            open(cartridge, 'wb').close()
            open(script, 'w', encoding='utf-8').close()

            self.assertEqual(cartridge, find_tic_file(script, 'tic-80'))

    def test_rejects_relative_paths(self):
        with self.assertRaisesRegex(ValueError, 'absolute'):
            find_tic_file('game/main.lua', 'tic-80')

    def test_rejects_projects_outside_carts_directory(self):
        with tempfile.TemporaryDirectory(prefix='not-carts-') as tmp:
            script = os.path.join(tmp, 'main.lua')
            open(script, 'w', encoding='utf-8').close()

            with self.assertRaisesRegex(ValueError, 'tic-80'):
                find_tic_file(script, 'tic-80')

    def test_rejects_multiple_cartridges_at_project_root(self):
        with tempfile.TemporaryDirectory(prefix='tic-80-') as tmp:
            open(os.path.join(tmp, 'a.tic'), 'wb').close()
            open(os.path.join(tmp, 'b.tic'), 'wb').close()
            script = os.path.join(tmp, 'main.lua')
            open(script, 'w', encoding='utf-8').close()

            with self.assertRaisesRegex(ValueError, 'More than 1'):
                find_tic_file(script, 'tic-80')


if __name__ == '__main__':
    unittest.main()
