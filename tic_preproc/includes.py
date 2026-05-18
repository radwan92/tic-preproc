import os

from tic_preproc.config import PreprocessOptions, dbg_print

STRIP_DIRECTIVE = '#:strip'


def expand_includes(
        source: str,
        project_dir: str,
        file_name: str,
        options: PreprocessOptions,
        is_top_level: bool = True
) -> str:
    lines = source.split('\n')
    return '\n'.join(_expand_include_lines(lines, project_dir, file_name, options, is_top_level))


def _expand_include_lines(
        lines: list[str],
        project_dir: str,
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

        if options.include_format not in start_line:
            continue

        include_line = i
        include_file = start_line.split(' ')[-1].strip().strip('"')
        include_full_path = include_file
        if not os.path.isabs(include_file):
            include_full_path = os.path.join(project_dir, include_file)
        dbg_print(f'{file_name} includes: {include_full_path}')

        if not os.path.exists(include_full_path):
            raise ValueError(f'{file_name} #{i + 1}: included file not found: {include_full_path}')

        with open(include_full_path, 'rb') as f:
            include_source = f.read().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
            include_content = _expand_include_lines(
                include_source.split('\n'),
                project_dir,
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
