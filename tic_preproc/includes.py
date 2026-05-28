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
    return '\n'.join(_expand_include_lines(lines, include_base_dir, file_name, options, is_top_level, set()))


def _expand_include_lines(
        lines: list[str],
        include_base_dir: str,
        file_name: str,
        options: PreprocessOptions,
        is_top_level: bool,
        included_paths: set[str]
) -> list[str]:
    dbg_print(f'Preprocessing file: {file_name}')
    keep_includes = is_top_level or options.retain_nested_includes

    i = -1
    while i < len(lines) - 1:
        i += 1
        start_line = lines[i]

        if start_line.strip() == IMPORT_INCLUDE_DIRECTIVE:
            del lines[i]
            i -= 1
            continue

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
        elif options.language == 'python':
            auto_marker, include_file, include_full_path = _resolve_auto_import_directive(
                start_line,
                include_base_dir,
            )
            if auto_marker == STRIP_DIRECTIVE:
                del lines[i]
                i -= 1
                continue
            if auto_marker != IMPORT_INCLUDE_DIRECTIVE:
                continue
        else:
            continue

        include_line = i
        dbg_print(f'{file_name} includes: {include_full_path}')

        if not os.path.exists(include_full_path):
            raise ValueError(f'{file_name} #{i + 1}: included file not found: {include_full_path}')

        past_end_include_line = include_line + 1

        if is_top_level:
            for j, end_line in enumerate(lines[i:], start=i):
                if f'{options.endinclude_format} {include_file}' in end_line:
                    past_end_include_line = j + 1
                    break

        original_len = len(lines)
        canonical_include_path = _canonical_include_path(include_full_path)

        if canonical_include_path in included_paths:
            include_content = []
        else:
            included_paths.add(canonical_include_path)
            with open(include_full_path, 'rb') as f:
                include_source = f.read().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
                include_content = _expand_include_lines(
                    include_source.split('\n'),
                    os.path.dirname(include_full_path),
                    include_file,
                    options,
                    False,
                    included_paths
                )

        if keep_includes:
            if IMPORT_INCLUDE_DIRECTIVE in start_line or options.include_format not in start_line:
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


def _canonical_include_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


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


def _resolve_auto_import_directive(
        line: str,
        include_base_dir: str
) -> tuple[str | None, str | None, str | None]:
    try:
        parsed = ast.parse(line)
    except SyntaxError:
        return None, None, None

    if len(parsed.body) != 1:
        return None, None, None

    statement = parsed.body[0]
    if isinstance(statement, ast.ImportFrom):
        if statement.level != 0 or not statement.module:
            return None, None, None
        module = statement.module
    elif isinstance(statement, ast.Import):
        if len(statement.names) != 1:
            return None, None, None
        module = statement.names[0].name
    else:
        return None, None, None

    include_file = module.replace('.', '/') + '.py'
    include_full_path = _find_existing_import_include_path(include_file, include_base_dir)
    marker = _get_first_line_marker(include_full_path) if include_full_path else None
    if not marker:
        return None, None, None

    return marker, include_file, include_full_path


def _find_import_include_path(include_file: str, include_base_dir: str) -> str:
    include_full_path = _find_existing_import_include_path(include_file, include_base_dir)
    if include_full_path:
        return include_full_path
    return os.path.normpath(os.path.join(include_base_dir, include_file))


def _find_existing_import_include_path(include_file: str, include_base_dir: str) -> str | None:
    current_dir = os.path.abspath(include_base_dir)
    while True:
        candidate = os.path.normpath(os.path.join(current_dir, include_file))
        if os.path.exists(candidate):
            return candidate

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            return None
        current_dir = parent_dir


def _get_first_line_marker(path: str) -> str | None:
    with open(path, 'r', encoding='utf-8') as f:
        marker = f.readline().strip()
        if marker in (IMPORT_INCLUDE_DIRECTIVE, STRIP_DIRECTIVE):
            return marker
        return None
