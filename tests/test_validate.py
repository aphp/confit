from datetime import datetime

import pytest

from confit import Registry


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


@registry.factory.register("bad-model")
class BadModel:
    def __init__(self, *args, value: float):
        self.value = value


def test_validate_submodel():
    model = GoodModel(
        value=3,
    )
    assert isinstance(model.value, float)


def test_fail_args():
    with pytest.raises(Exception) as e:
        BadModel(
            "ko",
            value=3,
        )
        assert "must not have positional only args" in str(e.value)
