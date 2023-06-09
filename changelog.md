# Changelog

# v0.2.1 - 11-05-2023

- Fix un-allowed kwargs: accepted signatures are `fn(paramA, paramB=..., ... **kwargs)`


# v0.2.0 - 05-04-2023

- `Config.merge(...)` now only copies collections (not the underlying data) and doesn't split keys around dots
- `__path__` option has been removed (having a override_structure in .to_str() would be better)
- Allow to skip some parameters when storing config before resolution
- Allow to resolve only a part of a configuration
- Improve serialization (can refer to dict/tuple/list objects now) and merge the instance's `.cfg` attribute (which can be updated by the instance) with the stored config
- Add the `invoker` option to `.register(...)` to modify the arguments of the call to the registered function or do something with the result
- User defined `class registry` should now inherit from `RegistryCollection`

# v0.1.5 - 02-03-2023

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
