from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Iterable, Any
from mtg import constants as cts

# Rôles principaux gérés par le système de scoring
ROLE_RAMP = "Ramp"
ROLE_DRAW = "Draw"
ROLE_REMOVAL = "Removal"  # target removal
ROLE_BOARDWIPE = "Boardwipe"
ROLE_WINCON = "Finisher"

PRIMARY_ROLES = {ROLE_RAMP, ROLE_DRAW, ROLE_REMOVAL, ROLE_BOARDWIPE, ROLE_WINCON}


# Poids par rôle pour le scoring (spec utilisateur)
ROLE_WEIGHTS: Dict[str, float] = {
    ROLE_RAMP: 0.9,
    ROLE_DRAW: 0.7,
    ROLE_REMOVAL: 0.3,
    ROLE_BOARDWIPE: 0.6,
    ROLE_WINCON: 1,
}

DEFAULT_ROLE_WEIGHT = 0.2


# Terrains de base autorisant les duplicatas
BASIC_LANDS: Set[str] = {
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    # Quelques variantes francisées courantes (au cas où la collection soit FR)
    "Plaine",
    "Ile",
    "Île",
    "Marais",
    "Montagne",
    "Forêt",
}

# Bornes de terrains
LANDS_MIN = 35
LANDS_MAX = 38


@dataclass
class Deck:
    """Représente un deck Commander généré.

    Attributes:
        commander: Nom du commandant.
        cards: Liste de noms de cartes constituant le deck. La taille visée
            est de 100 cartes au total.
    """

    commander: str
    cards: List[Dict]


