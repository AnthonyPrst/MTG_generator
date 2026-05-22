import ast
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DeckCandidate:
    name: str
    colors: str
    types: str
    scryfall_id: str
    image_url: str
    edhrec_rank: int
    occurence: int
    defaultCategory: str
    needed: int
    owned: int
    missing: int
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    rarity: str = ""

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "DeckCandidate":
        return cls(
            name=str(data.get("name", "")),
            colors=str(data.get("colors", "")),
            types=str(data.get("types", "")),
            scryfall_id=str(data.get("scryfall_id", "") or ""),
            image_url=str(data.get("image_url", "") or ""),
            edhrec_rank=int(data.get("edhrec_rank", 0) or 0),
            occurence=int(data.get("occurence", 0) or 0),
            defaultCategory=str(data.get("defaultCategory", "") or ""),
            needed=int(data.get("needed", 0) or 0),
            owned=int(data.get("owned", 0) or 0),
            missing=int(data.get("missing", 0) or 0),
            set_code=str(data.get("set_code", "") or ""),
            set_name=str(data.get("set_name", "") or ""),
            collector_number=str(data.get("collector_number", "") or ""),
            rarity=str(data.get("rarity", "") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "colors": self.colors,
            "types": self.types,
            "scryfall_id": self.scryfall_id,
            "image_url": self.image_url,
            "edhrec_rank": self.edhrec_rank,
            "occurence": self.occurence,
            "defaultCategory": self.defaultCategory,
            "needed": self.needed,
            "owned": self.owned,
            "missing": self.missing,
            "set_code": self.set_code,
            "set_name": self.set_name,
            "collector_number": self.collector_number,
            "rarity": self.rarity,
        }


@dataclass(slots=True)
class DeckSearchResult:
    candidates: List[DeckCandidate]
    decks_scanned: int
    decks_found: int
    excluded_count: int = 0
    color_filtered_count: int = 0

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [candidate.to_dict() for candidate in self.candidates]


class DeckSearchService:
    def __init__(self, collection_manager, external_provider, throttle_seconds: float = 0.1):
        self.collection_manager = collection_manager
        self.external_provider = external_provider
        self.throttle_seconds = throttle_seconds

    def search_commander_candidates(
        self,
        commander_name: str,
        order_by: str,
        deck_search_index: int,
        deck_ids: Optional[List[str]] = None,
        excluded_card_names: Optional[set[str]] = None,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> DeckSearchResult:
        if deck_ids is None:
            deck_ids = self.external_provider.get_archidekt_decks_id_for_commander(commander_name, order_by)
        decks_found = len(deck_ids)
        decks_scanned = self._resolve_deck_count(decks_found, deck_search_index)
        aggregated_cards = self._aggregate_archidekt_cards(deck_ids[:decks_scanned], progress_cb=progress_cb)
        owned_cards = self.collection_manager.compare_deck_to_collection(aggregated_cards)
        commander_colors = self.collection_manager.get_card_colors(commander_name)

        excluded_names = {name.lower() for name in (excluded_card_names or set())}
        color_filtered_count = 0
        excluded_count = 0
        filtered_candidates: List[DeckCandidate] = []

        for card in owned_cards:
            if not self._normalize_color_tokens(card.get("colors", "")).issubset(commander_colors):
                color_filtered_count += 1
                continue
            if excluded_names and str(card.get("name", "")).lower() in excluded_names and int(card.get("owned", 0) or 0) < 2:
                excluded_count += 1
                continue
            filtered_candidates.append(DeckCandidate.from_mapping(card))

        filtered_candidates.sort(key=lambda candidate: candidate.types)
        return DeckSearchResult(
            candidates=filtered_candidates,
            decks_scanned=decks_scanned,
            decks_found=decks_found,
            excluded_count=excluded_count,
            color_filtered_count=color_filtered_count,
        )

    def _aggregate_archidekt_cards(
        self,
        deck_ids: List[str],
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        cards: Dict[str, Dict[str, Any]] = {}
        for idx, deck_id in enumerate(deck_ids, start=1):
            if self.throttle_seconds > 0:
                time.sleep(self.throttle_seconds)
            deck = self.external_provider.load_archidekt_deck(deck_id)
            for name, info in deck.items():
                if name in cards:
                    cards[name]["occurence"] += info.get("occurence", 1)
                else:
                    cards[name] = dict(info)
            if progress_cb:
                progress_cb(idx)
        return cards

    @staticmethod
    def _resolve_deck_count(numbers_decks: int, deck_search_index: int) -> int:
        match deck_search_index:
            case 0:
                return round(numbers_decks / 3)
            case 1:
                return round(numbers_decks * 2 / 3)
            case _:
                return numbers_decks

    @staticmethod
    def _normalize_color_tokens(raw_colors: Any) -> set[str]:
        if isinstance(raw_colors, (list, tuple, set)):
            values = raw_colors
        else:
            try:
                values = ast.literal_eval(raw_colors) if raw_colors else []
            except Exception:
                values = str(raw_colors or "").replace("[", "").replace("]", "").replace("'", "").split(",")

        return {
            str(color).strip().upper()
            for color in values
            if str(color).strip() and str(color).strip().lower() != "colorless"
        }
