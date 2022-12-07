# Configuration system

Confit is a complete and easy-to-use configuration framework aimed at improving the reproducibility
of experiments by relying on the Python typing system, minimal configuration files and
command line interfaces.

## Backbone

The three pillars of this configuration system are the [catalogue](https://github.com/explosion/catalogue) registry,
the [Pydantic](https://github.com/pydantic/pydantic) validation system and the [typer](https://github.com/tiangolo/typer) CLI library.

### Registry

The catalogue registry records the various components and layers that can be composed
together to build a pipeline. Once registered, with the `registry.factory.register`
decorator, these components are accessible as [entry points] and can be
used in the configuration system.

### Typing system

The Pydantic `validate_arguments` decorator enhances a function to automatically parse
and validate its arguments every time it is called, using the Pydantic typing-based validation system.
For instance, strings can be automatically cast as Path objects, or datetime or numbers
depending on the type annotation of the argument.

Combined with our configuration system, dictionaries passed as arguments to a decorated
function can be "cast" as instantiated classes if these classes were them-selves decorated.

### CLI

...

## The Config object

The configuration object consists of a supercharged dict, the `Config` class, that can
be used to read and write to `cfg` files, interpolate variables and instantiate components
through the registry with some special `@factory` keys.
A cfg file can be used directly as an input to a CLI-decorated function.
