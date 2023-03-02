from datetime import datetime

import pydantic.error_wrappers
import pytest

from confit import Registry
from confit.registry import SignatureError, validate_arguments


class RegistryCollection:
    factory = Registry(("test_config", "factory"), entry_points=True)

    _catalogue = dict(
        factory=factory,
    )


registry = RegistryCollection()


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

    with pytest.raises(pydantic.error_wrappers.ValidationError) as e:
        GoodModel(3, value=4)


def test_validate_decorator():
    class GoodModel:
        def __init__(self, value: float, desc: str = ""):
            self.value = value

    validated = validate_arguments()(GoodModel)
    assert validated(3).value == 3
