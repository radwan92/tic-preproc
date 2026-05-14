from dataclasses import dataclass

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
class PreprocessOptions:
    retain_nested_includes: bool = False
    include_format: str = '#include'
    endinclude_format: str = '#endinclude'
    language: str = 'lua'


def set_debug(enabled: bool):
    global DEBUG
    DEBUG = enabled


def dbg_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)
