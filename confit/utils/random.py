import random
from collections import namedtuple
from typing import Optional

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
    torch_state = torch_cuda_state = numpy_state = None
    random_state = random.getstate()
    try:
        import torch

        torch_state = torch.random.get_rng_state()
        if cuda or (cuda is None and torch.cuda.is_available()):  # pragma: no cover
            torch_cuda_state = torch.cuda.get_rng_state_all()

    except ImportError:  # pragma: no cover
        pass
    try:
        import numpy

        numpy_state = numpy.random.get_state()
    except ImportError:  # pragma: no cover
        pass
    return RandomGeneratorState(
        random_state,
        torch_state,
        numpy_state,
        torch_cuda_state,
    )


def set_random_generator_state(state):
    """
    Set the `torch`, `numpy` and `random` random generator state.
    Parameters
    ----------
    state: RandomGeneratorState
    """
    random.setstate(state.random)
    if state.torch is not None:
        import torch

        torch.random.set_rng_state(state.torch)
        if (
            state.torch_cuda is not None
            and torch.cuda.is_available()
            and len(state.torch_cuda) == torch.cuda.device_count()
        ):  # pragma: no cover
            torch.cuda.set_rng_state_all(state.torch_cuda)
    if state.numpy is not None:
        import numpy

        numpy.random.set_state(state.numpy)


class set_seed:
    def __init__(self, seed, cuda: Optional[bool] = None):
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
        seed = random.randint(1, 2**16) if seed is True else seed
        self.state = get_random_generator_state(cuda)
        if seed is not None:
            random.seed(seed)
            try:
                import torch

                torch.manual_seed(seed)
                if cuda or (
                    cuda is None and torch.cuda.is_available()
                ):  # pragma: no cover
                    torch.cuda.manual_seed(seed)
                    torch.cuda.manual_seed_all(seed)
            except ImportError:  # pragma: no cover
                pass
            try:
                import numpy

                numpy.random.seed(seed)
            except ImportError:  # pragma: no cover
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_random_generator_state(self.state)
