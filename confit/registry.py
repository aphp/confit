import inspect
from functools import wraps
from typing import Any, Callable, Dict, Optional, Sequence, TypeVar

import catalogue
import pydantic

from confit.utils.settings import is_debug

try:
    from pydantic.decorator import ValidatedFunction
except ImportError:
    from pydantic.deprecated.decorator import ValidatedFunction
from pydantic import ValidationError

from confit.config import Config
from confit.errors import (
    ConfitValidationError,
    ErrorWrapper,
    LegacyValidationError,
    PydanticErrorMixin,
    SignatureError,
    patch_errors,
    remove_lib_from_traceback,
    to_legacy_error,
)

PYDANTIC_V1 = pydantic.VERSION.split(".")[0] == "1"


def _resolve_and_validate_call(
    args: Sequence[Any],
    kwargs: Dict[str, Any],
    pydantic_func: ValidatedFunction,
    use_self: bool,
    callee: Callable,
    invoker: Optional[Callable[[Callable, Dict[str, Any]], Any]],
) -> Any:
    returned = None
    resolved = None

    # Call the pydantic model with the values
    # If an invoker was provided, use it to invoke the function
    # to allow the user to update the values before calling the function
    # and/or do something with the result
    def invoked(kw):
        nonlocal returned, resolved
        # "self" must be passed as a positional argument
        if use_self:
            kw = {**kw, self_name: resolved}
        model_instance = pydantic_func.model(**kw)
        returned = pydantic_func.execute(model_instance)
        if not use_self:
            resolved = returned
        return resolved

    values = None

    try:
        try:
            values = pydantic_func.build_values(args, kwargs)

            if use_self:
                self_name = pydantic_func.arg_mapping[0]
                resolved = values.pop(self_name)

            if invoker is not None:
                invoker(invoked, values)
            else:
                invoked(values)
        except TypeError as type_error:
            loc_suffix = ()
            if str(type_error).startswith("multiple values for argument"):
                loc_suffix = ("v__duplicate_kwargs",)
            elif str(type_error).startswith("unexpected keyword argument"):
                loc_suffix = ("kwargs",)
            raise ConfitValidationError(
                errors=[ErrorWrapper(type_error, loc_suffix)],
                model=pydantic_func.model,
                name=callee.__module__ + "." + callee.__qualname__,
            )
    except (ValidationError, LegacyValidationError) as e:
        e = to_legacy_error(e, pydantic_func.model)
        flat_errors = e.raw_errors
        name = None
        if e.model is pydantic_func.model:
            name = callee.__module__ + "." + callee.__qualname__
            flat_errors = patch_errors(
                errors=flat_errors,
                path=(),
                values=values,
                model=pydantic_func.model,
                special_names=(
                    pydantic_func.v_args_name,
                    pydantic_func.v_kwargs_name,
                    "v__duplicate_kwargs",
                    "v__positional_only",
                    "v__args",
                    "v__kwargs",
                ),
            )
        non_valid_errors = [
            e
            for e in flat_errors
            if not isinstance(e.exc, (PydanticErrorMixin, TypeError))
        ]
        if name is None and hasattr(e.model, "type_"):
            name = e.model.type_.__module__ + "." + e.model.type_.__qualname__
        e = ConfitValidationError(
            flat_errors,
            model=e.model,
            name=name,
        )
        if non_valid_errors:
            raise e from non_valid_errors[0].exc
        if not is_debug():
            e.__cause__ = None
            e.__suppress_context__ = True
        raise e

    return returned


