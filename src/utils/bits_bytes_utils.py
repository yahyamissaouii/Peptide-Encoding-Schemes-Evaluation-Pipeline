

def bytes_to_bitstring(data: bytes) -> str:
    """Convert bytes -> bitstring (8 bits per byte)."""
    return "".join(f"{byte:08b}" for byte in data)


def bitstring_to_bytes(bits: str) -> bytes:
    """
    Convert bitstring -> bytes.

    Length must be a multiple of 8.
    """
    if len(bits) % 8 != 0:
        raise ValueError(
            f"Bitstring length must be multiple of 8, got {len(bits)}"
        )
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
