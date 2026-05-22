from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional, Set, Iterable, Any
from mtg import constants as cts
from mtg.deck_strategies import StrategyManager, DeckStrategy

# Rôles principaux gérés par le système de scoring
ROLE_RAMP = "Ramp"
ROLE_DRAW = "Draw"
ROLE_REMOVAL = "Removal"
ROLE_WINCON = "Finisher"

PRIMARY_ROLES = {ROLE_RAMP, ROLE_DRAW, ROLE_REMOVAL, ROLE_WINCON}


# Poids par rôle pour le scoring (spec utilisateur)
ROLE_WEIGHTS: Dict[str, float] = {
    ROLE_RAMP: 0.9,
    ROLE_DRAW: 0.7,
    ROLE_REMOVAL: 0.5,
    ROLE_WINCON: 1,
}

DEFAULT_ROLE_WEIGHT = 0.2

logger = logging.getLogger(__name__)


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
    cards: List["BuiltDeckCard"]


@dataclass
class BuiltDeckCard:
    name: str
    types: str
    role: str
    score: float
    cmc: float
    scryfall_id: Optional[str]
    image_url: Optional[str]
    colors: Any
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    rarity: str = ""
    selection_stage: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "types": self.types,
            "role": self.role,
            "score": self.score,
            "cmc": self.cmc,
            "scryfall_id": self.scryfall_id,
            "image_url": self.image_url,
            "colors": self.colors,
            "set_code": self.set_code,
            "set_name": self.set_name,
            "collector_number": self.collector_number,
            "rarity": self.rarity,
            "selection_stage": self.selection_stage,
        }


