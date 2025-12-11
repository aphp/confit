# Alternatives & Comparison

In this section, we will explore what inspired Confit and how it compares to other alternative Python packages.

### Confection

[Confection](https://github.com/explosion/confection) (originally part of the [Thinc](https://github.com/explosion/thinc) library)
is another configuration framework from which Confit takes most of its inspiration. Both Confit and Confection support loading and exporting configuration data from/to strings or config files, as well as basic interpolation and custom class instantiation from a registry.

However, Confit takes it a step further by allowing arbitrary expression evaluation, post-resolution interpolation, and exporting features such as saving to strings or config files, serialization of JSON-like objects, custom classes, and reference serialization.

Confit also adds support for command-line interfaces by either passing a config file as an argument or by passing arguments (or overrides) directly to the CLI, while benefiting from argument validation and type casting.

### Gin-config

[Gin Config](https://github.com/google/gin-config) is a flexible configuration system built for machine learning research. Like Confit and Confection, gin-config supports basic interpolation and custom class instantiation and offers CLI support. However, it does not provide exporting configuration objects functionalities like Confit does or parameter validation.

### Typer

[Typer](https://github.com/tiangolo/typer) is a CLI library that focuses on providing easy-to-use functionalities for building command-line interface. While Typer offers excellent CLI support and basic argument validation, it does not have configuration file-related features such as loading, exporting, or parameter validation like Confit does. Confit relies on Typer for its CLI support, but adds config file arguments and instantiating classes from a registry, both of which are not available in Typer.

However, if your primary focus is on building a robust CLI, Typer is a strong alternative.

### Pydantic-CLI

[Pydantic-CLI](https://github.com/mpkocher/pydantic-cli) is another CLI library that combines Pydantic and argparse for creating command-line interfaces. Pydantic-CLI provides CLI support and argument validation, similar to Typer. However, it does not have any configuration file-related features like Confit does, nor does it allow instantiating custom classes.

## Tabular comparison

### Loading

| Feature                       | Confit             | Confection         | Gin                | Typer           | Pydantic-cli    |
|-------------------------------|--------------------|--------------------|--------------------|-----------------|-----------------|
| Load from str/config file     | :white_check_mark: | :white_check_mark: | :no_entry_sign:    | :no_entry_sign: | :no_entry_sign: |
| Basic interpolation           | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |
| Arbitrary expression eval     | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Post-resolution interpolation | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Custom class instantiation    | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |
| Deferred instantiation        | :white_check_mark: | :no_entry_sign:    | :white_check_mark: | NA              | NA              |

### Exporting
| Feature                         | Confit             | Confection         | Gin             | Typer           | Pydantic-cli    |
|---------------------------------|--------------------|--------------------|-----------------|-----------------|-----------------|
| Save to str/config file         | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :no_entry_sign: | :no_entry_sign: |
| Serialization of JSON-like obj  | :white_check_mark: | :white_check_mark: | NA              | NA              | NA              |
| Serialization of custom classes | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |
| Reference serialization         | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |

### CLI
| Feature              | Confit             | Confection      | Gin                | Typer              | Pydantic-cli       |
|----------------------|--------------------|-----------------|--------------------|--------------------|--------------------|
| CLI support          | :white_check_mark: | :no_entry_sign: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| CLI short-hands      | :no_entry_sign:    | NA              | :no_entry_sign:    | :white_check_mark: | :no_entry_sign:    |
| Argument validation  | :white_check_mark: | NA              | :no_entry_sign:    | :white_check_mark: | :white_check_mark: |
| Config file argument | :white_check_mark: | NA              | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    |


### Parameter validation
| Feature                       | Confit             | Confection         | Gin             | Typer              | Pydantic-cli       |
|-------------------------------|--------------------|--------------------|-----------------|--------------------|--------------------|
| Parameter validation support  | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :white_check_mark: | :white_check_mark: |
| Auto casting                  | :white_check_mark: | :white_check_mark: | NA              | :white_check_mark: | :white_check_mark: |
| From a Python func/class call | :white_check_mark: | :no_entry_sign:    | NA              | :no_entry_sign:    | :no_entry_sign:    |
