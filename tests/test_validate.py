import datetime
import functools
import os

import pytest
from pydantic import Field, StrictBool, TypeAdapter, ValidationError
from typing_extensions import Literal

from confit import Config, Registry, Validatable
from confit.errors import ConfitValidationError
from confit.registry import (
    RegistryCollection,
    SignatureError,
    VisibleDeprecationWarning,
    validate_arguments,
)


class registry(RegistryCollection):
    factory = Registry(("test_config", "factory"), entry_points=True)


@registry.factory.register("good-model")
class GoodModel:
    def __init__(self, value: float, desc: str = ""):
        self.value = value


def test_validate_submodel():
    model = GoodModel(
        value=3,
    )
    assert isinstance(model.value, float)


def test_fail_args():
    with pytest.raises(SignatureError) as e:

        @registry.factory.register("bad-model")
        class BadModel:
            def __init__(self, *args, value: float): ...

    assert "positional only args or duplicated kwargs" in str(e.value)

    with pytest.raises(ConfitValidationError) as e:
        GoodModel(3, value=4)

    assert str(e.value) == (
        "1 validation error for test_validate.GoodModel()\n"
        "-> [signature]\n"
        "   multiple values for argument: 'value'"
    )


def test_validate_decorator():
    class GoodModel:
        def __init__(self, value: float, desc: str = ""):
            self.value = value

    validated = validate_arguments()(GoodModel)
    assert validated("3").value == 3


def test_custom_validators_v1():
    @validate_arguments()
    class ModelWithCustomValidation:
        def __init__(self, value: float, desc: str = ""):
            self.value = value
            self.desc = desc

        @classmethod
        def validate(cls, value: float):
            if isinstance(value, dict):
                value["desc"] = "Custom validation done"
                return value

        @classmethod
        def __get_validators__(cls):
            yield cls.validate

    @validate_arguments()
    def fn(value: ModelWithCustomValidation):
        return value.desc

    assert (
        fn(
            value=dict(
                value=3,
            )
        )
        == "Custom validation done"
    )


def test_custom_validators_v2():
    @validate_arguments()
    class ModelWithCustomValidation:
        def __init__(self, value: float, desc: str = ""):
            self.value = value
            self.desc = desc

        @classmethod
        def validate(cls, value: float):
            if isinstance(value, dict):
                value["desc"] = "Custom validation done"
                return value

        @classmethod
        def __get_pydantic_core_schema__(cls, *args, **kwargs):
            from pydantic_core import core_schema

            return core_schema.no_info_plain_validator_function(cls.validate)

    @validate_arguments()
    def fn(value: ModelWithCustomValidation):
        return value.desc

    assert (
        fn(
            value=dict(
                value=3,
            )
        )
        == "Custom validation done"
    )


def test_custom_validators_validatable():
    class ModelWithCustomValidation(Validatable):
        def __init__(self, value: float, desc: str = ""):
            self.value = value
            self.desc = desc

        @classmethod
        def validate(cls, value: float):
            if isinstance(value, dict):
                value["desc"] = "Custom validation done"
            return ModelWithCustomValidation(**value)

    @validate_arguments()
    def fn(value: ModelWithCustomValidation):
        return value.desc

    assert (
        fn(
            value=dict(
                value=3,
            )
        )
        == "Custom validation done"
    )


def test_literals():
    @validate_arguments()
    def test(val: Literal["ok", "ko"]):
        return val

    with pytest.raises(ConfitValidationError) as e:
        test("not ok")
    assert str(e.value) == (
        "1 validation error for test_validate.test_literals.<locals>.test()\n"
        "-> val\n"
        "   input should be 'ok' or 'ko', got 'not ok' (str)"
    )


def test_dates():
    @validate_arguments()
    def test(val: datetime.datetime):
        return val

    with pytest.raises(ConfitValidationError) as e:
        test("hello")
    err = str(e.value)
    assert "1 validation error for test_validate.test_dates.<locals>.test()" in err
    assert "-> val" in err
    assert "input is too short, got 'hello'" in err


