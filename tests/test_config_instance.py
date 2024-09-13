import datetime

import pytest

from confit import Config, Registry, validate_arguments
from confit.config import CyclicReferenceError, MissingReference, Reference
from confit.errors import ConfitValidationError
from confit.registry import PYDANTIC_V1, RegistryCollection
from confit.utils.xjson import dumps, loads


class registry(RegistryCollection):
    factory = Registry(("test_config", "factory"), entry_points=True)


class CustomClass:
    pass


class HeldValue:
    def __init__(self):
        self.value = "A value!"


@registry.factory.register("submodel")
class SubModel:
    def __init__(self, value: float, desc: str = ""):
        self.value = value
        self.desc = desc

        self.hidden_value = 5
        self.heldvalue = HeldValue()


@registry.factory.register("bigmodel")
class BigModel:
    def __init__(self, date: datetime.date, submodel: SubModel):
        self.date = date
        self.submodel = submodel

        self.hidden_value = 10

    def get_hidden_value(self):
        return self.hidden_value


pipeline_cfg_config = """\
[script]
modelA = ${modelA}
modelB = ${modelB}
hidden_value = ${modelA:hidden_value}

[modelA]
@factory = "bigmodel"
date = "2003-02-01"

[modelA.submodel]
@factory = "submodel"
value = 12.0

[modelB]
@factory = "bigmodel"
date = "2003-04-05"
submodel = ${modelA.submodel}

"""


def test_read_from_str():
    config = Config().from_str(pipeline_cfg_config)
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
        "script": {
            "modelA": Reference("modelA"),
            "modelB": Reference("modelB"),
            "hidden_value": Reference("modelA:hidden_value"),
        },
    }
    resolved = config.resolve(registry=registry)
    assert isinstance(resolved["modelA"].submodel, SubModel)
    exported_config = config.to_str()
    assert exported_config == pipeline_cfg_config


def test_write_to_str():
    def reexport(s):
        config = Config().from_str(s, resolve=True, registry=registry)
        return Config(
            script=dict(
                modelA=config["script"]["modelA"],
                modelB=config["script"]["modelB"],
            )
        ).to_str()

    exported = reexport(pipeline_cfg_config)
    assert reexport(exported) == exported


# store to a temp file
def test_to_disk(tmp_path):
    dest = tmp_path / "test.cfg"
    config = Config().from_str(pipeline_cfg_config)
    config.to_disk(dest)
    config2 = Config().from_disk(dest)
    assert config == config2


def test_write_resolved_to_str():
    s = Config().from_str(pipeline_cfg_config, resolve=True, registry=registry)
    assert s["modelA"] is s["script"]["modelA"]
    assert (
        s.to_str()
        == """\
[script]
modelA = ${modelA}
modelB = ${modelB}
hidden_value = 10

[modelA]
@factory = "bigmodel"
date = "2003-02-01"

[modelA.submodel]
@factory = "submodel"
value = 12.0

[modelB]
@factory = "bigmodel"
date = "2003-04-05"
submodel = ${modelA.submodel}

"""
    )


def test_inline_serialization():
    config = Config(
        {
            "section": {
                "a": [
                    "ok",
                    1.0,
                    30,
                    float("inf"),
                    -float("inf"),
                    float("nan"),
                    None,
                    True,
                    False,
                ],
                "b": ("ok", {"x": Reference("other.a")}),
            },
            "other": {"a": "a", "b": "b"},
        }
    )
    assert (
        config.resolve().to_str()
        == """\
[section]
a = ["ok", 1.0, 30, Infinity, -Infinity, NaN, null, true, false]
b = ("ok", {"x": "a"})

[other]
a = "a"
b = "b"

"""
    )


def test_xjson():
    obj = {
        "a": ["ok", 1.0, 30, float("inf"), -float("inf"), None, True, False],
        "b": ("ok", {"x": Reference("other.a")}),
    }
    print(dumps(obj))
    assert loads(dumps(obj)) == obj
    assert dumps(float("nan")) == "NaN"
    nan = loads("NaN")
    assert nan != nan


def test_xjson_fail():
    obj = {
        "a": CustomClass(),
    }
    with pytest.raises(TypeError):
        dumps(obj)


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


