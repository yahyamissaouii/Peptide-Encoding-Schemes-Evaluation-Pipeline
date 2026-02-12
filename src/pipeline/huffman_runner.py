
from src.encoding_schemes.huffman import huffman_encode, huffman_decode
from src.encoding_schemes.peptide_mapping import bits_to_peptides, peptides_to_bits
from src.error_correction import (
    ecc_encode_peptides,
    ecc_decode_peptides,
    RSEncodedPeptides,
)
from src.error_model import apply_peptide_errors, apply_peptide_errors_scored
from src.pipeline.config import PipelineConfig


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def encode_decode_file_huffman(data: bytes, cfg: PipelineConfig):
    """
    Encode, corrupt and decode a single file with Huffman + peptide mapping.
    Returns (original_peptides, corrupted_peptides, decoded_bytes).
    """
    enc = huffman_encode(data)

    mapping = bits_to_peptides(
        enc.bits,
        peptide_length=cfg.peptide_length,
        index_aa_length=cfg.index_aa_length,
    )
    ecc_packet: RSEncodedPeptides = ecc_encode_peptides(mapping, profile=cfg.ecc_profile)
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

    recovered_bits = peptides_to_bits(recovered_mapping)
    enc.bits = recovered_bits
    try:
        decoded = huffman_decode(enc)
    except Exception:
        decoded = b""

    return original_peptides, corrupted_peptides, decoded
