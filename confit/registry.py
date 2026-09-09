import importlib.metadata as importlib_metadata
import inspect
import warnings
from functools import WRAPPER_ASSIGNMENTS, wraps
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
    overload,
)

import catalogue
from pydantic import ValidationError, validate_call
from pydantic.fields import FieldInfo
from typing_extensions import ParamSpec

from confit.config import Config
from confit.draft import Draft, Draftable
from confit.errors import (
    ConfitValidationError,
    SignatureError,
    remove_lib_from_traceback,
)
from confit.typing import legacy_validator_schema
from confit.utils.settings import is_debug

# Reuse evaluated annotations, evaluating AsList[int] again can create a different class
WRAPPER_ATTRIBUTES = WRAPPER_ASSIGNMENTS + (
    "__annotations__",
    "__defaults__",
    "__kwdefaults__",
)


def make_wrapper(raw_function, callee, config, invoker):
    """
    Prepare validation once, then resolve and execute each registered call
    """
    is_class = isinstance(callee, type)
    target = inspect.unwrap(raw_function) if is_class else raw_function
    signature = inspect.signature(target)
    parameters = signature.parameters
    self_name = next(iter(parameters)) if is_class else None
    extras_name = next(
        (name for name, p in parameters.items() if p.kind == p.VAR_KEYWORD), None
    )
    callee_name = (
        f"{callee.__module__}.{callee.__qualname__}"
        if callee.__module__
        else callee.__qualname__
    )
    # Keep Field defaults, ordinary defaults stay omitted through stacked decorators
    omitted_defaults = {
        name
        for name, p in parameters.items()
        if p.default is not inspect.Parameter.empty
        and not isinstance(p.default, FieldInfo)
    }

    @wraps(target, assigned=WRAPPER_ATTRIBUTES)
    def collect(*args, **kwargs):
        return args, kwargs

    validator = validate_call(collect, config=config)

    @wraps(raw_function, assigned=WRAPPER_ATTRIBUTES)
    def wrapper(*args, **kwargs):
        try:
            extras = {
                k: v
                for k, v in kwargs.items()
                if k not in parameters and extras_name is None
            }
            try:
                bound = signature.bind_partial(
                    *args, **{k: v for k, v in kwargs.items() if k not in extras}
                )
            except TypeError as error:
                error = TypeError(
                    str(error).replace(
                        "multiple values for argument ",
                        "multiple values for argument: ",
                    )
                )
                raise ConfitValidationError(
                    [
                        {
                            "loc": ("[signature]",),
                            "msg": str(error),
                            "type": "arguments_error",
                        }
                    ],
                    source=callee,
                    name=callee_name,
                ) from None
            values = dict(bound.arguments)
            if extras_name in values:
                values.update(values.pop(extras_name))
            values.update(extras)
            resolved = values.pop(self_name) if self_name is not None else None
            returned = None

            def invoked(kw):
                nonlocal returned, resolved
                if self_name is not None:
                    kw = {self_name: resolved, **kw}
                bound = signature.bind_partial()
                bound.arguments.update(
                    {
                        name: kw[name]
                        for name in parameters
                        if name in kw and name != extras_name
                    }
                )
                extras = {
                    k: v
                    for k, v in kw.items()
                    if k not in parameters or k == extras_name
                }
                if extras and extras_name is None:
                    raise ConfitValidationError(
                        [
                            {
                                "loc": (name,),
                                "msg": "unexpected keyword argument",
                                "type": "unexpected_keyword_argument",
                            }
                            for name in extras
                        ],
                        source=callee,
                        name=callee_name,
                    )
                try:
                    validated_args, validated_kwargs = validator(
                        *bound.args, **bound.kwargs, **extras
                    )
                except (ValidationError, ConfitValidationError) as error:
                    raise ConfitValidationError.from_exception(
                        error,
                        source=callee,
                        name=callee_name,
                        signature=signature,
                    ) from None
                # Let the function supply its ordinary defaults
                call = signature.bind_partial(*validated_args, **validated_kwargs)
                for name in omitted_defaults - bound.arguments.keys():
                    call.arguments.pop(name, None)
                returned = raw_function(*call.args, **call.kwargs)
                if self_name is None:
                    resolved = returned
                return resolved

            if invoker is None:
                invoked(values)
            else:
                invoker(invoked, values)
            return returned
        except Exception as error:
            context = error.__context__ if is_class else error.__cause__
            if not is_debug() and isinstance(
                context, (ValidationError, ConfitValidationError)
            ):
                error.__cause__ = None
                error.__suppress_context__ = True
            raise error.with_traceback(remove_lib_from_traceback(error.__traceback__))

    return wrapper


