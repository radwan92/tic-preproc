import os
import tempfile
import unittest

from tic_preproc.config import PreprocessOptions
from tic_preproc.includes import expand_includes


class IncludeExpansionTests(unittest.TestCase):
    def test_expands_top_level_include_and_adds_endinclude(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.lua'), 'w', encoding='utf-8') as f:
                f.write('print("hi")')

            result = expand_includes(
                '-- #include main.lua',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='lua'),
            )

            self.assertEqual(
                '-- #include main.lua\nprint("hi")\n-- #endinclude main.lua',
                result,
            )

    def test_replaces_existing_top_level_include_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.lua'), 'w', encoding='utf-8') as f:
                f.write('print("fresh")')

            result = expand_includes(
                '-- #include main.lua\nprint("stale")\n-- #endinclude main.lua\nprint("tail")',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='lua'),
            )

            self.assertEqual(
                '-- #include main.lua\nprint("fresh")\n-- #endinclude main.lua\nprint("tail")',
                result,
            )

    def test_nested_includes_are_expanded_without_markers_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.lua'), 'w', encoding='utf-8') as f:
                f.write('function TIC()\n-- #include core.lua\nend')
            with open(os.path.join(tmp, 'core.lua'), 'w', encoding='utf-8') as f:
                f.write('cls()')

            result = expand_includes(
                '-- #include main.lua',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='lua'),
            )

            self.assertEqual(
                '-- #include main.lua\nfunction TIC()\ncls()\nend\n-- #endinclude main.lua',
                result,
            )

    def test_nested_includes_are_resolved_relative_to_including_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, 'dissolve')
            radlib_dir = os.path.join(tmp, 'radlib')
            os.makedirs(project_dir)
            os.makedirs(radlib_dir)

            with open(os.path.join(radlib_dir, 'game.py'), 'w', encoding='utf-8') as f:
                f.write('def TIC():\n# #include time.py\nupdate()')
            with open(os.path.join(radlib_dir, 'time.py'), 'w', encoding='utf-8') as f:
                f.write('ticks = 0')

            result = expand_includes(
                '# #include ../radlib/game.py',
                project_dir,
                os.path.join(project_dir, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                '# #include ../radlib/game.py\ndef TIC():\nticks = 0\nupdate()\n# #endinclude ../radlib/game.py',
                result,
            )

    def test_nested_include_markers_can_be_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.py'), 'w', encoding='utf-8') as f:
                f.write('def TIC():\n# #include core.py')
            with open(os.path.join(tmp, 'core.py'), 'w', encoding='utf-8') as f:
                f.write('cls()')

            result = expand_includes(
                '# #include main.py',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='python', retain_nested_includes=True),
            )

            self.assertEqual(
                '# #include main.py\ndef TIC():\n# #include core.py\ncls()\n# #endinclude core.py\n# #endinclude main.py',
                result,
            )

    def test_python_include_adds_bare_endinclude_for_bare_include_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.py'), 'w', encoding='utf-8') as f:
                f.write('t=0')

            result = expand_includes(
                '#include main.py',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                '#include main.py\nt=0\n#endinclude main.py',
                result,
            )

    def test_python_include_normalizes_existing_generated_endinclude_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.py'), 'w', encoding='utf-8') as f:
                f.write('t=0')

            result = expand_includes(
                '#include main.py\nstale\n# #endinclude main.py',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                '#include main.py\nt=0\n#endinclude main.py',
                result,
            )

    def test_python_import_include_expands_direct_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, 'dissolve')
            radlib_dir = os.path.join(tmp, 'radlib')
            os.makedirs(project_dir)
            os.makedirs(radlib_dir)

            with open(os.path.join(radlib_dir, 'game.py'), 'w', encoding='utf-8') as f:
                f.write('class Game:\n  pass')

            result = expand_includes(
                'from radlib.game import Game #:include',
                project_dir,
                os.path.join(project_dir, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                'from radlib.game import Game #:include\nclass Game:\n  pass\n#endinclude radlib/game.py',
                result,
            )

    def test_shared_nested_import_include_is_expanded_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, 'rainbow')
            radlib_dir = os.path.join(tmp, 'radlib')
            os.makedirs(project_dir)
            os.makedirs(radlib_dir)

            with open(os.path.join(radlib_dir, 'ram.py'), 'w', encoding='utf-8') as f:
                f.write('class Ram:\n  pass')
            with open(os.path.join(radlib_dir, 'colors.py'), 'w', encoding='utf-8') as f:
                f.write('from radlib.ram import Ram #:include\n\nclass Colors:\n  pass')

            result = expand_includes(
                'from radlib.ram import Ram #:include\nfrom radlib.colors import Colors #:include',
                project_dir,
                os.path.join(project_dir, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                'from radlib.ram import Ram #:include\n'
                'class Ram:\n'
                '  pass\n'
                '#endinclude radlib/ram.py\n'
                'from radlib.colors import Colors #:include\n'
                '\n'
                'class Colors:\n'
                '  pass\n'
                '#endinclude radlib/colors.py',
                result,
            )

    def test_colon_strip_lines_are_omitted_from_injected_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.py'), 'w', encoding='utf-8') as f:
                f.write('from radlib_py.tic_80_api import * #:strip\n\nt=0')

            result = expand_includes(
                '# #include main.py',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                '# #include main.py\n\nt=0\n# #endinclude main.py',
                result,
            )

    def test_plain_hash_strip_lines_are_retained_as_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'main.py'), 'w', encoding='utf-8') as f:
                f.write('from radlib_py.tic_80_api import * #strip\n\nt=0')

            result = expand_includes(
                '# #include main.py',
                tmp,
                os.path.join(tmp, 'game.tic'),
                PreprocessOptions(language='python'),
            )

            self.assertEqual(
                '# #include main.py\nfrom radlib_py.tic_80_api import * #strip\n\nt=0\n# #endinclude main.py',
                result,
            )

    def test_missing_include_mentions_calling_file_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'game.tic #1'):
                expand_includes(
                    '-- #include missing.lua',
                    tmp,
                    'game.tic',
                    PreprocessOptions(language='lua'),
                )

    def test_missing_import_include_mentions_calling_file_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = os.path.join(tmp, 'dissolve')
            os.makedirs(project_dir)

            with self.assertRaisesRegex(ValueError, 'game.tic #1'):
                expand_includes(
                    'from radlib.missing import Game #:include',
                    project_dir,
                    os.path.join(project_dir, 'game.tic'),
                    PreprocessOptions(language='python'),
                )


if __name__ == '__main__':
    unittest.main()
