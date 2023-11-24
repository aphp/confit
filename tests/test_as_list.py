from typing import Any, Generic, List, TypeVar

import pydantic
import pytest

from confit import validate_arguments
from confit.errors import ConfitValidationError, patch_errors

T = TypeVar("T")


class MetaAsList(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls.item = Any

    def __getitem__(self, item):
        new_type = MetaAsList(self.__name__, (self,), {})
        new_type.item = item
        return new_type

    def validate(cls, value, config=None):
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            value = [value]
        try:
            return pydantic.parse_obj_as(List[cls.item], value)
        except pydantic.ValidationError as e:
            e = patch_errors(e, drop_names=("__root__",))
            e.model = cls
            raise e

    def __get_validators__(cls):
        yield cls.validate


class AsList(Generic[T], metaclass=MetaAsList):
    pass


def test_as_list():
    @validate_arguments
    def func(a: AsList[int]):
        return a

    assert func("1") == [1]

    with pytest.raises(ConfitValidationError) as e:
        func("a")

    assert (
        "1 validation error for test_as_list.test_as_list.<locals>.func()\n" "-> a.0\n"
    ) in str(e.value)
