# Mise en route

## Installation

Installez la bibliothèque avec pip :

<div class="termy">

```console
$ pip install confit
```

</div>

## Un exemple simple

Confit ne fait qu'abstraire le code de base relatif au processus de configuration et laisse le reste de votre code inchangé.

Par exemple :


```diff title="script.py"
import datetime
+ from confit import Cli, Registry, get_default_registry, set_default_registry

+ app = Cli(pretty_exceptions_show_locals=False)

+ @set_default_registry
+ classe RegistryCollection :
+ factory = Registry(("test_cli", "factory"), entry_points=True)
+
+ _catalogue = dict(
+ factory=factory,
+ )

+ registry = get_default_registry()

+ @registry.factory.register("submodel")
classe SubModel :
    # Le typage est facultative mais recommandée !
    def __init__(self, value : float, desc : str = "") :
        self.value = valeur
        self.desc = desc


+ @registry.factory.register("bigmodel")
classe BigModel :
    def __init__(self, date : datetime.date, submodel : SubModel) :
        self.date = date
        self.submodel = submodel


+ @app.command(name="script")
def func(modelA : BigModel, modelB : BigModel, other : int, seed : int) :
    assert modelA.submodel is modelB.submodel
    assert modelA.date == datetime.date(2010, 10, 10)
    print("Autre :", autre)

+ if __name__ == "__main__" :
+ app()
```


Créez un nouveau fichier de configuration

```cfg title="config.cfg"
# Sections relative aux commandes disponibles via CLI
[script]
modelA = ${modelA}
modelB = ${modelB}

# Paramètres communs utilisés dans les commandes CLI
[modelA]
@factory = "bigmodel"
date = "2010-10-10"

[modelA.submodel]
@factory = "submodel"
valeur = 12

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

!!! tip "Nommage"
    Pour utiliser le nom du chemin de votre configuration (par exemple `config-expe-2` si le fichier de configuration est nommé `config-expe-2.cfg` *dans** la configuration (après résolution), il suffit de mentionner `name = None` sous la section dont le titre a été fourni à `@app.command(name=<section-title>)`.

!!! tip "Configurations multiples"
    Vous pouvez passer plusieurs fichiers de configuration en répétant l'option `--config`. Les configurations seront fusionnées dans l'ordre.


Vous pouvez toujours appeler `function` depuis votre code, mais vous bénéficiez désormais également de la validation des arguments !

```python
from script import func, BigModel, SubModel

# Pour "seeder" (initialiser le générateur de nombres aléatoires) avant de créer les modèles
from confit.utils.random import set_seed

seed = 42
set_seed(seed)

submodel = SubModel(value=12)
# BigModel va convertir les chaînes de date en objets datetime.date
modelA = BigModel(date="2003-02-01", submodel=submodel)
modèleB = BigModel(date="2003-04-05", submodel=submodel)
func(
    modelA=modelA,
    modelB=modelA,
    seed=seed,
)
```
