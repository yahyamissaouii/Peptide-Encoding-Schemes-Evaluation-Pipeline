from math import ceil, sqrt


def bytes_to_pgm(data: bytes, width: int = 0) -> bytes:
    """
    Map arbitrary bytes to a grayscale PGM image.

    This is uncompressed; corruption shows as pixel noise instead of breaking decoding.
    """
    if width <= 0:
        # auto-pick a width that yields roughly square output
        width = max(1, int(sqrt(len(data)))) if len(data) else 1

    height = ceil(len(data) / width) if len(data) else 1
    padded_len = width * height
    if len(data) < padded_len:
        data += b"\x00" * (padded_len - len(data))
    header = f"P5\n{width} {height}\n255\n".encode("ascii")
    return header + data
