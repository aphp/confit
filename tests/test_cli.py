import datetime
import io
import os
import random
import re
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import List, Literal, Optional, Union

import pytest

from confit import Cli, Config, Registry
from confit.registry import PYDANTIC_V1, RegistryCollection, set_default_registry


@dataclass
class CliResult:
    exit_code: int
    stdout: str
    stderr: str
    exception: Exception | None = None

    @property
    def output(self):
        return self.stdout + self.stderr


class CliRunner:
    def invoke(self, app, args, env=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        previous_env = os.environ.copy()
        if env is not None:
            os.environ.update(env)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                app.main(args=list(args))
            return CliResult(0, stdout.getvalue(), stderr.getvalue())
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            return CliResult(code, stdout.getvalue(), stderr.getvalue(), e)
        except Exception as e:
            return CliResult(1, stdout.getvalue(), stderr.getvalue(), e)
        finally:
            os.environ.clear()
            os.environ.update(previous_env)


runner = CliRunner()


def result_text(result):
    return "\n".join(
        str(part)
        for part in (result.output, result.stdout, result.stderr, result.exception)
        if part
    )


def make_multi_command_app():
    multi_app = Cli(pretty_exceptions_show_locals=False)

    @multi_app.command(name="first")
    def first(value: int = 1):
        print(f"first: {value}")

    @multi_app.command(name="second")
    def second(value: int = 2):
        print(f"second: {value}")

    return multi_app


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class registry(RegistryCollection):
    factory = Registry(("test_cli", "factory"), entry_points=True)


set_default_registry(registry)


class CustomClass:
    pass


class LinkedHelpModel:
    def __init__(self, value: int, label: str = "default"):
        """
        Linked help target.

        Parameters
        ----------
        value : int
            Nested value.
        label : str
            Nested label.
        """


def linked_help_function(value: int, enabled: bool = True):
    """
    Linked function help target.

    Parameters
    ----------
    value : int
        Function value.
    enabled : bool
        Whether it is enabled.
    """


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


def test_cli_call_delegates_to_main():
    call_app = Cli(pretty_exceptions_show_locals=False)

    @call_app.command(name="script")
    def call_command():
        print("called")

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        call_app([])

    assert stdout.getvalue() == "called\n"


def test_cli_explicit_command_in_multi_command_app():
    multi_app = make_multi_command_app()
    result = runner.invoke(multi_app, ["first", "--value", "3"])

    assert result.exit_code == 0, result_text(result)
    assert result.stdout == "first: 3\n"


def test_cli_multi_command_top_level_help():
    multi_app = make_multi_command_app()
    result = runner.invoke(multi_app, ["--help"])

    assert result.exit_code == 0
    assert "Commands:\n  first\n  second" in result.stdout


def test_cli_multi_command_without_command_args_shows_help():
    multi_app = make_multi_command_app()
    result = runner.invoke(multi_app, ["first"])

    assert result.exit_code == 0
    assert "Commands:\n  first\n  second" in result.stdout


def test_cli_accepts_config_equals_path(change_test_dir):
    result = runner.invoke(
        app,
        [
            "--config=config.cfg",
            "--modelA.date",
            "2010-10-10",
            "--other",
            "4",
            "--seed=42",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Other: 4" in result.stdout


def test_cli_help_formats_common_annotations():
    help_app = Cli(pretty_exceptions_show_locals=False)

    @help_app.command(name="script")
    def typed_command(
        untyped,
        maybe: Optional[int] = None,
        choice: Literal["small", "large"] = "small",
        numbers: list[int] | None = None,
        lookup: dict[str, int] | None = None,
        legacy_values: List = None,
        either: Union[int, str] = 1,
    ):
        pass

    result = runner.invoke(help_app, ["--help"])

    help_text = strip_ansi(result.stdout)
    assert result.exit_code == 0
    assert "--untyped <Any>" in help_text
    assert "--maybe <Optional[int]> (default: None)" in help_text
    assert "--choice <Literal['small', 'large']> (default: 'small')" in help_text
    assert "--numbers <Optional[list[int]]> (default: None)" in help_text
    assert "--lookup <Optional[dict[str, int]]> (default: None)" in help_text
    assert "--lookup.<field> VALUE" in help_text
    assert "--legacy_values <list> (default: None)" in help_text
    assert "--either <Union[int, str]> (default: 1)" in help_text


def test_cli_help_expands_linked_docstrings():
    linked_app = Cli(pretty_exceptions_show_locals=False)

    @linked_app.command(name="script")
    def linked_command(model: dict, direct: dict):
        pass

    linked_app.commands["script"]["fn"].__doc__ = f"""
    Run linked help.

    Parameters
    ----------
    model : dict
        Model settings.

        ??? note
            ::: {__name__}.LinkedHelpModel
        More model details.
    direct : dict
        ::: {__name__}.linked_help_function
    """

    result = runner.invoke(linked_app, ["--help"])

    help_text = strip_ansi(result.stdout)
    assert result.exit_code == 0
    assert f"Details for {__name__}.LinkedHelpModel:" in help_text
    assert f"Details for {__name__}.linked_help_function:" in help_text
    assert "More model details." in help_text
    assert "--model.value <int>" in help_text
    assert "--model.label <str>" in help_text
    assert "--direct.value <int>" in help_text
    assert "--direct.enabled <bool>" in help_text
    assert "???" not in help_text
    assert ":::" not in help_text


def test_cli_help_shows_config_overrides():
    result = runner.invoke(app, ["--help"])
    help_text = strip_ansi(result.stdout)
    assert result.exit_code == 0, result.stdout
    assert "\x1b[1m--modelA\x1b[0m" in result.stdout
    assert "Confit overrides:" not in help_text
    assert "--config <Path>" in help_text
    assert "Load a config file to fill in the following params" in help_text
    assert "--modelA <BigModel>" in help_text
    assert "--modelA.<field> VALUE" in help_text
    assert "--other <int>" in help_text
    assert "v__duplicate_kwargs" not in help_text


def test_edsnlp_train_help_shows_config_overrides():
    try:
        edsnlp_train = pytest.importorskip("edsnlp.train")
        from edsnlp.core.registries import registry as edsnlp_registry

        set_default_registry(edsnlp_registry)
        result = runner.invoke(edsnlp_train.app, ["--help"])
    finally:
        set_default_registry(registry)

    help_text = strip_ansi(result.stdout)
    assert result.exit_code == 0, result.stdout
    assert "\x1b[1m--train_data\x1b[0m" in result.stdout
    assert "Train a pipeline.\n\nParameters" in help_text
    assert "Confit overrides:" not in help_text
    assert "--config <Path>" in help_text
    assert "Load a config file to fill in the following params" in help_text
    assert "--nlp <Pipeline>" in help_text
    assert "--nlp.<field> VALUE" in help_text
    assert "--config <Path>\n    Load a config file" in help_text
    assert "--nlp <Pipeline>\n    The pipeline" in help_text
    assert "--nlp.<field> VALUE\n\n  --train_data" in help_text
    assert "--train_data <AsList[TrainingData]>" in help_text
    assert "--train_data.data <Stream>" in help_text
    assert "--train_data.batch_size <BatchSizeArg>" in help_text
    assert "--max_steps <int> (default: 1000)" in help_text
    assert "--seed <int> (default: 42)" in help_text
    assert "--validation_interval <Optional[int]> (default: None)" in help_text
    assert "--validation_interval.<field> VALUE" not in help_text
    assert "Details for edsnlp.training.trainer.TrainingData:" in help_text
    assert "A training data object." in help_text
    assert "Details for edsnlp.training.optimizer.ScheduledOptimizer:" in help_text
    assert "Wrapper optimizer that supports schedules" in help_text
    assert "Base class for all optimizers." not in help_text
    assert "Details for edsnlp.training.trainer.GenericScorer:" in help_text
    assert "--scorer.batch_size <Union[int, str]>" in help_text
    assert "--scorer.speed <bool>" in help_text
    assert "--scorer.autocast <Union[bool, Any]>" in help_text
    assert "--scorer.metrics.<field> <Any>" in help_text
    assert "--scorer.<field> VALUE" not in help_text
    assert "Returns" not in help_text
    assert ":::" not in help_text
    assert "only_parameters" not in help_text
    assert "v__duplicate_kwargs" not in help_text


def test_edsnlp_train_missing_pipe_parameter_error(tmp_path):
    try:
        edsnlp_train = pytest.importorskip("edsnlp.train")
        from edsnlp.core.registries import registry as edsnlp_registry

        set_default_registry(edsnlp_registry)
        config_path = tmp_path / "missing-pipe-param.yml"
        config_path.write_text(
            """
nlp:
  '@core': pipeline
  lang: eds
  components:
    qualifier:
      '@factory': eds.span_classifier
      attributes: [ 'negation' ]
      span_getter: [ 'ents' ]

train_data: []

train:
  nlp: ${nlp}
  train_data: ${train_data}
  max_steps: 1
  cpu: true
  logger: false
"""
        )

        result = runner.invoke(edsnlp_train.app, ["--config", str(config_path)])
    finally:
        set_default_registry(registry)

    text = result_text(result)
    assert result.exit_code == 1
    assert "Validation error: 1 validation error for " in text
    assert "TrainableSpanClassifier()" in text
    assert "-> train.nlp.components.qualifier.embedding" in text
    assert "field required" in text


def test_edsnlp_train_optimizer_parameter_error(tmp_path):
    try:
        edsnlp_train = pytest.importorskip("edsnlp.train")
        from edsnlp.core.registries import registry as edsnlp_registry

        set_default_registry(edsnlp_registry)
        config_path = tmp_path / "bad-optimizer-param.yml"
        config_path.write_text(
            f"""
nlp:
  '@core': pipeline
  lang: eds

optimizer:
  '@core': optimizer !draft
  optim: AdamW
  groups:
    '.*':
      lr: 1e-3
  total_steps: invalid

train_data: []

train:
  nlp: ${{nlp}}
  train_data: ${{train_data}}
  max_steps: 1
  cpu: true
  logger: false
  output_dir: {str(tmp_path / "train-artifacts")!r}
  optimizer: ${{optimizer}}
"""
        )

        result = runner.invoke(edsnlp_train.app, ["--config", str(config_path)])
    finally:
        set_default_registry(registry)

    text = result_text(result)
    assert result.exit_code == 1
    assert "Validation error: 1 validation error for ScheduledOptimizer()" in text
    assert "-> train.optimizer.total_steps" in text
    assert "input should be a valid integer" in text
    assert "got 'invalid' (str)" in text


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
    text = result_text(result)
    assert ("2 validation errors for ") in text
    assert (
        "-> script.modelA.submodel\n"
        "   field required\n"
        "-> script.modelB\n"
        "   field required"
    ) in text


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
    text = result_text(result)
    assert "field required" in text or "modelA" in text


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