P = ParamSpec("P")
R = TypeVar("R", covariant=True)


@overload
def validate_arguments(
    func: Callable[P, R],
    *,
    config: Dict = None,
    invoker: Optional[Callable[[Callable, Dict[str, Any]], Any]] = None,
    registry: Any = None,
) -> Draftable[P, R]: ...


@overload
def validate_arguments(
    *,
    config: Dict = None,
    invoker: Optional[Callable[[Callable, Dict[str, Any]], Any]] = None,
    registry: Any = None,
) -> Callable[[Callable[P, R]], Draftable[P, R]]: ...


def validate_arguments(
    func: Optional[Callable[P, R]] = None,
    *,
    config: Dict = None,
    invoker: Optional[Callable[[Callable, Dict[str, Any]], Any]] = None,
    registry: Any = None,
) -> Callable[[Callable[P, R]], Draftable[P, R]]:
    """
    Validate function or constructor arguments and support deferred calls with draft

    Parameters
    ----------
    func: Optional[Callable[P, R]]
        The function or class to call
    config: Dict
        The validation configuration object
    invoker: Optional[Callable]
        An optional invoker to apply on the validated function
    registry: Any
        The registry to use to resolve the default parameters

    Returns
    -------
    Callable[[Callable[P, R]], Draftable[P, R]]:
    """
    config = {**(config or {}), "arbitrary_types_allowed": True}

    def validate(_func: Callable) -> Callable:
        is_class = isinstance(_func, type)
        raw_function = _func.__init__ if is_class else _func
        wrapper = make_wrapper(raw_function, _func, config, invoker)
        draft_type = Draft[_func] if is_class else Draft

        @wraps(raw_function, assigned=WRAPPER_ATTRIBUTES)
        def draft(**kwargs):
            return draft_type(_func, kwargs)

        if is_class:
            old_get_validators = getattr(_func, "__get_validators__", None)
            old_get_pydantic_core_schema = getattr(
                _func, "__get_pydantic_core_schema__", None
            )

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

                steps = [core_schema.no_info_plain_validator_function(pre_validate)]
                if old_get_pydantic_core_schema is not None:
                    steps.append(old_get_pydantic_core_schema(*args, **kwargs))
                elif old_get_validators is not None:
                    steps.extend(
                        legacy_validator_schema(fn) for fn in old_get_validators()
                    )
                steps.append(
                    core_schema.no_info_plain_validator_function(post_validate)
                )
                return core_schema.chain_schema(steps)

            _func.__get_pydantic_core_schema__ = __get_pydantic_core_schema__
            _func.__init__ = wrapper
        result = _func if is_class else wrapper
        result.draft = draft
        return result

    return validate(func) if func is not None else validate


class VisibleDeprecationWarning(UserWarning):
    """
    Visible deprecation warning.

    By default, python will not show deprecation warnings, so this class
    can be used when a very visible warning is helpful, for example because
    the usage is most likely a user bug.

    Copied from https://github.com/numpy/numpy/blob/965b41d418e6100c1afae0b6f818a7ef152bc25d/numpy/_globals.py#L44-L51
    """  # noqa: E501