class DeckBuilder:
    """Interface orientée objet autour des fonctions de scoring et de build.

    Cette classe n'est pas utilisée directement par le reste du projet pour
    l'instant, mais elle offre un point d'entrée pratique pour intégrer le
    module à l'interface graphique ou à d'autres composants.
    """

    def __init__(self, app, commander_name:str, eventual_deck_data: List[Dict[str, Any]]) -> None:
        self.app = app
        self.commander_name = commander_name
        self.commander_colors = self._get_card_colors(commander_name)
        self.deck_data = eventual_deck_data
        self.scored_cards = self.score_cards()

    def _get_card_colors(self, name: str) -> Set[str]:
        """Retourne l'identité couleur connue d'une carte.

        Si aucune information n'est disponible, considère la carte comme
        incolore (ensemble vide), ce qui la rend toujours jouable vis-à-vis
        de l'identité couleur du commandant.
        """
        return self.app.collection_manager.get_card_colors(name)


    def _get_role_weight(self, role: str) -> float:
        """Retourne le poids de rôle pour le scoring."""

        return ROLE_WEIGHTS.get(role, DEFAULT_ROLE_WEIGHT)


    def score_cards(self) -> List[Dict[str, Any]]:
        """Calcule un score pour chaque carte de la collection.

        Returns:
            Liste de dicts ``{"name": str, "score": float, "role": str}``
            triée par score décroissant.
        """

        # Construction d'un lookup par nom à partir du format GUI (liste de dicts
        # contenant au moins name, occurence et edhrec_rank).
        #
        # On calcule un meta score combiné selon l'option 2 :
        #   - occ_norm = occurence / max(occurence)
        #   - rank_norm = 1 - (edhrec_rank / max(edhrec_rank))  (plus le rang est
        #     faible, meilleur est le score normalisé)
        #   - meta_score = (occ_norm + rank_norm) / 2

        max_occ = 0
        max_rank = 0
        for entry in self.deck_data:
            try:
                occ = int(entry.get("occurence", 0) or 0)
            except (TypeError, ValueError):
                occ = 0
            try:
                rank = int(entry.get("edhrec_rank", 0) or 0)
            except (TypeError, ValueError):
                rank = 0
            if occ > max_occ:
                max_occ = occ
            if rank > max_rank:
                max_rank = rank

        scored: List[Dict[str, Any]] = []
        commander_colors = set(self.commander_colors)
        for entry in self.deck_data:
            name = entry.get("name")
            if not name:
                continue
            # Filtre identité couleur : la carte doit être un sous-ensemble
            # des couleurs du commandant. Les cartes sans info sont considérées
            # comme incolores et donc toujours jouables.
            card_colors = self._get_card_colors(name)
            if card_colors and not card_colors.issubset(commander_colors):
                continue
            try:
                occ = int(entry.get("occurence", 0) or 0)
            except (TypeError, ValueError):
                occ = 0
            try:
                rank = int(entry.get("edhrec_rank", 0) or 0)
            except (TypeError, ValueError):
                rank = 0

            meta_score = (occ / max_occ) if max_occ > 0 else 0.0
            rank_score = 0.0
            if max_rank > 0 and rank > 0:
                rank_score = 1.0 - (rank / max_rank)
                if rank_score < 0.0:
                    rank_score = 0.0

            role = entry.get("defaultCategory")
            role_weight = self._get_role_weight(role)

            final = 0.65 * meta_score + 0.25 * rank_score + 0.10 * role_weight
            final = round(final, 4)

            scored.append({"name": name, "score": final, "role": role})

        # Tri décroissant par score, puis par nom pour déterminisme
        scored.sort(key=lambda c: (-c["score"], c["name"]))
        return scored


    def build_deck(self) -> Deck:
        """Construit un deck Commander valide à partir d'une liste scorée.

        L'algorithme suit les règles suivantes :

        - Crée des sous-listes par rôle.
        - Sélectionne les meilleures cartes de chaque rôle jusqu'aux bornes
          définies dans l'onglet Paramètres (ramp, draw, removal, boardwipe,
          wincondition).
        - Complète ensuite avec les meilleures cartes restantes (non-terrains),
          en gardant de la place pour au moins ``numb_min_land`` terrains.
        - Ajoute ensuite les terrains (lands) jusqu'à atteindre l'intervalle
          [``numb_min_land``, ``numb_max_land``], en autorisant les duplicatas
          uniquement pour les terrains de base.
        - S'arrête à 100 cartes exactement lorsque c'est possible ; si la
        collection est insuffisante, le deck peut être plus petit.
        """

        # Lecture des paramètres dynamiques depuis la fenêtre principale
        window = self.app.window
        lands_min = window.numb_min_land.value()
        lands_max = window.numb_max_land.value()

        role_targets_max: Dict[str, int] = {
            ROLE_RAMP: window.numb_ramp.value(),
            ROLE_DRAW: window.numb_draw.value(),
            ROLE_REMOVAL: window.numb_removal.value(),
            ROLE_BOARDWIPE: window.numb_boardwipe.value(),
            ROLE_WINCON: window.numb_wincondition.value(),
        }

        # Préparation des structures de sélection
        selected: List[str] = []
        selected_set: Set[str] = set()

        # Mapping rapide name -> (score, role)
        score_by_name: Dict[str, float] = {}
        role_by_name: Dict[str, str] = {}

        for entry in self.scored_cards:
            name = entry["name"]
            score_by_name[name] = float(entry.get("score", 0.0))
            role_by_name[name] = entry.get("role")

        # Extraction des candidats land / non-land
        land_candidates: List[str] = []
        nonland_candidates: List[str] = []

        for entry in self.scored_cards:
            name = entry["name"]
            role = entry["role"]
            if role == "Land":
                land_candidates.append(name)
            else:
                nonland_candidates.append(name)

        # Ajouter le commandant au tout début s'il n'est pas déjà dans les
        # candidats issus de la collection (cas commandant non possédé).
        commander_in_candidates = self.commander_name in nonland_candidates or self.commander_name in land_candidates
        if not commander_in_candidates:
            try:
                # data = self.app.external_provider.get_scryfall_data(self.commander_name)
                # types = data.get("type_line", "")
                # scryfall_id = data.get("id")

                # image_url = None
                # if "image_uris" in data:
                #     urls = data["image_uris"]
                #     image_url = (
                #         urls.get("normal")
                #         or urls.get("large")
                #         or urls.get("png")
                #     )
                # faces = data.get("card_faces")
                # if faces and not image_url:
                #     for face in faces:
                #         urls = face.get("image_uris")
                #         if urls:
                #             image_url = (
                #                 urls.get("normal")
                #                 or urls.get("large")
                #                 or urls.get("png")
                #             )
                #             if image_url:
                #                 break

                # On ajoute le commandant comme première carte sélectionnée
                selected.append(self.commander_name)
                selected_set.add(self.commander_name)
                score_by_name.setdefault(self.commander_name, 1.0)
                role_by_name.setdefault(self.commander_name, ROLE_WINCON)
                # S'assurer qu'on garde une place pour lui dans le total de 100
                # (les étapes suivantes sélectionnent au plus 99 autres cartes).
            except Exception:
                # Si l'appel à Scryfall échoue, on ne force pas l'ajout
                pass

        # 1) Sélection par rôles (hors terrains)
        current_role_counts: Dict[str, int] = {r: 0 for r in PRIMARY_ROLES}

        for name in nonland_candidates:
            if name in selected_set:
                continue

            role = role_by_name.get(name)
            if role not in PRIMARY_ROLES:
                continue

            max_for_role = role_targets_max.get(role, 0)
            if current_role_counts[role] >= max_for_role:
                continue

            selected.append(name)
            selected_set.add(name)
            current_role_counts[role] += 1

            if len(selected) >= 100:
                break

        # 2) Compléter avec les meilleures cartes restantes (hors terrains),
        # en laissant de la place pour au moins lands_min terrains si possible.
        max_nonlands = max(0, 100 - lands_min)

        for name in nonland_candidates:
            if len(selected) >= max_nonlands:
                break
            if name in selected_set:
                continue
            role = role_by_name.get(name)
            if role in PRIMARY_ROLES:
                continue

            selected.append(name)
            selected_set.add(name)

        # 3) Ajout des terrains
        remaining_slots = 100 - len(selected)
        if remaining_slots > 0 and land_candidates:
            # Objectif : rester dans [lands_min, lands_max] si possible.
            desired_lands = min(lands_max, remaining_slots)
            # Si on ne peut pas atteindre LANDS_MIN, on utilise simplement tous
            # les slots restants.
            if desired_lands < lands_min:
                desired_lands = remaining_slots

            lands_added = 0

            # a) Ajouter au moins une copie de chaque terrain candidat distinct
            #    qui n'est pas déjà présent.
            for name in land_candidates:
                if lands_added >= desired_lands or len(selected) >= 100:
                    break
                if name in selected_set:
                    continue

                selected.append(name)
                selected_set.add(name)
                lands_added += 1

            # b) Compléter avec des terrains de base (duplicatas autorisés)
            basic_candidates = [n for n in land_candidates if n in BASIC_LANDS]

            if basic_candidates and lands_added < desired_lands and len(selected) < 100:
                # On boucle de manière déterministe sur les terrains de base
                # pour remplir jusqu'à la cible.
                idx = 0
                while lands_added < desired_lands and len(selected) < 100:
                    name = basic_candidates[idx % len(basic_candidates)]
                    selected.append(name)
                    lands_added += 1
                    idx += 1

        # 4) Si on a encore moins de 100 cartes (collection très limitée),
        #    on tente de compléter avec le reste de carte non land
        remaining_slots = 100 - len(selected)
        if remaining_slots > 0 and land_candidates:
            list_of_candidate = []
            for name in nonland_candidates:
                if name in selected_set:
                    continue
                list_of_candidate.append(name)
            idx = 0
            while remaining_slots > 0 and list_of_candidate:
                name = list_of_candidate[idx % len(list_of_candidate)]
                selected.append(name)
                selected_set.add(name)
                remaining_slots -= 1
                idx += 1

        # Tronquer au cas où on aurait légèrement dépassé (sécurité)
        if len(selected) > 100:
            selected = selected[:100]
            
        list_info_selected = []
        cts.DECK_BUILD_SCRYFALL_ID_LIST = []
        for info in self.deck_data:
            if info["name"] in selected:
                cts.DECK_BUILD_SCRYFALL_ID_LIST.append(info["scryfall_id"])
                items = {
                    "name": info["name"],
                    "types": info["types"],
                    "role": info["defaultCategory"],
                    "score": score_by_name[info["name"]],
                    "scryfall_id": info["scryfall_id"],
                    "image_url": info["image_url"],
                }
                list_info_selected.append(items)

        # Si le commandant n'est pas présent dans les cartes sélectionnées
        # (parce qu'il n'est pas dans la collection), on l'ajoute quand même
        # en allant chercher ses informations via Scryfall.
        commander_already_in_deck = any(
            card["name"] == self.commander_name for card in list_info_selected
        )
        if not commander_already_in_deck:
            try:
                data = self.app.external_provider.get_scryfall_data(self.commander_name)
                types = data.get("type_line", "")
                scryfall_id = data.get("id")

                image_url = None
                if "image_uris" in data:
                    urls = data["image_uris"]
                    image_url = (
                        urls.get("normal")
                        or urls.get("large")
                        or urls.get("png")
                    )
                faces = data.get("card_faces")
                if faces and not image_url:
                    for face in faces:
                        urls = face.get("image_uris")
                        if urls:
                            image_url = (
                                urls.get("normal")
                                or urls.get("large")
                                or urls.get("png")
                            )
                            if image_url:
                                break

                commander_item = {
                    "name": self.commander_name,
                    "types": types,
                    "role": ROLE_WINCON,
                    "score": 1.0,
                    "scryfall_id": scryfall_id,
                    "image_url": image_url,
                }
                list_info_selected.insert(0, commander_item)
                if scryfall_id:
                    cts.DECK_BUILD_SCRYFALL_ID_LIST.insert(0, scryfall_id)
            except Exception:
                # En cas d'échec, on laisse simplement le deck sans commandant
                pass

        return Deck(commander=self.commander_name, cards=list_info_selected)


