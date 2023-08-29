import datetime

import pytest
from typer.testing import CliRunner

from confit import Cli, Registry
from confit.registry import PYDANTIC_V1, RegistryCollection, set_default_registry

runner = CliRunner()


class registry(RegistryCollection):
    factory = Registry(("test_cli", "factory"), entry_points=True)


set_default_registry(registry)


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
        self.date = date
        self.submodel = submodel


app = Cli(pretty_exceptions_show_locals=False)


@app.command(name="script")
def function(modelA: BigModel, modelB: BigModel, other: int, seed: int):
    assert modelA.submodel is modelB.submodel
    assert modelA.date == datetime.date(2010, 10, 10)
    print("Other:", other)


def test_cli_working(change_test_dir):
    result = runner.invoke(
        app,
        [
            "--config",
            "config.cfg",
            "--modelA.date",
            "2010-10-10",
            "--other",
            "4",
            "--seed=42",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Other: 4" in result.stdout


def test_cli_missing_debug(change_test_dir):
    result = runner.invoke(
        app,
        [
            "--modelA.date",
            "2010-10-10",
            "--other",
            "4",
            "--seed",
            "42",
        ],
        env={"CONFIT_DEBUG": "true"},
    )
    assert result.exit_code == 1
    assert str(result.exception) == (
        "2 validation errors for test_cli.function()\n"
        "-> script.modelA.submodel\n"
        "   field required\n"
        "-> script.modelB\n"
        "   field required"
    )


def test_cli_missing_no_debug(change_test_dir):
    result = runner.invoke(
        app,
        [
            "--modelA.date",
            "2010-10-10",
            "--other",
            "4",
            "--seed",
            "42",
        ],
    )
    assert result.exit_code == 1
    assert (
        "2 validation errors for test_cli.function()\n"
        "-> script.modelA.submodel\n"
        "   field required\n"
        "-> script.modelB\n"
        "   field required"
    ) in str(result.stdout)


def test_cli_merge(change_test_dir):
    result = runner.invoke(
        app,
        [
            "--config",
            "config.cfg",
            "--config",
            "config-add.cfg",
            "--modelA.date",
            "2010-10-10",
            "--seed",
            "42",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Other: 99" in result.stdout


app_with_meta = Cli(pretty_exceptions_show_locals=False)


@app_with_meta.command(name="script")
def app_with_meta_function(
    modelA: BigModel, modelB: BigModel, other: int, seed: int, config_meta=None
):
    assert modelA.submodel is modelB.submodel
    assert modelA.date == datetime.date(2010, 10, 10)

    config = config_meta["resolved_config"]

    assert config["modelA"].submodel.value == 12
    print("Other:", other)


def test_cli_working_with_meta(change_test_dir):
    result = runner.invoke(
        app_with_meta,
        [
            "--config",
            "config.cfg",
            "--modelA.date",
            "2010-10-10",
            "--other",
            "4",
            "--seed",
            "42",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Other: 4" in result.stdout


def test_fail_cli_shorthands(change_test_dir):
    result = runner.invoke(
        app,
        [
            "--modelA.date",
            "2010-10-10",
            "--other",
            "4",
            "-seed",
            "42",
        ],
    )
    assert result.exit_code == 1
    assert "shorthand" in result.stdout


bool_app = Cli(pretty_exceptions_show_locals=False)


@bool_app.command(name="script")
def bool_app_function(bool_value: bool, str_value: str):
    print("BOOL:", bool_value)
    print("STR:", str_value)


# fail if not PYDANTIC_V1


@pytest.mark.xfail(not PYDANTIC_V1, reason="pydantic v2 fails when casting bool to str")
def test_cli_bool(change_test_dir):
    result = runner.invoke(
        bool_app,
        [
            "--bool_value",
            "--str_value",
        ],
    )
    assert result.exit_code == 0, result.stdout
    # CLI detects bool param for other which is converted to 1 since we expect an int
    assert "BOOL: True" in result.stdout
    assert "STR: True" in result.stdout


def test_fail_override(change_test_dir):
    result = runner.invoke(
        bool_app,
        ["--section.int_value", "3"],
    )
    assert result.exit_code == 1
    # CLI detects bool param for other which is converted to 1 since we expect an int
    assert "does not match any existing section in config" in str(result.exception)
