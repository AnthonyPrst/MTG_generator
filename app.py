"""Point d'entrée principal de l'application."""

import sys
import argparse
import ast
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QInputDialog
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from mtg.collection import CollectionManager
from mtg.deck_analysis import DeckAnalysisService
from mtg.collection_import import CollectionImportService
from mtg.deck_search import DeckSearchService
from mtg.external_data import ExternalDataProvider
from mtg.deckbuilder import DeckBuilder
from mtg.validators import DeckValidator
from mtg.exporter import DeckExporter
from mtg.utils import setup_logging
from mtg import constants as cts
from gui.main_window import MainWindow


logger = logging.getLogger(__name__)

 
class Launcher(object):
    def __init__(self) -> None:
        setup_logging("INFO")
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        self.setup()
        self.window = MainWindow(self)
        self.update_collection_list()
        self.window.show()

        sys.exit(app.exec())

    def setup(self):
        """Fonction principale."""
        # Initialisation des composants
        self.collection_manager = CollectionManager(collection_type='physical')
        self.external_provider = ExternalDataProvider()
        self.collection_import_service = CollectionImportService(self.collection_manager)
        self.deck_search_service = DeckSearchService(
            collection_manager=self.collection_manager,
            external_provider=self.external_provider,
        )
        self.excluded_card_names: set[str] = set()
        self.eventual_owned: list[dict] = []
        self.current_language = "fr"

    @staticmethod
    def _normalize_color_tokens(raw_colors) -> set[str]:
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

    def import_collection(self):
        """Importe une collection depuis un fichier CSV."""
        file_path, import_type = self.window.get_csv_path_for_import_in_db()
        if file_path:
            self.window.show_progress("Import de collection", "Lecture du fichier...")
            try:
                result = self.collection_import_service.import_collection(
                    csv_path=file_path,
                    import_type=import_type,
                    progress_cb=self.window.update_progress,
                    label_cb=self.window.set_progress_label,
                    scryfall_sync=getattr(self.window, 'scryfall_sync', None),
                )
                if not result.success:
                    self.window.show_error(result.error_message)
                    return
                self.window.set_progress_label("Rafraîchissement de l'interface...")
                self.update_collection_list()
                self.window.refresh_commander_candidates()

                # Afficher le nombre de cartes ignorées
                skipped = getattr(self.collection_manager, '_last_skipped_count', 0)
                if skipped > 0:
                    self.window.statusBar().showMessage(f"Import terminé : {skipped} cartes ignorées (noms invalides)", 5000)
            finally:
                self.window.close_progress()

    def update_collection_list(self):
        """Mise à jour de la liste des cartes dans la fenêtre."""
        cards = self.collection_manager.get_all_cards()
        # Alimente l'onglet avec données + filtres
        if hasattr(self.window, "set_collection_cards"):
            self.window.set_collection_cards(cards)
            # Rafraîchir la langue pour recharger les libellés des filtres avec les nouvelles valeurs
            if hasattr(self.window, "apply_language"):
                self.window.apply_language(getattr(self.window, "language", "fr"))
        else:
            self.window.collection_list.clear()
            for card in cards:
                self.window.collection_list.addItem(' / '.join([card["name"], card["colors"], card["types"], str(card["quantity"]), card["set_name"], str(card["collector_number"])]))

    def set_language(self, lang: str):
        """Change la langue de l'interface et rafraîchit les textes."""
        self.current_language = lang or "fr"
        if hasattr(self.window, "apply_language"):
            self.window.apply_language(self.current_language)

    def export_collection(self):
        """Exporte la collection vers un fichier CSV."""
        file_path = self.window.get_save_file_name(
            "Exporter la collection", "collection.csv", "CSV files (*.csv)"
        )
        if file_path:
            self.collection_manager.export_db_to_csv(file_path)

    def delete_collection(self):
        """Supprime toute la collection après confirmation."""
        reply = self.window.confirm_delete_collection()
        if reply:
            self.collection_manager.clear_all_cards()
            self.update_collection_list()
            self.window.refresh_commander_candidates()
            self.window.statusBar().showMessage("Collection supprimée", 4000)

    def export_eventual_cards_list(self):
        """Exporte la liste des cartes eventuelles dans un fichier txt"""
        file_path = self.window.get_save_file_name(
            "Exporter la liste de carte eventuelles", "eventual_cards_list.txt", "TXT files (*.txt)"
        )
        if file_path:
            self.collection_manager.export_db_list_cards_to_txt(cts.EVENTUAL_SCRYFALL_ID_LIST, file_path)
    
    def export_deck_list(self):
        """Exporte la liste des cartes du deck dans un fichier txt"""
        if not cts.DECK_BUILD_SCRYFALL_ID_LIST:
            self.window.show_error("Aucune carte à exporter. Construisez d'abord un deck.")
            return

        commander_name = self.window.commander_input.currentText()
        if not commander_name:
            self.window.show_error("Aucun commandant sélectionné.")
            return

        # Choix du format d'export
        format_options = ["Standard", "MTG Arena"]
        export_format, accepted = QInputDialog.getItem(
            self.window,
            "Format d'export",
            "Choisir le format d'export:",
            format_options,
            0,
            False
        )
        if not accepted:
            return

        format_key = "mtga_arena" if export_format == "MTG Arena" else "standard"
        file_path = self.window.get_save_file_name(
            f"Exporter le deck {export_format}",
            f"deck_{export_format.lower().replace(' ', '_')}.txt",
            "TXT files (*.txt)"
        )
        if file_path:
            try:
                with self.collection_manager._get_connection() as conn:
                    exporter = DeckExporter()
                    exporter.export_deck_to_txt(cts.DECK_BUILD_SCRYFALL_ID_LIST, commander_name, conn, format_key, file_path)
                self.window.statusBar().showMessage(f"Deck exporté au format {export_format} : {file_path}", 5000)
            except Exception as e:
                logger.error(f"Erreur lors de l'export : {str(e)}")
                self.window.show_error(f"Erreur lors de l'export : {str(e)}")

    def get_decks_archidekt_from_commander(self):
        """Importe une collection depuis un fichier CSV."""
        commander_name = self.window.commander_input.currentText()
        order_by = self.window.order_by.currentText() 
        # Nettoyer le tableau des cartes éventuelles
        if hasattr(self.window, "deck_found_table"):
            self.window.deck_found_table.setRowCount(0)
        deck_search_params = self.window.numb_deck_search.currentIndex()

        decks_id = self.external_provider.get_archidekt_decks_id_for_commander(commander_name, order_by)
        numbers_decks = len(decks_id)
        len_decks = self.deck_search_service._resolve_deck_count(numbers_decks, deck_search_params)
        self.window.show_progress("Recherche de decks", "Chargement des decks Archidekt...", maximum=len_decks or 0)
        try:
            search_result = self.deck_search_service.search_commander_candidates(
                commander_name=commander_name,
                order_by=order_by,
                deck_search_index=deck_search_params,
                deck_ids=decks_id,
                excluded_card_names=self.excluded_card_names,
                progress_cb=self.window.update_progress,
            )
        finally:
            self.window.close_progress()

        self.eventual_owned = search_result.to_dicts()
        if search_result.excluded_count:
            self.window.statusBar().showMessage(f"{search_result.excluded_count} cartes exclues (pas de doublon)", 5000)
        cts.EVENTUAL_SCRYFALL_ID_LIST = []
        for card in self.eventual_owned:
            cts.EVENTUAL_SCRYFALL_ID_LIST.append(card["scryfall_id"])
        # Alimenter le tableau avec la nouvelle API
        if hasattr(self.window, "set_eventual_cards"):
            self.window.set_eventual_cards(self.eventual_owned)
        self.window.set_length_of_eventual_list(len(self.eventual_owned), search_result.decks_scanned, search_result.decks_found)

    def build_deck(self):
        """Construit un deck Commander valide à partir d'une liste scorée."""
        commander_name = self.window.commander_input.currentText()
        if not self.eventual_owned:
            self.window.show_error("Charge d'abord des cartes éventuelles pour ce commandant.")
            return
        strategy_manager = self.window.get_strategy_manager()
        deck_builder = DeckBuilder(self, commander_name, self._apply_exclusions(self.eventual_owned), strategy_manager)
        self.window.show_progress("Construction du deck", "Génération en cours...", maximum=100)
        try:
            deck = deck_builder.build_deck()
        except Exception:
            logger.exception("Échec de construction du deck pour le commandant '%s'", commander_name)
            self.window.show_error("La construction du deck a échoué. Consulte les logs pour plus de détails.")
            self.window.close_progress()
            return
        self.window.update_progress(25)
        cards = sorted((card.to_dict() for card in deck.cards), key=lambda d: d['types'])
        commander_first = [c for c in cards if c["name"] == commander_name]
        non_commander = [c for c in cards if c["name"] != commander_name]
        cards = commander_first + non_commander
        summary = self._summarize_deck(cards)
        sum_score = 0
        for card in cards:
            sum_score += card["score"]
        mean_score = sum_score / len(deck.cards)
        self.window.set_length_and_score_of_deck_list(len(deck.cards), mean_score)
        
        # Calculer le power level
        from mtg.edhrec_analytics import EDHRecAnalytics
        analytics = EDHRecAnalytics()
        power_data = analytics.calculate_deck_power_level(cards, commander_name)
        self.window.set_deck_power_level(power_data)
        if hasattr(self.window, "set_deck_cards"):
            self.window.set_deck_cards(cards)
        
        self.window.update_progress(50)
        mana_curve_text, stats_text = self._compute_deck_stats(summary)
        self.window.set_deck_stats(mana_curve_text, stats_text)
        self.window.update_progress(75)

        # Mettre à jour les scores dans les cartes éventuelles après la création du deck
        scored_cards = deck_builder.scored_cards
        score_by_name = {card["name"]: card["score"] for card in scored_cards}
        for card in self.eventual_owned:
            card_name = card.get("name")
            if card_name in score_by_name:
                card["score"] = score_by_name[card_name]
        if hasattr(self.window, "set_eventual_cards"):
            self.window.set_eventual_cards(self.eventual_owned)
        self.window.set_deck_graphs(summary)
        self.window.update_progress(100)
        self.window.close_progress()

        # Afficher les images du deck (3 par ligne)
        self.window.show_deck_images(cards, self.external_provider)

    def load_exclusion_list(self):
        """Charge un fichier texte listant les cartes à exclure si non possédées en double."""
        file_path = self.window.get_open_file_name("Sélectionner un fichier texte d'exclusion", "TXT files (*.txt)")
        if not file_path:
            return
        names = set()
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    lower = line.lower()
                    if lower.startswith("commander") or lower.startswith("deck"):
                        continue
                    # Supprime un éventuel préfixe de quantité ("1x", "2 x", etc.)
                    if "x" in line[:4]:
                        parts = line.split("x", 1)
                        candidate = parts[1] if len(parts) > 1 else line
                    else:
                        candidate = line
                    # Retire les informations de set entre parenthèses
                    candidate = candidate.split("(")[0].strip()
                    if candidate:
                        # On ignore les terrains de base (Basic Lands)
                        basic_lands = {
                            "forest", "plaine", "island", "swamp", "mountain", "plains", "forêt", "île", "marais", "montagne"
                        }
                        if candidate.lower() in basic_lands:
                            continue
                        names.add(candidate.lower())
            self.excluded_card_names = names
            self.window.statusBar().showMessage(f"{len(names)} cartes d'exclusion chargées", 5000)
        except Exception as exc:
            self.window.statusBar().showMessage("Erreur lors du chargement du fichier d'exclusion", 5000)
            raise exc

    def _apply_exclusions(self, cards: list[dict]) -> list[dict]:
        """Filtre les cartes à exclure si non possédées en double."""
        if not getattr(self, "excluded_card_names", None):
            return cards
        excluded = self.excluded_card_names
        filtered: list[dict] = []
        skipped = 0
        for card in cards:
            name_lower = card.get("name", "").lower()
            owned_qty = card.get("owned", 0)
            if name_lower in excluded and owned_qty < 2:
                skipped += 1
                continue
            filtered.append(card)
        if skipped:
            self.window.statusBar().showMessage(f"{skipped} cartes exclues (pas de doublon)", 5000)
        return filtered

    def _summarize_deck(self, cards: list[dict]) -> dict:
        """Retourne un résumé commun pour courbe de mana et stats rôles."""
        summary = self._get_deck_analysis_service().summarize_deck(cards)
        summary["targets"] = {
            "lands_min": self.window.numb_min_land.value(),
            "lands_max": self.window.numb_max_land.value(),
            "roles": {
                "Ramp": self.window.numb_ramp.value(),
                "Draw": self.window.numb_draw.value(),
                "Removal": self.window.numb_removal.value(),
                "Finisher": self.window.numb_wincondition.value(),
            },
        }
        return summary

    def _compute_deck_stats(self, summary: dict) -> tuple[str, str]:
        """Calcule la courbe de mana et quelques statistiques synthétiques."""
        return self._get_deck_analysis_service().compute_deck_stats(summary)

    def _get_deck_analysis_service(self) -> DeckAnalysisService:
        return DeckAnalysisService(
            collection_manager=self.collection_manager,
            external_provider=self.external_provider,
            bulk_provider=getattr(self.window, "scryfall_sync", None),
        )

    def switch_collection(self, collection_type: str):
        """Change la collection active (physical ou mtg_arena).

        Args:
            collection_type: Type de collection ('physical' ou 'mtg_arena')
        """
        try:
            # Fermer l'ancienne connexion si elle existe
            if hasattr(self.collection_manager, 'conn') and self.collection_manager.conn:
                self.collection_manager.conn.close()

            # Créer un nouveau gestionnaire de collection avec le bon type
            self.collection_manager = CollectionManager(collection_type=collection_type)
            self.collection_import_service = CollectionImportService(self.collection_manager)
            self.deck_search_service = DeckSearchService(
                collection_manager=self.collection_manager,
                external_provider=self.external_provider,
            )

            # Rafraîchir l'interface
            self.update_collection_list()
            self.window.refresh_commander_candidates()

            # Message de confirmation
            collection_name = "Collection physique" if collection_type == 'physical' else "MTG Arena"
            self.window.statusBar().showMessage(f"Collection changée : {collection_name}", 4000)

        except Exception as e:
            logger.exception("Erreur lors du changement de collection")
            self.window.show_error(f"Erreur lors du changement de collection : {str(e)}")


if __name__ == "__main__":
    app = Launcher()
