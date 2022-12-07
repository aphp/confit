import random
from collections import namedtuple

import numpy as np
import torch

RandomGeneratorState = namedtuple(
    "RandomGeneratorState", ["random", "torch", "numpy", "torch_cuda"]
)


def get_random_generator_state(cuda=None):
    """
    Get the `torch`, `numpy` and `random` random generator state.
    Parameters
    ----------
    cuda: bool
        Saves the cuda random states too

    Returns
    -------
    RandomGeneratorState
    """
    try:
        import torch

        if cuda is None:
            cuda = torch.cuda.is_available()
    except ImportError:
        cuda = False
        torch = None
    try:
        import numpy
    except ImportError:
        numpy = None
    return RandomGeneratorState(
        random.getstate(),
        torch.random.get_rng_state() if torch is not None else None,
        np.random.get_state() if numpy is not None else None,
        torch.cuda.get_rng_state_all() if cuda else None,
    )


def set_random_generator_state(state):
    """
    Set the `torch`, `numpy` and `random` random generator state.
    Parameters
    ----------
    state: RandomGeneratorState
    """

    cuda = False
    try:
        import torch

        cuda = torch.cuda.is_available()
    except ImportError:
        cuda = False
        torch = None
    try:
        import numpy
    except ImportError:
        numpy = None

    random.setstate(state.random)
    if torch is not None:
        torch.random.set_rng_state(state.torch)
    if numpy is not None:
        np.random.set_state(state.numpy)
    if (
        state.torch_cuda is not None
        and cuda
        and len(state.torch_cuda) == torch.cuda.device_count()
    ):  # pragma: no cover
        torch.cuda.set_rng_state_all(state.torch_cuda)


class set_seed:
    def __init__(self, seed, cuda=torch.cuda.is_available()):
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
        except ImportError:
            torch = None
        try:
            import numpy
        except ImportError:
            numpy = None

        if seed is True:
            seed = random.randint(1, 2**16)
        self.state = get_random_generator_state(cuda)
        if seed is not None:
            random.seed(seed)
            if torch is not None:
                torch.manual_seed(seed)
            if cuda:  # pragma: no cover
                torch.cuda.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)
            if numpy is not None:
                numpy.random.seed(seed)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_random_generator_state(self.state)
