"""
Interleaving utilities to spread burst errors across RS blocks.

This is a simple block interleaver that permutes bits (or generic sequences)
across `depth` rows.
"""
from typing import List, Sequence, TypeVar

T = TypeVar("T")


def interleave_bits(bits: str, depth: int = 1) -> str:
    """
    Interleave a bitstring to spread adjacent errors.
    """
    if depth <= 1 or not bits:
        return bits

    # Split into rows by striding
    rows = [bits[i::depth] for i in range(depth)]

    # Recombine column-wise
    out = []
    max_len = max(len(r) for r in rows)
    for i in range(max_len):
        for r in rows:
            if i < len(r):
                out.append(r[i])
    return "".join(out)


def deinterleave_bits(bits: str, depth: int = 1) -> str:
    """
    Reverse of `interleave_bits`.
    """
    if depth <= 1 or not bits:
        return bits

    q, r = divmod(len(bits), depth)
    rows = []
    idx = 0
    for i in range(depth):
        row_len = q + (1 if i < r else 0)
        rows.append(bits[idx:idx + row_len])
        idx += row_len

    out = []
    max_len = max(len(r) for r in rows)
    for i in range(max_len):
        for r in rows:
            if i < len(r):
                out.append(r[i])
    return "".join(out)


def interleave_sequence(items: Sequence[T], depth: int = 1) -> List[T]:
    """
    Interleave an arbitrary sequence with the same pattern as `interleave_bits`.
    """
    if depth <= 1 or not items:
        return list(items)

    rows = [items[i::depth] for i in range(depth)]
    out: List[T] = []
    max_len = max(len(r) for r in rows)
    for i in range(max_len):
        for r in rows:
            if i < len(r):
                out.append(r[i])
    return out


def deinterleave_sequence(items: Sequence[T], depth: int = 1) -> List[T]:
    """
    Reverse of `interleave_sequence`.
    """
    if depth <= 1 or not items:
        return list(items)

    q, r = divmod(len(items), depth)
    rows: List[List[T]] = []
    idx = 0
    for i in range(depth):
        row_len = q + (1 if i < r else 0)
        rows.append(list(items[idx:idx + row_len]))
        idx += row_len

    out: List[T] = []
    max_len = max(len(r) for r in rows)
    for i in range(max_len):
        for r in rows:
            if i < len(r):
                out.append(r[i])
    return out


if __name__ == "__main__":
    print(interleave_bits("0101010101010", 4))
