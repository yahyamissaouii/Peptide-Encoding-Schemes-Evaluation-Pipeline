from io import BytesIO
from typing import Dict, Tuple
import struct

MAGIC = b"IMH0"
HEADER_FMT = ">4sIIB"  # magic, width (u32), height (u32), channels (u8)
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def convert_image_to_ppm_bytes(data: bytes) -> Tuple[bytes, str, int, int]:
    """
    Convert an image byte stream (png/jpg/jpeg/bmp) to raw PPM/PGM bytes.

    Returns (ppm_bytes, mode, width, height), where mode is "L" for grayscale or "RGB" for color.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for image conversion. Install 'Pillow' to use convert_images_to_ppm."
        ) from exc

    with Image.open(BytesIO(data)) as img:
        # Convert to a safe mode
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        mode = img.mode
        width, height = img.size
        buf = BytesIO()
        fmt = "PPM" if mode == "RGB" else "PPM"  # PPM also stores grayscale as P5 via Pillow
        img.save(buf, format=fmt)
        return buf.getvalue(), mode, width, height


def attach_image_header(data: bytes, width: int, height: int, channels: int) -> bytes:
    """
    Prepend a tiny header with image dimensions/channels to the payload.
    """
    header = struct.pack(HEADER_FMT, MAGIC, width, height, channels)
    return header + data


def detach_image_header(data: bytes) -> Tuple[Dict[str, int], bytes]:
    """
    If an image header is present, return metadata and the stripped payload.
    Otherwise, returns ({}, original_data).
    """
    if len(data) < HEADER_SIZE:
        return {}, data
    try:
        magic, width, height, channels = struct.unpack(
            HEADER_FMT, data[:HEADER_SIZE]
        )
    except struct.error:
        return {}, data
    if magic != MAGIC:
        return {}, data
    meta = {
        "width": width,
        "height": height,
        "channels": channels,
    }
    return meta, data[HEADER_SIZE:]