def test_fail_init():
    @validate_arguments()
    class SubModel:
        def __init__(self, raise_attribute: bool, desc: str = ""):
            self.desc = desc
            if raise_attribute:
                raise AttributeError("some_attribute")

        def __repr__(self):
            return self.desc

    @validate_arguments()
    class Model:
        def __init__(self, raise_attribute: StrictBool):
            if raise_attribute:
                self.sub = SubModel(raise_attribute)
            else:
                self.sub = SubModel()

    @validate_arguments()
    class BigModel:
        def __init__(self, model: Model):
            self.model = model

    with pytest.raises(AttributeError) as e:
        Model(raise_attribute=True)

    with pytest.raises(ConfitValidationError) as e:
        Model(raise_attribute=False)
    assert str(e.value).replace("test_validate.test_fail_init.<locals>.", "") == (
        "1 validation error for SubModel()\n-> raise_attribute\n   field required"
    )

    with pytest.raises(ConfitValidationError) as e:
        BigModel(model=dict(raise_attribute="ok"))
    assert str(e.value).replace("test_validate.test_fail_init.<locals>.", "") == (
        "1 validation error for BigModel()\n"
        "-> model.raise_attribute\n"
        "   input should be a valid boolean, got 'ok' (str)"
    )
    repr(e)

    with pytest.raises(ConfitValidationError) as e:
        BigModel(model=dict(raise_attribute=False))
    # Nested error because we cannot merge the submodel error into the model error
    assert str(e.value).replace("test_validate.test_fail_init.<locals>.", "") == (
        "1 validation error for BigModel()\n"
        "-> model\n"
        "   1 validation error for SubModel()\n"
        "   -> raise_attribute\n"
        "      field required"
    )

    # A partially initialized input must not hide its validation error
    with pytest.raises(ConfitValidationError) as e:
        Model(raise_attribute=SubModel.__new__(SubModel))
    assert "input should be a valid boolean, got <" in str(e.value)


def test_debug():
    try:
        os.environ["CONFIT_DEBUG"] = "true"

        @validate_arguments()
        def test(val: Literal["ok", "ko"]):
            return val

        with pytest.raises(ConfitValidationError) as e:
            test("not ok")
        assert str(e.value) == (
            "1 validation error for test_validate.test_debug.<locals>.test()\n"
            "-> val\n"
            "   input should be 'ok' or 'ko', got 'not ok' (str)"
        )
    finally:
        os.environ.pop("CONFIT_DEBUG", None)


def test_extra_arg():
    @validate_arguments()
    def func(val: Literal["ok", "ko"]):
        return val

    with pytest.raises(ConfitValidationError) as e:
        func("ok", extra="extra")
    assert str(e.value) == (
        "1 validation error for test_validate.test_extra_arg.<locals>.func()\n"
        "-> extra\n"
        "   unexpected keyword argument"
    )


def test_deep_extra():  # from pydantic import validate_arguments
    @validate_arguments
    class Model:
        def __init__(self, a, b):
            print(a, b)

    @validate_arguments
    def func(val: Model):
        print(val)

    with pytest.raises(ConfitValidationError) as e:
        func(val={"c": 3, "d": 4})

    assert str(e.value) == (
        "2 validation errors for test_validate.test_deep_extra.<locals>.func()\n"
        "-> val.c\n"
        "   unexpected keyword argument\n"
        "-> val.d\n"
        "   unexpected keyword argument"
    )


def test_duplicated_arg():
    @validate_arguments()
    def func(val: Literal["ok", "ko"]):
        return val

    with pytest.raises(ConfitValidationError) as e:
        func("ok", val="ko")
    assert str(e.value) == (
        "1 validation error for test_validate.test_duplicated_arg.<locals>.func()\n"
        "-> [signature]\n"
        "   multiple values for argument: 'val'"
    )


