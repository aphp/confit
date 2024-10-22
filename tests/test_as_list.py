from dataclasses import is_dataclass
from typing import Generic, List, TypeVar

import pydantic
import pytest
from pydantic import BaseModel
from typing_extensions import is_typeddict

from confit import validate_arguments
from confit.errors import ConfitValidationError, patch_errors

T = TypeVar("T")
if pydantic.VERSION < "2":

    def cast(type_, obj):
        class Model(pydantic.BaseModel):
            __root__: type_

            class Config:
                arbitrary_types_allowed = True

        return Model(__root__=obj).__root__

else:
    from pydantic.type_adapter import ConfigDict, TypeAdapter
    from pydantic_core import core_schema

    def make_type_adapter(type_):
        config = None
        if not issubclass(type, BaseModel) or is_dataclass(type) or is_typeddict(type):
            config = ConfigDict(arbitrary_types_allowed=True)
        return TypeAdapter(type_, config=config)

    def cast(type_, obj):
        return make_type_adapter(type_).validate_python(obj)


class MetaAsList(type):
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls.type_ = List

    def __getitem__(self, item):
        new_type = MetaAsList(self.__name__, (self,), {})
        new_type.type_ = List[item]
        return new_type

    def validate(cls, value, config=None):
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            value = [value]
        try:
            return cast(cls.type_, value)
        except pydantic.ValidationError as e:
            e = patch_errors(e, drop_names=("__root__",))
            e.model = cls
            raise e

    def __get_validators__(cls):
        yield cls.validate

    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)


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


class CustomMeta(type):
    def __getattr__(self, item):
        raise AttributeError(item)

    def __dir__(self):
        return super().__dir__()


class Custom:
    def __init__(self, value: int):
        self.value = value


def test_as_list_custom():
    @validate_arguments
    def func(a: AsList[Custom]):
        return [x.value for x in a]

    assert func(Custom(4)) == [4]

    with pytest.raises(ConfitValidationError):
        func({"data": "ok"})
