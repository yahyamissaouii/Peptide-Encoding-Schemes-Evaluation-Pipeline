"""
Backend interface for connecting Streamlit frontend to the peptide encoding pipeline
"""

import sys
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

from PIL import Image

# Add the project root to the path to import src modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline.config import PipelineConfig
from src.pipeline.runner import encode_file_bytes
from src.error_correction.registry import PEPTIDE_RS_PROFILES, FOUNTAIN_PROFILES
from src.utils.image_utils import HEADER_SIZE, attach_image_header, detach_image_header


def prepare_image_payload(image_bytes: bytes) -> Dict[str, Any]:
    """
    Convert an image file into a robust payload:
    raw pixel bytes + compact dimension header.
    """
    with Image.open(BytesIO(image_bytes)) as image:
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        mode = image.mode
        width, height = image.size
        channels = 1 if mode == "L" else 3
        raw_pixels = image.tobytes()

    payload = attach_image_header(raw_pixels, width=width, height=height, channels=channels)
    return {
        "payload": payload,
        "mode": mode,
        "width": width,
        "height": height,
        "channels": channels,
        "raw_bytes_len": len(raw_pixels),
    }


def decode_image_payload(payload: bytes) -> Optional[Image.Image]:
    """
    Recover an image preview from payload bytes (header + raw pixels).
    """
    if not payload:
        return None

    meta, raw_pixels = detach_image_header(payload)
    if not meta:
        return None

    width = int(meta.get("width", 0) or 0)
    height = int(meta.get("height", 0) or 0)
    channels = int(meta.get("channels", 0) or 0)
    if width <= 0 or height <= 0 or channels not in (1, 3):
        return None

    expected_len = width * height * channels
    if len(raw_pixels) < expected_len:
        raw_pixels = raw_pixels + b"\x00" * (expected_len - len(raw_pixels))
    elif len(raw_pixels) > expected_len:
        raw_pixels = raw_pixels[:expected_len]

    mode = "L" if channels == 1 else "RGB"
    try:
        return Image.frombytes(mode, (width, height), raw_pixels)
    except Exception:
        return None


def decode_image_payload_with_shape(
    payload: bytes,
    width: int,
    height: int,
    channels: int,
) -> Optional[Image.Image]:
    """
    Decode payload with known image shape as fallback when header bytes are corrupted.
    """
    preview = decode_image_payload(payload)
    if preview is not None:
        return preview

    if width <= 0 or height <= 0 or channels not in (1, 3):
        return None
    if not payload:
        return None

    raw_pixels = payload[HEADER_SIZE:] if len(payload) > HEADER_SIZE else b""
    expected_len = width * height * channels
    if len(raw_pixels) < expected_len:
        raw_pixels = raw_pixels + b"\x00" * (expected_len - len(raw_pixels))
    elif len(raw_pixels) > expected_len:
        raw_pixels = raw_pixels[:expected_len]

    mode = "L" if channels == 1 else "RGB"
    try:
        return Image.frombytes(mode, (width, height), raw_pixels)
    except Exception:
        return None


