import logging
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CollectionImportResult:
    success: bool
    csv_path: str
    import_type: Optional[str]
    used_bulk_data: bool = False
    error_message: str = ""
    skipped_count: int = 0


class CollectionImportService:
    def __init__(self, collection_manager):
        self.collection_manager = collection_manager

    def import_collection(
        self,
        csv_path: str,
        import_type: Optional[str] = None,
        progress_cb=None,
        label_cb=None,
        scryfall_sync=None,
    ) -> CollectionImportResult:
        bulk_provider = None
        used_bulk_data = False

        try:
            if scryfall_sync and scryfall_sync.is_bulk_available():
                bulk_provider = scryfall_sync
                used_bulk_data = True
                if label_cb:
                    label_cb("Chargement du bulk Scryfall...")
                scryfall_sync.load_oracle_cards()

            success = self.collection_manager.load_from_csv(
                csv_path,
                import_type,
                progress_cb=progress_cb,
                label_cb=label_cb,
                bulk_provider=bulk_provider,
            )
            if success:
                return CollectionImportResult(
                    success=True,
                    csv_path=csv_path,
                    import_type=import_type,
                    used_bulk_data=used_bulk_data,
                )

            return CollectionImportResult(
                success=False,
                csv_path=csv_path,
                import_type=import_type,
                used_bulk_data=used_bulk_data,
                error_message="L'import de collection a échoué. Vérifie le format sélectionné, ou utilise 'Détection automatique'.",
            )
        except Exception as exc:
            logger.exception("Erreur pendant l'import de collection depuis '%s'", csv_path)
            return CollectionImportResult(
                success=False,
                csv_path=csv_path,
                import_type=import_type,
                used_bulk_data=used_bulk_data,
                error_message=str(exc) or "Erreur inattendue lors de l'import de collection.",
            )
