from typing import Callable, Optional

import catalogue


class Registry(catalogue.Registry):
    def register(
        self, name: str, *, func: Optional[catalogue.InFunc] = None
    ) -> Callable[[catalogue.InFunc], catalogue.InFunc]:
        from .config import validate_arguments

        registerer = super().register(name)

        def wrap_and_register(fn: catalogue.InFunc) -> catalogue.InFunc:
            fn = validate_arguments(fn, config={"arbitrary_types_allowed": True})
            return registerer(fn)

        if func is not None:
            return wrap_and_register(func)
        else:
            return wrap_and_register


_default_registry = None


def get_default_registry():
    return _default_registry


def set_default_registry(registry):
    global _default_registry
    _default_registry = registry
    return registry
