import argparse
import os

from tic_preproc.config import COMMENT_PREFIX_BY_LANGUAGE, LANGUAGE_BY_EXTENSION, dbg_print, set_debug
from tic_preproc.pipeline import RunOptions, run


def detect_language(file: str) -> str:
    ext = os.path.splitext(file)[1]
    lang = LANGUAGE_BY_EXTENSION.get(ext, 'lua')
    dbg_print(f'Detected language: {lang}')
    return lang


def build_parser() -> argparse.ArgumentParser:
    description = ('tic-80 preprocessor. Searches for the .tic file in the project, preprocesses the code section and'
                   'writes it back to disk. Currently the only supported directive is #include which appends included '
                   'files. The included files can also include other files, but there is no protection against '
                   'circular includes. The included files must be relative to the project root or absolute paths.')

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('file', help='Any file in the tic-80 project, '
                                     'at root of which the .tic file is located. Can be the .tic file itself.')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug output')
    parser.add_argument('--no-backup', action='store_true', help='Do not create a backup file')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Do not write the file back to disk, only print the preprocessed code')
    parser.add_argument('--include-format', default='#include', help='Include directive format')
    parser.add_argument('--endinclude-format', default='#endinclude', help='End include directive format')
    parser.add_argument('--retain-nested-includes', '-r', action='store_true',
                        help='Nested includes will also keep the "include" and "endinclude" lines. '
                             'By default only top level includes keep the include declarations.')
    parser.add_argument('--lang', '-l', default='', help='Language of the code to preprocess. Detected if'
                                                         ' "file" is a script file.',
                        choices=COMMENT_PREFIX_BY_LANGUAGE.keys())
    parser.add_argument('--carts-dir-name', default='tic-80',
                        help='Name of the directory containing TIC-80 projects')
    return parser


def main():
    parsed_args = build_parser().parse_args()
    options = RunOptions(
        parsed_args.file,
        parsed_args.debug,
        not parsed_args.no_backup,
        parsed_args.dry_run,
        parsed_args.retain_nested_includes,
        parsed_args.include_format,
        parsed_args.endinclude_format,
        parsed_args.lang or detect_language(parsed_args.file),
        parsed_args.carts_dir_name
    )

    set_debug(options.debug)
    run(options)
