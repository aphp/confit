import inspect
from functools import wraps
from typing import Any, Callable, Dict, Optional, Sequence, TypeVar, Union

import catalogue
import pydantic

from confit.config import Config


class SignatureError(TypeError):
    def __init__(self, func: Callable):
        message = f"{func} must not have positional only args or duplicated kwargs"
        super().__init__(message)


def _resolve_and_validate_call(
    args: Sequence[Any],
    kwargs: Dict[str, Any],
    pydantic_func: Union[pydantic.decorator.ValidatedFunction, Callable],
    use_self: bool,
    invoker: Optional[Callable[[Callable, Dict[str, Any]], Any]],
) -> Any:
    returned = None
    resolved = None

    # Convert the *args and **kwargs into a dict of values
    # mapping the parameter name to the value if given
    signature = inspect.signature(pydantic_func.raw_function)
    parameters = signature.parameters
    bound_arguments = signature.bind_partial(*args, **kwargs)
    values = {}
    for name, value in bound_arguments.arguments.items():
        param = parameters[name]
        assert param.kind in (param.POSITIONAL_OR_KEYWORD, param.VAR_KEYWORD)
        if param.kind == param.VAR_KEYWORD:
            values.update(value)
        else:
            values[name] = value

    if use_self:
        resolved = values.pop("self")

    # Call the pydantic model with the values
    # If an invoker was provided, use it to invoke the function
    # to allow the user to update the values before calling the function
    # and/or do something with the result
    def invoked(kw):
        nonlocal returned, resolved
        # "self" must be passed as a positional argument
        returned = pydantic_func.call(*(resolved,) if use_self else (), **kw)
        if not use_self:
            resolved = returned
        return resolved

    if invoker is not None:
        invoker(invoked, values)
    else:
        invoked(values)

    return returned


def _check_signature_for_save_params(func: Callable):
    """
    Checks that a function does not expect positional only arguments
    since these are not serializable using a nested dict data structure
    """
    spec = inspect.signature(func)
    if any(
        param.kind not in (param.POSITIONAL_OR_KEYWORD, param.VAR_KEYWORD)
        for param in spec.parameters.values()
    ):
        raise SignatureError(func)