def test_list_of_interpolated():
    config = """
[params]
l = [${values.a}, ${values.b}] # A list of values

[values]
a = 1
b = 2
"""
    params = Config.from_str(config).resolve()["params"]
    assert params == {"l": [1, 2]}


def test_operations_inside_interpolation():
    config = """
[params]
sum = ${values.a+10}

[values]
a = 1
"""
    params = Config.from_str(config).resolve()["params"]
    assert params == {"sum": 11}


def test_strings():
    config = """
[params]
foo = "foo"
bar = 'bar'
val = val
quoted = "'val'"
esc = "\\"val\\""
"""
    cfg = Config.from_str(config).resolve()
    assert cfg["params"] == {
        "foo": "foo",
        "bar": "bar",
        "val": "val",
        "quoted": "'val'",
        "esc": '"val"',
    }
    assert (
        cfg.to_str()
        == """\
[params]
foo = "foo"
bar = "bar"
val = "val"
quoted = "'val'"
esc = '"val"'

"""
    )


def test_illegal_interpolation():
    config = """\
[script]
modelA = ${modelA}
hidden_value = ${modelA:get_hidden_value()}

[modelA]
date = "2003-02-01"
@factory = "bigmodel"

[modelA.submodel]
@factory = "submodel"
value = 12

"""
    config = Config().from_str(config)
    with pytest.raises(RuntimeError):
        config.resolve(registry=registry)


def test_deep_interpolations():
    pipeline_config = """\
[script]
modelA = ${modelA}
value = ${modelA.submodel.value}
hidden_value = ${modelA.submodel:hidden_value}
held_value = ${modelA.submodel:heldvalue.value}

[modelA]
date = "2003-02-01"
@factory = "bigmodel"

[modelA.submodel]
@factory = "submodel"
value = 12

"""

    config = Config().from_str(pipeline_config)
    resolved = config.resolve(registry=registry)
    assert resolved["script"]["value"] == 12
    assert resolved["script"]["hidden_value"] == 5


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
        == "Could not interpolate the following reference: ${missing}"
    )


def test_type_hinted_instantiation_error():
    @validate_arguments
    def function(embedding: SubModel):
        pass

    params = Config.from_str(
        """
    [embedding]
    value = "ok"
    """
    )
    with pytest.raises(ConfitValidationError) as exc_info:
        function(**params)
    if PYDANTIC_V1:
        assert str(exc_info.value) == (
            "1 validation error for "
            "test_config_instance.test_type_hinted_instantiation_error.<locals>"
            ".function()\n"
            "-> embedding.value\n"
            "   value is not a valid float, got 'ok' (str)"
        )
    else:
        assert str(exc_info.value) == (
            "1 validation error for "
            "test_config_instance.test_type_hinted_instantiation_error.<locals>"
            ".function()\n"
            "-> embedding.value\n"
            "   input should be a valid number, unable to parse string as a number, "
            "got 'ok' (str)"
        )


def test_factory_instantiation_error():
    with pytest.raises(ConfitValidationError) as exc_info:
        Config.from_str(
            """
        [embedding]
        @factory = "submodel"
        value = "ok"
        """
        ).resolve(registry=registry)
    if PYDANTIC_V1:
        assert str(exc_info.value) == (
            "1 validation error for test_config_instance.SubModel()\n"
            "-> embedding.value\n"
            "   value is not a valid float, got 'ok' (str)"
        )
    else:
        assert str(exc_info.value) == (
            "1 validation error for test_config_instance.SubModel()\n"
            "-> embedding.value\n"
            "   input should be a valid number, unable to parse string as a number, got"
            " 'ok' (str)"
        )


