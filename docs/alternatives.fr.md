# Alternatives & Comparaison

Dans cette section, nous explorons ce qui a inspiré Confit et les différences notables avec d'autres packages Python.

### Confection

[Confection](https://github.com/explosion/confection) (issu de la librairie [Thinc](https://github.com/explosion/thinc)) est un autre framework de configuration dont Confit s'inspire largement. Confit et Confection permettent tous deux le chargement et l'exportation des données de configuration à partir de/vers des chaînes de caractères ou des fichiers de configuration, ainsi que interpolation sur des types basiques et l'instanciation de classes personnalisées à partir d'un registre.

Cependant, Confit va plus loin en permettant l'évaluation d'expressions arbitraires, l'interpolation post-résolution et des fonctionnalités d'exportation telles que la sauvegarde dans des chaînes de caractères ou des fichiers de configuration, la sérialisation d'objets de type JSON, les classes personnalisées et la sérialisation de références.

Confit offre également une API pour définir des interfaces en ligne de commande en passant soit un fichier de configuration en argument, soit en passant des arguments (ou des substitutions), tout en bénéficiant de la validation des arguments et du transtypage.

### Gin-config

[Gin Config](https://github.com/google/gin-config) est un système de configuration flexible conçu pour la recherche en apprentissage automatique. Comme Confit et Confection, gin-config permet l'interpolation sur des types basiques et l'instanciation de classes personnalisées et offre un support pour les interfaces en ligne de commande. Cependant, il ne fournit pas de fonctionnalités d'exportation d'objets de configuration comme le fait Confit ou de validation des paramètres.

### Typer

[Typer](https://github.com/tiangolo/typer) est une bibliothèque pour définir facilement interfaces en ligne de commande (CLI). Bien que Typer offre une excellent prise en charge pour les CLI et une validation basique des arguments, il ne dispose pas de fonctionnalités liées aux fichiers de configuration telles que le chargement, l'exportation ou la validation des paramètres comme le fait Confit. Confit s'appuie sur Typer pour ses fonctionnalités CLI mais prend également en charge les arguments de fichiers de configuration et l'instanciation de classes à partir d'un registre, qui ne sont pas disponibles dans Typer.

Cependant, si votre objectif principal est de construire une interface en ligne de commande robuste, Typer est une solide alternative.

### Pydantic-CLI

[Pydantic-CLI](https://github.com/mpkocher/pydantic-cli) est une autre bibliothèque CLI qui combine Pydantic et argparse pour créer des interfaces de ligne de commande. Pydantic-CLI fournit un support CLI et une validation des arguments, similaire à Typer. Cependant, elle n'a pas de fonctionnalités liées aux fichiers de configuration comme Confit, et ne permet pas non plus d'instancier des classes personnalisées.

## Tableau de comparaison

### Chargement

| Fonctionnalité                            | Confit             | Confection         | Gin                | Typer           | Pydantic-cli    |
|-------------------------------------------|--------------------|--------------------|--------------------|-----------------|-----------------|
| Chargement à partir du fichier str/config | :white_check_mark: | :white_check_mark: | :no_entry_sign:    | :no_entry_sign: | :no_entry_sign: |
| Interpolation basique                     | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |
| Évaluation d'expressions arbitraires      | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Interpolation post-résolution             | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Instanciation de classe personnalisée     | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |

### Export
| Fonctionnalité                           | Confit             | Confection         | Gin             | Typer           | Pydantic-cli    |
|------------------------------------------|--------------------|--------------------|-----------------|-----------------|-----------------|
| Export vers string / fichier cfg         | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :no_entry_sign: | :no_entry_sign: |
| Sérialisation d'objets de type JSON      | :white_check_mark: | :white_check_mark: | NA              | NA              | NA              |
| Sérialisation des classes personnalisées | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |
| Sérialisation des références             | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |

### Interface en ligne de commande (CLI)
| Fonctionnalité                     | Confit             | Confection      | Gin                | Typer              | Pydantic-cli       |
|------------------------------------|--------------------|-----------------|--------------------|--------------------|--------------------|
| Utilisation en CLI                 | :white_check_mark: | :no_entry_sign: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Options courtes en CLI             | :no_entry_sign:    | NA              | :no_entry_sign:    | :white_check_mark: | :no_entry_sign:    |
| Validation des arguments           | :white_check_mark: | NA              | :no_entry_sign:    | :white_check_mark: | :white_check_mark: |
| Option de fichier de configuration | :white_check_mark: | NA              | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    |


### Validation des paramètres
| Fonctionnalité                          | Confit             | Confection         | Gin             | Typer              | Pydantic-cli       |
|-----------------------------------------|--------------------|--------------------|-----------------|--------------------|--------------------|
| Support de la validation des paramètres | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :white_check_mark: | :white_check_mark: |
| Casting automatique                     | :white_check_mark: | :white_check_mark: | NA              | :white_check_mark: | :white_check_mark: |
| Depuis un appel fonction/classe Python  | :white_check_mark: | :no_entry_sign:    | NA              | :no_entry_sign:    | :no_entry_sign:    |