VisibleDeprecationWarning.__module__ = "confit"


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
        func: Optional[Union[Callable[P, R], Type[R]]] = None,
        save_params: Optional[Dict[str, Any]] = None,
        skip_save_params: Sequence[str] = (),
        invoker: Optional[Callable] = None,
        deprecated: Sequence[str] = (),
    ) -> Callable[[Callable[P, R]], Union[Callable[P, R], Draftable[R, P]]]:
        """
        This is a convenience wrapper around `catalogue.Registry.register`, that
        additionally validates the input arguments of the registered function and
        saves the result of any call to a mapping to its arguments.

        Parameters
        ----------
        name:
            The name of the function
        func:
            The function to register
        save_params:
            Additional parameters to save with the call arguments, defaults to the
            registry name when omitted or empty
        skip_save_params:
            List of parameters to skip when saving the function parameters
        invoker:
            An optional invoker to apply to the function before registering it.
            It is better to use this than to apply the invoker to the function
            to preserve the signature of the function or the class and enable
            validating its parameters.
        deprecated:
            The deprecated registry names for the function
        """
        registerer = super().register

        save_params = save_params or {f"@{self.namespace[-1]}": name}

        def invoke(func, params):
            resolved = invoker(func, params) if invoker is not None else func(params)
            params_to_save = {**save_params, **params}
            for name in skip_save_params:
                params_to_save.pop(name, None)
            Config._store_resolved(resolved, params_to_save)
            return resolved

        def wrap_and_register(fn: Callable[P, R]) -> Draftable[P, R]:
            signature = inspect.signature(fn.__init__ if isinstance(fn, type) else fn)
            if any(
                p.kind in (p.POSITIONAL_ONLY, p.VAR_POSITIONAL)
                for p in signature.parameters.values()
            ):
                raise SignatureError(fn)

            validated_fn = validate_arguments(
                fn,
                registry=self.registry,
                invoker=invoke,
            )

            registerer(name)(validated_fn)

            for deprecated_name in deprecated:

                def make_deprecated_fn(old):
                    @wraps(fn, assigned=WRAPPER_ATTRIBUTES)
                    def deprecated_fn(*args, **kwargs):
                        warnings.warn(
                            f'"{old}" is deprecated, please use "{name}" instead."',
                            VisibleDeprecationWarning,
                        )
                        return validated_fn(*args, **kwargs)

                    return deprecated_fn

                registerer(deprecated_name)(make_deprecated_fn(deprecated_name))

            return validated_fn

        if func is not None:
            return wrap_and_register(func)
        else:
            return wrap_and_register

    def get_entry_points(self):
        """Get registered entry points from other packages for this namespace.

        RETURNS (Dict[str, Any]): Entry points, keyed by name.
        """
        return importlib_metadata.entry_points(group=self.entry_point_namespace)

    def get(self, name: str):
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
        Func
        """
        path = list(self.namespace) + [name]
        try:
            return catalogue._get(path)
        except catalogue.RegistryError:
            if self.entry_points:
                from_entry_point = self.get_entry_point(name)
                if catalogue.check_exists(*path):
                    return catalogue._get(path)
                elif from_entry_point:
                    return from_entry_point
            if not catalogue.check_exists(*path):
                raise catalogue.RegistryError(
                    f"Can't find '{name}' in registry {' -> '.join(self.namespace)}. "
                    f"Available names: "
                    f"{', '.join(sorted(self.get_available())) or 'none'}"
                )
            return catalogue._get(path)

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


def __getattr__(name):
    # Older EDS-NLP converters import the Pydantic validator through Confit
    if name == "ValidatedFunction":
        warnings.warn(
            "ValidatedFunction is deprecated, use pydantic.validate_call",
            DeprecationWarning,
            stacklevel=2,
        )
        from pydantic.deprecated.decorator import ValidatedFunction

        return ValidatedFunction
    raise AttributeError(name)
