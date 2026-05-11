"""Tests pour le module collection."""

import sqlite3
from pathlib import Path

import pytest

from mtg import constants as cts
from mtg.collection import CollectionManager
from mtg.import_formats import CardNexusFormat


@pytest.fixture
def collection_manager(tmp_path):
    """Crée une base temporaire isolée pour chaque test."""
    cts.DB_PATH = tmp_path / "test_collection.db"
    cts.CSV_PATH = None
    manager = CollectionManager()
    yield manager
    if manager.conn:
        manager.conn.close()


def test_init_creates_empty_db(collection_manager, tmp_path):
    db_path = Path(cts.DB_PATH)
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM cards")
        assert cursor.fetchone()[0] == 0


def test_insert_and_find_cards(collection_manager):
    with collection_manager._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cards (name, quantity, scryfall_id, oracle_id, colors, types)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Sol Ring", 2, "scry-123", "oracle-123", "['C']", "Artifact"),
        )

    card_by_name = collection_manager.find_card_by_name("Sol Ring")
    assert card_by_name["quantity"] == 2

    card_by_scryfall = collection_manager.find_card_by_scryfallID("scry-123")
    assert card_by_scryfall["name"] == "Sol Ring"

    card_by_oracle = collection_manager.find_card_by_oracleID("oracle-123")
    assert card_by_oracle["name"] == "Sol Ring"


def test_search_and_quantity_helpers(collection_manager):
    with collection_manager._get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO cards (name, quantity, colors, types)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("Arcane Signet", 3, "['C']", "Artifact"),
                ("Arcanist's Owl", 1, "['W', 'U']", "Creature"),
            ],
        )

    matches = collection_manager.search_cards("Arcan")
    names = sorted(card["name"] for card in matches)
    assert names == ["Arcane Signet", "Arcanist's Owl"]

    assert collection_manager.get_card_quantity("Arcane Signet") == 3
    assert collection_manager.has_card("Arcanist's Owl") is True
    assert collection_manager.has_card("Nonexistent Card") is False


def test_multiple_printings_are_aggregated(collection_manager):
    with collection_manager._get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO cards (name, quantity, scryfall_id, oracle_id, set_code, colors, types)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Sol Ring", 1, "scry-cmd", "oracle-solring", "CMD", "['C']", "Artifact"),
                ("Sol Ring", 2, "scry-c15", "oracle-solring", "C15", "['C']", "Artifact"),
            ],
        )

    card_by_name = collection_manager.find_card_by_name("Sol Ring")
    assert card_by_name["quantity"] == 3

    card_by_oracle = collection_manager.find_card_by_oracleID("oracle-solring")
    assert card_by_oracle["quantity"] == 3

    all_printings = collection_manager.find_cards_by_name("Sol Ring")
    assert len(all_printings) == 2
    assert sorted(card["set_code"] for card in all_printings) == ["C15", "CMD"]


def test_colorless_sentinel_is_treated_as_empty_color_identity(collection_manager):
    with collection_manager._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cards (name, quantity, colors, types)
            VALUES (?, ?, ?, ?)
            """,
            ("Arcane Signet", 1, "['colorless']", "Artifact"),
        )

    assert collection_manager.get_card_colors("Arcane Signet") == set()


def test_cardnexus_printings_get_distinct_fallback_ids():
    import_format = CardNexusFormat()
    row_one = {
        "totalQtyOwned": "1",
        "name": "Arcane Signet",
        "expansion": "Outlaws of Thunder Junction Commander",
        "printNumber": "252",
        "language": "fr",
        "condition": "Near Mint",
        "finish": "Standard",
        "rarity": "common",
    }
    row_two = {
        "totalQtyOwned": "2",
        "name": "Arcane Signet",
        "expansion": "Wilds of Eldraine Commander",
        "printNumber": "145",
        "language": "fr",
        "condition": "Near Mint",
        "finish": "Standard",
        "rarity": "common",
    }

    bulk_result = {
        "oracle_id": "oracle-arcane-signet",
        "id": "real-scryfall-id",
        "type_line": "Artifact",
        "color_identity": [],
        "set": "soc",
        "collector_number": "127",
    }

    class BulkStub:
        def get_card_for_import(self, scryfall_id: str = '', card_name: str = ''):
            return bulk_result

    card_one = import_format.process_row(row_one, external_provider=None, bulk_provider=BulkStub())
    card_two = import_format.process_row(row_two, external_provider=None, bulk_provider=BulkStub())

    assert card_one["scryfall_id"] != card_two["scryfall_id"]
    assert card_one["collector_number"] == "252"
    assert card_two["collector_number"] == "145"
