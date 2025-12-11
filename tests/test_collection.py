"""Tests pour le module collection."""

import sqlite3
from pathlib import Path

import pytest

from mtg import constants as cts
from mtg.collection import CollectionManager


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
