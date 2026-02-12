from typing import List, Sequence
import random


def insert_aa_random_position(
    peptides: Sequence[str],
    insertion_prob: float,
    alphabet: str,
    rng: random.Random,
) -> List[str]:
    """

    """
    if insertion_prob <= 0.0 or not alphabet:
        return list(peptides)

    new_peptides: List[str] = []

    for p in peptides:
        chars = list(p)
        if not chars:
            new_peptides.append(p)
            continue

        out: List[str] = []

        for aa in chars:
            if rng.random() < insertion_prob:
                # choose a random extra amino acid
                ins_aa = rng.choice(alphabet)

                if rng.random() < 0.5:
                    # insert BEFORE
                    out.append(ins_aa)
                    out.append(aa)
                else:
                    # insert AFTER
                    out.append(aa)
                    out.append(ins_aa)
            else:
                # no insertion
                out.append(aa)

        new_peptides.append("".join(out))

    return new_peptides