def validate_arguments(
    func: Optional[Callable] = None,
    *,
    config: Dict = None,
    invoker: Optional[Callable[[Callable, Dict[str, Any]], Any]] = None,
    registry: Any = None,
) -> Any:
    """
    Decorator to validate the arguments passed to a function and store the result
    in a mapping from results to call parameters (allowing

    Parameters
    ----------
    func: Callable
        The function or class to call
    config: Dict
        The validation configuration object
    invoker: Optional[Callable]
        An optional invoker to apply on the validated function
    registry: Any
        The registry to use to resolve the default parameters

    Returns
    -------
    Any
    """
    if config is None:
        config = {}
    config = {**config, "arbitrary_types_allowed": True}

    def validate(_func: Callable) -> Callable:
        if isinstance(_func, type):
            _func: type
            if hasattr(_func.__init__, "raw_function"):
                vd = pydantic.decorator.ValidatedFunction(
                    _func.__init__.raw_function, config
                )
            else:
                vd = pydantic.decorator.ValidatedFunction(_func.__init__, config)
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
                    if isinstance(value, dict):
                        value = Config(value).resolve(registry=registry)

                    for validator in existing_validators:
                        value = validator(value)

                    if isinstance(value, _func):
                        return value

                    return _func(**value)

                yield _validate

            # This function is called when we do Model(variable=..., other=...)
            @wraps(vd.raw_function)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                return _resolve_and_validate_call(
                    args=args,
                    kwargs=kwargs,
                    pydantic_func=vd,
                    use_self=True,
                    invoker=invoker,
                )

            _func.vd = vd  # type: ignore
            _func.__get_validators__ = __get_validators__  # type: ignore
            _func.model = vd.model  # type: ignore
            _func.__init__ = wrapper_function
            _func.__init__.raw_function = vd.raw_function  # type: ignore
            return _func

        else:
            vd = pydantic.decorator.ValidatedFunction(_func, config)

            @wraps(_func)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                return _resolve_and_validate_call(
                    args=args,
                    kwargs=kwargs,
                    pydantic_func=vd,
                    use_self=False,
                    invoker=invoker,
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

    def __init__(self, namespace: Sequence[str], entry_points: bool = False) -> None:
        """
        Initialize the registry.

        Parameters
        ----------
        namespace: Sequence[str]
            The namespace of the registry
        entry_points: bool
            Should we use entry points to load the registered functions
        """
        super().__init__(namespace, entry_points=entry_points)
        self.registry = None

    def register(
        self,
        name: str,
        *,
        func: Optional[catalogue.InFunc] = None,
        save_params: Optional[Dict[str, Any]] = None,
        skip_save_params: Sequence[str] = (),
        invoker: Optional[Callable] = None,
    ) -> Callable[[catalogue.InFunc], catalogue.InFunc]:
        """
        This is a convenience wrapper around `catalogue.Registry.register`, that
        additionally validates the input arguments of the registered function and
        saves the result of any call to a mapping to its arguments.

        Parameters
        ----------
        name: str
            The name of the function
        func: Optional[catalogue.InFunc]
            The function to register
        save_params: Optional[Dict[str, Any]]
            Additional parameters to save when the function is called. If falsy,
            the function parameters are not saved
        skip_save_params: Sequence[str]
            List of parameters to skip when saving the function parameters
        invoker: Optional[Callable] = None,
            An optional invoker to apply to the function before registering it.
            It is better to use this than to apply the invoker to the function
            to preserve the signature of the function or the class and enable
            validating its parameters.

        Returns
        -------
        Callable[[catalogue.InFunc], catalogue.InFunc]
        """
        registerer = super().register(name)

        save_params = save_params or {f"@{self.namespace[-1]}": name}

        def invoke(func, params):
            resolved = invoker(func, params) if invoker is not None else func(params)
            if save_params is not None:
                params_to_save = {**save_params, **params}
                for name in skip_save_params:
                    params_to_save.pop(name, None)
                Config._store_resolved(resolved, params_to_save)
            return resolved

        def wrap_and_register(fn: catalogue.InFunc) -> catalogue.InFunc:

            if save_params is not None:
                _check_signature_for_save_params(
                    fn if not isinstance(fn, type) else fn.__init__
                )

            validated_fn = validate_arguments(
                fn,
                config={"arbitrary_types_allowed": True},
                registry=getattr(self, "registry", None),
                invoker=invoke,
            )
            registerer(validated_fn)
            return validated_fn

        if func is not None:
            return wrap_and_register(func)
        else:
            return wrap_and_register

    def get_available(self) -> Sequence[str]:
        """Get all functions for a given namespace.

        namespace (Tuple[str]): The namespace to get.
        RETURNS (Dict[str, Any]): The functions, keyed by name.
        """
        result = set()
        if self.entry_points:
            result.update({p.name for p in self._get_entry_points()})
        for keys in catalogue.REGISTRY.copy().keys():
            if len(self.namespace) == len(keys) - 1 and all(
                self.namespace[i] == keys[i] for i in range(len(self.namespace))
            ):
                result.add(keys[-1])
        return sorted(result)


_default_registry = None


class MetaRegistryCollection(type):
    """
    A metaclass for the registry collection that adds it as the
    registry collection of all registries defined in the body of the class.
    """

    def __setattr__(self, key, value):
        assert isinstance(value, Registry)
        value.registry = self
        super().__setattr__(key, value)

    def __init__(cls, name, bases, dct):
        """
        Initialize the registry collection by adding it-self as the registry collection
        of all registries.

        Parameters
        ----------
        name
        bases
        dct
        """
        super().__init__(name, bases, dct)
        for key, value in dct.items():
            if isinstance(value, Registry):
                value.registry = cls


class RegistryCollection(metaclass=MetaRegistryCollection):
    """
    A collection of registries.

    ```python
    class MyRegistries(RegistryCollection):
        my_registry = Registry(("package_name", "my_registry"), entry_points=True)
        my_other_registry = Registry(("package_name", "my_other_registry"))
    """


def get_default_registry() -> Any:
    """
    Get the default registered registry.

    Returns
    -------
    Registry
    """
    return _default_registry


CustomRegistry = TypeVar("CustomRegistry")


def set_default_registry(registry: CustomRegistry) -> CustomRegistry:
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
