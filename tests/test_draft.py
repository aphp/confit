import pytest

from confit import Config, validate_arguments
from confit.errors import ConfitValidationError
from confit.registry import Draft


class Custom:
    def __init__(self, value: int):
        self.value = value

    def foo(self):
        pass


def test_draft_from_config(registry):
    @registry.misc_bis.register("partial")
    def partial_function(required_val: int, param: int = 3) -> Custom:
        return Custom(required_val + param)

    config = """
[model]
@misc_bis = partial !draft
param = 3
"""
    obj = Config().from_str(config).resolve(registry=registry)["model"]
    assert isinstance(obj, Draft)
    with pytest.raises(TypeError):
        obj.foo()
    with pytest.raises(TypeError):
        obj()
    with pytest.raises(TypeError):
        obj + 5
    assert Draft.instantiate(obj, required_val=2).value == 5

    obj2 = partial_function(param=5, required_val=2)
    assert obj2.value == 7

    assert Draft.instantiate(obj2, required_val=2).value == 7


def test_draft_from_python(registry):
    def partial_function(required_val: int, param: int = 3) -> Custom:
        return Custom(required_val + param)

    partial_function = registry.misc_bis.register("partial", func=partial_function)

    @validate_arguments
    def use_draft(draft: Draft[Custom]) -> Custom:
        return draft.instantiate(required_val=2)

    assert partial_function.draft(required_val=2).instantiate().value == 5

    obj = partial_function.draft(param=3)
    assert use_draft(obj).value == 5

    assert isinstance(obj, Draft)
    with pytest.raises(TypeError):
        obj.foo()
    with pytest.raises(TypeError):
        obj()
    with pytest.raises(TypeError):
        obj + 5
    assert Draft.instantiate(obj, required_val=2).value == 5

    obj2 = partial_function(param=5, required_val=2)
    assert obj2.value == 7

    assert Draft.instantiate(obj2, required_val=2).value == 7


def test_draft_from_type(registry):
    class MyClass:
        def __init__(self, value: int):
            self.value = value

    MyClass = registry.misc_bis.register("partial")(MyClass)
    assert isinstance(MyClass.draft(value=3), Draft)

    obj = MyClass.draft()
    assert str(obj) == "Draft[test_draft_from_type.<locals>.MyClass]"


def test_draft_error_from_function(registry):
    class CustomError:
        def __init__(self, value: int):
            self.value = value

    def partial_function(required_val: int, param: int = 3) -> CustomError:
        return CustomError(required_val + param)

    partial_function = registry.misc_bis.register("partial")(partial_function)

    obj = partial_function.draft()

    @validate_arguments
    def use_draft(draft: Draft[Custom]) -> Custom:
        return draft.instantiate(value=2)

    with pytest.raises(ConfitValidationError) as e:
        use_draft("a string ?")

    with pytest.raises(ConfitValidationError) as e:
        use_draft(obj)

    assert (
        "Expected Draft[Custom], "
        "got Draft[test_draft_error_from_function.<locals>.CustomError]" in str(e.value)
    )


def test_draft_error_from_type(registry):
    class CustomError:
        def __init__(self, value: int):
            self.value = value

    CustomError = registry.misc_bis.register("partial")(CustomError)

    obj = CustomError.draft()

    @validate_arguments
    def use_draft(draft: Draft[Custom]) -> Custom:
        return draft.instantiate(value=2)

    with pytest.raises(ConfitValidationError) as e:
        use_draft(obj)

    assert (
        "Expected Draft[Custom], "
        "got Draft[test_draft_error_from_type.<locals>.CustomError]" in str(e.value)
    )
