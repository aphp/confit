from .cli import Cli
from .config import Config
from .registry import (
    validate_arguments,
    Registry,
    get_default_registry,
    set_default_registry,
    RegistryCollection,
    VisibleDeprecationWarning,
)
from .autoreload import autoreload_plugin

__version__ = "0.5.3"

autoreload_plugin()