def test_clean_error():
    class registry(RegistryCollection):
        factory = Registry(("test_cli", "factory"), entry_points=True)

    @registry.factory.register("submodel")
    class SubModel:
        # Type hinting is optional but recommended !
        def __init__(self, value: float, card: str = ""):
            self.value = value
            self.card = card

        @classmethod
        def __get_validators__(cls):
            yield cls.validate

        @classmethod
        def validate(cls, value, ctx=None):
            if isinstance(value, dict) and "card" in value:
                inner_get_card_length(value["card"])
            return value

    from pydantic.types import PaymentCardNumber

    @validate_arguments
    def inner_get_card_length(card: PaymentCardNumber):
        return len(card)

    @validate_arguments
    def func(submodel: SubModel):
        pass

    try:
        func(submodel=dict(value="hi"))
    except ConfitValidationError as e:
        assert e.__cause__ is None
        assert e.__suppress_context__ is True
    else:
        assert False, "Should have raised ConfitValidationError"

    try:
        func(submodel=dict(value="hi", card="hello"))
    except ConfitValidationError as e:
        detail = e.errors()[0]
        assert detail["loc"] == ("submodel",)
        assert isinstance(detail["ctx"]["error"], ConfitValidationError)
        assert detail["ctx"]["error"].errors()[0]["loc"] == ("card",)
        assert "inner_get_card_length()" in str(e)
        assert e.__cause__ is None
        assert e.__suppress_context__ is True
    else:
        assert False, "Should have raised ConfitValidationError"

    with pytest.raises(ValidationError) as e:
        TypeAdapter(list[SubModel]).validate_python([{"value": "hi"}])
    error = ConfitValidationError.from_exception(e.value)
    assert error.errors()[0]["loc"] == (0,)
    assert "SubModel()" in str(error)


def test_dump_kwargs():
    @registry.factory.register("kwargs-model")
    class KwargsModel:
        def __init__(self, value: float, **mykwargs: int):
            self.value = value
            self.mykwargs = mykwargs

    assert dict(Config.serialize(KwargsModel(value=3, a=1, b=2))) == {
        "@factory": "kwargs-model",
        "value": 3,
        "a": 1,
        "b": 2,
    }


def test_deprecated():
    @registry.factory.register("my-model", deprecated=["my-model-old"])
    class MyModel:
        def __init__(self, value: float):
            self.value = value

    with pytest.warns(VisibleDeprecationWarning) as record:
        instance = registry.factory.get("my-model-old")(3)
        assert dict(Config.serialize(instance)) == {
            "@factory": "my-model",
            "value": 3,
        }

    items = [x for x in record if isinstance(x.message, VisibleDeprecationWarning)]
    assert len(items) == 1
    assert items[0].message.args[0] == (
        '"my-model-old" is deprecated, please use "my-model" instead."'
    )


def test_wrapped_init():
    value = 5

    def decorator(func):
        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            nonlocal value
            value += 1
            return func(self, *args, **kwargs)

        return wrapped

    @validate_arguments()
    @validate_arguments()
    class MyClass:
        @decorator
        def __init__(self, value: int, desc: str = None):
            self.value = value

    obj = MyClass(10)
    assert obj.value == 10
    assert value == 6  # 5 + 1 from the decorator


def test_schema_argument():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")

        @validate_arguments
        def export(schema: int = Field(default=1), *, model_dump: int = 0):
            return schema + model_dump

        @validate_arguments
        class Writer:
            def __init__(self, schema: int = Field(default_factory=lambda: 1)):
                self.schema = schema

        assert export() == Writer().schema == 1
        assert export("2") == export(schema="2") == Writer(schema="2").schema == 2
        assert export(schema="2", model_dump="3") == 5
        for target in (export, Writer):
            with pytest.raises(ConfitValidationError, match="-> schema\n"):
                target(schema="invalid")


def test_legacy_errors():
    from confit.errors import patch_errors

    with pytest.raises(ValidationError) as caught:
        TypeAdapter(int).validate_python("bad")
    with pytest.warns(DeprecationWarning):
        error = patch_errors(caught.value, model=int, drop_names=("__root__",))
        error = patch_errors(error, model=int)
        error.model = int
        combined = ConfitValidationError([error.raw_errors], model=error.model)
        combined.raw_errors = patch_errors(combined.raw_errors, ("component",))
    assert combined.errors()[0]["loc"] == ("component",)
    assert combined.source is int
    assert "got 'bad' (str)" in str(combined)

    with pytest.warns(DeprecationWarning):
        from confit.registry import ValidatedFunction

    def converter(value: int):
        return value

    validator = ValidatedFunction(converter, {})
    assert validator.init_model_instance(value="2").value == 2
