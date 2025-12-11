import torch

from confit import Registry


class registry:
    misc = Registry(("mytest", "misc"), entry_points=True)


@registry.misc.register("get_len")
def get_len(*, string: str) -> torch.Tensor:
    """
    Get length of a string.

    Parameters
    ----------
    string : str
        Input string.

    Returns
    -------
    torch.Tensor
        Length of the string.
    """
    return torch.tensor([len(string)])


draft_value = get_len.draft(string="ok")
value = draft_value.instantiate()
