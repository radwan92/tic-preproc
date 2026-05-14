import os
import shutil
from dataclasses import dataclass

from tic_preproc.cartridge import TicCartridge
from tic_preproc.config import PreprocessOptions, dbg_print
from tic_preproc.includes import expand_includes
from tic_preproc.project import find_tic_file


@dataclass
class RunOptions:
    file: str
    debug: bool = False
    backup: bool = True
    dry_run: bool = False
    retain_nested_includes: bool = False
    include_format: str = '#include'
    endinclude_format: str = '#endinclude'
    language: str = 'lua'
    carts_dir_name: str = 'tic-80'


def run(options: RunOptions):
    tic_file = find_tic_file(options.file, options.carts_dir_name)
    dbg_print(f'Found .tic file: {tic_file}')

    project_dir = os.path.dirname(tic_file)
    dbg_print(f'Project directory: {project_dir}')

    cartridge = TicCartridge.load(tic_file)
    dbg_print(f'Code chunk found, at:{cartridge.code_chunk.position + cartridge.code_chunk.Size} size:{cartridge.code_chunk.size}')

    preprocess_options = PreprocessOptions(
        options.retain_nested_includes,
        options.include_format,
        options.endinclude_format,
        options.language
    )
    preprocessed_text = expand_includes(cartridge.code_text, project_dir, tic_file, preprocess_options)
    dbg_print(f'File preprocessed, code size:{cartridge.code_chunk.size}->{len(preprocessed_text.encode("utf-8"))}')

    if options.dry_run:
        print(preprocessed_text)
        return

    if options.backup:
        backup_file = tic_file + '.bak'
        dbg_print(f'Creating backup file: {backup_file}')
        shutil.copyfile(tic_file, backup_file)

    cartridge.replace_code(preprocessed_text)
    cartridge.write()
    dbg_print(f'File written back to disk: {tic_file}')
