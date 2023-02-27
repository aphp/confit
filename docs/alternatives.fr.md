# Alternatives et comparaison

Les sources d'inspiration de **Confit** et comment la librairie se compare aux autres alternatives.

- [confection](https://github.com/explosion/confection)
- [gin-config](https://github.com/google/gin-config)
- [typer](https://github.com/tiangolo/typer)
- [pydantic-cli](https://github.com/mpkocher/pydantic-cli/tree/master/pydantic_cli)


## Chargement

| Fonctionnalité                            | Confit             | Confection         | Gin                | Typer           | Pydantic-cli    |
|-------------------------------------------|--------------------|--------------------|--------------------|-----------------|-----------------|
| Chargement à partir du fichier str/config | :white_check_mark: | :white_check_mark: | :no_entry_sign:    | :no_entry_sign: | :no_entry_sign: |
| Interpolation basique                     | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |
| Évaluation d'expressions arbitraires      | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Interpolation post-résolution             | :white_check_mark: | :no_entry_sign:    | :no_entry_sign:    | NA              | NA              |
| Instanciation de classe personnalisée     | :white_check_mark: | :white_check_mark: | :white_check_mark: | NA              | NA              |

## Export
| Fonctionnalité                           | Confit             | Confection         | Gin             | Typer           | Pydantic-cli    |
|------------------------------------------|--------------------|--------------------|-----------------|-----------------|-----------------|
| Export vers string / fichier cfg         | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :no_entry_sign: | :no_entry_sign: |
| Sérialisation d'objets de type JSON      | :white_check_mark: | :white_check_mark: | NA              | NA              | NA              |
| Sérialisation des classes personnalisées | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |
| Sérialisation des références             | :white_check_mark: | :no_entry_sign:    | NA              | NA              | NA              |

## Interface en ligne de commande (CLI)
| Fonctionnalité                     | Confit             | Confection      | Gin             | Typer              | Pydantic-cli       |
|------------------------------------|--------------------|-----------------|-----------------|--------------------|--------------------|
| Utilisation en CLI                 | :white_check_mark: | :no_entry_sign: | :no_entry_sign: | :white_check_mark: | :white_check_mark: |
| Options courtes en CLI             | :no_entry_sign:    | NA              | NA              | :white_check_mark: | :no_entry_sign:    |
| Validation des arguments           | :white_check_mark: | NA              | NA              | :white_check_mark: | :white_check_mark: |
| Option de fichier de configuration | :white_check_mark: | NA              | NA              | :no_entry_sign:    | :no_entry_sign:    |


## Validation des paramètres
| Fonctionnalité                          | Confit             | Confection         | Gin             | Typer              | Pydantic-cli       |
|-----------------------------------------|--------------------|--------------------|-----------------|--------------------|--------------------|
| Support de la validation des paramètres | :white_check_mark: | :white_check_mark: | :no_entry_sign: | :white_check_mark: | :white_check_mark: |
| Casting automatique                     | :white_check_mark: | :white_check_mark: | NA              | :white_check_mark: | :white_check_mark: |
| Depuis un appel fonction/classe Python  | :white_check_mark: | :no_entry_sign:    | NA              | :no_entry_sign:    | :no_entry_sign:    |
