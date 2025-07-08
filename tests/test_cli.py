import datetime
import random

import pytest
from typer.testing import CliRunner

from confit import Cli, Config, Registry
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


seed_app = Cli(pretty_exceptions_show_locals=False)


@registry.factory.register("randmodel")
class RandModel:
    def __init__(self):
        self.value = random.randint(0, 100000)


@seed_app.command(name="seed", registry=registry)
def print_seed(model: RandModel, seed: int):
    print("Value:", model.value)


def test_seed(change_test_dir):
    """Checks that the program running twice will generate the same random numbers"""
    result = runner.invoke(seed_app, ["--seed", "42", "--model.@factory", "randmodel"])
    assert result.exit_code == 0, result.stdout
    first_seed = int(result.stdout.split(":")[1].strip())

    result = runner.invoke(seed_app, ["--seed", "42", "--model.@factory", "randmodel"])
    assert result.exit_code == 0, result.stdout
    second_seed = int(result.stdout.split(":")[1].strip())
    print(first_seed, second_seed)

    assert first_seed == second_seed


# Tests for default_config parameter
default_config_app = Cli(pretty_exceptions_show_locals=False)

default_config = Config(
    {
        "script": {
            "modelA": {
                "@factory": "bigmodel",
                "date": "2020-01-01",
                "submodel": {
                    "@factory": "submodel",
                    "value": 42,
                    "desc": "default description",
                },
            },
            "modelB": {
                "@factory": "bigmodel",
                "date": "2020-02-02",
                "submodel": {
                    "@factory": "submodel",
                    "value": 24,
                    "desc": "another default",
                },
            },
            "other": 100,
            "seed": 1337,
        }
    }
)


@default_config_app.command(
    name="script", registry=registry, default_config=default_config
)
def function_with_default_config(
    modelA: BigModel, modelB: BigModel, other: int, seed: int
):
    print(f"ModelA date: {modelA.date}")
    print(f"ModelA value: {modelA.submodel.value}")
    print(f"ModelB date: {modelB.date}")
    print(f"ModelB value: {modelB.submodel.value}")
    print(f"Other: {other}")
    print(f"Seed: {seed}")


def test_cli_with_default_config():
    """Test that default_config is used when no config file is provided"""
    result = runner.invoke(default_config_app, [])
    assert result.exit_code == 0, result.stdout
    assert "ModelA date: 2020-01-01" in result.stdout
    assert "ModelA value: 42.0" in result.stdout
    assert "ModelB date: 2020-02-02" in result.stdout
    assert "ModelB value: 24.0" in result.stdout
    assert "Other: 100" in result.stdout
    assert "Seed: 1337" in result.stdout


def test_cli_with_default_config_override():
    """Test that command line overrides work with default_config"""
    result = runner.invoke(
        default_config_app,
        ["--other", "200", "--modelA.submodel.value", "99"],
    )
    assert result.exit_code == 0, result.stdout
    assert "ModelA value: 99.0" in result.stdout
    assert "Other: 200" in result.stdout
    # Other values should remain from default config
    assert "ModelA date: 2020-01-01" in result.stdout
    assert "ModelB date: 2020-02-02" in result.stdout


# Tests for merge_with_default_config parameter
merge_config_app = Cli(pretty_exceptions_show_locals=False)

base_config = Config(
    {
        "script": {
            "modelA": {
                "@factory": "bigmodel",
                "date": "2019-01-01",
                "submodel": {
                    "@factory": "submodel",
                    "value": 10,
                    "desc": "base description",
                },
            },
            "other": 50,
            "seed": 999,
        }
    }
)


@merge_config_app.command(
    name="script",
    registry=registry,
    default_config=base_config,
    merge_with_default_config=True,
)
def function_with_merge_config(
    modelA: BigModel, modelB: BigModel, other: int, seed: int
):
    print(f"ModelA date: {modelA.date}")
    print(f"ModelA value: {modelA.submodel.value}")
    print(f"ModelA desc: {modelA.submodel.desc}")
    print(f"ModelB date: {modelB.date}")
    print(f"ModelB value: {modelB.submodel.value}")
    print(f"Other: {other}")
    print(f"Seed: {seed}")


def test_cli_merge_with_default_config(tmp_path):
    """Test that merge_with_default_config merges provided config with default"""
    # Create a temporary config file that only partially defines the configuration
    config_file = tmp_path / "partial_config.cfg"
    config_file.write_text("""
[script]
other = 75

[script.modelB]
@factory = "bigmodel"
date = "2021-12-31"

[script.modelB.submodel]
@factory = "submodel"
value = 33
desc = "partial config"
""")

    result = runner.invoke(merge_config_app, ["--config", str(config_file)])
    assert result.exit_code == 0, result.stdout

    # Values from config file should override default
    assert "Other: 75" in result.stdout
    assert "ModelB date: 2021-12-31" in result.stdout
    assert "ModelB value: 33.0" in result.stdout

    # Values not in config file should come from default
    assert "ModelA date: 2019-01-01" in result.stdout
    assert "ModelA value: 10.0" in result.stdout
    assert "ModelA desc: base description" in result.stdout
    assert "Seed: 999" in result.stdout


def test_cli_merge_with_default_config_no_merge_flag(tmp_path):
    """Test that without merge_with_default_config=True, default config is not merged"""
    no_merge_app = Cli(pretty_exceptions_show_locals=False)

    @no_merge_app.command(
        name="script",
        registry=registry,
        default_config=base_config,
        merge_with_default_config=False,  # Explicitly set to False
    )
    def function_no_merge(modelA: BigModel, modelB: BigModel, other: int, seed: int):
        print(f"ModelA date: {modelA.date}")
        print(f"Other: {other}")

    # Create a config file that doesn't have modelA defined
    config_file = tmp_path / "incomplete_config.cfg"
    config_file.write_text("""
[script]
other = 80
seed = 123

[script.modelB]
@factory = "bigmodel"
date = "2022-01-01"

[script.modelB.submodel]
@factory = "submodel"
value = 44
""")

    result = runner.invoke(no_merge_app, ["--config", str(config_file)])
    # This should fail because modelA is not defined and we're not merging
    # with default
    assert result.exit_code == 1
    assert (
        "field required" in str(result.stdout)
        or "field required" in str(result.exception)
        or "modelA" in str(result.exception)
    )


def test_cli_default_config_with_command_line_override():
    """Test that command line arguments can override specific parts of default config"""
    result = runner.invoke(
        default_config_app,
        [
            "--modelA.date",
            "2023-06-15",
            "--modelB.submodel.desc",
            "overridden description",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "ModelA date: 2023-06-15" in result.stdout
    # ModelB desc is not printed in this function
    assert "overridden description" not in result.stdout
