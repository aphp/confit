"""
Plugin to help IPython's autoreload magic reload functions wrapped with confit.
"""

import types


def check_wrapped(a, b):
    return (
        isinstance(b, types.FunctionType)
        and hasattr(a, "__wrapped__")
        and isinstance(a.__wrapped__, types.FunctionType)
    )


def update_wrapped_function(old, new):
    from IPython.extensions.autoreload import func_attrs

    """Upgrade the code object of a function"""
    new_func = new if not hasattr(new, "__wrapped__") else new.__wrapped__
    for name in func_attrs:
        try:
            setattr(old.__wrapped__, name, getattr(new_func, name))
        except (AttributeError, TypeError):
            pass


def autoreload_plugin():
    try:
        from IPython.extensions.autoreload import UPDATE_RULES
    except ImportError:
        return

    UPDATE_RULES.insert(
        0,
        (
            lambda a, b: check_wrapped(a, b),
            update_wrapped_function,
        ),
    )
