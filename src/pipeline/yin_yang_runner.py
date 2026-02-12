from src.encoding_schemes.yin_yang import YinYangEncoded, yin_yang_decode, yin_yang_encode
from src.encoding_schemes.peptide_mapping import PeptideMappingResult
from src.error_correction import ecc_decode_peptides, ecc_encode_peptides
from src.error_model import apply_peptide_errors, apply_peptide_errors_scored
from src.pipeline.config import PipelineConfig


def encode_decode_file_yin_yang(data: bytes, cfg: PipelineConfig):
    """
    Encode, corrupt and decode a single file with Yin-Yang + peptide-level RS.
    Returns (original_peptides, corrupted_peptides, decoded_bytes).
    """
    enc: YinYangEncoded = yin_yang_encode(data, cfg)

    mapping = PeptideMappingResult(
        peptides=enc.peptides,
        pad_bits=enc.pad_bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
    )
    ecc_packet = ecc_encode_peptides(mapping, profile=cfg.ecc_profile)
    original_peptides = ecc_packet.peptides

    if cfg.error_model == "scored":
        corrupted_peptides = apply_peptide_errors_scored(
            original_peptides,
            score_column=cfg.score_column,
            score_label=cfg.score_label,
            shuffle_passes=cfg.shuffle_passes,
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
        )

    recovered_mapping = ecc_decode_peptides(
        corrupted_peptides,
        encoded=ecc_packet,
        profile=cfg.ecc_profile,
    )

    recovered = YinYangEncoded(
        peptides=recovered_mapping.peptides,
        pad_bits=recovered_mapping.pad_bits,
        peptide_length=recovered_mapping.peptide_length,
        index_aa_length=recovered_mapping.index_aa_length,
        original_size_bytes=enc.original_size_bytes,
        scheme_id=enc.scheme_id,
    )

    try:
        decoded = yin_yang_decode(recovered)
    except Exception:
        decoded = b""

    return original_peptides, corrupted_peptides, decoded
