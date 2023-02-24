from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import catalogue
import pydantic
from pydantic.decorator import (
    ALT_V_ARGS,
    ALT_V_KWARGS,
    V_DUPLICATE_KWARGS,
    V_POSITIONAL_ONLY_NAME,
)

from confit.config import Config


def _resolve_and_validate_call(
    args: Tuple[Any],
    kwargs: Dict[str, Any],
    pydantic_func: pydantic.decorator.ValidatedFunction,
    save_params: Optional[Dict],
    use_self: bool,
):
    # args = Config.resolve(args)
    # kwargs = Config.resolve(kwargs)
    values = pydantic_func.build_values(args, kwargs)
    returned = pydantic_func.call(*args, **kwargs)
    if save_params is not None:
        if set(values.keys()) & {
            ALT_V_ARGS,
            ALT_V_KWARGS,
            V_POSITIONAL_ONLY_NAME,
            V_DUPLICATE_KWARGS,
            "args",
            "kwargs",
        }:
            raise Exception(
                f"{pydantic_func} must not have positional only args, "
                f"kwargs or duplicated kwargs : call params are "
                f"{values}"
            )
        params = dict(values)
        if use_self:
            resolved = params.pop("self")
        else:
            resolved = returned
        Config._store_resolved(resolved, {**save_params, **params})
    return returned


def validate_arguments(
    func: Optional[Callable] = None,
    *,
    config: Dict = None,
    save_params: Optional[Dict] = None,
) -> Any:
    """
    Decorator to validate the arguments passed to a function.

    Parameters
    ----------
    func: Callable
        The function or class to call
    config: Dict
        The validation configuration object
    save_params: bool
        Should we save the function parameters

    Returns
    -------
    Any
    """
    if config is None:
        config = {}
    config = {**config, "arbitrary_types_allowed": True}

    def validate(_func: Callable) -> Callable:

        if isinstance(_func, type):
            if hasattr(_func, "raw_function"):
                vd = pydantic.decorator.ValidatedFunction(_func.raw_function, config)
            else:
                vd = pydantic.decorator.ValidatedFunction(_func.__init__, config)
            vd.model.__name__ = _func.__name__
            vd.model.__fields__["self"].required = False

            # This function is called by Pydantic when asked to cast
            # a value (most likely a dict) as a Model (most often during
            # a function call)
            def __get_validators__():
                """
                This function is called by Pydantic when asked to cast
                a value (most likely a dict) as a Model (most often during
                a function call)

                Yields
                -------
                Callable
                    The validator function
                """

                def _validate(value):
                    params = value

                    if isinstance(value, dict):
                        value = Config(value).resolve()

                    if not isinstance(value, dict):
                        return value

                    m = vd.init_model_instance(**value)
                    d = {
                        k: v
                        for k, v in m._iter()
                        if k in m.__fields_set__ or m.__fields__[k].default_factory
                    }
                    var_kwargs = d.pop(vd.v_kwargs_name, {})
                    resolved = _func(**d, **var_kwargs)

                    if save_params is not None:
                        Config._store_resolved(resolved, {**save_params, **params})

                    return resolved

                yield _validate

            # This function is called when we do Model(variable=..., other=...)
            @wraps(vd.raw_function)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                return _resolve_and_validate_call(args, kwargs, vd, save_params, True)

            _func.vd = vd  # type: ignore
            _func.__get_validators__ = __get_validators__  # type: ignore
            _func.raw_function = vd.raw_function  # type: ignore
            _func.model = vd.model  # type: ignore
            _func.__init__ = wrapper_function
            return _func

        else:
            vd = pydantic.decorator.ValidatedFunction(_func, config)

            @wraps(_func)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                return _resolve_and_validate_call(args, kwargs, vd, save_params, False)

            wrapper_function.vd = vd  # type: ignore
            wrapper_function.validate = vd.init_model_instance  # type: ignore
            wrapper_function.raw_function = vd.raw_function  # type: ignore
            wrapper_function.model = vd.model  # type: ignore
            return wrapper_function

    if func:
        return validate(func)
    else:
        return validate


class Registry(catalogue.Registry):
    """
    A registry that validates the input arguments of the registered functions.
    """

    def register(
        self, name: str, *, func: Optional[catalogue.InFunc] = None
    ) -> Callable[[catalogue.InFunc], catalogue.InFunc]:
        """
        This is a convenience wrapper around `catalogue.Registry.register`, that
        additionally validates the input arguments of the registered function.

        Register a function as a catalogue entry-point, and validate its
        input arguments.

        Parameters
        ----------
        name: str
        func: Optional[catalogue.InFunc]

        Returns
        -------
        Callable[[catalogue.InFunc], catalogue.InFunc]
        """
        registerer = super().register(name)

        def wrap_and_register(fn: catalogue.InFunc) -> catalogue.InFunc:
            fn = validate_arguments(
                fn,
                config={"arbitrary_types_allowed": True},
                save_params={f"@{self.namespace[-1]}": name},
            )
            return registerer(fn)

        if func is not None:
            return wrap_and_register(func)
        else:
            return wrap_and_register


_default_registry = None


def get_default_registry() -> Registry:
    """
    Get the default registered registry.

    Returns
    -------
    Registry
    """
    return _default_registry


def set_default_registry(registry: Registry) -> Registry:
    """
    Set the default registered registry. This is used in
    [`Config.resolve()`][edspdf.config.Config.resolve] when no registry is provided.

    Parameters
    ----------
    registry: Registry

    Returns
    -------
    Registry
    """
    global _default_registry
    _default_registry = registry
    return registry
