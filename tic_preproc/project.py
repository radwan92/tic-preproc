import os

from tic_preproc.config import dbg_print


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
    if len(tic_files) == 1:
        return os.path.join(directory, tic_files[0])

    return find_tic_file(directory, carts_dir_name)
