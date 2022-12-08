import random


def set_seed(seed):
    """
    Set seed values for random generators.
    If used as a context, restore the random state
    used before entering the context.

    Parameters
    ----------
    seed: int
        Value used as a seed.
    cuda: bool
        Saves the cuda random states too
    """
    # if seed is True:
    #     seed = random.randint(1, 2**16)
    try:
        import torch

        cuda = torch.cuda.is_available()
    except ImportError:
        torch = None
        cuda = False
    try:
        import numpy
    except ImportError:
        numpy = None

    if seed is True:
        seed = random.randint(1, 2**16)
    if seed is not None:
        random.seed(seed)
        if torch is not None:
            torch.manual_seed(seed)
        if cuda:  # pragma: no cover
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        if numpy is not None:
            numpy.random.seed(seed)
