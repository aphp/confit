![Tests](https://img.shields.io/github/actions/workflow/status/aphp/confit/tests.yml?branch=main&label=tests&style=flat-square)
[![Documentation](https://img.shields.io/github/actions/workflow/status/aphp/confit/documentation.yml?branch=main&label=docs&style=flat-square)](https://aphp.github.io/confit/latest/)
[![PyPI](https://img.shields.io/pypi/v/confit?color=blue&style=flat-square)](https://pypi.org/project/confit/)
[![Codecov](https://img.shields.io/codecov/c/github/aphp/confit?logo=codecov&style=flat-square)](https://codecov.io/gh/aphp/confit)


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
 
+ @app.command(name="script", registry=registry)
def func(modelA: BigModel, modelB: BigModel, other: int, seed: int):
    assert modelA.submodel is modelB.submodel
    assert modelA.date == datetime.date(2010, 10, 10)
    print("Other:", other)
 
+ if __name__ == "__main__":
+     app()
```


Create a new config file

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
python script.py --config config.cfg --seed 42
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
# BigModel will cast date strings as datetime.date objects
modelA = BigModel(date="2003-02-01", submodel=submodel)
modelB = BigModel(date="2003-04-05", submodel=submodel)
func(
    modelA=modelA,
    modelB=modelA,
    seed=seed,
)
```


Visit the [documentation](https://aphp.github.io/confit/) for more information!

## Acknowledgement

We would like to thank [Assistance Publique – Hôpitaux de Paris](https://www.aphp.fr/)
and [AP-HP Foundation](https://fondationrechercheaphp.fr/) for funding this project.
