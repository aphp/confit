import inspect
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

from typer import Context, Typer, colors, secho
from typer.core import TyperCommand
from typer.models import CommandFunctionType, Default

from .config import Config, merge_from_disk
from .errors import ConfitValidationError, LegacyValidationError, patch_errors
from .registry import validate_arguments
from .utils.random import set_seed
from .utils.settings import is_debug
from .utils.xjson import loads


def parse_overrides(args: List[str]) -> Dict[str, Any]:
    """
    Parse the overrides from the command line into a dictionary
    of key-value pairs.

    Parameters
    ----------
    args: List[str]
        The arguments to parse

    Returns
    -------
    Dict[str, Any]
        The parsed overrides as a dictionary
    """
    result = {}
    while args:
        opt = args.pop(0)
        err = f"Invalid config override '{opt}'"
        if opt.startswith("--"):  # new argument
            opt = opt.replace("--", "")
            if "=" in opt:  # we have --opt=value
                opt, value = opt.split("=", 1)
            else:
                if not args or args[0].startswith("--"):  # flag with no value
                    value = "true"
                else:
                    value = args.pop(0)
            opt = opt.replace("-", "_")
            result[opt] = loads(value)
        else:
            secho(f"{err}: doesn't support shorthands", fg=colors.RED)
            exit(1)
    return result


class Cli(Typer):
    """
    Custom Typer object that:

    - validates a command parameters before executing it
    - accepts a configuration file describing the parameters
    - automatically instantiates parameters given a dictionary when type hinted
    """

    def command(  # noqa
        self,
        name,
        *,
        cls: Optional[Type[TyperCommand]] = None,
        context_settings: Optional[Dict[Any, Any]] = None,
        help: Optional[str] = None,
        epilog: Optional[str] = None,
        short_help: Optional[str] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: Union[str, None] = Default(None),
        registry: Any = None,
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        typer_command = super().command(
            name=name,
            cls=cls,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            no_args_is_help=no_args_is_help,
            hidden=hidden,
            deprecated=deprecated,
            rich_help_panel=rich_help_panel,
            context_settings={
                **(context_settings or {}),
                "ignore_unknown_options": True,
                "allow_extra_args": True,
            },
        )

        def wrapper(fn):
            validated = validate_arguments(fn)

            @typer_command
            def command(ctx: Context, config: Optional[List[Path]] = None):
                config_path = config

                has_meta = _fn_has_meta(fn)
                if config_path:
                    config, name_from_file = merge_from_disk(config_path)
                else:
                    config = Config({name: {}})
                model_fields = (
                    validated.model.model_fields
                    if hasattr(validated.model, "model_fields")
                    else validated.model.__fields__
                )
                for k, v in parse_overrides(ctx.args).items():
                    if "." not in k:
                        parts = (name, k)
                    else:
                        parts = k.split(".")
                        if parts[0] in model_fields and parts[0] not in config:
                            parts = (name, *parts)
                    current = config
                    if parts[0] not in current:
                        raise Exception(
                            f"{k} does not match any existing section in config"
                        )
                    for part in parts[:-1]:
                        current = current.setdefault(part, Config())
                    current[parts[-1]] = v
                try:
                    resolved_config = Config(config[name]).resolve(
                        registry=registry, root=config
                    )
                    default_seed = model_fields.get("seed")
                    if default_seed is not None:
                        default_seed = default_seed.get_default()
                    seed = config.get(name, {}).get("seed", default_seed)
                    if seed is not None:
                        set_seed(seed)
                    if has_meta:
                        config_meta = dict(
                            config_path=config_path,
                            resolved_config=resolved_config,
                            unresolved_config=config,
                        )
                        return validated(
                            **resolved_config,
                            config_meta=config_meta,
                        )
                    else:
                        return validated(**resolved_config)
                except (LegacyValidationError, ConfitValidationError) as e:
                    e.raw_errors = patch_errors(
                        e.raw_errors,
                        (name,),
                    )
                    if is_debug() or e.__cause__ is not None:
                        raise e
                    try:
                        import rich

                        console = rich.console.Console(stderr=True)
                        console.print("Validation error:", style="red", end=" ")
                        console.print(str(e))
                    except ImportError:  # pragma: no cover
                        print("Validation error:", file=sys.stderr, end=" ")
                        print(str(e), file=sys.stderr)
                    sys.exit(1)
                except KeyboardInterrupt as e:  # pragma: no cover
                    raise Exception("Interrupted by user") from e

            return validated

        return wrapper


def _fn_has_meta(fn):
    return "config_meta" in inspect.signature(fn).parameters
