from typing import List, Sequence
import random

from src.error_model.drop import drop_amino_acids, drop_peptides
from src.error_model.mutate import mutate_peptides
from src.error_model.insert import insert_aa_random_position
from src.error_model.shuffle import shuffle_amino_acids

DEFAULT_ALPHABET = "AVLSTFYE"


def apply_peptide_errors(
    peptides: Sequence[str],
    loss_prob: float = 0.10,
    mutation_prob: float = 0.02,
    insertion_prob: float = 0.02,
    shuffle_prob: float = 0.0,
    shuffle_passes: int = 1,
    alphabet: str = DEFAULT_ALPHABET,
    drop_empty: bool = True,
    loss_mode: str = "aa",
) -> List[str]:
    """
    Apply simulated biological / sequencing imperfections to peptide sequences.

    """
    rng = random.Random()

    if loss_prob > 0.0:
        if loss_mode == "peptide":
            after_loss = drop_peptides(
                peptides,
                loss_prob=loss_prob,
                rng=rng,
                drop_empty=drop_empty,
            )
        else:
            after_loss = drop_amino_acids(
                peptides,
                loss_prob=loss_prob,
                rng=rng,
                drop_empty=drop_empty,
            )
    else:
        after_loss = list(peptides)

    # everything lost return early
    if not after_loss:
        return []

    # 2) Mutate residues
    if mutation_prob > 0.0:
        after_mutation = mutate_peptides(
            after_loss,
            mutation_prob=mutation_prob,
            alphabet=alphabet,
            rng=rng,
        )
    else:
        after_mutation = after_loss

    # 3) Insertion error
    if insertion_prob > 0.0:
        after_insertion = insert_aa_random_position(
            after_mutation,
            insertion_prob=insertion_prob,
            alphabet=alphabet,
            rng=rng,
        )
    else:
        after_insertion = after_mutation

    # 4) Shuffle order
    if shuffle_prob > 0.0:
        after_shuffle = shuffle_amino_acids(
            after_insertion,
            shuffle_prob=shuffle_prob,
            rng=rng,
            passes=shuffle_passes,
        )
        return after_shuffle

    return after_insertion
