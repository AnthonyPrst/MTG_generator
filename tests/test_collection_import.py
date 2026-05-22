from mtg.collection_import import CollectionImportService


class CollectionManagerStub:
    def __init__(self, should_succeed=True, raise_error: Exception | None = None):
        self.should_succeed = should_succeed
        self.raise_error = raise_error
        self.calls = []

    def load_from_csv(self, csv_path, import_type=None, progress_cb=None, label_cb=None, bulk_provider=None):
        self.calls.append(
            {
                "csv_path": csv_path,
                "import_type": import_type,
                "progress_cb": progress_cb,
                "label_cb": label_cb,
                "bulk_provider": bulk_provider,
            }
        )
        if self.raise_error is not None:
            raise self.raise_error
        return self.should_succeed


class ScryfallSyncStub:
    def __init__(self, bulk_available=True):
        self.bulk_available = bulk_available
        self.loaded = False

    def is_bulk_available(self):
        return self.bulk_available

    def load_oracle_cards(self):
        self.loaded = True
        return {"cards": 1}


def test_import_collection_uses_bulk_when_available():
    manager = CollectionManagerStub(should_succeed=True)
    sync = ScryfallSyncStub(bulk_available=True)
    labels = []
    service = CollectionImportService(manager)

    result = service.import_collection(
        csv_path="collection.csv",
        import_type="ManaBox - Collection",
        label_cb=labels.append,
        scryfall_sync=sync,
    )

    assert result.success is True
    assert result.used_bulk_data is True
    assert sync.loaded is True
    assert labels == ["Chargement du bulk Scryfall..."]
    assert manager.calls[0]["bulk_provider"] is sync


def test_import_collection_without_bulk_stays_successful():
    manager = CollectionManagerStub(should_succeed=True)
    sync = ScryfallSyncStub(bulk_available=False)
    service = CollectionImportService(manager)

    result = service.import_collection(
        csv_path="collection.csv",
        import_type=None,
        scryfall_sync=sync,
    )

    assert result.success is True
    assert result.used_bulk_data is False
    assert sync.loaded is False
    assert manager.calls[0]["bulk_provider"] is None


def test_import_collection_returns_default_error_message_on_failed_load():
    manager = CollectionManagerStub(should_succeed=False)
    service = CollectionImportService(manager)

    result = service.import_collection(csv_path="collection.csv")

    assert result.success is False
    assert "Détection automatique" in result.error_message


def test_import_collection_captures_unexpected_exception():
    manager = CollectionManagerStub(raise_error=RuntimeError("boom"))
    service = CollectionImportService(manager)

    result = service.import_collection(csv_path="collection.csv")

    assert result.success is False
    assert result.error_message == "boom"
