from typing import Iterable, List, TypeVar

T = TypeVar("T")


def dedup(seq: Iterable["T"]) -> List["T"]:
    return list(dict.fromkeys(seq).keys())
