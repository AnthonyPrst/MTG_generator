"""Point d'entrée principal de l'application."""

import sys
import argparse
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication

from mtg.collection import CollectionManager
from mtg.external_data import ExternalDataProvider
from mtg.deckbuilder import DeckBuilder
from mtg.validators import DeckValidator
from mtg.exporter import DeckExporter
from mtg.utils import setup_logging
from mtg import constants as cts
from gui.main_window import MainWindow



class Launcher(object):
    def __init__(self) -> None:
        setup_logging("INFO")
        app = QApplication(sys.argv)
        # Style moderne
        app.setStyle('Fusion')
        # Création et affichage de la fenêtre principale
        self.setup()
        self.window = MainWindow(self)
        self.update_collection_list()
        self.window.show()


        # Exécution de l'application
        sys.exit(app.exec())

    def setup(self):
        """Fonction principale."""
        # Initialisation des composants
        self.collection_manager = CollectionManager()
        self.external_provider = ExternalDataProvider()
        self.excluded_card_names: set[str] = set()

    def import_collection(self):
        """Importe une collection depuis un fichier CSV."""
        file_path, import_type = self.window.get_csv_path_for_import_in_db()
        if file_path:
            self.collection_manager.load_from_csv(file_path, import_type)
            self.update_collection_list()
            self.window.refresh_commander_candidates()

    def update_collection_list(self):
        """Mise à jour de la liste des cartes dans la fenêtre."""
        cards = self.collection_manager.get_all_cards()
        # Alimente l'onglet avec données + filtres
        if hasattr(self.window, "set_collection_cards"):
            self.window.set_collection_cards(cards)
        else:
            self.window.collection_list.clear()
            for card in cards:
                self.window.collection_list.addItem(' / '.join([card["name"], card["colors"], card["types"], str(card["quantity"]), card["set_name"], str(card["collector_number"])]))

    def export_collection(self):
        """Exporte la collection vers un fichier CSV."""
        file_path = self.window.get_save_file_name(
            "Exporter la collection", "collection.csv", "CSV files (*.csv)"
        )
        if file_path:
            self.collection_manager.export_db_to_csv(file_path)

    def export_eventual_cards_list(self):
        """Exporte la liste des cartes eventuelles dans un fichier txt"""
        file_path = self.window.get_save_file_name(
            "Exporter la liste de carte eventuelles", "eventual_cards_list.txt", "TXT files (*.txt)"
        )
        if file_path:
            self.collection_manager.export_db_list_cards_to_txt(cts.EVENTUAL_SCRYFALL_ID_LIST, file_path)
    
    def export_deck_list(self):
        """Exporte la liste des cartes du deck dans un fichier txt"""
        file_path = self.window.get_save_file_name(
            "Exporter la liste de carte du deck", "deck_list.txt", "TXT files (*.txt)"
        )
        if file_path:
            self.collection_manager.export_db_list_cards_to_txt(cts.DECK_BUILD_SCRYFALL_ID_LIST, file_path)

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
        match deck_search_params:
            case 0:
                len_decks = round(numbers_decks/3)
            case 1:
                len_decks = round(numbers_decks*2/3)
            case 2:
                len_decks = numbers_decks
        cards = {}
        self.window.show_progress("Recherche de decks", "Chargement des decks Archidekt...", maximum=len_decks or 0)
        try:
            for idx, deck_id in enumerate(decks_id[:len_decks], start=1):
                time.sleep(0.1)
                deck = self.external_provider.load_archidekt_deck(deck_id)

                for name, info in deck.items():
                    if name in cards:
                        # on cumule les occurences (nb de decks où la carte apparaît)
                        cards[name]["occurence"] += info.get("occurence", 1)
                    else:
                        # première fois qu'on voit cette carte
                        cards[name] = info
                self.window.update_progress(idx)
        finally:
            self.window.close_progress()

        owned = self.collection_manager.compare_deck_to_collection(cards)
        owned = self._apply_exclusions(owned)
        self.eventual_owned = sorted(owned, key=lambda d: d['types'])
        cts.EVENTUAL_SCRYFALL_ID_LIST = []
        for card in self.eventual_owned:
            cts.EVENTUAL_SCRYFALL_ID_LIST.append(card["scryfall_id"])
        # Alimenter le tableau avec la nouvelle API
        if hasattr(self.window, "set_eventual_cards"):
            self.window.set_eventual_cards(self.eventual_owned)
        self.window.set_length_of_eventual_list(len(owned), len_decks, numbers_decks)

    def build_deck(self):
        """Construit un deck Commander valide à partir d'une liste scorée."""
        commander_name = self.window.commander_input.currentText()
        deck_builder = DeckBuilder(self, commander_name, self._apply_exclusions(self.eventual_owned))
        self.window.show_progress("Construction du deck", "Génération en cours...", maximum=0)
        try:
            deck = deck_builder.build_deck()
        finally:
            self.window.close_progress()
        cards = sorted(deck.cards, key=lambda d: d['types'])
        commander_first = [c for c in cards if c["name"] == commander_name]
        non_commander = [c for c in cards if c["name"] != commander_name]
        cards = commander_first + non_commander
        summary = self._summarize_deck(cards)
        sum_score = 0
        for card in cards:
            sum_score += card["score"]
        mean_score = sum_score / len(deck.cards)
        self.window.set_length_and_score_of_deck_list(len(deck.cards), mean_score)
        if hasattr(self.window, "set_deck_cards"):
            self.window.set_deck_cards(cards)
        mana_curve_text, stats_text = self._compute_deck_stats(summary)
        self.window.set_deck_stats(mana_curve_text, stats_text)
        mana_curve_pixmap, roles_pixmap = self._compute_deck_graphs(summary)
        self.window.set_deck_graphs(mana_curve_pixmap, roles_pixmap)

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
        buckets = {k: 0 for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]}
        total_cmc = 0.0
        cmc_count = 0
        lands = 0
        roles: dict[str, int] = {}

        for card in cards:
            types = card.get("types", "")
            role = card.get("role") or "Other"
            roles[role] = roles.get(role, 0) + 1

            if "Land" in types:
                lands += 1
                continue

            scryfall_id = card.get("scryfall_id")
            cmc = self.external_provider.get_card_cmc(scryfall_id) if scryfall_id else None
            if cmc is None:
                continue
            cmc_count += 1
            total_cmc += cmc
            if cmc >= 7:
                buckets["7+"] += 1
            else:
                bucket_key = str(int(cmc)) if cmc >= 0 else "0"
                if bucket_key not in buckets:
                    bucket_key = "7+"
                buckets[bucket_key] += 1

        return {
            "buckets": buckets,
            "total_cmc": total_cmc,
            "cmc_count": cmc_count,
            "lands": lands,
            "roles": roles,
            "total_cards": len(cards),
        }

    def _compute_deck_stats(self, summary: dict) -> tuple[str, str]:
        """Calcule la courbe de mana et quelques statistiques synthétiques."""
        buckets = summary["buckets"]
        total_cmc = summary["total_cmc"]
        cmc_count = summary["cmc_count"]
        lands = summary["lands"]
        roles = summary["roles"]
        total_cards = summary.get("total_cards", 0)

        # Texte courbe de mana
        curve_parts = [f"{k}: {v}" for k, v in buckets.items()]
        mana_curve_text = "Courbe de mana : " + " | ".join(curve_parts)

        avg_cmc = (total_cmc / cmc_count) if cmc_count else 0.0
        stats_lines = [
            f"Cartes totales : {total_cards}",
            f"Lands : {lands}",
            f"CMJ moyenne : {avg_cmc:.2f}" if cmc_count else "CMJ moyenne : n/a",
            "Répartition par rôle : " + ", ".join(f"{r}: {n}" for r, n in sorted(roles.items())),
        ]
        stats_text = "\n".join(stats_lines)
        return mana_curve_text, stats_text

    def _compute_deck_graphs(self, summary: dict):
        """Retourne deux QPixmap: histogramme courbe de mana et camembert rôles."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
        except Exception:
            return None, None

        buckets = summary["buckets"]
        roles = summary["roles"]

        # Figure histogramme
        fig1, ax1 = plt.subplots(figsize=(4, 3), dpi=120)
        x_labels = list(buckets.keys())
        vals = [buckets[k] for k in x_labels]
        ax1.bar(x_labels, vals, color="#3b82f6")
        ax1.set_title("Courbe de mana")
        ax1.set_ylabel("Nombre de cartes")
        ax1.set_xlabel("Coût")
        ax1.grid(axis="y", linestyle="--", alpha=0.4)
        fig1.tight_layout()

        # Figure camembert rôles
        fig2, ax2 = plt.subplots(figsize=(4, 3), dpi=120)
        labels = []
        sizes = []
        for r, n in sorted(roles.items()):
            if n > 0:
                labels.append(r)
                sizes.append(n)
        if sizes:
            ax2.pie(sizes, labels=labels, autopct="%1.0f%%", startangle=140)
            ax2.set_title("Répartition des rôles")
        fig2.tight_layout()

        # Convert figures to QPixmap
        def fig_to_qpixmap(fig):
            from io import BytesIO
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            from PySide6.QtGui import QPixmap
            pix = QPixmap()
            pix.loadFromData(buf.getvalue())
            buf.close()
            return pix

        mana_pix = fig_to_qpixmap(fig1)
        roles_pix = fig_to_qpixmap(fig2)
        plt.close(fig1)
        plt.close(fig2)
        return mana_pix, roles_pix

if __name__ == "__main__":
    app = Launcher()
