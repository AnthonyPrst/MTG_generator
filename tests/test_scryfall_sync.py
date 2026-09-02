import gzip
import json

from mtg.scryfall_sync import ScryfallSyncManager


def _write_jsonl_gz(path, cards):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for card in cards:
            f.write(json.dumps(card) + "\n")


def test_sync_downloads_and_converts_jsonl_gz_bulk_data(tmp_path, monkeypatch):
    """Regression test: Scryfall now only exposes `jsonl_download_uri`
    (gzip-compressed JSONL) for bulk data, no more `download_uri`.
    """
    manager = ScryfallSyncManager(data_dir=tmp_path)

    bulk_info = {
        "data": [
            {
                "type": "oracle_cards",
                "updated_at": "2026-09-01T09:01:52.679+00:00",
                "jsonl_download_uri": "https://data.scryfall.io/oracle-cards/oracle-cards.jsonl.gz",
            },
            {
                "type": "default_cards",
                "jsonl_download_uri": "https://data.scryfall.io/default-cards/default-cards.jsonl.gz",
            },
        ]
    }

    cards = [
        {"id": "abc-1", "name": "Sol Ring", "type_line": "Artifact"},
        {"id": "abc-2", "name": "Arcane Signet", "type_line": "Artifact"},
    ]

    monkeypatch.setattr(manager, "_get_bulk_data_info", lambda: bulk_info)

    def fake_download(url, destination, progress_callback=None):
        assert url == "https://data.scryfall.io/oracle-cards/oracle-cards.jsonl.gz"
        _write_jsonl_gz(destination, cards)
        return True

    monkeypatch.setattr(manager, "_download_file", fake_download)

    result = manager.sync(force=True)

    assert result is True
    assert manager.oracle_cards_file.exists()

    loaded = manager.load_oracle_cards()
    assert "sol ring" in loaded
    assert "arcane signet" in loaded
    assert manager.is_bulk_available() is True


def test_sync_fails_gracefully_when_no_url_available(tmp_path, monkeypatch):
    manager = ScryfallSyncManager(data_dir=tmp_path)
    monkeypatch.setattr(manager, "_get_bulk_data_info", lambda: {"data": [{"type": "default_cards"}]})

    result = manager.sync(force=True)

    assert result is False
    assert not manager.oracle_cards_file.exists()
