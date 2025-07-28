# Confit

Confit est un système de configuration complet et facile d'utilisation qui vise à améliorer la reproductibilité des expériences en s'appuyant sur le système de typage Python, sur des fichiers de configuration minimaux et avec une interface en ligne de commande.

Les trois piliers de ce système de configuration sont le registre [catalogue](https://github.com/explosion/catalogue),
le système de validation [Pydantic](https://github.com/pydantic/pydantic) et la bibliothèque de CLI [typer](https://github.com/tiangolo/typer).

## Registre

Le registre [catalogue](https://github.com/explosion/catalogue) stocke les différents objects (classes ou fonctions) qui peuvent être composés ensemble pour executer votre programme. Une fois enregistrés, avec le décorateur `registry.factory.register` ces objets sont accessibles via les [entry-points](https://packaging.python.org/en/latest/specifications/entry-points/#entry-points-specification) et peuvent être utilisés dans le système de configuration.
Pour commencer, vous pouvez créer un registre `"factory"` comme suit:
```python
from confit import Registry, RegistryCollection


class registry(RegistryCollection):
    factory = Registry(("my_library", "factory"), entry_points=True)
```

!!! tip "À quoi cela sert-il ?"

    Avec ce registre, vous pouvez *enregistrer* une fonction ou une classe :

    ```python
    @registry.factory.register("my-function")
    def my_function(value=10):
        print(f"The value is {value}!")
    ```

    Maintenant, vous pouvez récupérer dynamiquement la fonction depuis n'importe où :

    ```python
    func = registry.factory.get("my-function")
    func()
    # Out: "The value is 10!"
    func(value=42)
    # Out: "The value is 42!"
    ```

## Système de typage

Le décorateur Pydantic `validate_arguments` améliore une fonction pour analyser et valider automatiquement ses arguments à chaque appel, en utilisant le système de validation basé sur le typage Pydantic.
Par exemple, les chaînes de caractères peuvent être automatiquement converties en objets Path, ou en objets datetime ou en nombres, en fonction de l'annotation de type de l'argument.

Combiné avec notre système de configuration, les dictionnaires passés en arguments à une fonction décorée peuvent être "castés" en classes instanciées si ces classes étaient elles-mêmes décorées.

## CLI

Nous fournissons l'objet `confit.Cli`, un wrapper basé sur Typer qui transforme une fonction en une interface de ligne de commande. Une fois décorée avec `@app.command`, la fonction peut être exécutée depuis le terminal et accepte automatiquement un ou plusieurs fichiers `--config` contenant ses paramètres, ainsi que des paramètres simples (qui ont la priorité).

Par exemple, nous allons décorer la fonction `cool_function` pour la rendre disponible en tant qu'interface de ligne de commande, et placer certains de ses paramètres dans un fichier de configuration `config.yml` :

```python
from confit import Cli, Registry, RegistryCollection


class registry(RegistryCollection):
    factory = Registry(("myapp", "factory"), entry_points=True)


@registry.factory.register("my-class")
class MyClass:
    def __init__(self, value1: int, value2: float):
        self.value1 = value1
        self.value2 = value2


app = Cli()


@app.command(name="cool_function", registry=registry)
def cool_function(
    modelA: MyClass,
    modelB,
    seed: int = 0,
):
    ...


if __name__ == "__main__":
    app()
```

```yaml { title="config.yml" }
# Pas besoin de @factory ici, car le type hint est suffisant
modelA:
  value1: 0
  value2: 1.5

# ModelB n'est pas type hinté, alors nous devons indiquer comment l'instancier
modelB:
  "@factory": "my-class"
  value1: 2
  value2: 3.5

cool_function:
  modelA: ${modelA}
  modelB: ${modelB}
```

Il ne reste plus qu'à exécuter le script avec l'option `--config`, qui lira le fichier de configuration et instanciera les objets en conséquence:

```bash
python script.py --config config.yml --seed 42
```

Les arguments de ligne de commande remplacent les valeurs de la configuration. Si plusieurs fichiers de configuration sont fournis, ils sont fusionnés dans l'ordre.


## L'objet Config

L'objet de configuration, la classe `Config`, est un dictionnaire augmenté qui peut être utilisé pour lire et écrire des fichiers `cfg`, interpoler des variables et instancier des composants via le registre avec des clés spéciales `@factory`.
Un fichier cfg peut être utilisé directement comme entrée pour une fonction décorée en CLI.

Nous montrerons ci-dessous des exemples partiels de complexité croissante. Voir [ici][un-example-simple] pour un exemple complet.

### Instanciation d'un objet

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

Ici, **Confit** va :

- Analyser la configuration
- Récupérer la classe cible à partir du registre
- Valider les paramètres si nécessaire (dans ce cas, `value1` est typé en tant qu'entier, il sera donc converti en entier en définissant `value1=1`)
- Instancier la classe en utilisant les paramètres validés

### Interpolation des valeurs

Lorsque plusieurs sections de la configuration doivent accéder à la même valeur, vous pouvez utiliser une référence avec la syntaxe `${<section.value>}` :

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

Ici, `value2` sera défini à 10, comme `value3`.

### Interpolation avancée

Vous pouvez même passer des objets instanciés ! Supposons que nous ayons une classe enregistrée `myOtherClass` attendant une instance de `MyClass` en entrée. Vous pourriez utiliser la configuration suivante :

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

Enfin, vous pouvez vouloir accéder à certains attributs des classes Python qui sont disponibles *après* l'instanciation, mais pas présents dans le fichier de configuration. Par exemple, modifions notre classe `MyClass` :

```diff title="script.py"
@registry.factory.register("my-class")
class MyClass:
    def __init__(self, value1: int, value2: float):
        self.value1 = value1
        self.value2 = value2
+         self.hidden_value = 99
```

Pour accéder à ces valeurs directement dans le fichier de configuration, utilisez la syntaxe `${<obj:attribut>}` (remarquez les **deux points** au lieu du **point**)

=== "INI syntax"

    ```ini title="config.cfg"
    [object]
    @factory = "my-class"
    value1 = 1.1
    value2 = 2.5

    [other_values]
    value3 = ${object:hidden_value}
    ```

=== "YAML syntax"

    ```yaml title="config.yaml"
    object:
      "@factory": "my-class"
      value1: 1.1
      value2: 2.5

    other_values:
        value3: ${object:hidden_value}
    ```

## Drafts (brouillons)

Lorsqu'un composant est instancié avec `MyClass.draft(...)` au lieu de `MyClass(...)`, l'appel renvoie un objet `Draft` plutôt que de d'instancier l'objet immédiatement.

Ce "brouillon" conserve les paramètres fournis et peut être instancié plus tard via `Draft.instantiate()`. C'est notamment utile lorsque tous les paramètres ne sont pas prêts au même moment, et que l'instantiation de l'objet peut être deleguée à un autre composant.

Cela peut être vu comme une version simplifiée du [pattern de construction](https://en.wikipedia.org/wiki/Builder_pattern) en programmation.

```python
from confit import validate_arguments


@validate_arguments
class MyClass:
    def __init__(self, value1: int, value2: float):
        self.value1 = value1
        self.value2 = value2

    def __repr__(self):
        return f"MyClass(value1={self.value1}, value2={self.value2})"


draft = MyClass.draft(value1=1)
type(draft)
# Out: Draft[MyClass]

draft.instantiate(value2=2.5)
# Out: MyClass(value1=1, value2=2.5)
```

Depuis un fichier de configuration, un brouillon peut être instancié en utilisant la syntaxe suivante :
```yaml
modelA:
    "@draft": my-class !draft
    value1: 0
```