def _check_signature_for_save_params(func: Callable):
    """
    Checks that a function does not expect positional only arguments
    since these are not serializable using a nested dict data structure
    """
    spec = inspect.signature(func)
    if any(
        param.kind
        not in (param.POSITIONAL_OR_KEYWORD, param.VAR_KEYWORD, param.KEYWORD_ONLY)
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
                vd = ValidatedFunction(_func.__init__.raw_function, config)
            else:
                vd = ValidatedFunction(_func.__init__, config)
            vd.model.__name__ = _func.__name__
            if hasattr(vd.model, "model_fields"):
                vd.model.model_fields["self"].default = None
            else:
                vd.model.__fields__["self"].default = None

            # This function is called by Pydantic when asked to cast
            # a value (most likely a dict) as a Model (most often during
            # a function call)

            old_get_validators = (
                _func.__get_validators__
                if hasattr(_func, "__get_validators__")
                else None
            )
            old_get_pydantic_core_schema = (
                _func.__get_pydantic_core_schema__
                if hasattr(_func, "__get_pydantic_core_schema__")
                else None
            )

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

                    if old_get_validators is not None:
                        for validator in old_get_validators():
                            value = validator(value)

                    if isinstance(value, _func):
                        return value

                    return _func(**value)

                yield _validate

            def __get_pydantic_core_schema__(*args, **kwargs):
                from pydantic_core import core_schema

                def pre_validate(value):
                    if isinstance(value, dict):
                        value = Config(value).resolve(registry=registry)
                    return value

                def post_validate(value):
                    if isinstance(value, _func):
                        return value

                    return _func(**value)

                return core_schema.chain_schema(
                    [
                        core_schema.no_info_plain_validator_function(pre_validate),
                        *(
                            (old_get_pydantic_core_schema(*args, **kwargs),)
                            if old_get_pydantic_core_schema
                            else (
                                core_schema.no_info_plain_validator_function(fn)
                                for fn in old_get_validators()
                            )
                            if old_get_validators is not None
                            else ()
                        ),
                        core_schema.no_info_plain_validator_function(post_validate),
                    ]
                )

            # This function is called when we do Model(variable=..., other=...)
            @wraps(vd.raw_function)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                try:
                    return _resolve_and_validate_call(
                        args=args,
                        kwargs=kwargs,
                        pydantic_func=vd,
                        use_self=True,
                        invoker=invoker,
                        callee=_func,
                    )
                except Exception as e:
                    if not is_debug() and isinstance(
                        e.__context__, (ValidationError, LegacyValidationError)
                    ):
                        e.__cause__ = None
                        e.__suppress_context__ = True
                    raise e.with_traceback(remove_lib_from_traceback(e.__traceback__))

            _func.vd = vd  # type: ignore
            _func.__get_validators__ = __get_validators__  # type: ignore
            _func.__get_pydantic_core_schema__ = (
                __get_pydantic_core_schema__  # type: ignore
            )
            _func.model = vd.model  # type: ignore
            _func.model.type_ = _func  # type: ignore
            _func.__init__ = wrapper_function
            _func.__init__.raw_function = vd.raw_function  # type: ignore
            return _func

        else:
            vd = ValidatedFunction(_func, config)

            @wraps(_func)
            def wrapper_function(*args: Any, **kwargs: Any) -> Any:
                try:
                    return _resolve_and_validate_call(
                        args=args,
                        kwargs=kwargs,
                        pydantic_func=vd,
                        use_self=False,
                        invoker=invoker,
                        callee=_func,
                    )
                except Exception as e:
                    if not is_debug() and isinstance(
                        e.__cause__, (ValidationError, LegacyValidationError)
                    ):
                        e.__cause__ = None
                        e.__suppress_context__ = True
                    raise e.with_traceback(remove_lib_from_traceback(e.__traceback__))

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

    def get(self, name: str) -> catalogue.InFunc:
        """
        Get the registered function for a given name.

        Modified from catalogue.Registry.get to avoid importing
        all entry points when lookup fails, but rather list the
        available entry points.

        Parameters
        ----------
        name: str
            The name of the function

        Returns
        -------
        catalogue.InFunc
        """
        if self.entry_points:
            from_entry_point = self.get_entry_point(name)
            if from_entry_point:
                return from_entry_point
        namespace = list(self.namespace) + [name]
        if not catalogue.check_exists(*namespace):
            raise catalogue.RegistryError(
                f"Can't find '{name}' in registry {' -> '.join(self.namespace)}. "
                f"Available names: {', '.join(sorted(self.get_available())) or 'none'}"
            )
        return catalogue._get(namespace)

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
