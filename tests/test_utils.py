import random

from confit.utils.random import set_seed


def test_set_seed():
    with set_seed(42):
        number = random.randint(0, 100)

    set_seed(43)

    with set_seed(42):
        assert random.randint(0, 100) == number
