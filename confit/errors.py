from textwrap import indent
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pydantic
from pydantic.error_wrappers import (
    ErrorWrapper,
    ValidationError,
    get_exc_type,
)

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


PATCHED_ERRORS_CLS = {}


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


class ConfitValidationError(pydantic.ValidationError):
    __slots__ = "raw_errors", "model", "_error_cache"

    def __init__(
        self,
        errors: Sequence,
        model: Optional[Any] = None,
        name: Optional[str] = None,
    ) -> None:
        self.raw_errors = errors
        self.model = model
        self.name = name or (model.__name__ if model is not None else None)
        self._error_cache = None

    def __str__(self) -> str:
        errors = self.errors()
        no_errors = len(errors)
        err_list_str = "\n".join(
            "{loc_str}\n{msg}".format(
                loc_str="-> " + ".".join(str(e) for e in err["loc"]),
                msg=err["msg"],
            )
            for err in self.errors()
        )
        name_str = (" for " + self.name + "()") if self.name is not None else ""
        return (
            f'{no_errors} validation error{"" if no_errors == 1 else "s"}{name_str}\n'
            f"{err_list_str}"
        )

    def errors(self) -> List:
        error_dicts = []
        for err in flatten_errors(self.raw_errors):
            msg = (
                err.exc.msg_template.format(**err.exc.__dict__)
                if hasattr(err.exc, "msg_template")
                else str(err.exc)
            )
            error_dicts.append(
                {
                    "loc": err.loc_tuple(),
                    "msg": indent(msg, "   "),
                    "ctx": err.exc.__dict__,
                    "type": get_exc_type(err.exc.__class__),
                }
            )
        return error_dicts

    def __repr_args__(self):
        return [("model", self.name), ("errors", self.errors())]


def patch_errors(
    errors: Union[Sequence[ErrorWrapper], ErrorWrapper],
    path: Loc,
    values: Dict = None,
    model: Optional[pydantic.BaseModel] = None,
):
    """
    Patch the location of the errors to add the `path` prefix and complete
    the errors with the actual value if it is available.
    This is useful when the errors are raised in a sub-dict of the config.

    Parameters
    ----------
    errors: Union[Sequence[ErrorWrapper], ErrorWrapper]
        The pydantic errors to patch
    path: Loc
        The path to add to the errors
    values: Dict
        The values of the config
    post: bool
        Whether to add the path after the error location

    Returns
    -------
    Union[Sequence[ErrorWrapper], ErrorWrapper]
        The patched errors
    """
    if isinstance(errors, list):
        res = []
        for error in errors:
            res.extend(patch_errors(error, path, values, model))
        return res
    if isinstance(errors, ErrorWrapper) and isinstance(errors.exc, ValidationError):
        try:
            field_model = model
            for part in errors.loc_tuple():
                # if not issubclass(field_model, pydantic.BaseModel) and issubclass(
                #     field_model.vd.model, pydantic.BaseModel
                # ):
                #     field_model = field_model.vd.model
                field_model = field_model.__fields__[part].type_
            if (
                field_model is errors.exc.model
                or field_model.vd.model is errors.exc.model
            ):
                return patch_errors(
                    errors.exc.raw_errors, (*path, *errors.loc_tuple()), values, model
                )
        except (KeyError, AttributeError):  # pragma: no cover
            pass

    if (
        isinstance(errors.exc, pydantic.errors.PydanticErrorMixin)
        and values is not None
        and "actual_value" not in errors.exc.__dict__
        and errors.loc_tuple()
        and errors.loc_tuple()[0] in values
    ):
        actual_value = values
        for key in errors.loc_tuple():
            actual_value = actual_value[key]
        cls = errors.exc.__class__
        if cls not in PATCHED_ERRORS_CLS:

            def error_str(self):
                s = cls.__str__(self)
                s = (
                    s + f", got {self.actual_value} ({self.actual_type})"
                    if hasattr(self, "actual_value")
                    else s
                )
                return s

            PATCHED_ERRORS_CLS[cls] = type(
                cls.__name__,
                (cls,),
                {
                    "msg_template": cls.msg_template
                    + ", got {actual_value} ({actual_type})"
                }
                if hasattr(cls, "msg_template")
                else {
                    "__str__": error_str,
                },
            )
        errors.exc.__class__ = PATCHED_ERRORS_CLS[cls]
        vrepr = repr(actual_value)
        errors.exc.actual_value = vrepr[:50] + "..." if len(vrepr) > 50 else vrepr
        errors.exc.actual_type = type(actual_value).__name__
    return [
        ErrorWrapper(
            errors.exc,
            (*path, *errors.loc_tuple()),
        )
    ]


def flatten_errors(
    errors: Union[Sequence[ErrorWrapper], ErrorWrapper],
) -> Sequence[ErrorWrapper]:
    if isinstance(errors, list):
        for err in errors:
            yield from flatten_errors(err)
    else:
        yield errors
