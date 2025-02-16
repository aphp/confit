import inspect
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import catalogue
import pytest
from pytest import fixture

from confit import Config, Registry
from confit.registry import RegistryCollection

TEST_DIR = Path(__file__).parent


@fixture(scope="module")
def registry():
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

    class registry(RegistryCollection):
        misc = Registry(("mytest", "misc"), entry_points=True)
        misc_bis = Registry(("mytest", "misc_bis"), entry_points=True)
        default_factory = RegistryWithDefault(
            ("mytest", "default_factory"), entry_points=True
        )

    registry.other = Registry(("mytest", "other"), entry_points=True)
    return registry


@pytest.fixture
def change_test_dir(request):
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(request.config.invocation_dir)
