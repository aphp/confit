import os

import pytest
from pydantic import StrictBool, ValidationError
from typing_extensions import Literal

from confit import Registry
from confit.errors import ConfitValidationError
from confit.registry import RegistryCollection, SignatureError, validate_arguments


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
            def __init__(self, *args, value: float):
                ...

    assert "positional only args or duplicated kwargs" in str(e.value)

    with pytest.raises(TypeError) as e:
        GoodModel(3, value=4)

    assert str(e.value) == "multiple values for argument 'value'"


def test_validate_decorator():
    class GoodModel:
        def __init__(self, value: float, desc: str = ""):
            self.value = value

    validated = validate_arguments()(GoodModel)
    assert validated("3").value == 3


def test_literals():
    @validate_arguments()
    def test(val: Literal["ok", "ko"]):
        return val

    with pytest.raises(ConfitValidationError) as e:
        test("not ok")
    assert str(e.value) == (
        "1 validation error for test_validate.test_literals.<locals>.test()\n"
        "-> val\n"
        "   unexpected value; permitted: 'ok', 'ko', got 'not ok' (str)"
    )


def test_fail_init():
    @validate_arguments()
    class SubModel:
        def __init__(self, raise_attribute: bool, desc: str = ""):
            self.desc = desc
            if raise_attribute:
                raise AttributeError("some_attribute")

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

    with pytest.raises(ValidationError) as e:
        Model(raise_attribute=False)
    assert str(e.value) == (
        "1 validation error for test_validate.test_fail_init.<locals>.SubModel()\n"
        "-> raise_attribute\n"
        "   field required"
    )

    with pytest.raises(ValidationError) as e:
        BigModel(model=dict(raise_attribute="ok"))
    assert str(e.value) == (
        "1 validation error for test_validate.test_fail_init.<locals>.BigModel()\n"
        "-> model.raise_attribute\n"
        "   value is not a valid boolean, got 'ok' (str)"
    )
    repr(e)

    with pytest.raises(ValidationError) as e:
        BigModel(model=dict(raise_attribute=False))
    # Nested error because we cannot merge the submodel error into the model error
    assert str(e.value) == (
        "1 validation error for test_validate.test_fail_init.<locals>.BigModel()\n"
        "-> model\n"
        "   1 validation error for test_validate.test_fail_init.<locals>.SubModel()\n"
        "   -> raise_attribute\n"
        "      field required"
    )


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
            "   unexpected value; permitted: 'ok', 'ko', got 'not ok' (str)"
        )
    finally:
        os.environ.pop("CONFIT_DEBUG", None)
