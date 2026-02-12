import math
import random
import zlib
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from src.pipeline.config import PipelineConfig
from src.utils.bits_bytes_utils import bitstring_to_bytes, bytes_to_bitstring


@dataclass
class FountainEncoded:
    bits: str
    droplet_size_bytes: int
    droplet_count: int
    symbol_size: int
    pad_bytes: int
    k: int
    original_size: int
    seed_bytes: int
    degree_bytes: int
    crc_bytes: int


def _xor_into(target: bytearray, other: bytes) -> None:
    for i, b in enumerate(other):
        target[i] ^= b


def _ideal_soliton(k: int) -> List[float]:
    rho = [0.0] * (k + 1)
    if k <= 0:
        return rho
    rho[1] = 1.0 / k
    for i in range(2, k + 1):
        rho[i] = 1.0 / (i * (i - 1))
    return rho


def _robust_soliton(k: int, c: float, delta: float) -> List[float]:
    if k <= 1:
        return [0.0, 1.0]
    rho = _ideal_soliton(k)
    tau = [0.0] * (k + 1)
    R = c * math.log(k / delta) * math.sqrt(k)
    if R > 0:
        k_over_r = int(k / R) if R else 0
        if k_over_r < 1:
            k_over_r = 1
        if k_over_r > k:
            k_over_r = k
        for i in range(1, k_over_r):
            tau[i] = R / (i * k)
        if 1 <= k_over_r <= k:
            tau_val = R * math.log(R / delta) / k if (R / delta) > 0 else 0.0
            if tau_val < 0:
                tau_val = 0.0
            tau[k_over_r] = tau_val

    z = sum(rho[1:]) + sum(tau[1:])
    mu = [0.0] * (k + 1)
    for i in range(1, k + 1):
        mu[i] = (rho[i] + tau[i]) / z if z else 0.0
    return mu


def _build_degree_cdf(k: int, c: float, delta: float) -> List[float]:
    mu = _robust_soliton(k, c, delta)
    cdf = []
    acc = 0.0
    for i in range(1, k + 1):
        acc += mu[i]
        cdf.append(acc)
    if cdf:
        cdf[-1] = 1.0
    return cdf


def _sample_degree(rng: random.Random, cdf: Sequence[float]) -> int:
    if not cdf:
        return 1
    r = rng.random()
    for i, p in enumerate(cdf, start=1):
        if r <= p:
            return i
    return len(cdf)


def _split_symbols(data: bytes, symbol_size: int) -> Tuple[List[bytes], int]:
    if symbol_size <= 0:
        raise ValueError("symbol_size must be positive")
    original_size = len(data)
    k = math.ceil(original_size / symbol_size) if original_size else 1
    padded_size = k * symbol_size
    if original_size < padded_size:
        data = data + b"\x00" * (padded_size - original_size)
    symbols = [data[i:i + symbol_size] for i in range(0, padded_size, symbol_size)]
    return symbols, original_size


def _build_droplet(
    seed: int,
    degree: int,
    indices: Sequence[int],
    symbols: Sequence[bytes],
    symbol_size: int,
    pad_bytes: int,
    seed_bytes: int,
    degree_bytes: int,
    crc_bytes: int,
) -> bytes:
    payload = bytearray(symbol_size)
    for idx in indices:
        _xor_into(payload, symbols[idx])

    seed_part = seed.to_bytes(seed_bytes, "big")
    degree_part = degree.to_bytes(degree_bytes, "big")
    header = seed_part + degree_part
    pad = b"\x00" * pad_bytes
    body = header + payload + pad
    crc = zlib.crc32(body) & 0xFFFFFFFF
    crc_part = crc.to_bytes(crc_bytes, "big")
    return body + crc_part


def _indices_from_seed(
    seed: int,
    degree: int,
    k: int,
) -> List[int]:
    if degree <= 1:
        return [seed % k]
    rng = random.Random(seed)
    degree = min(degree, k)
    return rng.sample(range(k), degree)