def encode_data(
    data: bytes,
    peptide_length: int = 18,
    encoder: str = "huffman",
    ecc_profile: str = "none",
    error_model: str = "basic",
    score_column: str | None = None,
    score_label: str | None = None,
    loss_prob: float = 0.0,
    mutation_prob: float = 0.0,
    insertion_prob: float = 0.0,
    shuffle_prob: float = 0.0,
    shuffle_passes: int = 1,
) -> Dict[str, Any]:
    """
    Encode data using the peptide encoding pipeline

    Args:
        data: Input bytes to encode
        peptide_length: Length of each peptide sequence
        encoder: Encoding scheme name
        ecc_profile: Error correction code profile
        error_model: Error simulation model ("basic" or "scored")
        score_column: Optional score column for scored mode
        score_label: Optional label used for score report naming
        loss_prob: Probability of peptide loss
        mutation_prob: Probability of amino acid mutation
        insertion_prob: Probability of amino acid insertion
        shuffle_prob: Probability of amino acid shuffling
        shuffle_passes: Number of shuffle passes

    Returns:
        Dictionary containing encoding results and metrics
    """
    start_time = time.time()

    # Create pipeline configuration
    cfg = PipelineConfig(
        peptide_length=peptide_length,
        encoder=encoder,
        ecc_profile=ecc_profile,
        error_model=error_model,
        score_column=score_column,
        score_label=score_label,
        # Keep UI responsive while allowing chunked scored-mode requests
        # to complete for larger inputs.
        score_retry_sleep=1.0,
        score_max_sleep=30.0,
        score_timeout=15.0,
        score_batch_size=4000,
        score_batch_max_payload_bytes=120_000,
        loss_prob=loss_prob,
        mutation_prob=mutation_prob,
        insertion_prob=insertion_prob,
        shuffle_prob=shuffle_prob,
        shuffle_passes=shuffle_passes,
        convert_images_to_ppm=False,
        embed_image_header=False,
        visualize_as_pgm=False,
    )

    # Run encoding/decoding pipeline
    try:
        original_peptides, corrupted_peptides, result_bytes = encode_file_bytes(data, cfg)
    except Exception as e:
        # If encoding fails, return error information
        encoding_time = time.time() - start_time
        return {
            "success": False,
            "original_data": data,
            "recovered_data": None,
            "encoded_peptides": None,
            "original_size": len(data),
            "recovered_size": 0,
            "encoding_time": encoding_time,
            "bit_error_rate": 100.0,
            "bit_errors": len(data) * 8,
            "total_bits": len(data) * 8,
            "error_model": error_model,
            "score_column": score_column,
            "score_label": score_label,
            "error": str(e),
        }

    # Calculate metrics
    encoding_time = time.time() - start_time
    original_size = len(data)

    # Ensure result_bytes is bytes or None
    if result_bytes is not None and not isinstance(result_bytes, bytes):
        # Handle case where result might be a list or other type
        try:
            result_bytes = bytes(result_bytes)
        except:
            result_bytes = None

    recovered_size = len(result_bytes) if result_bytes else 0
    recovery_success = (result_bytes is not None and data == result_bytes)

    # Calculate bit error rate if recovery failed
    bit_errors = 0
    if not recovery_success and result_bytes and isinstance(result_bytes, bytes):
        min_len = min(len(data), len(result_bytes))
        for i in range(min_len):
            if data[i] != result_bytes[i]:
                bit_errors += bin(data[i] ^ result_bytes[i]).count('1')
        # Add errors for length difference
        bit_errors += abs(len(data) - len(result_bytes)) * 8

    total_bits = len(data) * 8
    bit_error_rate = (bit_errors / total_bits * 100) if total_bits > 0 else 0

    return {
        "success": recovery_success,
        "original_data": data,
        "recovered_data": result_bytes,
        "encoded_peptides": original_peptides,
        "original_size": original_size,
        "recovered_size": recovered_size,
        "encoding_time": encoding_time,
        "bit_error_rate": bit_error_rate,
        "bit_errors": bit_errors,
        "total_bits": total_bits,
        "error_model": error_model,
        "score_column": score_column,
        "score_label": score_label,
    }


def get_amino_acid_alphabet() -> List[str]:
    """Get the 8-letter peptide alphabet used for encoding"""
    return ["A", "V", "L", "S", "T", "F", "Y", "E"]


def get_encoders() -> List[str]:
    """Get available encoding schemes"""
    return ["huffman", "yin_yang", "fountain"]


def get_ecc_profiles(encoder: str | None = None) -> List[str]:
    """Get available error correction code profiles"""
    if encoder == "fountain":
        return list(FOUNTAIN_PROFILES.keys())
    profiles = list(PEPTIDE_RS_PROFILES.keys())
    if "none" in profiles:
        profiles.remove("none")
        profiles.insert(0, "none")
    return profiles


def get_profile_description(profile: str) -> str:
    """Get description for an ECC profile"""
    profile = profile.lower()
    if profile == "none":
        return "No error correction - fastest but no error recovery"

    if profile in FOUNTAIN_PROFILES:
        overhead_pct = int(FOUNTAIN_PROFILES[profile] * 100)
        return f"Fountain with ~{overhead_pct}% overhead"

    match = re.fullmatch(r"rs(\d+)(?:_int(\d+))?", profile)
    if match:
        parity_symbols = int(match.group(1))
        interleave_depth = match.group(2)
        if interleave_depth:
            depth = int(interleave_depth)
            return (
                f"Reed-Solomon with {parity_symbols} parity symbols + "
                f"{depth}-level interleaving for burst error protection"
            )
        return f"Reed-Solomon with {parity_symbols} parity symbols"

    return "Unknown profile"
