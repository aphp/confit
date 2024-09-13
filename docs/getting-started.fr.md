# Mise en route

## Installation

Installez la bibliothèque avec pip :

<div class="termy">

```console
$ pip install confit
```

</div>

## Un exemple simple

Confit n'abstrait que le code standard lié à la configuration et
laisse le reste de votre code inchangé.

Voici un exemple :

```diff title="script.py"
import datetime
+ from confit import Cli, Registry, RegistryCollection

+ app = Cli(pretty_exceptions_show_locals=False)

+ class RegistryCollection(:
+     factory = Registry(("test_cli", "factory"), entry_points=True)

+ @registry.factory.register("submodel")
class SubModel:
    # Le typage est facultatif mais recommandé pour bénéficier du transtypage des arguments
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
    print("Autre :", other)

+ if __name__ == "__main__":
+     app()
```

Créez un nouveau fichier de configuration

=== "INI syatax"

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

    et exécutez la commande suivante depuis le terminal

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

    et exécutez la commande suivante depuis le terminal

    <div class="termy">

    ```console
    $ python script.py --config config.yaml --seed 42
    ```

    </div>

!!! tip "Nom"

    Pour utiliser le nom de votre chemin de configuration (par exemple `config-expe-2` si le fichier de configuration est nommé `config-expe-2.cfg` *dans** la configuration (après résolution), mentionnez simplement `name = None` sous la section dont le titre a été fourni à `@app.command(name=<section-title>)`

!!! tip "Configurations multiples"
    Vous pouvez passer plusieurs fichiers de configuration en répétant l'option `--config`. La configuration sera fusionnée dans l'ordre.

Vous pouvez toujours appeler la méthode `function` depuis votre code, mais vous bénéficiez maintenant également de la validation des arguments !

```python
from script import func, BigModel, SubModel

# Pour initialiser la graine avant de créer les modèles
from confit.utils.random import set_seed

seed = 42
set_seed(seed)

submodel = SubModel(value=12)
# BigModel convertira les chaînes de caractères de date en objets datetime.date
modelA = BigModel(date="2003-02-01", submodel=submodel)
modelB = BigModel(date="2003-04-05", submodel=submodel)
func(
    modelA=modelA,
    modelB=modelA,
    seed=seed,
)
```