def test_absolute_dump_path():
    cfg = Reference("my.deep.path")
    config_str = Config(
        value=dict(
            moved=cfg,
        ),
        my=dict(deep=dict(path=Config(test="ok"))),
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
    config = Config().from_str(pipeline_cfg_config, resolve=False)
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
            "modelA": {"date": "2006-06-06"},
            "script": {"other_extra": {"key": "val"}},
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


def test_cyclic_reference():
    config = """\
[modelA]
@factory = "bigmodel"
date = "2003-02-01"
submodel = ${modelB}

[modelB]
@factory = "bigmodel"
date = "2010-02-01"
submodel = ${modelA}

"""
    config = Config().from_str(config)
    with pytest.raises(CyclicReferenceError) as exc_info:
        config.resolve(registry=registry)
    assert str(exc_info.value) == "Cyclic reference detected at modelA"


@registry.factory.register("inherited-model")
@registry.factory.register("inherited-model-alias")
class InheritedModel(BigModel):
    def __init__(self, date: datetime.date, submodel: SubModel, special: int = 3, **kw):
        super().__init__(date, submodel)
        self.special = special
        self.kw = kw


def test_inheritance():
    cfg = """\
[modelA]
@factory = "inherited-model"
date = "2003-02-01"
special = 5
extra = 'extra'


[modelA.submodel]
@factory = "submodel"
value = 12.0

"""
    model = Config.from_str(cfg).resolve(registry=registry)["modelA"]
    assert model.special == 5
    assert model.kw == {"extra": "extra"}


def test_partial_interpolation():
    config = Config.from_str(pipeline_cfg_config)
    model = config["modelB"].resolve(registry=registry, root=config)
    assert isinstance(model.submodel, SubModel)


def test_deep_key():
    config = Config.from_str(
        """
    [section]
    deep.key = "ok"
    """
    )
    assert config["section"]["deep"] == {"key": "ok"}


def test_escaped_key():
    config = Config.from_str(
        """
    [section]
    "    escaped" = "ok"
    """
    )
    assert config == {"section": {"    escaped": "ok"}}

    assert config.to_str() == "[section]\n'    escaped' = \"ok\"\n\n"


def test_root_level_config_error():
    with pytest.raises(Exception) as exc_info:
        Config({"ok": "ok"}).to_str()

    assert "root level config" in str(exc_info.value)


def test_simple_dump():
    config = Config({"section": {"date": datetime.date(2023, 8, 31)}})
    assert config.to_str() == '[section]\ndate = "2023-08-31"\n\n'


def test_list_interpolation():
    config = Config.from_str(
        """
    [section]
    "key.with.dot" = ["foo", "bar"]
    b = ${[*section."key.with.dot", "baz"]}
    """
    ).resolve()
    assert config["section"]["b"] == ["foo", "bar", "baz"]


def test_fail_if_suspected_json_malformation():
    with pytest.raises(ConfitValidationError) as exc_info:
        Config.from_str(
            """
        [section]
        string = 'ok
        list = 'ok']
        """
        )
    assert str(exc_info.value) == (
        "2 validation errors\n"
        "-> string\n"
        '   Malformed value: "\'ok"\n'
        "-> list\n"
        "   Malformed value: \"'ok']\""
    )


def test_string():
    config = Config.from_str(
        """
    [section]
    string1 = '\"ok\"'
    # When writing config strings in Python
    # We have to double escape the backslashes,
    # once for Python and once for the config parser
    string2 = "\\\\bok\\\\b"
    string3 = ok
    """
    )
    assert config["section"]["string1"] == '"ok"'
    assert config["section"]["string2"] == "\\bok\\b"
    assert config["section"]["string3"] == "ok"


pipeline_yaml_config = """\
script:
    modelA: ${modelA}
    modelB: ${modelB}
    hidden_value: ${modelA:hidden_value}
modelA:
    '@factory': bigmodel
    date: '2003-02-01'
    submodel:
        '@factory': submodel
        value: 12.0
modelB:
    '@factory': bigmodel
    date: '2003-04-05'
    submodel: ${modelA.submodel}
"""


def test_read_write_yaml_str():
    config = Config().from_yaml_str(pipeline_yaml_config)
    assert config == {
        "script": {
            "modelA": Reference("modelA"),
            "modelB": Reference("modelB"),
            "hidden_value": Reference("modelA:hidden_value"),
        },
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
    }
    config_str = config.to_yaml_str()
    assert config_str == pipeline_yaml_config


def test_to_from_disk(tmp_path):
    dest = tmp_path / "test.yml"
    config = Config().from_yaml_str(pipeline_yaml_config)
    config.to_disk(dest)
    config2 = Config().from_disk(dest)
    assert config == config2


def test_yaml_str_dump():
    cfg = Config.from_yaml_str(
        """\
ner:
    "@key": 'eds."normalizer.test".ok'
    test.ok: ${ner.pollution}
    pollution: false
"""
    )
    assert (
        cfg.to_yaml_str()
        == """\
ner:
    '@key': 'eds."normalizer.test".ok'
    test.ok: ${ner.pollution}
    pollution: false
"""
    )
