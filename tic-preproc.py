import argparse
import os
import shutil
import struct
from dataclasses import dataclass
from typing import BinaryIO, Optional

DEBUG = False
COMMENT_PREFIX_BY_LANGUAGE = {
    'fennel': ';',
    'javascript': '//',
    'janet': ';',
    'lua': '--',
    'moonscript': '--',
    'python': '#',
    'ruby': '#',
    'squirrel': '//',
    'wren': '//',
}
LANGUAGE_BY_EXTENSION = {
    '.fnl': 'fennel',
    '.js': 'javascript',
    '.janet': 'janet',
    '.lua': 'lua',
    '.moon': 'moonscript',
    '.py': 'python',
    '.rb': 'ruby',
    '.nut': 'squirrel',
    '.wren': 'wren',
}


@dataclass
class Args:
    file: str
    debug: bool
    backup: bool
    dry_run: bool
    retain_nested_includes: bool
    include_format: str
    endinclude_format: str
    language: str
    carts_dir_name: str


# Based on https://github.com/nesbox/TIC-80/blob/d348ab1d028e4dac12c4f511bcd0ff13a8660e90/src/cart.c#L61
@dataclass
class TicChunk:
    type: int
    bank: int
    size: int
    temp: int
    position: int

    Size = 4

    class Types:
        Code = 5
        CodeZip = 16
        Max = 20

    @classmethod
    def from_binary(cls, stream: BinaryIO) -> Optional['TicChunk']:
        pos = stream.tell()
        data = stream.read(4)

        if not data:
            return None

        (pack,) = struct.unpack('<I', data)
        chunk_type = pack & 0b11111
        bank = (pack >> 5) & 0b111
        size = (pack >> 8) & 0xFFFF
        temp = (pack >> 24) & 0xFF

        return cls(chunk_type, bank, size, temp, pos)

    def write_binary(self, stream: BinaryIO):
        pack = self.type | (self.bank << 5) | (self.size << 8) | (self.temp << 24)
        stream.write(struct.pack('<I', pack))


@dataclass
class CodeChunkInfo:
    chunk: TicChunk
    file_pos: int
    content: str
    rest: bytes


def dbg_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def detect_language(file: str) -> str:
    ext = os.path.splitext(file)[1]
    lang = LANGUAGE_BY_EXTENSION.get(ext, 'lua')
    dbg_print(f'Detected language: {lang}')
    return lang


# Recursively search for the .tic, starting from the file's directory
# and going up until the root is reached (dir fir .tic file) or we get
# outside the cart projects directory.
def find_tic_file(file: str, carts_dir_name: str) -> str:
    dbg_print(f'Finding .tic file for {file}')

    if not os.path.isabs(file):
        raise ValueError(f'The file path must be absolute: {file}')

    if carts_dir_name.lower() not in file.lower():
        raise ValueError(f'The file path must contain "tic-80": {file}')

    directory = os.path.dirname(file)
    dbg_print(f'Checking directory: {directory}')

    files = os.listdir(directory)

    tic_files = [f for f in files if f.endswith('.tic')]
    if len(tic_files) > 1:
        raise ValueError(f'More than 1 .tic file found at the root: {directory}')
    elif len(tic_files) == 1:
        return os.path.join(directory, tic_files[0])
    else:
        return find_tic_file(directory, carts_dir_name)


