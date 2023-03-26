from functools import wraps
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

import catalogue
import pydantic

from confit.config import Config


class SignatureError(TypeError):
    def __init__(self, func: Callable):
        message = f"{func} must not have positional only args or duplicated kwargs"
        super().__init__(message)


def _resolve_and_validate_call(
    args: Tuple[Any],
    kwargs: Dict[str, Any],
    pydantic_func: pydantic.decorator.ValidatedFunction,
    save_params: Optional[Dict],
    skip_save_params: Sequence[str],
    use_self: bool,
):
    # args = Config.resolve(args)
    # kwargs = Config.resolve(kwargs)
    values = pydantic_func.build_values(args, kwargs)
    returned = pydantic_func.call(*args, **kwargs)
    if save_params is not None:
        params = dict(values)
        params_kwargs = params.pop(pydantic_func.v_kwargs_name, {})
        resolved = params.pop("self") if use_self else returned

        params_to_save = {**save_params, **params, **params_kwargs}
        for name in skip_save_params:
            params_to_save.pop(name, None)

        Config._store_resolved(
            resolved,
            Config(params_to_save),
        )
    return returned


def _check_signature_for_save_params(func: Callable):
    """
    Checks that a function does not expect positional only arguments
    since these are not serializable using a nested dict data structure
    """
    import inspect

    spec = inspect.signature(func)
    if any(
        param.kind == inspect.Parameter.VAR_POSITIONAL
        for param in spec.parameters.values()
    ):
        raise SignatureError(func)


def validate_arguments(
    func: Optional[Callable] = None,
    *,
    config: Dict = None,
    save_params: Optional[Dict] = None,
    skip_save_params: Sequence[str] = (),
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
    skip_save_params: Sequence[str]
        List of parameters to skip when saving the function parameters

    Returns
    -------
    Any
    """
    if config is None:
        config = {}
    config = {**config, "arbitrary_types_allowed": True}

    def validate(_func: Callable) -> Callable:
        if isinstance(_func, type):
            if hasattr(_func.__init__, "raw_function"):
                vd = pydantic.decorator.ValidatedFunction(
                    _func.__init__.raw_function, config
                )
            else:
                vd = pydantic.decorator.ValidatedFunction(_func.__init__, config)
            if save_params is not None:
                _check_signature_for_save_params(vd.raw_function)
            vd.model.__name__ = _func.__name__
            vd.model.__fields__["self"].required = False

            # Should we store the generator instead ?
            existing_validators = (
                list(_func.__get_validators__())
                if hasattr(_func, "__get_validators__")
                else []
            )

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

                    for validator in existing_validators:
                        value = validator(value)

                    if isinstance(value, _func):
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
                        params_to_save = {**save_params, **params}
                        for name in skip_save_params:
                            params_to_save.pop(name, None)
                        Config._store_resolved(resolved, params_to_save)

                    return resolved

                yield _validate

            # This function is called when we do Model(variable=..., other=...)
            @wraps(vd.raw_function)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                return _resolve_and_validate_call(
                    args, kwargs, vd, save_params, skip_save_params, True
                )

            _func.vd = vd  # type: ignore
            _func.__get_validators__ = __get_validators__  # type: ignore
            _func.model = vd.model  # type: ignore
            _func.__init__ = wrapper_function
            _func.__init__.raw_function = vd.raw_function  # type: ignore
            return _func

        else:
            vd = pydantic.decorator.ValidatedFunction(_func, config)
            if save_params is not None:
                _check_signature_for_save_params(vd.raw_function)

            @wraps(_func)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                return _resolve_and_validate_call(
                    args,
                    kwargs,
                    vd,
                    save_params,
                    skip_save_params,
                    False,
                )

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
        self,
        name: str,
        *,
        func: Optional[catalogue.InFunc] = None,
        save_params=None,
        **kwargs: Any,
    ) -> Callable[[catalogue.InFunc], catalogue.InFunc]:
        """
        This is a convenience wrapper around `catalogue.Registry.register`, that
        additionally validates the input arguments of the registered function.

        Register a function as a catalogue entry-point, and validate its
        input arguments.

        Parameters
        ----------
        name: str
            The name of the function
        func: Optional[catalogue.InFunc]
            The function to register
        save_params: Optional[Dict]
            Additional parameters to save when the function is called. If falsy,
            the function parameters are not saved.

        Returns
        -------
        Callable[[catalogue.InFunc], catalogue.InFunc]
        """
        registerer = super().register(name)

        save_params = save_params or {f"@{self.namespace[-1]}": name}

        def wrap_and_register(fn: catalogue.InFunc) -> catalogue.InFunc:
            fn = validate_arguments(
                fn,
                config={"arbitrary_types_allowed": True},
                save_params=save_params,
                **kwargs,
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
    [`Config.resolve()`][confit.config.Config.resolve] when no registry is provided.

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
