import os
from functools import lru_cache

from confit.utils.xjson import loads


@lru_cache(maxsize=1)
def parse_debug(value):
    try:
        return bool(loads(value))
    except Exception:
        return True


def is_debug():
    return parse_debug(os.environ.get("CONFIT_DEBUG", "0"))
