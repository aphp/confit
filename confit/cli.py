import importlib
import inspect
import re
import sys
from pathlib import Path
from types import UnionType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
)

from .config import Config, merge_from_disk
from .errors import ConfitValidationError, LegacyValidationError, patch_errors
from .registry import validate_arguments
from .utils.random import set_seed
from .utils.settings import is_debug
from .utils.xjson import loads

BOLD = "\033[1m"
RESET = "\033[0m"


def parse_overrides(args: List[str]) -> Dict[str, Any]:
    """
    Parse the overrides from the command line into a dictionary
    of key value pairs.

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
        if opt.startswith("--"):
            opt = opt.replace("--", "")
            if "=" in opt:
                opt, value = opt.split("=", 1)
            else:
                if not args or args[0].startswith("--"):
                    value = "true"
                else:
                    value = args.pop(0)
            opt = opt.replace("-", "_")
            result[opt] = loads(value)
        else:
            print(f"{err}: doesn't support shorthands")
            exit(1)
    return result


class Cli:
    """
    Command line application for Confit commands that:

    - validates a command parameters before executing it
    - accepts a configuration file describing the parameters
    - automatically instantiates parameters given a dictionary when type hinted
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self.commands = {}

    # User code calls this as a decorator to register one command.
    # The stored metadata is used by main.
    def command(  # noqa
        self,
        name,
        *,
        cls: Optional[Type] = None,
        context_settings: Optional[Dict[Any, Any]] = None,
        help: Optional[str] = None,
        epilog: Optional[str] = None,
        short_help: Optional[str] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        rich_help_panel: Union[str, None] = None,
        registry: Any = None,
        default_config: Optional[Config] = None,
        merge_with_default_config: bool = False,
    ) -> Callable[[Callable], Callable]:
        def wrapper(fn):
            validated = validate_arguments(fn)
            # main will read this record to resolve config values and call the function.
            self.commands[name] = {
                "fn": fn,
                "validated": validated,
                "help": help,
                "registry": registry,
                "default_config": default_config,
                "merge_with_default_config": merge_with_default_config,
            }
            return validated

        return wrapper

    def __call__(self, args: Optional[List[str]] = None):
        return self.main(args=args)

    # Script entry points call this to handle argv.
    # It either prints help or executes the selected command.
    def main(self, args: Optional[List[str]] = None):
        args = list(sys.argv[1:] if args is None else args)
        commands_help = "\n".join(
            ["Commands:", *(f"  {name}" for name in self.commands)]
        )

        # The command name is optional for single command apps.
        # args is left with only config paths and overrides.
        if args and args[0] in self.commands:
            name = args.pop(0)
            command = self.commands[name]
        elif len(self.commands) == 1:
            name = next(iter(self.commands))
            command = self.commands[name]
        elif args and args[0] in {"--help", "-h"}:
            print(commands_help)
            raise SystemExit(0)
        else:
            raise Exception("Missing command")

        if not args and len(self.commands) > 1:
            print(commands_help)
            raise SystemExit(0)

        if any(arg in {"--help", "-h"} for arg in args):
            print(add_config_overrides_help(command["help"], command["fn"]))
            raise SystemExit(0)

        # config_path is passed to merge_from_disk.
        # overrides is passed to parse_overrides and merged under the command section.
        config_path = []
        overrides = []
        while args:
            arg = args.pop(0)
            if arg == "--config":
                if not args:
                    raise Exception("--config expects a path")
                config_path.append(Path(args.pop(0)))
            elif arg.startswith("--config="):
                config_path.append(Path(arg.split("=", 1)[1]))
            else:
                overrides.append(arg)

        return self.run_command(name, command, config_path or None, overrides)

    # main calls this with paths and overrides parsed from argv.
    # The returned value is the wrapped command result.
    def run_command(self, name, command, config_path, overrides):
        fn = command["fn"]
        validated = command["validated"]
        registry = command["registry"]
        default_config = command["default_config"]
        merge_with_default_config = command["merge_with_default_config"]

        if config_path:
            config, _name_from_file = merge_from_disk(config_path)
        elif default_config is not None:
            config = default_config
        else:
            config = Config({name: {}})
        if default_config is not None and merge_with_default_config:
            config = Config(default_config).merge(config)

        # model_fields tells whether dotted overrides start at the command section.
        # For example model.date becomes script.model.date when model is a parameter.
        model_fields = (
            validated.model.model_fields
            if hasattr(validated.model, "model_fields")
            else validated.model.__fields__
        )
        for key, value in parse_overrides(overrides).items():
            if "." not in key:
                parts = (name, key)
            else:
                parts = key.split(".")
                if parts[0] in model_fields and parts[0] not in config:
                    parts = (name, *parts)
            current = config
            if parts[0] not in current:
                raise Exception(f"{key} does not match any existing section in config")
            for part in parts[:-1]:
                current = current.setdefault(part, Config())
            current[parts[-1]] = value

        try:
            default_seed = model_fields.get("seed")
            if default_seed is not None:
                default_seed = default_seed.get_default()
            seed = Config.resolve(
                config.get(name, {}).get("seed", default_seed),
                registry=registry,
                root=config,
            )
            if seed is not None:
                set_seed(seed)
            resolved_config = Config(config[name]).resolve(
                registry=registry,
                root=config,
            )
            if "config_meta" in inspect.signature(fn).parameters:
                config_meta = dict(
                    config_path=config_path,
                    resolved_config=resolved_config,
                    unresolved_config=config,
                )
                return validated(**resolved_config, config_meta=config_meta)
            return validated(**resolved_config)
        except (LegacyValidationError, ConfitValidationError) as e:
            e.raw_errors = patch_errors(e.raw_errors, (name,))
            if is_debug() or e.__cause__ is not None:
                raise e
            print("Validation error:", str(e))
            sys.exit(1)
        except KeyboardInterrupt as e:  # pragma: no cover
            raise Exception("Interrupted by user") from e


