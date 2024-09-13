![Tests](https://img.shields.io/github/actions/workflow/status/aphp/confit/tests.yml?branch=main&label=tests&style=flat-square)
[![Documentation](https://img.shields.io/github/actions/workflow/status/aphp/confit/documentation.yml?branch=main&label=docs&style=flat-square)](https://aphp.github.io/confit/latest/)
[![PyPI](https://img.shields.io/pypi/v/confit?color=blue&style=flat-square)](https://pypi.org/project/confit/)
[![Coverage](https://raw.githubusercontent.com/aphp/confit/coverage/coverage.svg)](https://raw.githubusercontent.com/aphp/confit/coverage/coverage.txt)


# Confit

Confit is a complete and easy-to-use configuration framework aimed at improving the reproducibility
of experiments by relying on the Python typing system, minimal configuration files and
command line interfaces.

## Getting started

Install the library with pip:

<div class="termy">

```bash
pip install confit
```

</div>

Confit only abstracts the boilerplate code related to configuration and
leaves the rest of your code unchanged.

Here is an example:

<h5 a><strong><code>script.py</code></strong></h5>

```diff
+ from confit import Cli, Registry, RegistryCollection
  
+ class registry(RegistryCollection):
+     factory = Registry(("test_cli", "factory"), entry_points=True)
 
+ @registry.factory.register("submodel")
class SubModel:
    # Type hinting is optional but recommended !
    def __init__(self, value: float, desc: str = ""):
        self.value = value
        self.desc = desc
 
 
+ @registry.factory.register("bigmodel")
class BigModel:
    def __init__(self, date: datetime.date, submodel: SubModel):
        self.date = date
        self.submodel = submodel
 
+ app = Cli(pretty_exceptions_show_locals=False)

# you can use @confit.validate_arguments instead if you don't plan on using the CLI
+ @app.command(name="script", registry=registry)
def func(modelA: BigModel, modelB: BigModel, seed: int = 42):
    assert modelA.submodel is modelB.submodel
    print("modelA.date:", modelA.date.strftime("%B %-d, %Y"))
    print("modelB.date:", modelB.date.strftime("%B %-d, %Y"))
 
+ if __name__ == "__main__":
+     app()
```


Create a new config file

The following also works with YAML files

<h5 a><strong><code>config.cfg</code></strong></h5>

```ini
# CLI sections
[script]
modelA = ${modelA}
modelB = ${modelB}

# CLI common parameters
[modelA]
@factory = "bigmodel"
date = "2003-02-01"

[modelA.submodel]
@factory = "submodel"
value = 12

[modelB]
date = "2003-04-05"
submodel = ${modelA.submodel}
```

and run the following command from the terminal

<div class="termy">

```bash
python script.py --config config.cfg --seed 43
```

</div>

You can still call the `function` method from your code, but now also benefit from
argument validation !

```python
from script import func, BigModel, SubModel

# To seed before creating the models
from confit.utils.random import set_seed

seed = 42
set_seed(seed)

submodel = SubModel(value=12)
func(
    # BigModel will cast date strings as datetime.date objects
    modelA=BigModel(date="2003-02-01", submodel=submodel),
    # Since the modelB argument was typed, the dict is cast as a BigModel instance
    modelB=dict(date="2003-04-05", submodel=submodel),
    seed=seed,
)
```

```
modelA.date: February 1, 2003
modelB.date: April 5, 2003
```

#### Serialization

You can also serialize registered classes, while keeping references between instances:

```python
from confit import Config

submodel = SubModel(value=12)
modelA = BigModel(date="2003-02-01", submodel=submodel)
modelB = BigModel(date="2003-02-01", submodel=submodel)
print(Config({"modelA": modelA, "modelB": modelB}).to_str())
```

```ini
[modelA]
@factory = "bigmodel"
date = "2003-02-01"

[modelA.submodel]
@factory = "submodel"
value = 12

[modelB]
@factory = "bigmodel"
date = "2003-02-01"
submodel = ${modelA.submodel}
```

#### Error handling

You also benefit from informative validation errors:

```python
func(
    modelA=dict(date="hello", submodel=dict(value=3)),
    modelB=dict(date="2010-10-05", submodel=dict(value="hi")),
)
```

```
ConfitValidationError: 2 validation errors for __main__.func()
-> modelA.date
   invalid date format, got 'hello' (str)
-> modelB.submodel.value
   value is not a valid float, got 'hi' (str)
```




Visit the [documentation](https://aphp.github.io/confit/) for more information!

## Acknowledgement

We would like to thank [Assistance Publique – Hôpitaux de Paris](https://www.aphp.fr/)
and [AP-HP Foundation](https://fondationrechercheaphp.fr/) for funding this project.
