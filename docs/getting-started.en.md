# Getting started

## Installation

Install the library with pip:

<div class="termy">

```console
$ pip install confit
```

</div>

## A simple example

Confit only abstracts the boilerplate code related to configuration and
leaves the rest of your code unchanged.

Here is an example:


```diff title="script.py"
import datetime
+ from confit import Cli, Registry, RegistryCollection

+ app = Cli(pretty_exceptions_show_locals=False)

+ class RegistryCollection(:
+     factory = Registry(("test_cli", "factory"), entry_points=True)

+ @registry.factory.register("submodel")
class SubModel:
    # Type hinting is optional but recommended to benefit for argument casting !
    def __init__(self, value: float, desc: str = ""):
        self.value = value
        self.desc = desc


+ @registry.factory.register("bigmodel")
class BigModel:
    def __init__(self, date: datetime.date, submodel: SubModel):
        self.date = date
        self.submodel = submodel


+ @app.command(name="script", registry=registry)
def func(modelA: BigModel, modelB: BigModel, other: int, seed: int):
    assert modelA.submodel is modelB.submodel
    assert modelA.date == datetime.date(2010, 10, 10)
    print("Other:", other)

+ if __name__ == "__main__":
+     app()
```


Create a new config file

=== "INI syntax"

    ```ini title="config.cfg"
    # CLI sections
    [script]
    modelA = ${modelA}
    modelB = ${modelB}

    # CLI common parameters
    [modelA]
    @factory = "bigmodel"
    date = "2010-10-10"

    [modelA.submodel]
    @factory = "submodel"
    value = 12

    [modelB]
    date = "2003-04-05"
    submodel = ${modelA.submodel}
    ```

    and run the following command from the terminal

    <div class="termy">

    ```console
    $ python script.py --config config.cfg --seed 42
    ```

    </div>

=== "YAML syntax"

    ```yaml title="config.yaml"
    script:
      modelA: ${modelA}
      modelB: ${modelB}

    modelA:
      "@factory": "bigmodel"
      date: "2010-10-10"

      submodel:
        "@factory": "submodel"
        value: 12

    modelB:
      date: "2003-04-05"
      submodel: ${modelA.submodel}
    ```

    and run the following command from the terminal

    <div class="termy">

    ```console
    $ python script.py --config config.yaml --seed 42
    ```

    </div>

!!! tip "Naming"

    To use the name of your config path (e.g. `config-expe-2` if the configuration file is named `config-expe-2.cfg` *in* the configuration (after resolution), simply mention `name = None` under the section which title was provided at `@app.command(name=<section-title>)`

!!! tip "Multiple configurations"

    You can pass multiple configuration files by repeating the `--config` option. Configuration will be merged in order.


You can still call the `function` method from your code, but now also benefit from argument validation !

```python
from script import func, BigModel, SubModel

# To seed before creating the models
from confit.utils.random import set_seed

seed = 42
set_seed(seed)

submodel = SubModel(value=12)
# BigModel will cast date strings as datetime.date objects
modelA = BigModel(date="2003-02-01", submodel=submodel)
modelB = BigModel(date="2003-04-05", submodel=submodel)
func(
    modelA=modelA,
    modelB=modelA,
    seed=seed,
)
```
