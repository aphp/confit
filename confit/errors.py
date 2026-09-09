import inspect
import warnings
from textwrap import indent
from typing import Callable, Tuple, Union

import pydantic

from confit.utils.collections import join_path
from confit.utils.settings import is_debug
from confit.utils.xjson import Reference

Loc = Tuple[Union[int, str]]


class MissingReference(Exception):
    """
    Raised when one or multiple references cannot be resolved.
    """

    def __init__(self, ref: Reference):
        """
        Parameters
        ----------
        ref: Reference
            The reference that could not be resolved.
        """
        self.ref = ref
        super().__init__()

    def __str__(self):
        """
        String representation of the exception
        """
        return "Could not interpolate the following reference: {}".format(self.ref)


class CyclicReferenceError(Exception):
    """
    Raised when a cyclic reference is detected.
    """

    def __init__(self, path: Loc):
        """
        Parameters
        ----------
        path: Loc
            The path of the cyclic reference
        """
        self.path = path
        super().__init__()

    def __str__(self):
        """
        String representation of the exception
        """
        return "Cyclic reference detected at {}".format(join_path(self.path))


def remove_lib_from_traceback(tb):
    """
    Remove the lib folder from the traceback
    """
    # compare package to module in f_globals
    if is_debug():
        return tb
    if tb is not None and tb.tb_frame.f_globals.get("__package__") == __package__:
        return remove_lib_from_traceback(tb.tb_next)
    if tb is None or tb.tb_next is None:
        return tb
    tb.tb_next = remove_lib_from_traceback(tb.tb_next)
    return tb


class ConfitValidationError(ValueError):
    """
    Structured validation errors with paths added by config and pipeline resolution
    """

    def __init__(self, errors, *, name=None, source=None, model=None):
        if model is not None:
            warnings.warn(
                "Use source instead of model", DeprecationWarning, stacklevel=2
            )
            source = model
        self.source = source
        self.name = name or getattr(source, "__qualname__", None)
        # Old EDS-NLP callers can aggregate lists of errors inside another list
        self.details = [
            detail
            for error in errors
            for detail in (
                ConfitValidationError(error).details
                if isinstance(error, list)
                else [error]
            )
        ]
        super().__init__(self.details)

    @classmethod
    def from_exception(cls, error, *, source=None, name=None, signature=None):
        """
        Normalize Pydantic errors before config resolution adds its parent path
        """
        if isinstance(error, cls):
            return cls(
                error.errors(), source=source or error.source, name=name or error.name
            )
        if not isinstance(error, pydantic.ValidationError):
            return cls(
                [
                    {
                        "loc": (),
                        "msg": str(error),
                        "type": "value_error",
                        "ctx": {"error": error},
                    }
                ],
                source=source,
                name=name,
            )
        details = []
        for detail in error.errors(include_url=False):
            loc = detail["loc"]
            if signature is not None and loc and isinstance(loc[0], int):
                names = [
                    name
                    for name, p in signature.parameters.items()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
                if loc[0] < len(names):
                    loc = (names[loc[0]], *loc[1:])
            nested = detail.get("ctx", {}).get("error")
            if isinstance(nested, cls):
                target = source
                # Only typed construction joins paths, separate calls keep their name
                try:
                    for part in loc:
                        target = (
                            target.model_fields[part].annotation
                            if hasattr(target, "model_fields")
                            else inspect.signature(target).parameters[part].annotation
                        )
                except (KeyError, AttributeError, TypeError, ValueError):
                    target = None
                if target is not None and target is nested.source:
                    details.extend(nested.with_path(loc).errors())
                    continue
            details.append({**detail, "loc": loc})
        return cls(details, source=source, name=name)

    def with_path(self, path, *, name=None):
        """
        Return an error with a parent path without modifying shared component errors
        """
        return type(self)(
            [{**detail, "loc": (*path, *detail["loc"])} for detail in self.details],
            source=self.source,
            name=name or self.name,
        )

    @classmethod
    def combine(cls, errors, *, name=None):
        """
        Collect failures from sibling components in their original order
        """
        return cls([detail for error in errors for detail in error.errors()], name=name)

    def errors(self):
        return [dict(detail) for detail in self.details]

    def __str__(self):
        lines = []
        for detail in self.details:
            original = detail.get("ctx", {}).get("error")
            original = original if isinstance(original, BaseException) else None
            msg = str(original) if original is not None else detail["msg"]
            if original is None:
                msg = (
                    "field required"
                    if detail["type"].startswith("missing")
                    else msg[:1].lower() + msg[1:]
                )
                if "input" in detail and not detail["type"].startswith("missing"):
                    value = detail["input"]
                    try:
                        preview = repr(value)
                    except Exception:
                        preview = object.__repr__(value)
                    preview = preview[:50] + "..." if len(preview) > 50 else preview
                    msg += f", got {preview} ({type(value).__name__})"
            lines.append(
                "-> " + ".".join(map(str, detail["loc"])) + "\n" + indent(msg, "   ")
            )
        count = len(self.details)
        name = f" for {self.name}()" if self.name is not None else ""
        return (
            f"{count} validation error{'s' if count != 1 else ''}{name}\n"
            + "\n".join(lines)
        )

    @property
    def raw_errors(self):
        warnings.warn(
            "Use errors() instead of raw_errors", DeprecationWarning, stacklevel=2
        )
        return self.errors()

    @raw_errors.setter
    def raw_errors(self, errors):
        warnings.warn(
            "Use with_path or combine instead of assigning raw_errors",
            DeprecationWarning,
            stacklevel=2,
        )
        self.details = type(self)(errors).details

    @property
    def model(self):
        warnings.warn("Use source instead of model", DeprecationWarning, stacklevel=2)
        return self.source

    @model.setter
    def model(self, model):
        warnings.warn("Use source instead of model", DeprecationWarning, stacklevel=2)
        self.source = model


class SignatureError(TypeError):
    def __init__(self, func: Callable):
        message = f"{func} must not have positional only args or duplicated kwargs"
        super().__init__(message)


def patch_errors(errors, path=(), values=None, model=None, drop_names=()):
    """
    Adapt old EDS-NLP error calls to ConfitValidationError methods
    """
    warnings.warn(
        "Use ConfitValidationError.from_exception and with_path "
        "instead of patch_errors",
        DeprecationWarning,
        stacklevel=2,
    )
    is_exception = isinstance(errors, (pydantic.ValidationError, ConfitValidationError))
    error = (
        ConfitValidationError.from_exception(errors, source=model)
        if is_exception
        else ConfitValidationError(errors, source=model)
    )
    error = error.with_path(path)
    if drop_names:
        error = ConfitValidationError(
            [
                {
                    **detail,
                    "loc": tuple(
                        part for part in detail["loc"] if part not in drop_names
                    ),
                }
                for detail in error.errors()
            ],
            source=error.source,
            name=error.name,
        )
    return error if is_exception else error.errors()