def fountain_encode(data: bytes, cfg: PipelineConfig, overhead: Optional[float] = None) -> FountainEncoded:
    if len(data) > cfg.fountain_max_bytes:
        raise ValueError(f"Fountain encoder supports up to {cfg.fountain_max_bytes} bytes for now.")

    # IMPORTANT: Droplets must be short enough to survive per-residue noise; otherwise
    # almost every droplet fails CRC and the LT decoder sees no usable equations.
    #
    # We clamp symbol_size so one droplet spans the *minimum* whole number of peptides.
    payload_bits_per_peptide = (cfg.peptide_length - cfg.index_aa_length) * 3
    if payload_bits_per_peptide <= 0:
        raise ValueError("peptide_length must be greater than index_aa_length.")
    required_multiple = payload_bits_per_peptide // math.gcd(payload_bits_per_peptide, 8)  # bytes
    header_bytes = cfg.fountain_seed_bytes + cfg.fountain_degree_bytes
    droplet_size_bytes = required_multiple
    capacity_bytes = droplet_size_bytes - header_bytes - cfg.fountain_crc_bytes
    if capacity_bytes < 1:
        raise ValueError(
            "Fountain droplet too small for configured headers; "
            "reduce seed/degree/crc bytes or increase peptide payload capacity."
        )
    symbol_size = min(cfg.fountain_symbol_size, capacity_bytes)
    if cfg.fountain_symbol_size > capacity_bytes:
        print(
            f"[fountain] symbol_size={cfg.fountain_symbol_size}B too large for "
            f"peptide_length={cfg.peptide_length} index_aa_length={cfg.index_aa_length}; "
            f"clamping to {symbol_size}B"
        )
    pad_bytes = capacity_bytes - symbol_size

    symbols, original_size = _split_symbols(data, symbol_size)
    k = len(symbols)
    cdf = _build_degree_cdf(k, cfg.fountain_c, cfg.fountain_delta)
    if overhead is None:
        overhead = cfg.fountain_overhead
    # Ensure at least a handful of droplets for tiny k, and apply overhead on top
    # of that baseline so profiles still matter for small files.
    baseline = max(8, k)
    droplet_count = max(baseline, math.ceil(baseline * (1.0 + overhead)))

    rng = random.Random(cfg.fountain_seed)
    droplets: List[bytes] = []
    max_degree = (1 << (cfg.fountain_degree_bytes * 8)) - 1

    for idx in range(k):
        seed = idx
        degree = 1
        indices = _indices_from_seed(seed, degree, k)
        droplets.append(
            _build_droplet(
                seed,
                degree,
                indices,
                symbols,
                symbol_size,
                pad_bytes,
                cfg.fountain_seed_bytes,
                cfg.fountain_degree_bytes,
                cfg.fountain_crc_bytes,
            )
        )

    remaining = max(0, droplet_count - k)
    for _ in range(remaining):
        seed = rng.getrandbits(cfg.fountain_seed_bytes * 8)
        droplet_rng = random.Random(seed)
        degree = _sample_degree(droplet_rng, cdf)
        degree = max(1, min(degree, k, max_degree))
        indices = _indices_from_seed(seed, degree, k)
        droplets.append(
            _build_droplet(
                seed,
                degree,
                indices,
                symbols,
                symbol_size,
                pad_bytes,
                cfg.fountain_seed_bytes,
                cfg.fountain_degree_bytes,
                cfg.fountain_crc_bytes,
            )
        )

    droplet_size = droplet_size_bytes
    droplet_stream = b"".join(droplets)
    droplet_bits = bytes_to_bitstring(droplet_stream)

    return FountainEncoded(
        bits=droplet_bits,
        droplet_size_bytes=droplet_size,
        droplet_count=droplet_count,
        symbol_size=symbol_size,
        pad_bytes=pad_bytes,
        k=k,
        original_size=original_size,
        seed_bytes=cfg.fountain_seed_bytes,
        degree_bytes=cfg.fountain_degree_bytes,
        crc_bytes=cfg.fountain_crc_bytes,
    )


def _parse_droplet(
    packet: bytes,
    k: int,
    symbol_size: int,
    pad_bytes: int,
    seed_bytes: int,
    degree_bytes: int,
    crc_bytes: int,
) -> Optional[Tuple[List[int], bytes]]:
    header_len = seed_bytes + degree_bytes
    expected_len = header_len + symbol_size + pad_bytes + crc_bytes
    if len(packet) != expected_len:
        return None
    body = packet[:-crc_bytes]
    header = body[:header_len]
    payload = body[header_len:header_len + symbol_size]
    crc_part = packet[-crc_bytes:]
    expected_crc = int.from_bytes(crc_part, "big")
    actual_crc = zlib.crc32(body) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        return None
    seed = int.from_bytes(header[:seed_bytes], "big")
    degree = int.from_bytes(header[seed_bytes:], "big")
    if degree <= 0:
        return None
    degree = min(degree, k)
    indices = _indices_from_seed(seed, degree, k)
    return indices, payload


def fountain_decode(encoded: FountainEncoded) -> bytes:
    payload_bytes = bitstring_to_bytes(encoded.bits)
    total_bytes = encoded.droplet_size_bytes * encoded.droplet_count
    payload_bytes = payload_bytes[:total_bytes]
    droplets: List[Tuple[List[int], bytearray]] = []
    index_to_drops: List[set[int]] = [set() for _ in range(encoded.k)]

    for idx in range(encoded.droplet_count):
        start = idx * encoded.droplet_size_bytes
        end = start + encoded.droplet_size_bytes
        packet = payload_bytes[start:end]
        parsed = _parse_droplet(
            packet,
            k=encoded.k,
            symbol_size=encoded.symbol_size,
            pad_bytes=encoded.pad_bytes,
            seed_bytes=encoded.seed_bytes,
            degree_bytes=encoded.degree_bytes,
            crc_bytes=encoded.crc_bytes,
        )
        if parsed is None:
            continue
        indices, payload = parsed
        drop_idx = len(droplets)
        droplets.append((indices, bytearray(payload)))
        for sym_idx in indices:
            index_to_drops[sym_idx].add(drop_idx)

    recovered: List[Optional[bytes]] = [None] * encoded.k
    queue: List[int] = [i for i, (idxs, _) in enumerate(droplets) if len(idxs) == 1]

    while queue:
        d_idx = queue.pop()
        indices, payload = droplets[d_idx]
        if len(indices) != 1:
            continue
        sym_idx = indices[0]
        if recovered[sym_idx] is None:
            recovered[sym_idx] = bytes(payload)

        for other_idx in list(index_to_drops[sym_idx]):
            if other_idx == d_idx:
                continue
            other_indices, other_payload = droplets[other_idx]
            if sym_idx not in other_indices:
                continue
            _xor_into(other_payload, recovered[sym_idx])
            other_indices.remove(sym_idx)
            index_to_drops[sym_idx].discard(other_idx)
            if len(other_indices) == 1:
                queue.append(other_idx)

        index_to_drops[sym_idx].discard(d_idx)

    if any(sym is None for sym in recovered):
        return b""

    combined = b"".join(sym for sym in recovered if sym is not None)
    return combined[:encoded.original_size]
