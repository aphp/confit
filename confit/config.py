import collections.abc
import re
from configparser import ConfigParser
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, TypeVar, Union
from weakref import WeakKeyDictionary

import pydantic_core

from confit.errors import (
    ConfitValidationError,
    CyclicReferenceError,
    ErrorWrapper,
    MissingReference,
    patch_errors,
    remove_lib_from_traceback,
)
from confit.utils.collections import flatten_sections, join_path, split_path
from confit.utils.eval import safe_eval
from confit.utils.settings import is_debug
from confit.utils.xjson import Reference, dumps, loads

RESOLVED_TO_CONFIG = WeakKeyDictionary()

Loc = Tuple[Union[int, str]]
T = TypeVar("T")

ID = r"[^\d\W]\w*"
UNQUOTED_ID = rf"(?<![\'\"\w]){ID}(?![\'\"\w])"
PATH_PART = rf"(?:'{ID}(?:[.]{ID})+'|\"{ID}(?:[.]{ID})+\"|{UNQUOTED_ID})"
PATH = rf"{UNQUOTED_ID}(?:[.]{PATH_PART})*"


class Config(dict):
    """
    The configuration system consists of a supercharged dict, the `Config` class,
    that can be used to read and write to `cfg` files, interpolate variables and
    instantiate components through the registry with some special `@factory` keys.
    A cfg file can be used directly as an input to a CLI-decorated function.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        """
        A new config object can be instantiated either from a dict as a positional
        argument, or from keyword arguments. Only one of these two options can be
        used at a time.

        Parameters
        ----------
        args: Any
        kwargs: Any
        """
        if len(args) == 1 and isinstance(args[0], dict):
            assert len(kwargs) == 0
            kwargs = args[0]
        super().__init__(**kwargs)

    @classmethod
    def from_cfg_str(cls, s: str, resolve: bool = False, registry: Any = None) -> Any:
        """
        Load a config object from a config string

        Parameters
        ----------
        s: Union[str, Path]
            The cfg config string
        resolve
            Whether to resolve sections with '@' keys
        registry
            Optional registry to resolve from.
            If None, the default registry will be used.

        Returns
        -------
        Config
        """
        parser = ConfigParser(interpolation=None)
        parser.optionxform = str
        parser.read_string(s)

        config = Config()

        for section in parser.sections():
            parts = split_path(section)
            current = config
            for part in parts:
                if part not in current:
                    current[part] = current = Config()
                else:
                    current = current[part]

            current.clear()
            errors = []
            for k, v in parser.items(section):
                path = split_path(k)
                for part in path[:-1]:
                    if part not in current:
                        current[part] = current = Config()
                    else:
                        current = current[part]
                try:
                    current[path[-1]] = loads(v)
                except ValueError as e:
                    errors.append(ErrorWrapper(e, loc=path))

            if errors:
                raise ConfitValidationError(errors=errors)

        if resolve:
            return config.resolve(registry=registry)

        return config

    @classmethod
    def from_yaml_str(cls, s: str, resolve: bool = False, registry: Any = None) -> Any:
        import yaml

        class ConfitYamlLoader(yaml.SafeLoader):
            def construct_object(self, x, deep=False):
                if isinstance(x, yaml.ScalarNode):
                    return loads(self.buffer[x.start_mark.index : x.end_mark.index])
                return super().construct_object(x, deep)

        stream = StringIO(s)
        config = Config(yaml.load(stream, Loader=ConfitYamlLoader))
        if resolve:
            return config.resolve(registry=registry)

        return config

    @classmethod
    def from_disk(
        cls, path: Union[str, Path], resolve: bool = False, registry: Any = None
    ) -> "Config":
        """
        Load a config object from a '.cfg' file

        Parameters
        ----------
        path: Union[str, Path]
            The path to the config object
        resolve
            Whether to resolve mappings with '@' keys
        registry
            Optional registry to resolve from.
            If None, the default registry will be used.

        Returns
        -------
        Config
        """
        s = Path(path).read_text(encoding="utf-8")
        path_str = str(path)
        if path_str.endswith(".yaml") or path_str.endswith(".yml"):
            return cls.from_yaml_str(s, resolve=resolve, registry=registry)
        else:
            return cls.from_cfg_str(s, resolve=resolve, registry=registry)

    from_str = from_cfg_str

    def to_disk(self, path: Union[str, Path]):
        """
        Export a config to the disk (usually to a .cfg file)

        Parameters
        ----------
        path: Union[str, path]
        """
        path_str = str(path)
        if path_str.endswith(".yaml") or path_str.endswith(".yml"):
            s = self.to_yaml_str()
        else:
            s = Config.to_str(self)
        Path(path).write_text(s, encoding="utf-8")

    def serialize(self: Any):
        """
        Try to convert non-serializable objects using the RESOLVED_TO_CONFIG object
        back to their original catalogue + params form

        We try to preserve referential equalities between non dict/list/tuple
        objects by serializing subsequent references to the same object as references
        to its first occurrence in the tree.

        ```python
        a = A()  # serializable object
        cfg = {"a": a, "b": a}
        print(Config.serialize(cfg))
        # Out: {"a": {...}, "b": Reference("a")}
        ```

        Returns
        -------
        Config
        """
        refs = {}

        # Temp memory to avoid objects being garbage collected
        mem = []

        def is_simple(o):
            return o is None or isinstance(o, (str, int, float, bool, Reference))

        def rec(o: Any, path: Loc = ()):
            if id(o) in refs:
                return refs[id(o)]
            if is_simple(o):
                return o
            if isinstance(o, collections.abc.Mapping):
                items = sorted(
                    o.items(),
                    key=lambda x: 1
                    if (
                        is_simple(x[1])
                        or isinstance(x[1], (collections.abc.Mapping, list, tuple))
                    )
                    else 0,
                )
                serialized = {k: rec(v, (*path, k)) for k, v in items}
                serialized = {k: serialized[k] for k in o.keys()}
                mem.append(o)
                refs[id(o)] = Reference(join_path(path))
                if isinstance(o, Config):
                    serialized = Config(serialized)
                return serialized
            if isinstance(o, (list, tuple)):
                mem.append(o)
                refs[id(o)] = Reference(join_path(path))
                return type(o)(rec(v, (*path, i)) for i, v in enumerate(o))
            cfg = None
            try:
                cfg = (cfg or Config()).merge(RESOLVED_TO_CONFIG[o])
            except (KeyError, TypeError):
                pass
            try:
                cfg = (cfg or Config()).merge(o.cfg)
            except (AttributeError, TypeError):
                pass
            if cfg is not None:
                mem.append(o)
                refs[id(o)] = Reference(join_path(path))
                return rec(cfg, path)
            try:
                return pydantic_core.to_jsonable_python(o)
            except Exception:
                raise TypeError(f"Cannot dump {o!r} at {join_path(path)}")

        return rec(self)

    def to_cfg_str(self):
        """
        Export a config to a string in the cfg format
        by serializing it first

        Returns
        -------
        str
        """
        additional_sections = {}

        prepared = flatten_sections(Config.serialize(self))
        prepared.update(flatten_sections(additional_sections))

        parser = ConfigParser(interpolation=None)
        parser.optionxform = str
        for section_name, section in prepared.items():
            parser.add_section(section_name)
            parser[section_name].update(
                {join_path((k,)): dumps(v) for k, v in section.items()}
            )
        s = StringIO()
        parser.write(s)
        return s.getvalue()

    def to_yaml_str(self):
        import yaml

        class ConfitYamlDumper(yaml.SafeDumper):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def represent_ref(self, node):
                return super().represent_scalar("tag:yaml.org,2002:str", str(node))

            def represent_str(self, data):
                node = super().represent_scalar("tag:yaml.org,2002:str", data)
                if set(",'\"{}[]$") & set(data):
                    # node.value = dumps(data)
                    node.style = "'" if data.count('"') > data.count("'") else '"'
                return node

            yaml_representers = {
                **yaml.SafeDumper.yaml_representers,
                Config: yaml.SafeDumper.represent_dict,
                Reference: represent_ref,
                str: represent_str,
            }

        return yaml.dump(
            self.serialize(), Dumper=ConfitYamlDumper, sort_keys=False, indent=4
        )

    to_str = to_cfg_str

    def resolve(self, deep=True, registry: Any = None, root: Mapping = None) -> Any:
        """
        Resolves the parts of the nested config object with @ variables using
        a registry, and then interpolate references in the config.

        Parameters
        ----------
        deep: bool
            Should we resolve deeply
        registry:
            Registry to use when resolving
        root: Mapping
            The root of the config tree. Used for resolving references.

        Returns
        -------
        Union[Config, Any]
        """
        if root is None:
            root = self

        if registry is None:
            from .registry import get_default_registry

            registry = get_default_registry()
        resolved_locs = {}
        seen_locs = set()

        def resolve_reference(ref: Reference) -> Any:
            pat = re.compile(PATH + ":?")

            def replace(match: re.Match):
                start = match.start()
                if start > 0 and ref.value[start - 1] == ":":
                    return match.group()

                path = match.group()
                parts = split_path(path.rstrip(":"))
                try:
                    return local_names[parts] + ("." if path.endswith(":") else "")
                except KeyError:
                    raise KeyError(path)

            local_leaves = {}
            local_names = {}
            for match in pat.finditer(ref.value):
                start = match.start()
                if start > 0 and ref.value[start - 1] == ":":
                    continue
                path = match.group()
                parts = split_path(path.rstrip(":"))
                current = root
                for part in parts:
                    current = current[part]
                if id(current) not in resolved_locs:
                    resolved = rec(current, parts)
                else:
                    resolved = resolved_locs[id(current)]
                local_names[parts] = f"var_{len(local_leaves)}"
                local_leaves[f"var_{len(local_leaves)}"] = resolved

            replaced = pat.sub(replace, ref.value)

            res = safe_eval(replaced, local_leaves)

            return res

        def rec(obj, loc: Tuple[Union[str, int]] = ()):
            """
            Parameters
            ----------
            obj: Any
                The current object being resolved
            loc: Sequence[str]
                Internal variable
                Current path in tree

            Returns
            -------

            """
            if id(obj) in resolved_locs:
                return resolved_locs[id(obj)]

            if id(obj) in seen_locs:
                raise CyclicReferenceError(tuple(loc))

            seen_locs.add(id(obj))

            if not deep and len(loc) > 1:
                return obj

            if isinstance(obj, Mapping):
                resolved = Config({k: rec(v, (*loc, k)) for k, v in obj.items()})

                registries = [
                    (key, value, getattr(registry, key[1:]))
                    for key, value in resolved.items()
                    if key.startswith("@")
                ]
                assert (
                    len(registries) <= 1
                ), f"Cannot resolve using multiple registries at {'.'.join(loc)}"

                if len(registries) == 1:
                    cfg = resolved
                    params = dict(resolved)
                    params.pop(registries[0][0])
                    fn = registries[0][2].get(registries[0][1])
                    try:
                        resolved = fn(**params)
                        # The `validate_arguments` decorator has most likely
                        # already put the resolved config in the registry
                        # but for components that are instantiated without it
                        # we need to do it here
                        Config._store_resolved(resolved, cfg)
                    except ConfitValidationError as e:
                        e = ConfitValidationError(
                            errors=patch_errors(e.raw_errors, loc, params),
                            model=e.model,
                            name=getattr(e, "name", None),
                        ).with_traceback(remove_lib_from_traceback(e.__traceback__))
                        if not is_debug():
                            e.__cause__ = None
                            e.__suppress_context__ = True
                        raise e

            elif isinstance(obj, list):
                resolved = [rec(v, (*loc, i)) for i, v in enumerate(obj)]
            elif isinstance(obj, tuple):
                resolved = tuple(rec(v, (*loc, i)) for i, v in enumerate(obj))
            elif isinstance(obj, Reference):
                resolved = None
                while resolved is None:
                    try:
                        resolved = resolve_reference(obj)
                    except KeyError:
                        raise MissingReference(obj)
            else:
                resolved = obj

            resolved_locs[id(obj)] = resolved

            return resolved

        return rec(self, ())

    def merge(
        self,
        *updates: Union[Dict[str, Any], "Config"],
        remove_extra: bool = False,
    ) -> "Config":
        """
        Deep merge two configs. Heavily inspired from `thinc`'s config merge function.

        Parameters
        ----------
        updates: Union[Config, Dict]
            Configs to update the original config
        remove_extra:
            If true, restricts update to keys that existed in the original config

        Returns
        -------
        The new config
        """

        def deep_set(current, path, val):
            if path not in current and remove_extra:
                return
            current[path] = val

        def rec(old, new):
            for key, new_val in list(new.items()):
                if "." in key:
                    deep_set(old, key, new_val)
                    continue

                if key not in old:
                    if remove_extra:
                        continue
                    else:
                        old[key] = new_val
                        continue

                old_val = old[key]
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    old_resolver = next((k for k in old_val if k.startswith("@")), None)
                    new_resolver = next((k for k in new_val if k.startswith("@")), None)
                    if (
                        new_resolver is not None
                        and old_resolver is not None
                        and (
                            old_resolver != new_resolver
                            or old_val.get(old_resolver) != new_val.get(new_resolver)
                        )
                    ):
                        old[key] = new_val
                    else:
                        rec(old[key], new_val)
                else:
                    old[key] = new_val
            return old

        config = self.copy()
        for u in updates:
            rec(config, u)
        return config

    def copy(self: T) -> T:
        """
        Deep copy of the config, but not of the underlying data.
        Should also work with other types of objects (e.g. lists, tuples, etc.)

        ```
        Config.copy([1, 2, {"ok": 3}}]) == [1, 2, {"ok": 3}]
        ```

        Returns
        -------
        Any
        """
        seen = {}

        def rec(obj):
            if id(obj) in seen:
                return seen[id(obj)]
            seen[id(obj)] = obj
            if isinstance(obj, (Config, dict)):
                return type(obj)(
                    {k: rec(v) for k, v in obj.items()},
                )
            elif isinstance(obj, list):
                return [rec(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(rec(v) for v in obj)
            elif isinstance(obj, Reference):
                return Reference(obj.value)
            else:
                return obj

        copy = rec(self)
        return copy

    @classmethod
    def _store_resolved(cls, resolved: Any, config: Dict[str, Any]):
        """
        Adds a resolved object to the RESOLVED_TO_CONFIG dict
        for later retrieval during serialization
        ([`.serialize`][confit.config.Config.serialize])

        Parameters
        ----------
        resolved: Any
        config: Config
        """
        try:
            RESOLVED_TO_CONFIG[resolved] = config
        except TypeError:
            pass


def merge_from_disk(
    config_paths: Union[Path, List[Path]],
    returned_name: str = "first",
):
    """
    Merge multiple configs loaded from the filesystem
    and return the merged config as well as the name of the config

    Parameters
    ----------
    config_paths: Union[Path, List[Path]]
        Paths to the config files
    returned_name: str
        If "first", the name of the first config is returned as the name of the merged
        config. If "concat", the names of the configs are concatenated with a "+" sign

    Returns
    -------

    """
    assert returned_name in {"first", "concat"}
    if isinstance(config_paths, Path):
        config_paths = [config_paths]

    configs = [Config.from_disk(p, resolve=False) for p in config_paths]
    config_names = [p.stem for p in config_paths]

    name = config_names[0] if returned_name == "first" else "+".join(config_names)

    config = configs.pop(0)
    return config.merge(*configs), name
