from confit import Registry


class RegistryCollection:
    misc = Registry(("mytest", "misc"), entry_points=True)

    _catalogue = dict(
        misc=misc,
    )


registry = RegistryCollection()


def test_register_decorator():
    @registry.misc.register("test-1")
    def test_function(param: int = 3):
        pass

    assert test_function is registry.misc.get("test-1")


def test_register_call():
    def test_function(param: int = 3):
        pass

    test_function_2 = registry.misc.register("test", func=test_function)
    assert test_function_2 is registry.misc.get("test")


def test_register_no_decorate():
    class GoodModel:
        def __init__(self, value: float, desc: str = ""):
            self.value = value

    registry.misc.register("good-model", func=GoodModel)
    assert GoodModel is registry.misc.get("good-model")
