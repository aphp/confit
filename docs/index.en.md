# Confit

Confit is a complete and easy-to-use configuration framework aimed at improving the reproducibility of experiments by relying on the Python typing system, minimal configuration files and command line interfaces.

## Architecture

The three pillars of this configuration system are the [catalogue](https://github.com/explosion/catalogue) registry,
the [Pydantic](https://github.com/pydantic/pydantic) validation system and the [typer](https://github.com/tiangolo/typer) CLI library.

### Registry

The catalogue registry records the various objects (classes or functions) that can be composed
together to run your program. Once registered, with the `registry.factory.register`
decorator, these objects are accessible as [entry points] and can be
used in the configuration system.
To start, you can create a simple registry `"factory"` as follows:

```python
from confit import Registry, RegistryCollection


class registry(RegistryCollection):
    factory = Registry(("my_library", "factory"), entry_points=True)
```

!!! tip "What is this useful for?"

    With this registry, you can *register* a function or a class:

    ```python
    @registry.factory.register("my-function")
    def my_function(value=10):
        print(f"The value is {value}!")
    ```

    Now you can dynamically retrieve the function from anywhere:

    ```python
    func = registry.factory.get("my-function")
    func()
    # Out: "The value is 10!"
    func(value=42)
    # Out: "The value is 42!"
    ```

### Typing system

The Pydantic `validate_arguments` decorator enhances a function to automatically parse and validate its arguments every time it is called, using the Pydantic typing-based validation system.
For instance, strings can be automatically cast as Path objects, or datetime or numbers depending on the type annotation of the argument.

Combined with our configuration system, dictionaries passed as arguments to a decorated function can be "cast" as instantiated classes if these classes were them-selves decorated.

### CLI

TBD

## The Config object

The configuration object consists of a supercharged dict, the `Config` class, that can  be used to read and write to `cfg` files, interpolate variables and instantiate components  through the registry with some special `@factory` keys.
A cfg file can be used directly as an input to a CLI-decorated function.

We will show partial examples with increasing complexity below. See [here][a-simple-example] for an end-to-end example.

### Instantiating an object

```python title="script.py"
@registry.factory.register("my-class")
class MyClass:
    def __init__(self, value1: int, value2: float):
        self.value1 = value1
        self.value2 = value2
```

=== "INI syntax"

    ```ini title="config.cfg"
    [myclass]
    @factory = "my-class"
    value1 = 1.1
    value2 = 2.5
    ```

=== "YAML syntax"

    ```yaml title="config.yaml"
    myclass:
      "@factory": "my-class"
      value1: 1.1
      value2: 2.5
    ```

Here, **Confit** will:

- Parse the configuration
- Get the target class from the registry
- Validate parameters if needed (in this case, `value1` is typed as an int, thus it will be casted as an int by setting `value1=1`)
- Instantiate the class using the validated parameters

### Interpolating values

When multiple sections of the configuration need to access the same value, you can provide it using the `${<section.value>}` syntax:

=== "INI syntax"

    ```ini title="config.cfg"
    [myclass]
    @factory = "my-class"
    value1 = 1.1
    value2 = ${other_values.value3}

    [other_values]
    value3 = 10
    ```

=== "YAML syntax"

    ```yaml title="config.yaml"
    myclass:
      "@factory": "my-class"
      value1: 1.1
      value2: ${other_values.value3}
    ```

Here, `value2` will be set to 10.

### Advanced interpolation

You can even pass instantiated objects! Suppose we have a registered `myOtherClass` class expecting an instance of `MyClass` as input. You could use the following configuration:

=== "INI syntax"

    ```ini title="config.cfg"
    [func]
    @factory = "my-other-class"
    obj = ${myclass}

    [myclass]
    @factory = "my-class"
    value1 = 1.1
    value2 = ${other_values.value3}

    [other_values]
    value3 = 10
    ```

=== "YAML syntax"

    ```yaml title="config.yaml"
    func:
      "@factory": "my-other-class"
      obj: ${myclass}

    myclass:
        "@factory": "my-class"
        value1: 1.1
        value2: ${other_values.value3}

    other_values:
        value3: 10
    ```

Finally, you may want to access some attributes of Python classes that are available *after* instantiation, but not present in the configuration file. For instance, let's modify our `MyClass` class:


```diff title="script.py"
@registry.factory.register("my-class")
class MyClass:
    def __init__(self, value1: int, value2: float):
        self.value1 = value1
        self.value2 = value2
+         self.hidden_value = 99
```

To access those values directly in the configuration file, use the `${<obj:attribute>}` syntax (notice the **colon** instead of the **point**)

=== "INI syntax"

    ```ini title="config.cfg"
    [myclass]
    @factory = "my-class"
    value1 = 1.1
    value2 = 2.5

    [other_values]
    value3 = ${myclass:hidden_value}
    ```

=== "YAML syntax"

    ```yaml title="config.yaml"
    myclass:
      "@factory": "my-class"
      value1: 1.1
      value2: 2.5

    other_values:
        value3: ${myclass:hidden_value}
    ```
