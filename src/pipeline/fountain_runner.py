from src.encoding_schemes.fountain import FountainEncoded, fountain_decode, fountain_encode
from src.encoding_schemes.peptide_mapping import bits_to_peptides, peptides_to_bits_fixed
from src.error_correction.registry import get_fountain_overhead
from src.error_model import apply_peptide_errors, apply_peptide_errors_scored
from src.pipeline.config import PipelineConfig


def encode_decode_file_fountain(data: bytes, cfg: PipelineConfig):
    """
    Encode, corrupt and decode a single file with Fountain + peptide mapping.
    Returns (original_peptides, corrupted_peptides, decoded_bytes).
    """
    overhead = get_fountain_overhead(cfg.ecc_profile, cfg.fountain_overhead)
    encoded: FountainEncoded = fountain_encode(data, cfg, overhead=overhead)
    payload_bits = encoded.bits
    mapping = bits_to_peptides(
        payload_bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
        pad_to_full_peptide=True,
    )
    original_peptides = mapping.peptides
    total_peptides = len(mapping.peptides)

    if cfg.error_model == "scored":
        corrupted_peptides = apply_peptide_errors_scored(
            original_peptides,
            score_column=cfg.score_column,
            score_label=cfg.score_label,
            shuffle_passes=cfg.shuffle_passes,
            drop_empty=(cfg.index_aa_length > 0),
            # Fountain assumes an erasure channel. Interpret "loss" as whole-peptide
            # dropout so a lost peptide wipes out its droplet segment cleanly.
            loss_mode="peptide",
            retry_sleep=cfg.score_retry_sleep,
            max_sleep=cfg.score_max_sleep,
            request_timeout=cfg.score_timeout,
            score_batch_size=cfg.score_batch_size,
            score_batch_max_payload_bytes=cfg.score_batch_max_payload_bytes,
        )
    else:
        corrupted_peptides = apply_peptide_errors(
            original_peptides,
            loss_prob=cfg.loss_prob,
            mutation_prob=cfg.mutation_prob,
            insertion_prob=cfg.insertion_prob,
            shuffle_prob=cfg.shuffle_prob,
            shuffle_passes=cfg.shuffle_passes,
            drop_empty=(cfg.index_aa_length > 0),
            # Fountain assumes an erasure channel; use whole-peptide dropout.
            loss_mode="peptide",
        )

    recovered_bits = peptides_to_bits_fixed(
        list(corrupted_peptides),
        peptide_length=mapping.peptide_length,
        index_aa_length=mapping.index_aa_length,
        total_peptides=total_peptides,
        pad_bits=mapping.pad_bits,
    )
    encoded.bits = recovered_bits
    decoded = fountain_decode(encoded)
    return original_peptides, corrupted_peptides, decoded