# command stores this plain text and main prints it for help requests.
def add_config_overrides_help(help_text, fn):
    signature = inspect.signature(fn)
    params = {
        param.name: param
        for param in signature.parameters.values()
        if param.name != "config_meta"
        and param.kind
        not in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }
    }
    base_help = help_text if help_text is not None else inspect.getdoc(fn)
    if base_help:
        return format_cli_help_text(base_help, params)

    lines = [
        "Parameters:",
        "----------",
        format_config_parameter(),
    ]
    for param in params.values():
        lines.append("")
        lines.append(format_cli_parameter(param))
        if annotation_allows_fields(param.annotation):
            lines.append(f"    {BOLD}--{param.name}.<field>{RESET} VALUE")

    return "\n".join(lines)


# The top level help builder calls this to turn a docstring into option help.
# prefix is used when rendering nested object fields like scorer batch size.
def format_cli_help_text(
    help_text,
    params,
    prefix=None,
    include_parameters_heading=True,
):
    from griffe import Docstring, DocstringSectionKind, Parser

    result = []
    help_text = re.sub(
        r"^(\s*)([A-Za-z_]\w*)\s*:\s+(.+)$",
        r"\1\2 : \3",
        help_text,
        flags=re.MULTILINE,
    )
    for section in Docstring(help_text, lineno=1).parse(
        Parser.numpy,
        warnings=False,
        warn_unknown_params=False,
        warn_missing_types=False,
    ):
        if section.kind is DocstringSectionKind.text:
            result.extend(
                sanitize_help_lines(
                    section.value.splitlines(),
                    base_indent=0,
                    prefix=prefix,
                )
            )
            continue
        if section.kind is DocstringSectionKind.parameters:
            if result and result[-1]:
                result.append("")
            param_lines = []
            for doc_param in section.value:
                param = params.get(doc_param.name)
                if param is None:
                    continue

                if param_lines:
                    param_lines.append("")

                # param_lines is the rendered help for this Parameters section.
                # Nested object docs use prefix and omit constructor defaults.
                param_lines.append(
                    format_cli_parameter(
                        param,
                        annotation=doc_param.annotation,
                        prefix=prefix,
                        include_default=prefix is None,
                    )
                )
                param_lines.extend(
                    sanitize_help_lines(
                        doc_param.description.splitlines(),
                        base_indent=4,
                        prefix=parameter_option_path(param, prefix),
                    )
                )
                if (
                    prefix is None
                    and annotation_allows_fields(param.annotation)
                    and not re.search(
                        r"^\s*:::\s+\S+",
                        doc_param.description,
                        flags=re.MULTILINE,
                    )
                ):
                    # Use a generic field hint only when no linked object docs exist.
                    # Linked object docs produce concrete nested fields instead.
                    param_lines.append("")
                    param_lines.append(f"    {BOLD}--{param.name}.<field>{RESET} VALUE")
            if include_parameters_heading:
                result.extend(
                    [
                        "Parameters",
                        "----------",
                        format_config_parameter(),
                        "",
                        *param_lines,
                    ]
                )
            else:
                result.extend(param_lines)
            continue
        if section.kind in {
            DocstringSectionKind.returns,
            DocstringSectionKind.yields,
        }:
            continue

    return "\n".join(result)


def format_config_parameter():
    return "\n".join(
        [
            f"  {BOLD}--config{RESET} <Path>",
            "    Load a config file to fill in the following params. Can be repeated.",
        ]
    )


# The docstring renderer calls this for each option line.
# prefix is the parent path for nested options.
def format_cli_parameter(param, annotation=None, prefix=None, include_default=True):
    option = parameter_option_path(param, prefix)
    annotation = (
        "Any"
        if param.kind is inspect.Parameter.VAR_KEYWORD
        else annotation or format_annotation(param.annotation)
    )
    default = (
        "required"
        if param.default is inspect.Signature.empty
        else f"default: {param.default!r}"
    )
    suffix = "" if not include_default or default == "required" else f" ({default})"
    return f"  {BOLD}--{option}{RESET} <{annotation}>{suffix}"


