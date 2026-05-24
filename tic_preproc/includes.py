import ast
import os

from tic_preproc.config import PreprocessOptions, dbg_print

STRIP_DIRECTIVE = '#:strip'
IMPORT_INCLUDE_DIRECTIVE = '#:include'


def expand_includes(
        source: str,
        project_dir: str,
        file_name: str,
        options: PreprocessOptions,
        is_top_level: bool = True
) -> str:
    lines = source.split('\n')
    include_base_dir = os.path.dirname(file_name) if os.path.isabs(file_name) else project_dir
    return '\n'.join(_expand_include_lines(lines, include_base_dir, file_name, options, is_top_level))


def _expand_include_lines(
        lines: list[str],
        include_base_dir: str,
        file_name: str,
        options: PreprocessOptions,
        is_top_level: bool
) -> list[str]:
    dbg_print(f'Preprocessing file: {file_name}')
    keep_includes = is_top_level or options.retain_nested_includes

    i = -1
    while i < len(lines) - 1:
        i += 1
        start_line = lines[i]

        if STRIP_DIRECTIVE in start_line:
            del lines[i]
            i -= 1
            continue

        include_file = None
        include_full_path = None

        if IMPORT_INCLUDE_DIRECTIVE in start_line:
            include_file, include_full_path = _resolve_import_include(
                start_line,
                include_base_dir,
                file_name,
                i + 1,
                options,
            )
        elif options.include_format in start_line:
            include_file = start_line.split(' ')[-1].strip().strip('"')
            include_full_path = include_file
            if not os.path.isabs(include_file):
                include_full_path = os.path.normpath(os.path.join(include_base_dir, include_file))
        else:
            continue

        include_line = i
        dbg_print(f'{file_name} includes: {include_full_path}')

        if not os.path.exists(include_full_path):
            raise ValueError(f'{file_name} #{i + 1}: included file not found: {include_full_path}')

        with open(include_full_path, 'rb') as f:
            include_source = f.read().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
            include_content = _expand_include_lines(
                include_source.split('\n'),
                os.path.dirname(include_full_path),
                include_file,
                options,
                False
            )

        past_end_include_line = include_line + 1
        has_end_include = False

        if is_top_level:
            for j, end_line in enumerate(lines[i:], start=i):
                if f'{options.endinclude_format} {include_file}' in end_line:
                    has_end_include = True
                    past_end_include_line = j + 1
                    break

        original_len = len(lines)

        if keep_includes:
            if IMPORT_INCLUDE_DIRECTIVE in start_line:
                include_prefix = ''
            else:
                include_prefix = start_line.split(options.include_format, 1)[0]
            end_include = f'{include_prefix}{options.endinclude_format} {include_file}'
            include_content += [end_include]
        elif lines[include_line].endswith('\n'):
            include_content += ['\n']

        to_line = include_line + 1 if keep_includes else include_line
        lines = lines[:to_line] + include_content + lines[past_end_include_line:]

        delta_len = len(lines) - original_len
        i = past_end_include_line + delta_len - 1

    return lines


def _resolve_import_include(
        line: str,
        include_base_dir: str,
        file_name: str,
        line_number: int,
        options: PreprocessOptions
) -> tuple[str, str]:
    if options.language != 'python':
        raise ValueError(f'{file_name} #{line_number}: #:include import directives are only supported for python')

    try:
        parsed = ast.parse(line)
    except SyntaxError as e:
        raise ValueError(f'{file_name} #{line_number}: unsupported #:include import directive') from e

    if len(parsed.body) != 1 or not isinstance(parsed.body[0], ast.ImportFrom):
        raise ValueError(f'{file_name} #{line_number}: unsupported #:include import directive')

    import_from = parsed.body[0]
    if import_from.level != 0 or not import_from.module:
        raise ValueError(f'{file_name} #{line_number}: unsupported #:include import directive')

    include_file = import_from.module.replace('.', '/') + '.py'
    include_full_path = _find_import_include_path(include_file, include_base_dir)
    return include_file, include_full_path


def _find_import_include_path(include_file: str, include_base_dir: str) -> str:
    current_dir = os.path.abspath(include_base_dir)
    while True:
        candidate = os.path.normpath(os.path.join(current_dir, include_file))
        if os.path.exists(candidate):
            return candidate

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            return os.path.normpath(os.path.join(include_base_dir, include_file))
        current_dir = parent_dir
