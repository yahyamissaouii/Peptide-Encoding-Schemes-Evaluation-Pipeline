from typing import List, Sequence
import random


def shuffle_amino_acids(
    peptides: Sequence[str],
    shuffle_prob: float,
    rng: random.Random,
    passes: int = 1,
) -> List[str]:
    """

    """
    shuffled_peptides = []

    for p in peptides:
        chars = list(p)
        n = len(chars)

        if n <= 1 or shuffle_prob <= 0.0 or passes <= 0:
            shuffled_peptides.append(p)
            continue

        for _ in range(passes):
            for i in range(n - 1):
                if rng.random() < shuffle_prob:
                    # swap neighbors i and i+1
                    chars[i], chars[i + 1] = chars[i + 1], chars[i]
        shuffled_peptides.append("".join(chars))

    return shuffled_peptides
