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
    
        # # Construction du deck
        # builder = DeckBuilder(self.collection_manager)
        # deck = builder.build_deck(commander_name)
        
        # # Validation
        # validator = DeckValidator()
        # is_valid, errors = validator.validate_deck(deck)
        
        # if not is_valid:
        #     print("Le deck généré n'est pas valide :")
        #     for error in errors:
        #         print(f"- {error}")
        #     return

        # # Export
        # exporter = DeckExporter()
        # exporter.export_to_txt(deck, f"{args.output}.txt")
        # exporter.export_to_csv(deck, f"{args.output}.csv")
        

    def import_collection(self):
        """Importe une collection depuis un fichier CSV."""
        file_path, import_type = self.window.get_csv_path_for_import_in_db()
        if file_path:
            self.collection_manager.load_from_csv(file_path, import_type)
            self.update_collection_list()

    def update_collection_list(self):
        """Mise à jour de la liste des cartes dans la fenêtre."""
        self.window.collection_list.clear()
        cards = self.collection_manager.get_all_cards()
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
        self.window.deck_found_list.clear()
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
        for deck_id in decks_id[:len_decks]:
            time.sleep(0.1)
            deck = self.external_provider.load_archidekt_deck(deck_id)

            for name, info in deck.items():
                if name in cards:
                    # on cumule les occurences (nb de decks où la carte apparaît)
                    cards[name]["occurence"] += info.get("occurence", 1)
                else:
                    # première fois qu'on voit cette carte
                    cards[name] = info

        owned = self.collection_manager.compare_deck_to_collection(cards)
        self.eventual_owned = sorted(owned, key=lambda d: d['types'])
        cts.EVENTUAL_SCRYFALL_ID_LIST = []
        for card in self.eventual_owned:
            cts.EVENTUAL_SCRYFALL_ID_LIST.append(card["scryfall_id"])
            list_items = [
                card["name"], 
                card["colors"],
                card["types"],
                str(card["edhrec_rank"]),
                str(card["occurence"]),
                card["defaultCategory"]
            ]
            str_items = ' / '.join(list_items)
            self.window.deck_found_list.addItem(str_items)
        self.window.set_length_of_eventual_list(len(owned), len_decks, numbers_decks)

    def build_deck(self):
        """Construit un deck Commander valide à partir d'une liste scorée."""
        commander_name = self.window.commander_input.currentText()
        deck_builder = DeckBuilder(self, commander_name, self.eventual_owned)
        deck = deck_builder.build_deck()
        self.window.deck_list.clear()
        cards = sorted(deck.cards, key=lambda d: d['types'])
        commander_first = [c for c in cards if c["name"] == commander_name]
        non_commander = [c for c in cards if c["name"] != commander_name]
        cards = commander_first + non_commander
        sum_score = 0
        for card in cards:
            list_items = [
                card["name"], 
                card["types"],
                card["role"],
                str(card["score"])
            ]
            str_items = ' / '.join(list_items)
            self.window.deck_list.addItem(str_items)
            sum_score += card["score"]
        mean_score = sum_score / len(deck.cards)
        self.window.set_length_and_score_of_deck_list(len(deck.cards), mean_score)

        # Afficher les images du deck (3 par ligne)
        self.window.show_deck_images(cards, self.external_provider)

if __name__ == "__main__":
    app = Launcher()
