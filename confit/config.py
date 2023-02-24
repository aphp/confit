import collections
import re
from configparser import ConfigParser
from copy import deepcopy
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union
from weakref import WeakKeyDictionary

from pydantic import ValidationError
from pydantic.error_wrappers import ErrorWrapper
from pydantic.schema import encode_default

from confit.utils.collections import dedup, flatten_sections, join_path, split_path
from confit.utils.eval import safe_eval
from confit.utils.xjson import Reference, dumps, loads

RESOLVED_TO_CONFIG = WeakKeyDictionary()

Loc = Tuple[Union[int, str]]


def patch_errors(
    errors: Union[Sequence[ErrorWrapper], ErrorWrapper],
    path: Loc,
):
    """
    Patch the location of the errors to add the `path` prefix.
    This is useful when the errors are raised in a sub-dict of the config.

    Parameters
    ----------
    errors: Union[Sequence[ErrorWrapper], ErrorWrapper]
        The pydantic errors to patch
    path: Loc
        The path to add to the errors

    Returns
    -------
    Union[Sequence[ErrorWrapper], ErrorWrapper]
        The patched errors
    """
    if isinstance(errors, list):
        res = []
        for error in errors:
            res.append(patch_errors(error, path))
        return res
    return ErrorWrapper(errors.exc, (*path, *errors.loc_tuple()))


class MissingReference(Exception):
    """
    Raised when one or multiple references cannot be resolved.
    """

    def __init__(self, references: List[Reference]):
        """
        Parameters
        ----------
        references: List[Reference]
            The references that could not be resolved.
        """
        self.references = references
        super().__init__()

    def __str__(self):
        """
        String representation of the exception
        """
        return "Could not interpolate the following references: {}".format(
            ", ".join("${{{}}}".format(r) for r in self.references)
        )


