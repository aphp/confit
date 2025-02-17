import datetime
import inspect

import catalogue
import pytest

from confit import Config


def test_register_decorator(registry):
    @registry.misc.register("test-1")
    def test_function(param: int = 3):
        pass

    assert test_function is registry.misc.get("test-1")


def test_register_call(registry):
    def test_function(param: int = 3):
        pass

    test_function_2 = registry.misc.register("test", func=test_function)
    assert test_function_2 is registry.misc.get("test")


def test_register_no_decorate(registry):
    class GoodModel:
        def __init__(self, value: float, desc: str = ""):
            pass

    registry.misc.register("good-model", func=GoodModel)
    assert GoodModel is registry.misc.get("good-model")


def test_available(registry):
    assert set(registry.misc.get_available()) == {"good-model", "test", "test-1"}


def test_default_config_invoker(registry):
    @registry.misc.register("submodel")
    class SubModel:
        def __init__(self, value: float, desc: str = ""):
            self.value = value
            self.desc = desc

            self.hidden_value = 5

    @registry.default_factory.register(
        "defaultmodel",
        default_config={
            "date": "2003-02-01",
            "submodel": {"@misc": "submodel", "value": 28},
        },
    )
    class DefaultModel:
        def __init__(
            self,
            date: datetime.date = datetime.date(2003, 2, 1),
            submodel: SubModel = None,
        ):
            self.date = date
            self.submodel = submodel

    pipeline_config = """
    [model]
    @default_factory = "defaultmodel"
    """
    config = Config().from_str(pipeline_config)
    resolved = config.resolve(registry=registry)
    assert resolved["model"].submodel.value == 28

    model = DefaultModel(date="2004-02-01")
    assert model.submodel.value == 28
    assert model.date.strftime("%Y-%m-%d") == "2004-02-01"
    registered = registry.default_factory.get("defaultmodel")
    params = inspect.signature(registered).parameters
    assert params["date"].default == "2003-02-01"
    assert params["submodel"].default == {
        "@misc": "submodel",
        "value": 28.0,
    }


def test_missing(registry):
    with pytest.raises(catalogue.RegistryError) as e:
        registry.misc.get("clearly_missing_function")

    assert (
        "Can't find 'clearly_missing_function' in registry mytest -> misc. "
        "Available names:" in str(e.value)
    )


def test_cannot_store(registry):
    @registry.misc.register("unstorable")
    def return_none():
        return None

    return_none()
