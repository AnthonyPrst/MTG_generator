from mtg.deck_search import DeckCandidate, DeckSearchService


class ExternalProviderStub:
    def __init__(self, decks_by_id: dict[str, dict], deck_ids: list[str]):
        self.decks_by_id = decks_by_id
        self.deck_ids = deck_ids
        self.requested_commanders: list[tuple[str, str]] = []

    def get_archidekt_decks_id_for_commander(self, commander_name: str, order_by: str) -> list[str]:
        self.requested_commanders.append((commander_name, order_by))
        return list(self.deck_ids)

    def load_archidekt_deck(self, deck_id: str) -> dict:
        return self.decks_by_id[deck_id]


class CollectionManagerStub:
    def __init__(self, commander_colors: set[str], compared_cards: list[dict]):
        self.commander_colors = set(commander_colors)
        self.compared_cards = compared_cards
        self.compared_payloads: list[dict] = []

    def compare_deck_to_collection(self, deck_data: dict) -> list[dict]:
        self.compared_payloads.append(deck_data)
        return list(self.compared_cards)

    def get_card_colors(self, name: str) -> set[str]:
        return set(self.commander_colors)


def make_compared_card(name: str, *, colors: str, owned: int = 1, role: str = "Other") -> dict:
    return {
        "name": name,
        "colors": colors,
        "types": "Creature",
        "scryfall_id": f"id-{name.lower().replace(' ', '-')}",
        "image_url": "",
        "edhrec_rank": 123,
        "occurence": 5,
        "defaultCategory": role,
        "needed": 1,
        "owned": owned,
        "missing": 0,
        "set_code": "",
        "set_name": "",
        "collector_number": "",
        "rarity": "common",
    }


def test_search_commander_candidates_aggregates_and_filters_results():
    decks_by_id = {
        "1": {
            "Sol Ring": {"oracle_id": "oracle-sol-ring", "quantity": 1, "edhrec_rank": 1, "defaultCategory": "Ramp", "occurence": 1},
            "Counterspell": {"oracle_id": "oracle-counterspell", "quantity": 1, "edhrec_rank": 2, "defaultCategory": "Removal", "occurence": 1},
        },
        "2": {
            "Sol Ring": {"oracle_id": "oracle-sol-ring", "quantity": 1, "edhrec_rank": 1, "defaultCategory": "Ramp", "occurence": 1},
            "Shock": {"oracle_id": "oracle-shock", "quantity": 1, "edhrec_rank": 3, "defaultCategory": "Removal", "occurence": 1},
        },
        "3": {
            "Cultivate": {"oracle_id": "oracle-cultivate", "quantity": 1, "edhrec_rank": 4, "defaultCategory": "Ramp", "occurence": 1},
        },
    }
    compared_cards = [
        make_compared_card("Sol Ring", colors="['C']", owned=1, role="Ramp"),
        make_compared_card("Counterspell", colors="['U']", owned=1, role="Removal"),
        make_compared_card("Shock", colors="['R']", owned=1, role="Removal"),
    ]
    collection_manager = CollectionManagerStub({"U"}, compared_cards)
    external_provider = ExternalProviderStub(decks_by_id, ["1", "2", "3"])
    progress_updates: list[int] = []
    service = DeckSearchService(collection_manager, external_provider, throttle_seconds=0)

    result = service.search_commander_candidates(
        commander_name="Talrand",
        order_by="Vues",
        deck_search_index=1,
        excluded_card_names={"counterspell"},
        progress_cb=progress_updates.append,
    )

    assert result.decks_found == 3
    assert result.decks_scanned == 2
    assert result.color_filtered_count == 2
    assert result.excluded_count == 1
    assert result.candidates == []
    assert progress_updates == [1, 2]
    assert collection_manager.compared_payloads[0]["Sol Ring"]["occurence"] == 2
    assert "Cultivate" not in collection_manager.compared_payloads[0]


def test_search_commander_candidates_can_reuse_prefetched_deck_ids():
    compared_cards = [make_compared_card("Arcane Signet", colors="[]", owned=3, role="Ramp")]
    collection_manager = CollectionManagerStub({"W", "U"}, compared_cards)
    external_provider = ExternalProviderStub(
        {
            "10": {
                "Arcane Signet": {"oracle_id": "oracle-arcane-signet", "quantity": 1, "edhrec_rank": 10, "defaultCategory": "Ramp", "occurence": 1}
            }
        },
        ["unused"],
    )
    service = DeckSearchService(collection_manager, external_provider, throttle_seconds=0)

    result = service.search_commander_candidates(
        commander_name="Shorikai",
        order_by="Updated",
        deck_search_index=2,
        deck_ids=["10"],
    )

    assert external_provider.requested_commanders == []
    assert result.decks_found == 1
    assert result.decks_scanned == 1
    assert result.to_dicts()[0]["name"] == "Arcane Signet"


def test_deck_candidate_roundtrip_preserves_fields():
    candidate = DeckCandidate.from_mapping(
        {
            "name": "Swords to Plowshares",
            "colors": "['W']",
            "types": "Instant",
            "scryfall_id": "abc",
            "image_url": "img",
            "edhrec_rank": "7",
            "occurence": "42",
            "defaultCategory": "Removal",
            "needed": "1",
            "owned": "2",
            "missing": "0",
            "set_code": "lea",
            "set_name": "Limited Edition Alpha",
            "collector_number": "40",
            "rarity": "uncommon",
        }
    )

    assert candidate.to_dict() == {
        "name": "Swords to Plowshares",
        "colors": "['W']",
        "types": "Instant",
        "scryfall_id": "abc",
        "image_url": "img",
        "edhrec_rank": 7,
        "occurence": 42,
        "defaultCategory": "Removal",
        "needed": 1,
        "owned": 2,
        "missing": 0,
        "set_code": "lea",
        "set_name": "Limited Edition Alpha",
        "collector_number": "40",
        "rarity": "uncommon",
    }
