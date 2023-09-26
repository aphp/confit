import collections
import re
from typing import Any, Dict, Tuple, TypeVar, Union

T = TypeVar("T")

KEY_PART = r"(?:'([^']*)'|\"([^\"]*)\"|([^.]*))(?:[.]|$)"


def join_path(path):
    """
    Join a path into a string and quotes subpaths that contain dots.

    Parameters
    ----------
    path: Tuple[Union[int, str]]

    Returns
    -------
    str
    """
    return ".".join(
        repr(x) if not isinstance(x, str) or split_path(x.strip()) != (x,) else x
        for x in path
    )


def split_path(path: str) -> Tuple[Union[int, str]]:
    """
    Split a path around "." into a tuple of strings and ints.
    If a sub-path is quoted, it will be returned as a full non-split string.

    Parameters
    ----------
    path: str

    Returns
    -------

    """
    offset = 0
    result = []
    for match in re.finditer(KEY_PART, str(path)):
        assert match.start() == offset, f"Malformed path: {path!r} in config"
        offset = match.end()
        part = next((g for g in match.groups() if g is not None))
        result.append(int(part) if part.isdigit() else part)
        if offset == len(path):
            break
    return tuple(result)


def flatten_sections(root: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a nested dict of dicts into a "flat" dict of dict.

    Parameters
    ----------
    root: Dict[str, Any]
        The root dict to flatten

    Returns
    -------
    Dict[str, Dict[str, Any]]
    """
    res = collections.defaultdict(lambda: {})

    def rec(d, path):
        res.setdefault(join_path(path), {})
        section = {}
        for k, v in d.items():
            if isinstance(v, dict):
                rec(v, (*path, k))
            else:
                section[k] = v
        res[join_path(path)].update(section)

    rec(root, ())
    root_level = res.pop("", None)
    if root_level is not None and len(root_level) > 0:
        raise Exception("Cannot dump root level config", root_level)
    return dict(res)
