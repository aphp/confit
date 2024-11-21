from textwrap import indent
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union

import pydantic

from confit.utils.settings import is_debug

try:
    from pydantic.error_wrappers import (
        ErrorWrapper,
        get_exc_type,
    )
    from pydantic.error_wrappers import (
        ValidationError as LegacyValidationError,
    )
    from pydantic.errors import PydanticErrorMixin
except ImportError:
    from pydantic.v1.error_wrappers import (
        ErrorWrapper,
        get_exc_type,
    )
    from pydantic.v1.error_wrappers import (
        ValidationError as LegacyValidationError,
    )
    from pydantic.v1.errors import PydanticErrorMixin

from confit.utils.collections import join_path
from confit.utils.xjson import Reference

Loc = Tuple[Union[int, str]]
PYDANTIC_V1 = pydantic.VERSION.split(".")[0] == "1"


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


class ConfitValidationError(LegacyValidationError):
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


class SignatureError(TypeError):
    def __init__(self, func: Callable):
        message = f"{func} must not have positional only args or duplicated kwargs"
        super().__init__(message)


class PydanticNewStyleError(PydanticErrorMixin, Exception):
    msg_template = "{msg}"
    code = "pydantic_new_style_error"


def to_legacy_error(err: pydantic.ValidationError, model: Any) -> LegacyValidationError:
    """
    Decorator to convert a Pydantic ValidationError into a ConfitValidationError
    """
    if isinstance(err, LegacyValidationError):
        return err
    errors = err.errors(include_url=False)
    raw_errors = []
    for err in errors:
        try:
            vrepr = repr(err["input"])
        except Exception:  # pragma: no cover
            vrepr = object.__repr__(err["input"])
        vrepr = vrepr[:50] + "..." if len(vrepr) > 50 else vrepr
        err = dict(err)
        msg = err.pop("msg", "")
        msg = (msg[0].lower() + msg[1:]) if msg else msg
        raw_errors.append(
            ErrorWrapper(
                exc=err["ctx"]["error"]
                if "ctx" in err
                and "error" in err["ctx"]
                and isinstance(err["ctx"]["error"], BaseException)
                else PydanticNewStyleError(
                    **err,
                    msg=msg,
                    actual_value=vrepr,
                    actual_type=type(err["input"]).__name__,
                ),
                loc=err["loc"],
            )
        )
    return ConfitValidationError(raw_errors, model=model)


T = TypeVar("T")


def patch_errors(
    errors: T,
    path: Loc = (),
    values: Dict = None,
    model: Optional[pydantic.BaseModel] = None,
    special_names: Sequence[str] = (),
    drop_names: Sequence[str] = (),
) -> T:
    """
    Patch the location of the errors to add the `path` prefix and complete
    the errors with the actual value if it is available.
    This is useful when the errors are raised in a sub-dict of the config.

    Parameters
    ----------
    errors: Union[LegacyValidationError, Sequence[ErrorWrapper], ErrorWrapper]
        The pydantic errors to patch
    path: Loc
        The path to add to the errors
    values: Dict
        The values of the config
    special_names: Sequence[str]
        The names of the special keys of the model signature, to replace with a wildcard
        when encountered in the error path
    model: Optional[pydantic.BaseModel]
        The model of the config
    drop_names: Sequence[str]
        The names of the keys to drop from the error path

    Returns
    -------
    Union[LegacyValidationError, Sequence[ErrorWrapper], ErrorWrapper]
        The patched errors
    """
    if isinstance(errors, pydantic.ValidationError):
        errors = to_legacy_error(errors, model).raw_errors
        errors = patch_errors(errors, path, values, model, special_names, drop_names)
        return ConfitValidationError(errors, model=model)
    if isinstance(errors, list):
        res = []
        for error in errors:
            res.extend(
                patch_errors(error, path, values, model, special_names, drop_names)
            )
        return res
    if isinstance(errors, ErrorWrapper) and isinstance(
        errors.exc, LegacyValidationError
    ):
        try:
            field_model = model
            for part in errors.loc_tuple():
                # if not issubclass(field_model, pydantic.BaseModel) and issubclass(
                #     field_model.vd.model, pydantic.BaseModel
                # ):
                #     field_model = field_model.vd.model
                if PYDANTIC_V1:
                    field_model = field_model.__fields__[part]
                else:
                    field_model = field_model.model_fields[part]
                if PYDANTIC_V1:
                    field_model = field_model.type_
                else:
                    field_model = field_model.annotation
            if (
                field_model is errors.exc.model
                or field_model.vd.model is errors.exc.model
            ):
                return patch_errors(
                    errors.exc.raw_errors,
                    (*path, *errors.loc_tuple()),
                    values,
                    model,
                    special_names,
                    drop_names,
                )
        except (KeyError, AttributeError):  # pragma: no cover
            print("Could not find model for", errors.loc_tuple())

    if (
        isinstance(errors.exc, PydanticErrorMixin)
        and values is not None
        and errors.loc_tuple()
        and errors.loc_tuple()[0] in values
    ):
        if "actual_value" not in errors.exc.__dict__:
            actual_value = values
            for key in errors.loc_tuple():
                actual_value = actual_value[key]
            vrepr = repr(actual_value)
            errors.exc.actual_value = vrepr[:50] + "..." if len(vrepr) > 50 else vrepr
            errors.exc.actual_type = type(actual_value).__name__

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

            new_cls = type(
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
            PATCHED_ERRORS_CLS[cls] = new_cls
            PATCHED_ERRORS_CLS[new_cls] = new_cls
        errors.exc.__class__ = PATCHED_ERRORS_CLS[cls]

    if (
        isinstance(errors.exc, TypeError)
        and str(errors.exc).startswith("unexpected keyword argument")
        and ":" in errors.exc.args[0]
    ):
        extra_keys = errors.exc.args[0].split(": ")[1].split(", ")
        return [
            ErrorWrapper(
                TypeError("unexpected keyword argument"),
                (*path, *errors.loc_tuple()[:-1], key.strip("'")),
            )
            for key in extra_keys
        ]

    loc_tuple = errors.loc_tuple()
    if loc_tuple and loc_tuple[-1] in special_names:
        loc_tuple = (*loc_tuple[:-1], "[signature]")
    loc_tuple = tuple(part for part in loc_tuple if part not in drop_names)

    return [
        ErrorWrapper(
            errors.exc,
            (*path, *loc_tuple),
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


def convert_type_error(err, pydantic_func, callee):
    loc_suffix = ()
    if str(err).startswith("multiple values for argument"):
        loc_suffix = ("v__duplicate_kwargs",)
    elif str(err).startswith("unexpected keyword argument"):
        loc_suffix = ("kwargs",)
    raise ConfitValidationError(
        errors=[ErrorWrapper(err, loc_suffix)],
        model=pydantic_func.model,
        name=callee.__module__ + "." + callee.__qualname__,
    )
