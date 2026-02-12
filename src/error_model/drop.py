from typing import List, Sequence
import random




def drop_peptides(
        peptides: Sequence[str],
        loss_prob: float,
        rng: random.Random,
        drop_empty: bool = True,
) -> List[str]:
    """
    Drop whole peptides (erasures) with probability `loss_prob`.

    If drop_empty=False, dropped peptides are kept as empty strings so the caller
    can preserve positional alignment.
    """
    if loss_prob <= 0.0:
        return list(peptides)

    out: List[str] = []
    for p in peptides:
        if rng.random() < loss_prob:
            if not drop_empty:
                out.append("")
            continue
        out.append(p)
    return out


def drop_amino_acids(
        peptides: Sequence[str],
        loss_prob: float,
        rng: random.Random,
        drop_empty: bool = True,
) -> List[str]:
    """
    Drop amino acids independently at each position with probability `loss_prob`.
    """
    if loss_prob <= 0.0:
        return list(peptides)

    out: List[str] = []
    for p in peptides:
        kept_chars = [aa for aa in p if rng.random() >= loss_prob]
        new_p = "".join(kept_chars)

        if new_p or not drop_empty:
            out.append(new_p)

    return out
