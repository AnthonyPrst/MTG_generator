# MTG Commander Deck Builder

Outil PySide6 pour générer automatiquement des decks Commander Magic: The Gathering (100 cartes) à partir d’une collection locale et des données Scryfall/EDHRec.

Motivation : pouvoir tester de nouveaux commandants sans racheter des cartes. L’application récupère jusqu’à ~60 decks Archidekt (triés par date de mise à jour ou nombre de vues), croise avec votre collection, puis calcule un score par carte (rôle ramp/draw/etc., occurrence dans les decks, rang EDHREC). Les meilleures cartes sont sélectionnées et le deck est prêt à jouer.

## Fonctionnalités

- Chargement d’une collection locale (SQLite, import CSV).
- Génération d’un deck Commander en respectant les rôles clefs (ramp, draw, removal, boardwipe, finisher) et l’identité couleur du commandant.
- Récupération des images via Scryfall et affichage dans l’UI (grille).
- Paramétrage du nombre de cartes par rôle et du nombre de terrains (min/max).
- Liste des cartes trouvées dans la collection et deck généré avec score moyen.

## Prérequis

- Python 3.11+ recommandé
- Accès réseau pour la récupération des données Scryfall (selon vos usages)

## Installation

1. Cloner le dépôt
2. Créer un environnement virtuel : `python -m venv venv`
3. Activer l’environnement :
   - Windows : `.\venv\Scripts\activate`
   - Unix/macOS : `source venv/bin/activate`
4. Installer les dépendances : `pip install -r requirements.txt`

## Configuration
Assurez-vous que le dossier `data/` existe ou mettez à jour les chemins.

## Lancer l’application

```bash
python main.py
```

Une fenêtre PySide6 s’ouvre :
- Si aucune collection n’a été importée :
  1. Aller dans l’onglet **Ma collection**
  2. Importer une collection via un CSV (actuellement format ManaBox Whole Collection)
- Ensuite :
  1. Sélectionner un commandant (ou saisir son nom)
  2. Générer les cartes disponibles dans votre collection
  3. Générer le deck pour voir la liste et la grille d’images

## Tests

Les tests utilisent pytest.

```bash
pip install -r requirements-dev.txt  # si disponible, sinon installer pytest
pytest
```

## Structure du projet

- `mtg/` : Code source principal (collection, scoring, builders, UI helper)
- `gui/` : Fenêtre principale PySide6
- `tests/` : Tests unitaires (pytest)
- `data/` : Fichiers de données (base SQLite, bulk Scryfall, CSV éventuels)

## Contributions

Les issues et PR sont bienvenues. Merci d’ajouter des tests et une courte description des changements.
