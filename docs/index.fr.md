# Confit

Confit est un système de configuration complet et facile d'utilisation qui vise à améliorer la reproductibilité des expériences en s'appuyant sur le système de typage Python, sur des fichiers de configuration minimaux et avec une interface en ligne de commande.

## Architecture

Les trois piliers de ce système de configuration sont le registre [catalogue](https://github.com/explosion/catalogue),
le système de validation [Pydantic](https://github.com/pydantic/pydantic) et la bibliothèque de CLI [typer](https://github.com/tiangolo/typer).

### Registre

Le registre du catalogue enregistre les différents composants et couches qui peuvent être composés ensemble pour construire un pipeline. Une fois enregistrés, avec le décorateur `registry.factory.register` ces composants sont accessibles en tant que [points d'entrée](https://packaging.python.org/en/latest/specifications/entry-points/#entry-points-specification) et peuvent être utilisés dans le système de configuration.
Pour commencer, vous pouvez créer un registre simple avec une seule clé `"factory"` comme suit :

```python
from confit import Registry, set_default_registry


@set_default_registry
class registry:
    factory = Registry(("my_registry", "factory"), entry_points=True)

    _catalogue = dict(
        factory=factory,
    )
```

!!! tip "À quoi-cela sert-il ?"
    Avec ce registre, vous pouvez *ajouter au registre* soit une fonction ou une classe :
    ```python
    @registry.factory.register("ma-fonction")
    def ma_fonction(valeur=10):
        print(f"La valeur est {valeur} !")
    ```
    Maintenant, vous pouvez récupérer la fonction de n'importe où :
    ```python
    func = registry.factory.get("ma-fonction")
    func()
    # Out : "La valeur est 10 !"
    func(valeur=42)
    # Out : "La valeur est 42 !"
    ```

### Système de typage

Le décorateur Pydantic `validate_arguments` permet à une fonction d'analyser et de valider et valider ses arguments à chaque fois qu'elle est appelée, en utilisant le système de validation Pydantic basé sur le typage.
Par exemple, les chaînes de caractères peuvent être automatiquement transformées en objets Path, en dates ou en nombres.
en fonction de l'annotation du type de l'argument.

Combiné avec notre système de configuration, les dictionnaires passés en tant qu'arguments d'une fonction décorée peuvent être "castés" (retypés) comme des classes instanciées si ces classes ont été elles-mêmes décorées.

### CLI

...

## L'objet Config

L'objet configuration consiste en un dictionnaire superchargé, la classe `Config`, qui peut qui peut être utilisée pour lire et écrire dans les fichiers `cfg`, interpoler les variables et instancier les composants par le biais du registre avec certaines clés spéciales `@factory`. Un fichier cfg peut être utilisé directement comme entrée d'une fonction décorée par le CLI.

Nous allons exposer quelques exemples partiels de complexité croissante ci-dessous. Voir [ici][un-exemple-simple] pour un exemple de bout en bout.

### Instanciation d'un objet

```python title="script.py"
@registry.factory.register("ma-classe")
class MaClasse:
    def __init__(self, valeur1 : int, valeur2 : float) :
        self.valeur1 = valeur1
        self.valeur2 = valeur2
```

```ini title="config.cfg"
[objet]
@factory = "ma-classe"
valeur1 = 1.0
valeur2 = 2.5
```

Ici, **Confit** va :

- Analyser la configuration
- Récupérer la classe cible depuis le registre
- Valider les paramètres si nécessaire (dans ce cas, `valeur1` est typée comme un int, donc elle sera castée comme un int en mettant `valeur1=1`)
- Instanciez la classe en utilisant les paramètres validés

### Interpolation des valeurs

Lorsque plusieurs sections de la configuration doivent accéder à la même valeur, vous pouvez la fournir en utilisant la syntaxe `${<section.valeur>}` :

```ini title="config.cfg"
[objet]
@factory = "ma-classe"
valeur1 = 1.1
valeur2 = ${autres_valeurs.valeur3}

[autres_valeurs]
valeur3 = 10
```

Ici, `valeur2` sera fixé à 10.

### Interpolation d'objets

Vous pouvez même passer des objets instanciés ! Supposons que nous ayons une classe enregistrée `mon-autre-classe` qui attend une instance de `MaClasse` en entrée. Vous pourriez utiliser la configuration suivante :

```ini title="config.cfg"
[func]
@factory = "mon-autre-classe"
obj = ${objet}

[objet]
@factory = "ma-classe"
valeur1 = 1.1
valeur2 = ${autres_valeurs.valeur3}

[autres_valeurs]
valeur3 = 10
```

Enfin, vous pouvez vouloir accéder à certains attributs des classes Python qui sont disponibles *après* l'instanciation, mais qui ne sont pas présents dans le fichier de configuration. Par exemple, modifions notre classe `MaClasse` :


```diff title="script.py"
@registry.factory.register("ma-classe")
class MaClasse:
    def __init__(self, valeur1 : int, valeur2 : float) :
        self.valeur1 = valeur1
        self.valeur2 = valeur2
+       self.valeur_cachée = 99
```

Pour accéder à ces valeurs directement dans le fichier de configuration, utilisez la syntaxe ${<obj:attribut>} (remarquez les **deux points** au lieu du **point** mentionné [ici][interpolation-dobjets])


```ini title="config.cfg"
[objet]
@factory = "ma-classe
valeur1 = 1.1
valeur2 = 2.5

[autres_valeurs]
valeur3 = ${objet:valeur_cachée}
```
