import functools
import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Type,
    TypeVar,
    Union,
)

import pydantic
from typing_extensions import ParamSpec, Protocol

from confit.errors import (
    ConfitValidationError,
    ErrorWrapper,
    to_legacy_error,
)
from confit.typing import cast

if pydantic.VERSION >= "2":
    from pydantic_core import core_schema


PYDANTIC_V1 = pydantic.VERSION.split(".")[0] == "1"

P = ParamSpec("P")
R = TypeVar("R", covariant=True)


class Draftable(Protocol[P, R]):
    draft: Callable[P, "Draft[R]"]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


class MetaDraft(type):
    """
    A metaclass for Draft that allows the user to create specify
    the type the Draft should become when instantiated.

    In addition to allowing static typing, this metaclass also
    provides a way to validate the Draft object when used in
    combination with pydantic validation.

    Examples
    --------

    ```python
    from confit import Draft


    @validate_arguments
    def make_hi(name, prefix) -> str:
        return prefix + " " + name


    @validate_arguments
    def print_hi(param: Draft[str]):
        val = param.instantiate(prefix="Hello")
        print(val)


    print_hi(make_hi.draft(name="John"))
    ```
    """

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls.type_ = Any

    @functools.lru_cache(maxsize=None)
    def __getitem__(self, item):
        # TODO: allow to specify which parameters will be filled
        # eg. Draft[int, ["name"]] declares the library only allow to fill the
        # "name" parameter
        new_type = MetaDraft(self.__name__, (self,), {})
        new_type.type_ = item
        return new_type

    def validate(cls, value, config=None):
        if not isinstance(value, Draft):
            raise ConfitValidationError(
                [
                    ErrorWrapper(
                        exc=TypeError(f"Expected {cls}, got {value.__class__}"),
                        loc=(),
                    ),
                ],
                model=cls,
                name=cls.__name__,
            )
        actual = value._func
        try:
            return_type = inspect.signature(actual).return_annotation
            if return_type is not inspect.Signature.empty:
                actual = return_type
                cast(Type[cls.type_], actual)
            elif isinstance(actual, type):
                cast(Type[cls.type_], actual)
            else:  # pragma: no cover
                cast(Union[Type[cls.type_], Callable[..., cls.type_]], actual)
        except pydantic.ValidationError as e:
            e = to_legacy_error(e, None)
            e = ConfitValidationError(
                [
                    ErrorWrapper(
                        exc=TypeError(f"Expected {cls}, got {Draft[actual]}"),
                        loc=e.raw_errors[0]._loc,
                    ),
                ],
                model=cls,
                name=cls.__name__,
            )
            raise e
        return value

    def __get_validators__(cls):
        yield cls.validate

    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    def __repr__(self):
        return f"Draft[{self.type_.__qualname__}]"


T = TypeVar("T")


class Draft(Generic[T], metaclass=MetaDraft):
    """
    A Draft is a placeholder for a value that has not been instantiated yet, likely
    because it is missing an argument that will be provided later by the library.
    """

    def __init__(
        self,
        func: Callable[..., T],
        kwargs: Dict[str, Any],
    ):
        self._func = func
        self._kwargs = kwargs

    def instantiate(self: "Union[T, Draft[T]]", **kwargs) -> T:
        """
        Finalize the Draft object into an instance of the expected type
        using the provided arguments. The new arguments are merged with the
        existing ones, with the old ones taking precedence. The rationale
        for this is that the user makes the Draft, and the library
        completes any missing arguments.

        Parameters
        ----------
        kwargs:
            The arguments to complete the Draft

        Returns
        -------
        T
        """
        if not isinstance(self, Draft):
            return self

        # Order matters: priority is given to the kwargs provided
        # by the user, so most likely when the Partial is instantiated
        return self._func(**{**kwargs, **self._kwargs})

    def _raise_draft_error(self):
        raise TypeError(
            f"This {self} has not been instantiated "
            f"yet, likely because it was missing an argument."
        )

    def __call__(self, *args, **kwargs):
        self._raise_draft_error()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self._raise_draft_error()

    def __repr__(self):
        return f"Draft[{self._func.__qualname__}]"
