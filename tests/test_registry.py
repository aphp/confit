import datetime
import inspect
from typing import Any, Callable, Dict, Optional

import catalogue
import pytest
from pytest import fixture

from confit import Config, Registry
from confit.registry import RegistryCollection


class RegistryWithDefault(Registry):
    @staticmethod
    def update_signature_(func, new_defaults):
        sig = inspect.signature(func)
        new_params = []
        for name, param in sig.parameters.items():
            if name in new_defaults:
                print("Updating param: ", name, " to default: ", new_defaults[name])
                new_params.append(
                    inspect.Parameter(
                        name,
                        param.kind,
                        default=new_defaults[name],
                        annotation=param.annotation,
                    )
                )
            else:
                new_params.append(param)

        new_sig = sig.replace(parameters=new_params)
        setattr(func, "__signature__", new_sig)

    def register(
        self,
        name: str,
        *,
        func: Optional[catalogue.InFunc] = None,
        save_params: Optional[Dict[str, Any]] = None,
        default_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[catalogue.InFunc], catalogue.InFunc]:
        def invoke(func, values):
            values = (
                values
                if default_config is None
                else Config(default_config).merge(values)
            )
            return func(values)

        # Wrapper to update the signature of the function and register it
        def wrapper(func: catalogue.InFunc) -> catalogue.InFunc:
            if default_config is not None:
                self.update_signature_(func, default_config)
            return Registry.register(
                self,
                name,
                func=func,
                save_params=save_params,
                skip_save_params=["to_skip"],
                invoker=invoke,
            )

        return wrapper if func is None else wrapper(func)


@fixture(scope="module")
def registry():
    class registry(RegistryCollection):
        misc = Registry(("mytest", "misc"), entry_points=True)
        default_factory = RegistryWithDefault(
            ("mytest", "default_factory"), entry_points=True
        )

    registry.other = Registry(("mytest", "other"), entry_points=True)
    return registry


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
