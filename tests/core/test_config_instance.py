import datetime

import pytest
from pydantic import ValidationError, validate_arguments

from confit import Config, Registry
from confit.config import MissingReference, Reference


class RegistryCollection:
    factory = Registry(("mytest", "factory"), entry_points=True)

    _catalogue = dict(
        factory=factory,
    )


registry = RegistryCollection()


class CustomClass:
    pass


@registry.factory.register("submodel")
class SubModel:
    def __init__(self, value: float, desc: str = ""):
        self.value = value
        self.desc = desc


@registry.factory.register("bigmodel")
class BigModel:
    def __init__(self, date: datetime.date, submodel: SubModel):
        self.datetime = date
        self.submodel = submodel


pipeline_config = """\
[script]
modelA = ${modelA}
modelB = ${modelB}

[modelA]
date = "2003-02-01"
@factory = "bigmodel"

[modelA.submodel]
@factory = "submodel"
value = 12

[modelB]
date = "2003-04-05"
@factory = "bigmodel"
submodel = ${modelA.submodel}

"""


def test_read_from_str():
    config = Config().from_str(pipeline_config)
    assert config == {
        "modelA": {
            "@factory": "bigmodel",
            "date": "2003-02-01",
            "submodel": {"@factory": "submodel", "value": 12},
        },
        "modelB": {
            "@factory": "bigmodel",
            "date": "2003-04-05",
            "submodel": Reference("modelA.submodel"),
        },
        "script": {"modelA": Reference("modelA"), "modelB": Reference("modelB")},
    }
    resolved = config.resolve(registry=registry)
    assert isinstance(resolved["modelA"].submodel, SubModel)
    exported_config = config.to_str()
    assert exported_config == pipeline_config


def test_write_to_str():
    def reexport(s):
        config = Config().from_str(s, resolve=True, registry=registry)
        return Config(
            script=dict(
                modelA=config["script"]["modelA"],
                modelB=config["script"]["modelB"],
            )
        ).to_str()

    exported = reexport(pipeline_config)
    assert reexport(exported) == exported


def test_cast_parameters():
    @validate_arguments
    def function(a: str, b: str, c: int, d: int):
        assert a == b
        assert c == d

    config = """
[params]
a = okok.okok
b = "okok.okok"
c = "12"
d = 12
"""
    params = Config.from_str(config)["params"]
    assert params == {
        "a": "okok.okok",
        "b": "okok.okok",
        "c": "12",
        "d": 12,
    }
    function(**params)


def test_dump_error():
    with pytest.raises(TypeError):
        Config(test=CustomClass()).to_str()


def test_missing_error():
    with pytest.raises(MissingReference) as exc_info:
        Config.from_str(
            """
        [params]
        a = okok.okok
        b = ${missing}
        """
        ).resolve(registry=registry)
    assert (
        str(exc_info.value)
        == "Could not interpolate the following references: ${missing}"
    )


def test_type_hinted_instantiation_error():
    @validate_arguments
    def function(embedding: SubModel):
        ...

    params = Config.from_str(
        """
    [embedding]
    value = "ok"
    """
    )
    with pytest.raises(ValidationError) as exc_info:
        function(**params)
    assert str(exc_info.value) == (
        "1 validation error for Function\n"
        "embedding -> value\n"
        "  value is not a valid float (type=type_error.float)"
    )


def test_factory_instantiation_error():
    with pytest.raises(ValidationError) as exc_info:
        Config.from_str(
            """
        [embedding]
        @factory = "submodel"
        value = "ok"
        """
        ).resolve(registry=registry)
    assert str(exc_info.value) == (
        "1 validation error for SubModel\n"
        "embedding -> value\n"
        "  value is not a valid float (type=type_error.float)"
    )


def test_absolute_dump_path():
    config_str = Config(
        value=dict(
            moved=Config(
                test="ok",
                __path__=("my", "deep", "path"),
            ),
        )
    ).to_str()
    assert config_str == (
        "[value]\n"
        "moved = ${my.deep.path}\n"
        "\n"
        "[my]\n"
        "\n"
        "[my.deep]\n"
        "\n"
        "[my.deep.path]\n"
        'test = "ok"\n'
        "\n"
    )


def test_merge():
    config = Config().from_str(pipeline_config, resolve=False)
    other = Config().from_str(
        """\
[modelA.submodel]
@factory = "submodel"
value = 22

[script.extra]
size = 128
""",
        resolve=False,
    )
    merged = config.merge(other, remove_extra=True)
    merged = merged.merge(
        Config(script=Config(new_component=Config(test="ok"))), remove_extra=False
    )
    assert merged["modelA"]["date"] == "2003-02-01"
    assert "extra" not in merged["script"]
    merged = merged.merge(
        {
            "modelA.date": "2006-06-06",
            "script.other_extra": {"key": "val"},
        },
        remove_extra=False,
    )
    merged = merged.merge(
        {
            "script.missing_subsection.size": 96,
            "modelA.missing_key": 96,
        },
        remove_extra=True,
    )
    resolved = merged.resolve(registry=registry)
    assert merged["modelA"]["date"] == "2006-06-06"
    assert "extra" not in resolved["script"]
    assert "other_extra" in resolved["script"]