# Preprocess the file, replacing #include directives with the content of the included files.
# The included files can also include other files, but there is no protection against circular includes.
def preprocess_file(
        lines: list[str],
        project_dir: str,
        is_top_level: bool,
        file_name: str,
        args: Args
) -> list[str]:
    dbg_print(f'Preprocessing file: {file_name}')
    keep_includes = is_top_level or args.retain_nested_includes

    i = -1
    while i < len(lines) - 1:
        i += 1
        start_line = lines[i]

        # Look for #include
        if args.include_format not in start_line:
            continue

        include_line = i

        # Handle the include path
        include_file = start_line.split(' ')[-1].strip().strip('"')
        include_full_path = include_file
        if not os.path.isabs(include_file):
            include_full_path = os.path.join(project_dir, include_file)
        dbg_print(f'{file_name} includes: {include_full_path}')

        if not os.path.exists(include_full_path):
            raise ValueError(f'{file_name} #{i + 1}: included file not found: {include_full_path}')

        # Read and preprocess included file
        with open(include_full_path, 'r') as f:
            include_content = preprocess_file(
                f.read().split('\n'),
                project_dir,
                False,
                include_file,
                args
            )

        past_end_include_line = include_line + 1
        has_end_include = False

        # Look for #endinclude. Only top-level should contain #endincludes
        if is_top_level:
            for j, end_line in enumerate(lines[i:], start=i):
                if f'{args.endinclude_format} {include_file}' in end_line:
                    has_end_include = True
                    past_end_include_line = j + 1
                    break

        original_len = len(lines)

        if keep_includes:
            end_include = lines[past_end_include_line - 1]
            if not has_end_include:
                comment_prefix = COMMENT_PREFIX_BY_LANGUAGE[args.language]
                end_include = f'{comment_prefix} {args.endinclude_format} {include_file}'
            include_content += [f'{end_include}']
        elif lines[include_line].endswith('\n'):
            # include had newline, but since we're replacing it, we have to re-add it
            include_content += ['\n']

        # Replace the include line with the included content
        to_line = include_line + 1 if keep_includes else include_line
        lines = lines[:to_line] + include_content + lines[past_end_include_line:]

        delta_len = len(lines) - original_len
        i = past_end_include_line + delta_len - 1

    return lines


# Find the code chunk in the .tic file.
# Based on tic_cart_load: https://github.com/nesbox/TIC-80/blob/d348ab1d028e4dac12c4f511bcd0ff13a8660e90/src/cart.c#L160
def find_code_chunk(tic_file: str) -> CodeChunkInfo:
    with open(tic_file, 'rb') as f:
        header = f.read(4)

        # Perhaps in another iteration
        if header == b'x89PNG':
            raise ValueError('PNG files are not supported')
        f.seek(0)

        while chunk := TicChunk.from_binary(f):
            if chunk.type >= TicChunk.Types.Max:
                raise ValueError(f'Chunk read error, invalid type {chunk.type} at {f.tell() - 4}')

            dbg_print(f'Chunk {chunk.type} at 0x{chunk.position:08X}/{chunk.position}')

            if chunk.type != TicChunk.Types.Code:
                f.seek(chunk.size, os.SEEK_CUR)
                continue

            return CodeChunkInfo(
                chunk,
                f.tell(),
                f.read(chunk.size).decode('utf-8'),
                f.read()
            )

        raise ValueError('No code chunk found')


def run(args: Args):
    tic_file = find_tic_file(args.file, args.carts_dir_name)
    dbg_print(f'Found .tic file: {tic_file}')

    project_dir = os.path.dirname(tic_file)
    dbg_print(f'Project directory: {project_dir}')

    code_chunk_info = find_code_chunk(tic_file)
    dbg_print(f'Code chunk found, at:{code_chunk_info.file_pos} size:{code_chunk_info.chunk.size}')

    preprocessed_lines = preprocess_file(
        code_chunk_info.content.split('\n'),
        project_dir,
        True,
        tic_file,
        args
    )

    preprocessed_text = '\n'.join(preprocessed_lines)
    preprocessed_bin = preprocessed_text.encode('utf-8')
    dbg_print(f'File preprocessed, code size:{code_chunk_info.chunk.size}->{len(preprocessed_bin)}')

    if args.dry_run:
        print(preprocessed_text)
        return

    code_chunk_info.chunk.size = len(preprocessed_bin)

    if args.backup:
        backup_file = tic_file + '.bak'
        dbg_print(f'Creating backup file: {backup_file}')
        shutil.copyfile(tic_file, backup_file)

    with open(tic_file, 'r+b') as f:
        f.seek(code_chunk_info.chunk.position)
        code_chunk_info.chunk.write_binary(f)
        f.write(preprocessed_bin)
        f.write(code_chunk_info.rest)

    dbg_print(f'File written back to disk: {tic_file}')


def main():
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

    parsed_args = parser.parse_args()
    args = Args(
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

    global DEBUG
    DEBUG = args.debug

    run(args)


if __name__ == '__main__':
    main()
