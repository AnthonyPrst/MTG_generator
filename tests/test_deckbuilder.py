from types import SimpleNamespace

from mtg.deckbuilder import DeckBuilder
from mtg.deck_strategies import StrategyManager


class ValueStub:
    def __init__(self, value: int):
        self._value = value

    def value(self) -> int:
        return self._value


class WindowStub:
    def __init__(self):
        self.numb_min_land = ValueStub(35)
        self.numb_max_land = ValueStub(38)
        self.numb_ramp = ValueStub(0)
        self.numb_draw = ValueStub(0)
        self.numb_removal = ValueStub(0)
        self.numb_wincondition = ValueStub(0)
        self.scryfall_sync = None


class CollectionManagerStub:
    def __init__(self, colors_by_name: dict[str, set[str]]):
        self.colors_by_name = {name: set(colors) for name, colors in colors_by_name.items()}

    def get_card_colors(self, name: str) -> set[str]:
        return set(self.colors_by_name.get(name, set()))


class ExternalProviderStub:
    def __init__(self, commander_data=None, fail_commander: bool = False):
        self.commander_data = commander_data or {}
        self.fail_commander = fail_commander

    def get_scryfall_data(self, commander_name: str):
        if self.fail_commander:
            raise RuntimeError("scryfall unavailable")
        return self.commander_data.get(commander_name, {})

    def get_card_cmc(self, scryfall_id: str):
        raise AssertionError(f"Unexpected live CMC lookup for {scryfall_id}")


def make_candidate(
    name: str,
    *,
    role: str | None = "Other",
    rarity: str = "common",
    types: str = "Creature",
    scryfall_id: str | None = None,
    occurence: int = 10,
    edhrec_rank: int = 100,
    role_field_only: bool = False,
):
    card = {
        "name": name,
        "types": types,
        "occurence": occurence,
        "edhrec_rank": edhrec_rank,
        "scryfall_id": scryfall_id or f"cardnexus::{name.lower().replace(' ', '-')}",
        "image_url": "",
        "colors": "[]",
        "set_code": "",
        "set_name": "",
        "collector_number": "",
        "rarity": rarity,
    }
    if role_field_only:
        card["role"] = role
    else:
        card["defaultCategory"] = role
    return card


def make_app(colors_by_name: dict[str, set[str]], external_provider: ExternalProviderStub):
    return SimpleNamespace(
        collection_manager=CollectionManagerStub(colors_by_name),
        external_provider=external_provider,
        window=WindowStub(),
    )


def test_build_deck_preserves_basic_land_duplicates_and_adds_missing_commander():
    commander_name = "Titania"
    deck_data = [
        make_candidate("Forest", role="Land", types="Land"),
        *[make_candidate(f"Spell {idx}") for idx in range(64)],
    ]
    app = make_app(
        {commander_name: {"G"}},
        ExternalProviderStub(
            commander_data={
                commander_name: {
                    "id": "commander-id",
                    "type_line": "Legendary Creature",
                    "cmc": 5,
                    "color_identity": ["G"],
                }
            }
        ),
    )

    deck = DeckBuilder(app, commander_name, deck_data).build_deck()

    assert len(deck.cards) == 100
    assert deck.cards[0].name == commander_name
    assert deck.cards[0].selection_stage == "commander_seed"
    assert sum(1 for card in deck.cards if card.name == "Forest") == 35
    assert any(card.selection_stage == "land:basic_fill" for card in deck.cards if card.name == "Forest")


def test_build_deck_keeps_commander_when_external_lookup_fails():
    commander_name = "Unknown Commander"
    deck_data = [
        make_candidate("Forest", role="Land", types="Land"),
        *[make_candidate(f"Card {idx}") for idx in range(64)],
    ]
    app = make_app({commander_name: {"G"}}, ExternalProviderStub(fail_commander=True))

    deck = DeckBuilder(app, commander_name, deck_data).build_deck()

    commander_cards = [card for card in deck.cards if card.name == commander_name]
    assert len(commander_cards) == 1
    assert commander_cards[0].scryfall_id is None
    assert commander_cards[0].selection_stage == "commander_seed"


def test_score_cards_uses_role_field_when_default_category_is_missing():
    commander_name = "Omnath"
    candidate = make_candidate("Nature's Lore", role="Ramp", role_field_only=True)
    app = make_app({commander_name: {"G"}}, ExternalProviderStub())

    builder = DeckBuilder(app, commander_name, [candidate])

    assert builder.scored_cards == [{"name": "Nature's Lore", "score": 0.74, "role": "Ramp"}]


def test_strategy_manager_budget_and_pauper_modes_filter_rarities():
    manager = StrategyManager()

    assert manager.is_budget_card({"rarity": "rare"}) is True

    manager.set_budget_mode(True)
    assert manager.is_budget_card({"rarity": "common"}) is True
    assert manager.is_budget_card({"rarity": "uncommon"}) is True
    assert manager.is_budget_card({"rarity": "rare"}) is False

    manager.set_pauper_mode(True)
    assert manager.budget_mode is True
    assert manager.is_budget_card({"rarity": "common"}) is True
    assert manager.is_budget_card({"rarity": "uncommon"}) is False

    manager.set_budget_mode(False)
    assert manager.pauper_mode is False


def test_built_deck_card_to_dict_preserves_selection_stage():
    commander_name = "Aesi"
    deck_data = [
        make_candidate("Forest", role="Land", types="Land"),
        *[make_candidate(f"Spell {idx}") for idx in range(64)],
    ]
    app = make_app({commander_name: {"G", "U"}}, ExternalProviderStub())

    deck = DeckBuilder(app, commander_name, deck_data).build_deck()
    first_card = deck.cards[0].to_dict()

    assert first_card["name"] == commander_name
    assert first_card["selection_stage"] == "commander_seed"
