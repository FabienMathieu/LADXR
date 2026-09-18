"""Tag type for assembled code and a minimal SM83 operand scanner."""

from typing import Iterator, Tuple


class Code(bytes):
    """Hexlified assembled code, distinguishable from raw data patches."""
    pass


# Opcodes carrying a 16-bit absolute address operand.
ABS16_OPS = {
    0x01, 0x11, 0x21, 0x31, 0x08,
    0xC2, 0xC3, 0xC4, 0xCA, 0xCC, 0xCD,
    0xD2, 0xD4, 0xDA, 0xDC,
    0xEA, 0xFA,
}

# Instruction length in bytes for every base opcode.
OPCODE_LENGTH = [1] * 256
for _op in ABS16_OPS:
    OPCODE_LENGTH[_op] = 3
for _op in (0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E,
            0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE,
            0xE0, 0xF0, 0xE8, 0xF8,
            0x18, 0x20, 0x28, 0x30, 0x38, 0x10):
    OPCODE_LENGTH[_op] = 2
OPCODE_LENGTH[0xCB] = 2
del _op


def iter_abs16_operands(raw: bytes) -> Iterator[Tuple[int, int]]:
    """Yield (index, operand) for every 16-bit absolute operand in code."""
    i = 0
    length = len(raw)
    while i < length:
        op = raw[i]
        size = OPCODE_LENGTH[op]
        if i + size > length:
            break
        if op in ABS16_OPS:
            yield i, raw[i + 1] | (raw[i + 2] << 8)
        i += size
