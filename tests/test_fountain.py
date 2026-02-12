import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.encoding_schemes.fountain import fountain_decode, fountain_encode
from src.error_correction.registry import get_fountain_overhead
from src.pipeline.config import PipelineConfig
from src.pipeline.fountain_runner import encode_decode_file_fountain


def test_fountain_roundtrip_profile():
    data = b"fountain-profile-roundtrip" * 4
    cfg = PipelineConfig(
        peptide_length=18,
        index_aa_length=0,
        ecc_profile="fnt10",
        fountain_symbol_size=8,
        fountain_overhead=0.0,
        fountain_seed=12345,
        # Deterministic roundtrip: no channel noise.
        loss_prob=0.0,
        mutation_prob=0.0,
        insertion_prob=0.0,
        shuffle_prob=0.0,
    )

    _, _, decoded = encode_decode_file_fountain(data, cfg)

    assert decoded == data


def test_fountain_overhead_applied():
    data = b"overhead-check" * 16
    cfg = PipelineConfig(
        ecc_profile="fnt20",
        fountain_symbol_size=16,
        fountain_overhead=0.0,
        fountain_seed=99,
    )
    overhead = get_fountain_overhead(cfg.ecc_profile, cfg.fountain_overhead)
    encoded = fountain_encode(data, cfg, overhead=overhead)

    expected_k = math.ceil(len(data) / encoded.symbol_size) or 1
    baseline = max(8, expected_k)
    expected_droplets = max(baseline, math.ceil(baseline * (1.0 + overhead)))

    assert encoded.k == expected_k
    assert encoded.droplet_count == expected_droplets


def test_fountain_encode_decode_sequence():
    data = bytes((i % 256) for i in range(4096))
    cfg = PipelineConfig(
        ecc_profile="fnt20",
        fountain_symbol_size=64,
        fountain_overhead=0.05,
        fountain_seed=2024,
    )
    overhead = get_fountain_overhead(cfg.ecc_profile, cfg.fountain_overhead)
    encoded = fountain_encode(data, cfg, overhead=overhead)
    decoded = fountain_decode(encoded)

    print("Fountain test config:")
    print(
        f"  data_len={len(data)} symbol_size={encoded.symbol_size} "
        f"k={encoded.k} overhead={overhead} droplets={encoded.droplet_count} "
        f"droplet_size={encoded.droplet_size_bytes}"
    )
    print(f"  bits_len={len(encoded.bits)} expected_bits={encoded.droplet_count * encoded.droplet_size_bytes * 8}")

    assert len(encoded.bits) == encoded.droplet_count * encoded.droplet_size_bytes * 8
    assert decoded == data


if __name__ == "__main__":
    print("Running fountain tests directly...")
    test_fountain_roundtrip_profile()
    test_fountain_overhead_applied()
    test_fountain_encode_decode_sequence()
    print("Fountain tests completed.")