def resolve_reference(ref: Reference, leaves: Dict[Loc, Any]) -> Any:
    """
    Resolves a reference to a value using a dict of already resolved
    config subtrees.

    Parameters
    ----------
    ref: Reference
        The reference to resolve
    leaves: Dict[Loc, Any]
        The already resolved config subtrees

    Raises
    ------
    KeyError
        If a variable in the reference cannot be found
        in the `leaves` dict.

    Returns
    -------
    Any
    """
    pat = re.compile(
        r"\b((?:[^\W0-9]\w*\.)*[^\W0-9]\w*)" r"(?::((?:[^\W0-9]\w*\.)*[^\W0-9]\w*))?",
    )

    local_leaves = {}
    local_names = {}
    for i, (key, val) in enumerate(leaves.items()):
        local_leaves[f"var_{i}"] = val
        local_names[key] = f"var_{i}"

    def replace(match):
        var = match.group(1)
        path = split_path(var)
        try:
            return local_names[path] + ("." + match.group(2) if match.group(2) else "")
        except KeyError:
            raise KeyError(var)

    replaced = pat.sub(replace, ref)

    res = safe_eval(replaced, local_leaves)

    return res


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
        path: Loc = kwargs.pop("__path__", None)
        kwargs = {
            key: Config(value)
            if isinstance(value, dict) and not isinstance(value, Config)
            else value
            for key, value in kwargs.items()
        }
        super().__init__(**kwargs)
        self.__path__: Loc = path

    @classmethod
    def from_str(cls, s: str, resolve: bool = False, registry: Any = None) -> Any:
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
        parser = ConfigParser()
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
            current.update({k: loads(v) for k, v in parser.items(section)})

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
            Whether to resolve sections with '@' keys
        registry
            Optional registry to resolve from.
            If None, the default registry will be used.

        Returns
        -------
        Config
        """
        s = Path(path).read_text()
        return cls.from_str(s, resolve=resolve, registry=registry)

    def to_disk(self, path: Union[str, Path]):
        """
        Export a config to the disk (usually to a .cfg file)

        Parameters
        ----------
        path: Union[str, path]
        """
        s = Config.to_str(self)
        Path(path).write_text(s)

    def serialize(self):
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

        def is_simple(o):
            return o is None or isinstance(o, (str, int, float, bool, Reference))

        def rec(o: Any, path: Loc = ()):
            if is_simple(o):
                return o
            if isinstance(o, collections.Mapping):
                items = sorted(
                    o.items(),
                    key=lambda x: 1
                    if (
                        is_simple(x[1])
                        or isinstance(x[1], (collections.Mapping, list, tuple))
                    )
                    else 0,
                )
                print("ITEMS", items)
                serialized = {k: rec(v, (*path, k)) for k, v in items}
                serialized = {k: serialized[k] for k in o.keys()}
                if isinstance(o, Config):
                    serialized = Config(serialized)
                    serialized.__path__ = o.__path__
                return serialized
            if isinstance(o, (list, tuple)):
                return type(o)(rec(v, (*path, i)) for i, v in enumerate(o))
            if id(o) in refs:
                return refs[id(o)]
            cfg = None
            try:
                cfg = o.cfg
            except AttributeError:
                try:
                    cfg = RESOLVED_TO_CONFIG[o]
                except (KeyError, TypeError):
                    pass
            if cfg is not None:
                refs[id(o)] = Reference(join_path(path))
                return rec(cfg, path)
            try:
                return encode_default(o)
            except Exception:
                raise TypeError(f"Cannot dump {o!r}")

        return rec(self)

    def to_str(self):
        """
        Export a config to a string in the cfg format
        by serializing it first

        Returns
        -------
        str
        """
        additional_sections = {}

        def rec(o, path=()):
            if isinstance(o, collections.Mapping):
                if isinstance(o, Config) and o.__path__ is not None:
                    res = {k: rec(v, (*o.__path__, k)) for k, v in o.items()}
                    current = additional_sections
                    for part in o.__path__[:-1]:
                        current = current.setdefault(part, Config())
                    current[o.__path__[-1]] = res
                    return Reference(join_path(o.__path__))
                elif isinstance(o, (tuple, list)):
                    return type(o)(rec(item) for item in o)
                else:
                    return {k: rec(v, (*path, k)) for k, v in o.items()}
            return o

        prepared = flatten_sections(rec(Config.serialize(self)))
        prepared.update(flatten_sections(additional_sections))

        parser = ConfigParser()
        parser.optionxform = str
        for section_name, section in prepared.items():
            parser.add_section(section_name)
            parser[section_name].update({k: dumps(v) for k, v in section.items()})
        s = StringIO()
        parser.write(s)
        return s.getvalue()

    def resolve(self, deep=True, registry: Any = None) -> Any:
        """
        Resolves the parts of the nested config object with @ variables using
        a registry, and then interpolate references in the config.

        Parameters
        ----------
        deep: bool
            Should we resolve deeply
        registry:
            Registry to use when resolving

        Returns
        -------
        Union[Config, Any]
        """
        if registry is None:
            from .registry import get_default_registry

            registry = get_default_registry()
        leaves = {}

        def rec(obj, _path=()):
            """
            Parameters
            ----------
            obj: Any
                The current object being resolved
            _path: Sequence[str]
                Internal variable
                Current path in tree


            Returns
            -------

            """
            if not deep and len(_path) > 1:
                return obj
            if isinstance(obj, Mapping):
                copy = Config(obj)
                unresolved_items = [(k, v) for k, v in obj.items()]
            elif isinstance(obj, (list, tuple)):
                copy = list(obj)
                unresolved_items = list(enumerate(obj))
            else:
                return obj

            last_count = len(leaves)

            while len(unresolved_items):
                traced_missing_values = []
                missing = []
                for key, value in unresolved_items:
                    try:
                        if isinstance(value, Reference):
                            try:
                                leaves[(*_path, key)] = resolve_reference(value, leaves)
                            except (KeyError, NameError):
                                raise MissingReference([value])
                            else:
                                copy[key] = leaves[(*_path, key)]
                        else:
                            leaves[(*_path, key)] = rec(value, (*_path, key))
                            copy[key] = leaves[(*_path, key)]
                    except MissingReference as e:
                        traced_missing_values.extend(e.references)
                        missing.append((key, value))
                # If we found a missing reference and the number of
                # resolved leaves since the last iteration of the unresolved items
                # is the same, then we need to resolve other parts of the tree
                if len(missing) > 0 and len(leaves) == last_count:
                    raise MissingReference(dedup(traced_missing_values))

                unresolved_items = missing
                last_count = len(leaves)

            # If simple sequence, don't try to resolve it using a registry
            if isinstance(obj, list):
                return copy
            if isinstance(obj, tuple):
                return tuple(copy)

            registries = [
                (key, value, registry._catalogue[key[1:]])
                for key, value in copy.items()
                if key.startswith("@")
            ]
            assert len(registries) <= 1, (
                f"Cannot resolve using multiple " f"registries at {'.'.join(_path)}"
            )

            if len(registries) == 1:
                params = dict(copy)
                params.pop(registries[0][0])
                fn = registries[0][2].get(registries[0][1])
                try:
                    resolved = fn(**params)
                    try:
                        resolved.cfg
                    except Exception:
                        try:
                            RESOLVED_TO_CONFIG[resolved] = copy
                        except Exception:
                            pass

                    return resolved
                except ValidationError as e:
                    raise ValidationError(patch_errors(e.raw_errors, _path), e.model)

            return copy

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
            try:
                path = split_path(path)
                for part in path[:-1]:
                    current = (
                        current[part] if remove_extra else current.setdefault(part, {})
                    )
            except KeyError:
                return
            if path[-1] not in current and remove_extra:
                return
            current[path[-1]] = val

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

        config = deepcopy(self)
        for u in updates:
            u = deepcopy(u)
            rec(config, u)
        return Config(**config)

    @classmethod
    def _store_resolved(cls, resolved: Any, config: "Config"):
        """
        Adds a resolved object to the RESOLVED_TO_CONFIG dict
        for later retrieval during serialization
        ([`.serialize`][confit.config.Config.serialize])

        Parameters
        ----------
        resolved: Any
        config: Config
        """
        RESOLVED_TO_CONFIG[resolved] = config


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
