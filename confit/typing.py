from dataclasses import is_dataclass
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel
from pydantic.type_adapter import ConfigDict, TypeAdapter
from pydantic_core import PydanticCustomError, core_schema
from typing_extensions import is_typeddict

T = TypeVar("T")


def legacy_validator_schema(validator):
    """
    Keep TypeError as a validation failure for custom get_validators hooks
    """

    def validate(value):
        try:
            return validator(value)
        except TypeError as error:
            raise PydanticCustomError(
                "type_error", "{error}", {"error": error}
            ) from error

    return core_schema.no_info_plain_validator_function(validate)


class Validatable:
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.chain_schema(
            [legacy_validator_schema(v) for v in cls.__get_validators__()]
        )


@lru_cache(maxsize=32)
def make_type_adapter(type_):
    config = None

    if not (
        (isinstance(type_, type) and issubclass(type_, BaseModel))
        or is_dataclass(type_)
        or is_typeddict(type_)
    ):
        config = ConfigDict(arbitrary_types_allowed=True)
    return TypeAdapter(type_, config=config)


def cast(type_, obj):
    return make_type_adapter(type_).validate_python(obj)
