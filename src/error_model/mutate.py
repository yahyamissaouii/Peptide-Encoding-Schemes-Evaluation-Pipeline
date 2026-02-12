from typing import List, Sequence
import random


def mutate_peptides(
    peptides: Sequence[str],
    mutation_prob: float,
    alphabet: str,
    rng: random.Random,
) -> List[str]:
    """
    Randomly mutate amino acids in peptides.

    """
    mutated = []
    for p in peptides:
        chars = list(p)
        for i, aa in enumerate(chars):
            if rng.random() < mutation_prob:
                # choose a different amino acid than the current one
                choices = [x for x in alphabet if x != aa]
                if choices:
                    chars[i] = rng.choice(choices)
        mutated.append("".join(chars))
    return mutated