# Option line rendering and nested help expansion use this to join option paths.
# Var keyword parameters become field placeholders.
def parameter_option_path(param, prefix=None):
    name = param.name
    if param.kind is inspect.Parameter.VAR_KEYWORD:
        name = f"{name}.<field>"
    return name if prefix is None else f"{prefix}.{name}"


# Option line rendering uses this to display compact type names in help output.
def format_annotation(annotation):
    if annotation is inspect.Signature.empty:
        return "Any"
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in {Union, UnionType}:
        non_none_args = tuple(arg for arg in args if arg is not type(None))
        if len(non_none_args) == 1 and len(non_none_args) != len(args):
            return f"Optional[{format_annotation(non_none_args[0])}]"
        return "Union[{}]".format(
            ", ".join(format_annotation(arg) for arg in non_none_args)
        )
    if origin is Literal:
        return "Literal[{}]".format(", ".join(repr(arg) for arg in args))
    if origin is not None:
        name = getattr(origin, "__name__", str(origin).replace("typing.", ""))
        if args:
            return "{}[{}]".format(
                name,
                ", ".join(format_annotation(arg) for arg in args),
            )
        return name
    return getattr(annotation, "__name__", str(annotation).replace("typing.", ""))


# Used by the docstring renderer to decide when a generic field hint is useful.
def annotation_allows_fields(annotation):
    if annotation is inspect.Signature.empty:
        return False

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in {Union, UnionType}:
        args = tuple(arg for arg in args if arg is not type(None))
        return bool(args) and any(annotation_allows_fields(arg) for arg in args)

    if origin is not None:
        if origin in {dict, Dict}:
            return True
        return False

    if getattr(annotation, "__name__", None) == "AsList":
        return False

    return annotation not in {Any, str, int, float, bool, Path, type(None)}


# The docstring renderer passes parameter descriptions here.
# MkDocs object references are expanded into nested options when possible.
def sanitize_help_lines(lines, base_indent, prefix=None):
    result = []
    skipping_indent = None
    replacement = []
    directive_re = re.compile(r"^\s*:::\s+([^\s]+)")

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if skipping_indent is not None:
            match = directive_re.match(line)
            if match is not None:
                # replacement stores expanded object docs until the admonition ends.
                replacement = format_linked_docstring(
                    match.group(1),
                    base_indent,
                    prefix=prefix,
                )
            if not stripped or indent > skipping_indent:
                continue
            if replacement:
                result.extend(replacement)
                replacement = []
            skipping_indent = None

        if stripped.startswith("???"):
            # MkDocs admonitions are omitted from CLI help.
            # Their object directive is expanded if one appears inside.
            skipping_indent = indent
            replacement = []
            continue
        match = directive_re.match(line)
        if match is not None:
            result.extend(
                format_linked_docstring(match.group(1), indent, prefix=prefix)
            )
            continue
        result.append(" " * base_indent + line if line else "")

    if skipping_indent is not None and replacement:
        result.extend(replacement)

    return result


# Called for description cleanup for linked object references in docstrings.
# The returned lines are inserted under the current option description.
def format_linked_docstring(reference, base_indent, prefix=None):
    parts = reference.split(".")
    obj = None
    # A reference can point to an attribute not just a module.
    # Import the longest module prefix then traverse the rest as attributes.
    for index in range(len(parts), 0, -1):
        module_name = ".".join(parts[:index])
        try:
            obj = importlib.import_module(module_name)
        except Exception:
            continue
        for part in parts[index:]:
            try:
                obj = getattr(obj, part)
            except AttributeError:  # pragma: no cover
                obj = None
                break
        if obj is not None:
            break
    if obj is None:  # pragma: no cover
        return []

    # For classes, init usually carries the configurable parameter docstring.
    if inspect.isclass(obj):
        candidates = [
            getattr(obj, "__init__", None),
            obj,
            getattr(obj, "__call__", None),
        ]
    else:
        candidates = [
            obj,
            getattr(obj, "__init__", None),
            getattr(obj, "__call__", None),
        ]
    doc = None
    target = None
    for candidate in candidates:
        doc = inspect.getdoc(candidate)
        if doc and doc != "Call self as a function.":
            target = candidate
            break
    if doc is None:  # pragma: no cover
        return []

    # params is used by the recursive docstring renderer to produce nested paths.
    # Var keyword parameters are shown only for linked objects as field placeholders.
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):  # pragma: no cover
        params = {}
    else:
        params = {
            param.name: param
            for param in signature.parameters.values()
            if param.name not in {"self", "config_meta"}
            and param.kind is not inspect.Parameter.VAR_POSITIONAL
            and (prefix is not None or param.kind is not inspect.Parameter.VAR_KEYWORD)
        }

    indent = " " * base_indent
    lines = [f"{indent}Details for {reference}:", ""]
    formatted = format_cli_help_text(
        doc,
        params,
        prefix=prefix,
        include_parameters_heading=prefix is None,
    )
    for line in formatted.splitlines():
        lines.append(indent + line if line else "")
    return lines
