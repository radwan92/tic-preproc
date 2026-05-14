import os
import struct
from dataclasses import dataclass
from typing import BinaryIO, Optional

from tic_preproc.config import dbg_print


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
class TicCartridge:
    path: str
    code_chunk: TicChunk
    code_text: str
    rest: bytes

    @classmethod
    def load(cls, path: str) -> 'TicCartridge':
        with open(path, 'rb') as f:
            header = f.read(4)

            if header == b'\x89PNG':
                raise ValueError('PNG files are not supported')
            f.seek(0)

            while chunk := TicChunk.from_binary(f):
                if chunk.type >= TicChunk.Types.Max:
                    raise ValueError(f'Chunk read error, invalid type {chunk.type} at {f.tell() - 4}')

                dbg_print(f'Chunk {chunk.type} at 0x{chunk.position:08X}/{chunk.position}')

                if chunk.type != TicChunk.Types.Code:
                    f.seek(chunk.size, os.SEEK_CUR)
                    continue

                return cls(
                    path,
                    chunk,
                    f.read(chunk.size).decode('utf-8'),
                    f.read()
                )

            raise ValueError('No code chunk found')

    def replace_code(self, code_text: str):
        self.code_text = code_text
        self.code_chunk.size = len(code_text.encode('utf-8'))

    def write(self, path: str | None = None):
        write_path = path or self.path
        code_bin = self.code_text.encode('utf-8')
        self.code_chunk.size = len(code_bin)

        with open(write_path, 'r+b') as f:
            f.seek(self.code_chunk.position)
            self.code_chunk.write_binary(f)
            f.write(code_bin)
            f.write(self.rest)
            f.truncate()
