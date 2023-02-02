import datetime

from confit import Cli, Registry, get_default_registry, set_default_registry

app = Cli(pretty_exceptions_show_locals=False)


@set_default_registry
class RegistryCollection:
    factory = Registry(("test_cli", "factory"), entry_points=True)

    _catalogue = dict(
        factory=factory,
    )


registry = get_default_registry()


@registry.factory.register("submodel")
class SubModel:
    # Type hinting is optional but recommended !
    def __init__(self, value: float, desc: str = ""):
        self.value = value
        self.desc = desc


@registry.factory.register("bigmodel")
class BigModel:
    def __init__(self, date: datetime.date, submodel: SubModel):
        self.date = date
        self.submodel = submodel


@app.command(name="script")
def func(modelA: BigModel, modelB: BigModel, other: int, seed: int):
    assert modelA.submodel is modelB.submodel
    assert modelA.date == datetime.date(2010, 10, 10)
    print("Other:", other)
    print(modelA.submodel.value)


if __name__ == "__main__":
    app()
