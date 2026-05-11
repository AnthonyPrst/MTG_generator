# AGENT.md

## Objectif

Ce dépôt contient une application PySide6 de génération de decks Commander à partir d’une collection locale et de données externes (Scryfall, Archidekt, EDHRec).

## Stack

- Python 3.11+
- PySide6
- SQLite
- pytest
- Environnement local Windows

## Point d’entrée

- Application : `app.py`
- Classe principale : `Launcher`

## Structure du projet

- `app.py` : orchestration principale de l’application
- `mtg/` : logique métier
  - `collection.py` : base SQLite, import/export, recherches collection
  - `import_formats.py` : parsing CSV par plateforme
  - `external_data.py` : appels API externes
  - `scryfall_sync.py` : cache bulk Scryfall local
- `gui/` : interface PySide6
  - `main_window.py` : orchestrateur UI
  - `tabs/collection_tab.py` : onglet collection
  - `tabs/build_tab.py` : génération de deck
  - `tabs/settings_tab.py` : configuration
- `tests/` : tests pytest
- `data/` : base SQLite et données locales

## Commandes utiles

### Lancer l’application

```powershell
.\env\Scripts\python.exe app.py
```

### Lancer les tests

```powershell
.\env\Scripts\python.exe -m pytest -q
```

### Lancer un test ciblé

```powershell
.\env\Scripts\python.exe -m pytest tests/test_collection.py -q
```

## Règles de modification

- Privilégier des changements ciblés et minimaux.
- Ne pas modifier l’architecture UI sans nécessité.
- Ajouter ou mettre à jour des tests pour toute correction métier non triviale.
- Conserver les imports en haut des fichiers.
- Ne pas ajouter de commentaires ou documentation dans le code sans demande explicite.

## Invariants importants

- La collection est stockée dans `data/collection.db`.
- La table `cards` autorise plusieurs impressions d’une même carte si leur identifiant diffère.
- Les lookups par nom peuvent agréger plusieurs impressions côté métier, mais l’onglet collection doit pouvoir afficher chaque ligne importée.
- Le bulk Scryfall local est prioritaire pour limiter les appels API.
- Les objets non jouables Scryfall (ex. `art_series`) ne doivent pas écraser les vraies cartes lors des lookups par nom.

## Import de collection

- Les formats sont gérés dans `mtg/import_formats.py`.
- Toujours vérifier si un problème vient du parsing CSV, d’un mauvais mapping d’identifiant, ou d’un fallback API trop agressif.
- Pour `CardNexus`, conserver une identité distincte par impression si le print exact ne peut pas être résolu.
- En cas d’échec d’import, l’UI doit afficher une erreur explicite.

## Debugging recommandé

- Vérifier d’abord ce qui est réellement stocké en base avant de suspecter l’UI.
- Comparer le CSV source avec les lignes SQLite importées.
- En cas de cartes manquantes, inspecter :
  - le format détecté
  - le `scryfall_id`
  - le `oracle_id`
  - le `set_name`
  - le `collector_number`

## Tests à privilégier

- `tests/test_collection.py` pour les régressions d’import et d’agrégation.
- Ajouter des tests ciblés quand plusieurs impressions d’un même nom sont concernées.

## Remarques

- Le projet utilise actuellement l’interpréteur local : `c:\Users\paris\OneDrive\Documents\Project code\MTG_generator\env\Scripts\python.exe`
- Le README mentionne `main.py`, mais le point d’entrée actuel du projet est `app.py`.