class DeckBuilder:
    """Interface orientée objet autour des fonctions de scoring et de build.

    Cette classe n'est pas utilisée directement par le reste du projet pour
    l'instant, mais elle offre un point d'entrée pratique pour intégrer le
    module à l'interface graphique ou à d'autres composants.
    """

    def __init__(self, app, commander_name:str, eventual_deck_data: List[Dict[str, Any]], strategy_manager: Optional[StrategyManager] = None) -> None:
        self.app = app
        self.commander_name = commander_name
        self.commander_colors = self._get_card_colors(commander_name)
        self.deck_data = eventual_deck_data
        self.strategy_manager = strategy_manager
        self.commander_synergies: List[str] = []
        
        # Récupérer les données du commandant pour détecter les synergies
        if strategy_manager:
            self._load_commander_data()
        
        self.scored_cards = self.score_cards()

    def _get_card_colors(self, name: str) -> Set[str]:
        """Retourne l'identité couleur connue d'une carte.

        Si aucune information n'est disponible, considère la carte comme
        incolore (ensemble vide), ce qui la rend toujours jouable vis-à-vis
        de l'identité couleur du commandant.
        """
        return self.app.collection_manager.get_card_colors(name)
    
    def _load_commander_data(self):
        """Charge les données du commandant pour détecter les synergies."""
        try:
            commander_data = self.app.external_provider.get_scryfall_data(self.commander_name)
            if commander_data:
                self.commander_synergies = self.strategy_manager.detect_commander_synergies(commander_data)
        except Exception:
            logger.exception("Impossible de charger les données Scryfall du commandant '%s'", self.commander_name)
            self.commander_synergies = []


    def _get_role_weight(self, role: str) -> float:
        """Retourne le poids de rôle pour le scoring."""

        return ROLE_WEIGHTS.get(role, DEFAULT_ROLE_WEIGHT)

    def _get_card_cmc(self, card_info: Dict[str, Any]) -> float:
        scryfall_id = card_info.get("scryfall_id")
        card_name = card_info.get("name", "")
        cmc = None

        # Priorité au bulk local (offline) pour éviter les appels API pendant le build.
        bulk_provider = getattr(self.app.window, "scryfall_sync", None)
        if bulk_provider and (scryfall_id or card_name):
            bulk_data = bulk_provider.get_card_for_import(
                scryfall_id=str(scryfall_id or ""),
                card_name=card_name,
            )
            if bulk_data:
                raw_cmc = bulk_data.get("cmc")
                try:
                    cmc = float(raw_cmc) if raw_cmc is not None else None
                except (TypeError, ValueError):
                    cmc = None

        # Fallback API seulement si bulk indisponible/incomplet.
        if cmc is None and scryfall_id and not str(scryfall_id).startswith("cardnexus::"):
            cmc = self.app.external_provider.get_card_cmc(scryfall_id)

        return float(cmc or 0)

    def _get_card_role(self, entry: Dict[str, Any]) -> str:
        return str(entry.get("defaultCategory") or entry.get("role") or "")

    def _make_selected_card_item(
        self,
        info: Dict[str, Any],
        score_by_name: Dict[str, float],
        role_by_name: Dict[str, str],
        selection_stage: str,
    ) -> BuiltDeckCard:
        card_name = info.get("name", "")
        return BuiltDeckCard(
            name=card_name,
            types=info.get("types", ""),
            role=role_by_name.get(card_name) or self._get_card_role(info),
            score=score_by_name.get(card_name, 0.0),
            cmc=self._get_card_cmc(info),
            scryfall_id=info.get("scryfall_id"),
            image_url=info.get("image_url"),
            colors=info.get("colors", ""),
            set_code=info.get("set_code", ""),
            set_name=info.get("set_name", ""),
            collector_number=info.get("collector_number", ""),
            rarity=info.get("rarity", ""),
            selection_stage=selection_stage,
        )

    def _make_commander_fallback_item(self, score_by_name: Dict[str, float], selection_stage: str) -> BuiltDeckCard:
        commander_data: Dict[str, Any] = {}
        try:
            commander_data = self.app.external_provider.get_scryfall_data(self.commander_name) or {}
        except Exception:
            logger.exception("Impossible de récupérer le commandant '%s' depuis Scryfall", self.commander_name)

        image_url = None
        if "image_uris" in commander_data:
            urls = commander_data["image_uris"]
            image_url = (
                urls.get("normal")
                or urls.get("large")
                or urls.get("png")
            )
        faces = commander_data.get("card_faces")
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

        return BuiltDeckCard(
            name=self.commander_name,
            types=commander_data.get("type_line", ""),
            role=ROLE_WINCON,
            score=score_by_name.get(self.commander_name, 1.0),
            cmc=commander_data.get("cmc", 0) or 0,
            scryfall_id=commander_data.get("id"),
            image_url=image_url,
            colors=commander_data.get("color_identity", sorted(self.commander_colors)),
            rarity=commander_data.get("rarity", ""),
            set_code=commander_data.get("set", ""),
            set_name=commander_data.get("set_name", ""),
            collector_number=commander_data.get("collector_number", ""),
            selection_stage=selection_stage,
        )


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
        
        # Filtrer par rareté en mode budget
        filtered_data = self.deck_data
        if self.strategy_manager and self.strategy_manager.budget_mode:
            filtered_data = [
                entry for entry in self.deck_data 
                if self.strategy_manager.is_budget_card(entry)
            ]
        
        for entry in filtered_data:
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

            role = self._get_card_role(entry)
            role_weight = self._get_role_weight(role)

            final = 0.65 * meta_score + 0.25 * rank_score + 0.10 * role_weight
            final = round(final, 4)
            
            # Bonus de synergie avec le commandant
            if self.strategy_manager and self.commander_synergies:
                final = self.strategy_manager.score_card_synergy(entry, self.commander_synergies, final)
            
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
            ROLE_WINCON: window.numb_wincondition.value(),
        }

        # Préparation des structures de sélection
        selected: List[str] = []
        selected_set: Set[str] = set()
        selection_stage_by_index: Dict[int, str] = {}

        def _add_selected_card(name: str, selection_stage: str) -> None:
            selected.append(name)
            selection_stage_by_index[len(selected) - 1] = selection_stage
            if name not in BASIC_LANDS:
                selected_set.add(name)

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
                # On ajoute le commandant comme première carte sélectionnée
                _add_selected_card(self.commander_name, "commander_seed")
                score_by_name.setdefault(self.commander_name, 1.0)
                role_by_name.setdefault(self.commander_name, ROLE_WINCON)
                # S'assurer qu'on garde une place pour lui dans le total de 100
                # (les étapes suivantes sélectionnent au plus 99 autres cartes).
            except Exception:
                # Si l'appel à Scryfall échoue, on ne force pas l'ajout
                pass
        else:
            # Le commandant est dans les candidats, on l'ajoute explicitement
            # avec le bon stage pour éviter qu'il soit sélectionné par erreur
            _add_selected_card(self.commander_name, "commander_seed")
            score_by_name.setdefault(self.commander_name, 1.0)
            role_by_name.setdefault(self.commander_name, ROLE_WINCON)

        # 1) Sélection par rôles (hors terrains)
        current_role_counts: Dict[str, int] = {r: 0 for r in PRIMARY_ROLES}

        for name in nonland_candidates:
            if name in selected_set:
                continue
            # Ignorer le commandant ici, il sera traité explicitement
            if name == self.commander_name:
                continue

            role = role_by_name.get(name)
            if role not in PRIMARY_ROLES:
                continue

            max_for_role = role_targets_max.get(role, 0)
            if current_role_counts[role] >= max_for_role:
                continue

            _add_selected_card(name, f"role:{role}")
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
            # Ignorer le commandant ici, il sera traité explicitement
            if name == self.commander_name:
                continue
            role = role_by_name.get(name)
            if role in PRIMARY_ROLES:
                continue

            _add_selected_card(name, "fill:nonland")

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

                _add_selected_card(name, "land:distinct")
                lands_added += 1

            # b) Compléter avec des terrains de base (duplicatas autorisés)
            basic_candidates = [n for n in land_candidates if n in BASIC_LANDS]

            if basic_candidates and lands_added < desired_lands and len(selected) < 100:
                # On boucle de manière déterministe sur les terrains de base
                # pour remplir jusqu'à la cible.
                idx = 0
                while lands_added < desired_lands and len(selected) < 100:
                    name = basic_candidates[idx % len(basic_candidates)]
                    _add_selected_card(name, "land:basic_fill")
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
                _add_selected_card(name, "fill:collection_limit")
                remaining_slots -= 1
                idx += 1

        # Tronquer au cas où on aurait légèrement dépassé (sécurité)
        if len(selected) > 100:
            selected = selected[:100]
            
        list_info_selected: List[BuiltDeckCard] = []
        cts.DECK_BUILD_SCRYFALL_ID_LIST = []
        info_by_name: Dict[str, Dict[str, Any]] = {}
        for info in self.deck_data:
            name = info.get("name")
            if name and name not in info_by_name:
                info_by_name[name] = info

        for selected_index, card_name in enumerate(selected):
            selection_stage = selection_stage_by_index.get(selected_index, "")
            info = info_by_name.get(card_name)
            if info is None:
                if card_name == self.commander_name:
                    commander_item = self._make_commander_fallback_item(score_by_name, selection_stage or "commander_fallback")
                    list_info_selected.append(commander_item)
                    if commander_item.scryfall_id:
                        cts.DECK_BUILD_SCRYFALL_ID_LIST.append(commander_item.scryfall_id)
                    continue
                logger.warning("Carte sélectionnée absente des données candidates: %s", card_name)
                continue

            list_info_selected.append(self._make_selected_card_item(info, score_by_name, role_by_name, selection_stage))
            if info.get("scryfall_id"):
                cts.DECK_BUILD_SCRYFALL_ID_LIST.append(info["scryfall_id"])

        # Si le commandant n'est pas présent dans les cartes sélectionnées
        # (parce qu'il n'est pas dans la collection), on l'ajoute quand même
        # en allant chercher ses informations via Scryfall.
        commander_already_in_deck = any(
            card.name == self.commander_name for card in list_info_selected
        )
        if not commander_already_in_deck:
            commander_item = self._make_commander_fallback_item(score_by_name, "commander_fallback")
            list_info_selected.insert(0, commander_item)
            if commander_item.scryfall_id:
                cts.DECK_BUILD_SCRYFALL_ID_LIST.insert(0, commander_item.scryfall_id)

        return Deck(commander=self.commander_name, cards=list_info_selected)


