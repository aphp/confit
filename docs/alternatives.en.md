# Alternatives & Comparison

What inspired **Confit** and how it compares to other alternatives.

- [confection](https://github.com/explosion/confection)
- [gin-config](https://github.com/google/gin-config)
- [typer](https://github.com/tiangolo/typer)
- [pydantic-cli](https://github.com/mpkocher/pydantic-cli/tree/master/pydantic_cli)


## Loading

| Feature                       | Confit             | Confection         | Gin                | Typer           | Pydantic-cli    |
|-------------------------------|--------------------|--------------------|--------------------|-----------------|-----------------|
| Load from str/config file     | :white_check_mark: | :white_check_mark: | :no_entry_sign:    | :no_entry_sign: | :no_entry_sign: |
| Basic interpolation           | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |
| Arbitrary expression eval     | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Post-resolution interpolation | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Custom class instantiation    | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |

## Exporting
| Feature                         | Confit             | Confection         | Gin             | Typer           | Pydantic-cli    |
|---------------------------------|--------------------|--------------------|-----------------|-----------------|-----------------|
| Save to str/config file         | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :no_entry_sign: | :no_entry_sign: |
| Serialization of JSON-like obj  | :white_check_mark: | :white_check_mark: | NA              | NA              | NA              |
| Serialization of custom classes | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |
| Reference serialization         | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |

## CLI
| Feature              | Confit             | Confection      | Gin             | Typer              | Pydantic-cli       |
|----------------------|--------------------|-----------------|-----------------|--------------------|--------------------|
| CLI support          | :white_check_mark: | :no_entry_sign: | :no_entry_sign: | :white_check_mark: | :white_check_mark: |
| CLI short-hands      | :no_entry_sign:    | NA              | NA              | :white_check_mark: | :no_entry_sign:    |
| Argument validation  | :white_check_mark: | NA              | NA              | :white_check_mark: | :white_check_mark: |
| Config file argument | :white_check_mark: | NA              | NA              | :no_entry_sign:    | :no_entry_sign:    |


## Parameter validation
| Feature                       | Confit             | Confection         | Gin             | Typer              | Pydantic-cli       |
|-------------------------------|--------------------|--------------------|-----------------|--------------------|--------------------|
| Parameter validation support  | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :white_check_mark: | :white_check_mark: |
| Auto casting                  | :white_check_mark: | :white_check_mark: | NA              | :white_check_mark: | :white_check_mark: |
| From a Python func/class call | :white_check_mark: | :no_entry_sign:    | NA              | :no_entry_sign:    | :no_entry_sign:    |
