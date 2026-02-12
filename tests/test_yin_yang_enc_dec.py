import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.config import PipelineConfig
from src.pipeline.yin_yang_runner import encode_decode_file_yin_yang


data = b"hello peptide!"
cfg = PipelineConfig(
    peptide_length=18,
    ecc_profile="none",
    loss_prob=0.0,
    mutation_prob=0.0,
    insertion_prob=0.0,
    shuffle_prob=0.0,
    shuffle_passes=1,
    encoder="yin_yang",
    index_aa_length=0,
    error_model="basic",
)

original_peptides, corrupted_peptides, decoded = encode_decode_file_yin_yang(data, cfg)

print("Original peptides:", len(original_peptides))
print("\n".join(original_peptides[:5]))
print("Corrupted peptides:", len(corrupted_peptides))
print("Decoded:", decoded)
print("OK?   ", decoded == data)
