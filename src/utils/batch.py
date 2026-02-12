import os
from pathlib import Path

from src.pipeline.huffman_runner import encode_decode_file_huffman
from src.pipeline.fountain_runner import encode_decode_file_fountain
from src.pipeline.yin_yang_runner import encode_decode_file_yin_yang

from src.pipeline.config import PipelineConfig
from src.utils import (
    convert_image_to_ppm_bytes,
    attach_image_header,
    detach_image_header,
    add_suffix_to_top_level,
    suffix_filename,
    bytes_to_pgm,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def run_batch_on_folder(
    input_root: Path,
    output_root: Path,
    cfg: PipelineConfig | None = None,
) -> None:
    if cfg is None:
        cfg = PipelineConfig()

    input_root = input_root.resolve()
    output_root = output_root.resolve()

    out_encoded_root = output_root / "out_encoded"
    out_decoded_root = output_root / "out_decoded"
    out_chunked_root = output_root / "out_chunked"

    for root, _, files in os.walk(input_root):
        root_path = Path(root)
        rel_root = root_path.relative_to(input_root)

        for filename in files:
            in_path = root_path / filename
            print("Processing:", in_path)

            encoder = cfg.encoder.lower()
            if encoder == "huffman":
                process_file(
                    in_path=in_path,
                    rel_root=rel_root,
                    out_encoded_root=out_encoded_root,
                    out_decoded_root=out_decoded_root,
                    out_chunked_root=out_chunked_root,
                    cfg=cfg,
                )
            elif encoder == "yin_yang":
                process_file_yin_yang(
                    in_path=in_path,
                    rel_root=rel_root,
                    out_encoded_root=out_encoded_root,
                    out_decoded_root=out_decoded_root,
                    out_chunked_root=out_chunked_root,
                    cfg=cfg,
                )
            elif encoder == "fountain":
                process_file_fountain(
                    in_path=in_path,
                    rel_root=rel_root,
                    out_encoded_root=out_encoded_root,
                    out_decoded_root=out_decoded_root,
                    out_chunked_root=out_chunked_root,
                    cfg=cfg,
                )
            else:
                raise ValueError(f"Unsupported encoder: {cfg.encoder}")



def process_file(
    in_path: Path,
    rel_root: Path,
    out_encoded_root: Path,
    out_decoded_root: Path,
    out_chunked_root: Path,
    cfg: PipelineConfig,
):
    data = in_path.read_bytes()
    cfg.score_label = in_path.name

    # Optionally convert images to raw PPM so they remain viewable even with some bit flips.
    converted_to_ppm = False
    ppm_mode = None
    ppm_dims = None

    """
    if cfg.convert_images_to_ppm and in_path.suffix.lower() in IMAGE_EXTS:
        try:
            data, ppm_mode, width, height = convert_image_to_ppm_bytes(data)
            converted_to_ppm = True
            ppm_dims = (width, height)
            if cfg.embed_image_header:
                channels = 1 if ppm_mode == "L" else 3
                data = attach_image_header(data, width, height, channels)
        except Exception as exc:
            print(f"Image conversion failed for {in_path}: {exc}")
    """

    # Use the imported Huffman encoder/decoder
    original_peptides, _, decoded_bytes = encode_decode_file_huffman(data, cfg)

    encoded_rel_dir = add_suffix_to_top_level(rel_root, "_encoded")
    encoded_rel_file = suffix_filename(Path(in_path.name), "_encoded")
    encoded_out_dir = out_encoded_root / encoded_rel_dir
    encoded_out_dir.mkdir(parents=True, exist_ok=True)
    encoded_out_path = encoded_out_dir / encoded_rel_file.name
    print("Encoded output dir:", encoded_out_dir)
    encoded_out_path.write_text(
        "\n".join(original_peptides),
        encoding="utf-8",
    )

    # Write chunked peptides (with block/index/role) to a sibling folder.
    chunk_rel_dir = add_suffix_to_top_level(rel_root, "_chunked")
    chunk_rel_file = suffix_filename(Path(in_path.name), "_chunked")
    chunk_out_dir = out_chunked_root / chunk_rel_dir
    chunk_out_dir.mkdir(parents=True, exist_ok=True)
    chunk_out_path = chunk_out_dir / chunk_rel_file.name
    try:
        from src.encoding_schemes.huffman import huffman_encode
        from src.encoding_schemes.peptide_mapping import bits_to_peptides
        from src.error_correction.registry import ecc_encode_peptides

        reenc = huffman_encode(data)
        mapping = bits_to_peptides(
            reenc.bits,
            peptide_length=cfg.peptide_length,
            index_aa_length=cfg.index_aa_length,
        )
        ecc_packet = ecc_encode_peptides(mapping, profile=cfg.ecc_profile)

        lines = []
        for pep, meta in zip(ecc_packet.peptides, ecc_packet.metadata):
            role = "parity" if meta.is_parity else "data"
            lines.append(f"{meta.block_id},{meta.index_in_block},{role},{pep}")

        if not lines:
            lines = [f"0,{idx},data,{pep}" for idx, pep in enumerate(ecc_packet.peptides)]

        chunk_out_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:
        chunk_out_path.write_text(f"chunk_export_failed: {exc}", encoding="utf-8")

    # If we embedded header, strip it before writing out and use dimensions for visualization.
    header_meta = {}
    if cfg.embed_image_header:
        header_meta, decoded_bytes = detach_image_header(decoded_bytes)

    decoded_rel_dir = add_suffix_to_top_level(rel_root, "_decoded")
    decoded_rel_name = Path(in_path.name)
    if converted_to_ppm:
        decoded_rel_name = decoded_rel_name.with_suffix(".ppm")
    decoded_rel_file = suffix_filename(decoded_rel_name, "_decoded")
    decoded_out_dir = out_decoded_root / decoded_rel_dir
    decoded_out_dir.mkdir(parents=True, exist_ok=True)
    decoded_out_path = decoded_out_dir / decoded_rel_file.name
    print("Decoded output dir:", decoded_out_dir)
    decoded_out_path.write_bytes(decoded_bytes)

    if cfg.visualize_as_pgm and in_path.suffix.lower() in IMAGE_EXTS:
        pgm_width = cfg.visualize_width
        if header_meta.get("width"):
            pgm_width = header_meta["width"]
        elif ppm_dims and ppm_dims[0] and pgm_width <= 0:
            pgm_width = ppm_dims[0]
        pgm_bytes = bytes_to_pgm(decoded_bytes, width=pgm_width)
        visual_rel_file = suffix_filename(Path(in_path.name).with_suffix(".pgm"), "_decoded")
        visual_out_dir = decoded_out_dir
        visual_out_path = visual_out_dir / visual_rel_file.name
        print("Decoded PGM output dir:", visual_out_dir)
        visual_out_path.write_bytes(pgm_bytes)


def process_file_fountain(
    in_path: Path,
    rel_root: Path,
    out_encoded_root: Path,
    out_decoded_root: Path,
    out_chunked_root: Path,
    cfg: PipelineConfig,
):
    data = in_path.read_bytes()
    cfg.score_label = in_path.name

    original_peptides, _, decoded_bytes = encode_decode_file_fountain(data, cfg)

    encoded_rel_dir = add_suffix_to_top_level(rel_root, "_encoded")
    encoded_rel_file = suffix_filename(Path(in_path.name), "_encoded")
    encoded_out_dir = out_encoded_root / encoded_rel_dir
    encoded_out_dir.mkdir(parents=True, exist_ok=True)
    encoded_out_path = encoded_out_dir / encoded_rel_file.name
    encoded_out_path.write_text(
        "\n".join(original_peptides),
        encoding="utf-8",
    )

    chunk_rel_dir = add_suffix_to_top_level(rel_root, "_chunked")
    chunk_rel_file = suffix_filename(Path(in_path.name), "_chunked")
    chunk_out_dir = out_chunked_root / chunk_rel_dir
    chunk_out_dir.mkdir(parents=True, exist_ok=True)
    chunk_out_path = chunk_out_dir / chunk_rel_file.name
    chunk_out_path.write_text("\n".join(original_peptides), encoding="utf-8")

    decoded_rel_dir = add_suffix_to_top_level(rel_root, "_decoded")
    decoded_rel_file = suffix_filename(Path(in_path.name), "_decoded")
    decoded_out_dir = out_decoded_root / decoded_rel_dir
    decoded_out_dir.mkdir(parents=True, exist_ok=True)
    decoded_out_path = decoded_out_dir / decoded_rel_file.name
    decoded_out_path.write_bytes(decoded_bytes)


def process_file_yin_yang(
    in_path: Path,
    rel_root: Path,
    out_encoded_root: Path,
    out_decoded_root: Path,
    out_chunked_root: Path,
    cfg: PipelineConfig,
):
    data = in_path.read_bytes()
    cfg.score_label = in_path.name

    original_peptides, _, decoded_bytes = encode_decode_file_yin_yang(data, cfg)

    encoded_rel_dir = add_suffix_to_top_level(rel_root, "_encoded")
    encoded_rel_file = suffix_filename(Path(in_path.name), "_encoded")
    encoded_out_dir = out_encoded_root / encoded_rel_dir
    encoded_out_dir.mkdir(parents=True, exist_ok=True)
    encoded_out_path = encoded_out_dir / encoded_rel_file.name
    encoded_out_path.write_text("\n".join(original_peptides), encoding="utf-8")

    chunk_rel_dir = add_suffix_to_top_level(rel_root, "_chunked")
    chunk_rel_file = suffix_filename(Path(in_path.name), "_chunked")
    chunk_out_dir = out_chunked_root / chunk_rel_dir
    chunk_out_dir.mkdir(parents=True, exist_ok=True)
    chunk_out_path = chunk_out_dir / chunk_rel_file.name
    try:
        from src.encoding_schemes.yin_yang import yin_yang_encode
        from src.encoding_schemes.peptide_mapping import PeptideMappingResult
        from src.error_correction.registry import ecc_encode_peptides

        reenc = yin_yang_encode(data, cfg)
        mapping = PeptideMappingResult(
            peptides=reenc.peptides,
            pad_bits=reenc.pad_bits,
            peptide_length=cfg.peptide_length,
            index_aa_length=cfg.index_aa_length,
        )
        ecc_packet = ecc_encode_peptides(mapping, profile=cfg.ecc_profile)

        lines = []
        for pep, meta in zip(ecc_packet.peptides, ecc_packet.metadata):
            role = "parity" if meta.is_parity else "data"
            lines.append(f"{meta.block_id},{meta.index_in_block},{role},{pep}")

        if not lines:
            lines = [f"0,{idx},data,{pep}" for idx, pep in enumerate(ecc_packet.peptides)]

        chunk_out_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:
        chunk_out_path.write_text(f"chunk_export_failed: {exc}", encoding="utf-8")

    decoded_rel_dir = add_suffix_to_top_level(rel_root, "_decoded")
    decoded_rel_file = suffix_filename(Path(in_path.name), "_decoded")
    decoded_out_dir = out_decoded_root / decoded_rel_dir
    decoded_out_dir.mkdir(parents=True, exist_ok=True)
    decoded_out_path = decoded_out_dir / decoded_rel_file.name
    decoded_out_path.write_bytes(decoded_bytes)
