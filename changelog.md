# Changelog

## v0.8.0 (2025-04-15)

- Added `auto_draft_in_config` parameter to `register(...)` function. This is meant for functions that can only be partially be instantiated by a user, because a required parameter will be provided by the library later.

  For instance:

  - EDS-NLP's `ScheduledOptimizer` requires the pipeline parameters, which depends on the pipeline being trained
  - EDS-NLP's local trackers (like `csv` and `json`) require `logging_dir` which might be defined in the `edsnlp.train` function.

  If a callable registered with `auto_draft_in_config=True` is resolved with missing required parameters, a `Draft[ReturnType]` class is returned.
  This class can then be instantiated via the draft.instantiate method.
  We don't instantiate a Draft class via the `__call__` method to avoid users mistakenly proceeding with a non instantiated class.
  Instead, whenever a Draft an attribute or a method is requested on Draft class, outside the Draft few specific attrs/methods,
  a message error is displayed explaining how this object is not instantiated yet.

  The user can also explicitly instantiate the Draft object via the `Class.draft` method for classes that have been wrapped with `validate_arguments`.

- Added a `Validatable` class that can be inherited from to run a `validate` class method whenever the class is validated


## v0.7.5 (2025-03-21)

- Allow non-string keys in config files

## v0.7.4 (2025-01-15)

- Allow larger than 4096 bytes config files
- Escape tabs and newline when serializing to a config file
- Fix an infinite loop that occurred when resolving a reference to a field with a null value

## v0.7.3 (2024-12-11)

- Support interpolated seed in the config file (as a reminder, the seed is treated specifically by confit to initialize random generators **before** any object is resolved)
- Support if/else expressions in interpolation, and only resolve the relevant branch

## v0.7.2 (2024-11-23)

- Seed the program *BEFORE* the config file is resolved and components have been instantiated, to ensure reproducibility.

## v0.7.1 (2024-11-21)

- Force utf-8 encoding when writing a config file (ini or yaml)

## v0.7.0 (2024-10-22)

### Changed

- Aborting a script will now show the traceback

### Fixed

- Confit should no longer cause pydantic v1 deprecation warnings

## v0.6.0 (2024-09-13)

### Fixed

- Support IPython autoreload on confit wrapped functions
- Support using config files with scripts without a dedicated section header
- Disable configparser interpolation (% symbol)
- Better support for escaped strings in config files
- Various registry-related fixes

### Added

- Non-relevant fields (outside the script dedicated section) are no longer instantiated when running a script with a config file
- We now support loading and serializing configs in yaml syntax (`Confit.from_yaml_str`, `Confit.to_yaml_str`, `Confit.from_disk("___.yaml")` and `Confit.to_disk("___.yaml")`)

## v0.5.5

### Added

- Support fixing the path of validation errors raised inside a "validate" function (see the `AsList` meta type in the tests)

## v0.5.4

### Fixed

- We now forward function signature when accessing a callable via a deprecated registry name.
  This is useful when registry.get("deprecated-name") is inspected.

## v0.5.3

### Changed

- We now raise an error if a value in the config cannot be deserialized as a JSON object but contains characters that hint at a JSON object (e.g. quotes, brackets, etc.). This changes the old behavior where we would silently ignore the value and keep the string as is.

### Fixed

- Allow complex interpolations like `${[*section."key.with.dot", "baz"]}`

## v0.5.2

### Changed

- Keys with dots (or path-like keys in general) will be escaped when serializing a config
```python
{"section": {"deep.key": "ok"}}
```
will be serialized as
```ini
[section]
'deep.key' = "ok"
```

## v0.5.1

### Added

- Use context instead of func for set_seed to allow
  ```python
  with set_seed(42):
      # do stuff
      num = random.randint(0, 100)
  ```
- Add auto-reload plugin to work with confit wrapped functions in notebooks

## v0.5.0

### Added

- `deprecated` parameter to register an object under multiple names with deprecation warnings

### Fixed

- Stop interpreting type errors as validation errors when executing a validated function

## v0.4.3 - 31-08-2023

### Fixed

- Save var kwargs as separate fields

## v0.4.2 - 31-08-2023

### Fixed

- Re-enable extra/duplicate arg errors and uniformize between pydantic v1/v2
- Add pydantic-core dependency for jsonable types during dump

## v0.4.1 - 29-08-2023

### Fixed

- Use pydantic v2 context error only if it is an exception

## v0.4.0 - 29-08-2023

### Added

- Improve validation errors merging and display. By default, confit related frames and exception causes
  in the traceback are hidden.
- Show inner-confit traceback and exception chains if `CONFIT_DEBUG` env var is true
- Support for both Pydantic v2 and v1

### Fixed

- If the `seed` is given a default value in CLI, it can now be used by confit when no seed is given

## v0.3.0 - 25-08-2023

- Allow keyword only parameters
- Avoid import of all entry points by catalogue during failed registry lookup
- Fix bug in serialization, leading to mixed config fields

## v0.2.1 - 11-05-2023

- Fix un-allowed kwargs: accepted signatures are `fn(paramA, paramB=..., ... **kwargs)`


## v0.2.0 - 05-04-2023

- `Config.merge(...)` now only copies collections (not the underlying data) and doesn't split keys around dots
- `__path__` option has been removed (having a override_structure in .to_str() would be better)
- Allow to skip some parameters when storing config before resolution
- Allow to resolve only a part of a configuration
- Improve serialization (can refer to dict/tuple/list objects now) and merge the instance's `.cfg` attribute (which can be updated by the instance) with the stored config
- Add the `invoker` option to `.register(...)` to modify the arguments of the call to the registered function or do something with the result
- User defined `class registry` should now inherit from `RegistryCollection`

## v0.1.5 - 02-03-2023

- Verify the signature when registering rather than during a call
- Allow `**kwargs`

## v0.1.4 - 27-02-2023

- More robust resolution algorithm
- Cyclic reference detection
- Extended JSON syntax reading & writing (tuple & nested refs)
- Fix lists and tuple parsing
- Fix multi registration
- Fix inheritance between registered classes
- Multilingual doc & improved docs style

## v0.1.1 - 06-01-2023

### Features

- Enhanced references capabilities

## v0.1.0 - 30-12-2022

Inception ! :tada:

### Features

- Config object with pre-resolve
- typer CLI wrappers
- catalogue registries
- ...
