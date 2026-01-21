from functools import partial
from pathlib import Path
import time
import requests
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QListWidget,
    QFileDialog,
    QSpinBox,
    QMessageBox,
    QComboBox,
    QTabWidget,
    QFormLayout,
    QCompleter,
    QScrollArea,
    QGridLayout,
    QProgressDialog,
    QSizePolicy,
    QMenu,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter

class MainWindow(QMainWindow):
    """Fenêtre principale de l'application."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("MTG Commander Deck Builder")
        self.setMinimumSize(1980, 1200)
        self.card_index_to_widget = {}
        self.card_index_to_pixmap = {}
        self.cards_data = []
        self.missing_image_indices = []
        self.preview_label = None
        self.roles_available = set()
        self.collection_cards = []
        self.filtered_collection_cards: List[Dict] = []
        self.eventual_cards_data: List[Dict] = []
        self.filtered_eventual_cards: List[Dict] = []
        self.deck_cards_data: List[Dict] = []
        self.filtered_deck_cards: List[Dict] = []
        
        # Widget central
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Layout principal
        self.layout = QVBoxLayout(self.central_widget)
        
        # Onglets
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        self._apply_modern_styles()
        
        # Onglet Construction
        self.setup_build_tab()
        
        # Onglet Collection
        self.setup_collection_tab()
        
        # Onglet Paramètres
        self.setup_settings_tab()
        
        # Barre de statut
        self.statusBar().showMessage("Prêt")
    
    def setup_build_tab(self):
        """Configure l'onglet de construction de deck."""
        tab = QWidget()
        main_layout = QHBoxLayout(tab)
        layout1 = QVBoxLayout()
        layout2 = QVBoxLayout()
        layout3 = QVBoxLayout()
        main_layout.addLayout(layout1)
        main_layout.addLayout(layout2)
        main_layout.addLayout(layout3)
        
        # Sélection du commandant
        form_layout = QFormLayout()

        self.commander_input = QComboBox()
        self.commander_input.setPlaceholderText("Nom du commandant...")
        commanders_candidates = self.app.collection_manager.get_commander_candidates()
        self.commander_input.addItems(commanders_candidates)
        self.commander_input.setCurrentIndex(0)
        self.commander_input.setEditable(True)
        completer = QCompleter(commanders_candidates, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.commander_input.setCompleter(completer)
        self.commander_input.currentTextChanged.connect(self.update_commander_preview)

        self.search_commander_btn = QPushButton("Rechercher")
        form_layout.addRow("Commandant:", self.commander_input)
        
        # Bouton de construction
        self.build_btn = QPushButton("Construire le deck")
        self.build_btn.setMinimumHeight(40)
        
        # Liste des cartes trouvées
        self.label_deck_found_list = QLabel("Liste des cartes éventuelles:")
        self.deck_found_table = QTableWidget()
        self.deck_found_table.setColumnCount(6)
        self.deck_found_table.setHorizontalHeaderLabels([
            "Nom",
            "Couleurs",
            "Types",
            "Rank",
            "Occurrences",
            "Catégorie",
        ])
        header_found = self.deck_found_table.horizontalHeader()
        header_found.setSectionResizeMode(QHeaderView.Stretch)
        header_found.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_found.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.deck_found_table.setAlternatingRowColors(True)
        self.deck_found_table.setSelectionBehavior(self.deck_found_table.SelectionBehavior.SelectRows)
        self.deck_found_table.setEditTriggers(self.deck_found_table.EditTrigger.NoEditTriggers)
        self.deck_found_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.deck_found_table.customContextMenuRequested.connect(lambda pos: self.show_card_context_menu(pos, source="eventual"))
        self.export_deck_found_list = QPushButton("Exporter la listes des cartes éventuelles")
        self.load_exclusion_btn = QPushButton("Charger un fichier d'exclusion")
        # Liste des cartes du deck
        self.label_deck_list = QLabel("Deck:")
        self.deck_table = QTableWidget()
        self.deck_table.setColumnCount(4)
        self.deck_table.setHorizontalHeaderLabels([
            "Nom",
            "Types",
            "Rôle",
            "Score",
        ])
        header_deck = self.deck_table.horizontalHeader()
        header_deck.setSectionResizeMode(QHeaderView.Stretch)
        header_deck.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.deck_table.setAlternatingRowColors(True)
        self.deck_table.setSelectionBehavior(self.deck_table.SelectionBehavior.SelectRows)
        self.deck_table.setEditTriggers(self.deck_table.EditTrigger.NoEditTriggers)
        self.deck_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.deck_table.customContextMenuRequested.connect(lambda pos: self.show_card_context_menu(pos, source="deck"))
        self.export_deck_list = QPushButton("Exporter la listes des cartes du deck")
        self.export_deck_list.setMinimumHeight(40)
        self.deck_search = QLineEdit()
        self.deck_search.setPlaceholderText("Rechercher une carte dans le deck...")
        self.deck_search.textChanged.connect(self.filter_deck_list)
        self.deck_table.itemSelectionChanged.connect(self.update_preview_from_selection)
        self.deck_table.itemSelectionChanged.connect(self.scroll_to_selected_image)
        
        layout1.addLayout(form_layout)
        layout1.addWidget(self.search_commander_btn)
        layout1.addWidget(self.label_deck_found_list)
        layout1.addWidget(self.deck_found_table)
        layout1.addWidget(self.export_deck_found_list)
        layout1.addWidget(self.load_exclusion_btn)
        layout1.addWidget(self.build_btn)
        layout1.addWidget(self.label_deck_list)
        layout1.addWidget(self.deck_search)
        layout1.addWidget(self.deck_table)
        layout1.addWidget(self.export_deck_list)

        self.deck_filter_role = QComboBox()
        self.deck_filter_role.addItem("Toutes")
        self.deck_filter_role.currentTextChanged.connect(self.apply_role_filter)
        # Zone d'affichage des images du deck construit
        self.deck_images_area = QScrollArea()
        self.deck_images_area.setWidgetResizable(True)
        self.deck_images_container = QWidget()
        self.deck_images_grid = QGridLayout(self.deck_images_container)
        self.deck_images_grid.setContentsMargins(4, 4, 4, 4)
        self.deck_images_grid.setHorizontalSpacing(8)
        self.deck_images_grid.setVerticalSpacing(8)
        self.deck_images_area.setWidget(self.deck_images_container)
        # Aperçu grande taille
        self.preview_label = QLabel("Aperçu")
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout2.addWidget(self.preview_label)
        layout2.addWidget(QLabel("Catégories:"))
        layout2.addWidget(self.deck_filter_role)
        layout2.addWidget(self.deck_images_area)

        # Carte "statistiques" à droite
        self.stats_card = QWidget()
        self.stats_card.setObjectName("statsCard")
        stats_card_layout = QVBoxLayout(self.stats_card)
        stats_card_layout.setContentsMargins(16, 16, 16, 16)
        stats_card_layout.setSpacing(14)

        self.mana_curve_label = QLabel("Courbe de mana")
        self.mana_curve_label.setObjectName("statsTitle")
        self.mana_curve_label.setWordWrap(True)
        self.mana_curve_image = QLabel()
        self.mana_curve_image.setAlignment(Qt.AlignCenter)
        self.mana_curve_image.setMinimumHeight(320)
        self.mana_curve_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mana_curve_image.setStyleSheet("background: #161b22; border: 1px solid #243040; border-radius: 10px; padding: 8px;")

        self.deck_stats_label = QLabel("Statistiques")
        self.deck_stats_label.setObjectName("statsTitle")
        self.deck_stats_label.setWordWrap(True)

        self.deck_roles_image = QLabel()
        self.deck_roles_image.setAlignment(Qt.AlignCenter)
        self.deck_roles_image.setMinimumHeight(320)
        self.deck_roles_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.deck_roles_image.setStyleSheet("background: #161b22; border: 1px solid #243040; border-radius: 10px; padding: 8px;")

        stats_card_layout.addWidget(self.mana_curve_label)
        stats_card_layout.addWidget(self.mana_curve_image)
        stats_card_layout.addWidget(self.deck_stats_label)
        stats_card_layout.addWidget(self.deck_roles_image)
        stats_card_layout.addStretch()

        layout3.addWidget(self.stats_card)

        self.search_commander_btn.clicked.connect(self.app.get_decks_archidekt_from_commander)
        self.export_deck_found_list.clicked.connect(self.app.export_eventual_cards_list)
        self.load_exclusion_btn.clicked.connect(self.app.load_exclusion_list)
        self.build_btn.clicked.connect(self.app.build_deck)
        self.export_deck_list.clicked.connect(self.app.export_deck_list)

        self.tabs.addTab(tab, "Construction")
        # Aperçu initial du commandant sélectionné
        self.update_commander_preview(self.commander_input.currentText())

    def set_deck_stats(self, mana_curve_text: str, stats_text: str):
        """Affiche la courbe de mana et les stats synthétiques du deck."""
        self.mana_curve_label.setText(mana_curve_text)
        self.deck_stats_label.setText(stats_text)
    
    def set_deck_graphs(self, mana_curve_pixmap, roles_pixmap):
        """Affiche les représentations graphiques."""
        if mana_curve_pixmap:
            self.mana_curve_image.setPixmap(mana_curve_pixmap)
        else:
            self.mana_curve_image.clear()
        if roles_pixmap:
            self.deck_roles_image.setPixmap(roles_pixmap)
        else:
            self.deck_roles_image.clear()
        # Ajuster les tailles pour garder un rendu net
        for lbl in (self.mana_curve_image, self.deck_roles_image):
            if lbl.pixmap():
                lbl.setPixmap(lbl.pixmap().scaled(lbl.width(), lbl.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def show_progress(self, title: str, label: str, maximum: int = 0):
        """Affiche une barre de progression modale (0 = busy)."""
        self.progress_dialog = QProgressDialog(label, "Annuler", 0, maximum, self)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setCancelButton(None)
        # Pour un mode indéterminé, Qt recommande min=max=0
        if maximum and maximum > 0:
            self.progress_dialog.setRange(0, maximum)
        else:
            self.progress_dialog.setRange(0, 0)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        QApplication.processEvents()

    def update_progress(self, value: int):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.setValue(value)
            QApplication.processEvents()

    def close_progress(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
    
    def refresh_commander_candidates(self):
        """Rafraîchit la liste des commandants disponibles après mise à jour de la collection."""
        candidates = self.app.collection_manager.get_commander_candidates()
        current = self.commander_input.currentText()
        self.commander_input.blockSignals(True)
        self.commander_input.clear()
        self.commander_input.addItems(candidates)
        # Rétablir la sélection si possible
        idx = self.commander_input.findText(current, Qt.MatchFixedString | Qt.MatchCaseSensitive)
        if idx == -1:
            idx = 0 if candidates else -1
        if idx >= 0:
            self.commander_input.setCurrentIndex(idx)
        # Mettre à jour l'auto-complétion
        completer = QCompleter(candidates, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.commander_input.setCompleter(completer)
        self.commander_input.blockSignals(False)
        # Mettre à jour l'aperçu du commandant affiché
        self.update_commander_preview(self.commander_input.currentText())

    def _apply_modern_styles(self):
        """Applique un thème moderne sombre pour une meilleure lisibilité."""
        self.setStyleSheet("""
            QWidget {
                background-color: #0d1117;
                color: #e6edf3;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #1f2937;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #161b22;
                border: 1px solid #1f2937;
                padding: 8px 14px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #1f2937;
                border-color: #2563eb;
            }
            QListWidget {
                background: #0f172a;
                border: 1px solid #1f2937;
                border-radius: 6px;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: #0f172a;
                border: 1px solid #1f2937;
                border-radius: 6px;
                padding: 6px 8px;
            }
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:pressed {
                background: #1e3a8a;
            }
            QLabel#statsTitle {
                font-size: 15px;
                font-weight: 600;
                color: #93c5fd;
            }
            QWidget#statsCard {
                background: #111827;
                border: 1px solid #243040;
                border-radius: 10px;
            }
            QProgressBar {
                border: 1px solid #1f2937;
                border-radius: 6px;
                background: #0f172a;
                height: 16px;
                text-align: center;
                color: #e6edf3;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 6px;
            }
        """)
    
    def setup_collection_tab(self):
        """Configure l'onglet de gestion de la collection."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Boutons d'import/export
        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("Importer une collection")
        self.export_btn = QPushButton("Exporter la collection")
        self.clear_filters_btn = QPushButton("Réinitialiser les filtres")
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clear_filters_btn)
        
        # Tableau de la collection
        self.label_collection = QLabel("Nom / Couleur / Type / Quantité / Nom du set / Numéro de la carte")
        self.collection_table = QTableWidget()
        self.collection_table.setColumnCount(6)
        self.collection_table.setHorizontalHeaderLabels([
            "Nom",
            "Couleurs",
            "Types",
            "Qté",
            "Set",
            "Numéro",
        ])
        header = self.collection_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.collection_table.setAlternatingRowColors(True)
        self.collection_table.setSelectionBehavior(self.collection_table.SelectionBehavior.SelectRows)
        self.collection_table.setEditTriggers(self.collection_table.EditTrigger.NoEditTriggers)
        self.collection_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.collection_table.customContextMenuRequested.connect(self.show_collection_context_menu)

        # Recherche et filtres
        filters_row = QHBoxLayout()
        self.collection_search = QLineEdit()
        self.collection_search.setPlaceholderText("Rechercher par nom, set ou numéro...")
        self.collection_color_filter = QComboBox()
        self.collection_color_filter.addItem("Toutes les couleurs")
        self.collection_type_filter = QComboBox()
        self.collection_type_filter.addItem("Tous les types")
        filters_row.addWidget(QLabel("Recherche:"))
        filters_row.addWidget(self.collection_search)
        filters_row.addWidget(QLabel("Couleur:"))
        filters_row.addWidget(self.collection_color_filter)
        filters_row.addWidget(QLabel("Type:"))
        filters_row.addWidget(self.collection_type_filter)
        
        self.collection_summary = QLabel("")
        self.collection_summary.setObjectName("statsTitle")
        
        layout.addLayout(btn_layout)
        layout.addLayout(filters_row)
        layout.addWidget(self.collection_summary)
        layout.addWidget(self.label_collection)
        layout.addWidget(self.collection_table)

        self.import_btn.clicked.connect(self.app.import_collection)
        self.export_btn.clicked.connect(self.app.export_collection)
        self.collection_search.textChanged.connect(self.refresh_collection_list)
        self.collection_color_filter.currentTextChanged.connect(self.refresh_collection_list)
        self.collection_type_filter.currentTextChanged.connect(self.refresh_collection_list)
        self.clear_filters_btn.clicked.connect(self.clear_collection_filters)
        
        self.tabs.addTab(tab, "Ma Collection")

    # --- Collection helpers ---
    def set_collection_cards(self, cards: List[Dict]):
        """Réceptionne les cartes et (re)charge filtres + liste."""
        self.collection_cards = cards or []
        self._update_collection_filters()
        self.refresh_collection_list()

    def _update_collection_filters(self):
        colors = set()
        types = set()
        for card in self.collection_cards:
            colors_field = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            for part in colors_field.split(','):
                val = part.strip()
                if val:
                    colors.add(val)
            types_field = card.get("types") or ""
            main_type = types_field.split(" — ")[0].strip()
            if main_type:
                types.add(main_type)

        self.collection_color_filter.blockSignals(True)
        self.collection_color_filter.clear()
        self.collection_color_filter.addItem("Toutes les couleurs")
        for c in sorted(colors):
            self.collection_color_filter.addItem(c)
        self.collection_color_filter.blockSignals(False)

        self.collection_type_filter.blockSignals(True)
        self.collection_type_filter.clear()
        self.collection_type_filter.addItem("Tous les types")
        for t in sorted(types):
            self.collection_type_filter.addItem(t)
        self.collection_type_filter.blockSignals(False)

    def refresh_collection_list(self):
        """Applique recherche/filtre et met à jour la liste + résumé."""
        query = self.collection_search.text().strip().lower() if hasattr(self, "collection_search") else ""
        color_filter = self.collection_color_filter.currentText() if hasattr(self, "collection_color_filter") else "Toutes les couleurs"
        type_filter = self.collection_type_filter.currentText() if hasattr(self, "collection_type_filter") else "Tous les types"

        self.collection_table.setRowCount(0)
        filtered_cards: List[Dict] = []
        total_qty = 0

        for card in self.collection_cards:
            name = card.get("name", "")
            set_name = card.get("set_name", "")
            collector_number = str(card.get("collector_number", ""))
            colors_field = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            types_field = card.get("types", "")

            if query:
                target = " ".join([name, set_name, collector_number]).lower()
                if query not in target:
                    continue

            if color_filter != "Toutes les couleurs":
                color_tokens = {c.strip() for c in colors_field.split(',') if c.strip()}
                if color_filter not in color_tokens:
                    continue

            if type_filter != "Tous les types":
                if type_filter.lower() not in types_field.lower():
                    continue

            filtered_cards.append(card)
            total_qty += int(card.get("quantity", 0) or 0)

        self.filtered_collection_cards = filtered_cards

        self.collection_table.setRowCount(len(filtered_cards))
        for row, card in enumerate(filtered_cards):
            name = card.get("name", "")
            colors_field = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            types_field = card.get("types", "") or "-"
            qty = str(card.get("quantity", 0))
            set_name = card.get("set_name", "")
            collector_number = str(card.get("collector_number", ""))

            for col, value in enumerate([
                name,
                colors_field or "-",
                types_field,
                qty,
                set_name,
                collector_number,
            ]):
                item = QTableWidgetItem(value)
                if col == 3:
                    item.setTextAlignment(Qt.AlignCenter)
                self.collection_table.setItem(row, col, item)

        unique_total = len(self.collection_cards)
        filtered_total = len(filtered_cards)
        summary_text = f"{filtered_total} cartes filtrées sur {unique_total} ( {total_qty} exemplaires )"
        self.collection_summary.setText(summary_text)

    def clear_collection_filters(self):
        """Réinitialise recherche et filtres collection."""
        self.collection_search.clear()
        self.collection_color_filter.setCurrentIndex(0)
        self.collection_type_filter.setCurrentIndex(0)
        self.refresh_collection_list()

    def show_collection_context_menu(self, pos):
        """Affiche un menu contextuel sur la liste des cartes."""
        row = self.collection_table.rowAt(pos.y())
        if row < 0 or row >= len(self.filtered_collection_cards):
            return
        menu = QMenu(self)
        action_open = menu.addAction("Ouvrir l'image de la carte")
        action = menu.exec_(self.collection_table.mapToGlobal(pos))
        if action == action_open:
            card = self.filtered_collection_cards[row]
            self.open_card_image_dialog(card)

    def open_card_image_dialog(self, card: Dict):
        """Ouvre une fenêtre avec l'image de la carte (via image_url ou Scryfall)."""
        if not card:
            return

        url = card.get("image_url")
        if not url:
            scryfall_id = card.get("scryfall_id")
            if scryfall_id and hasattr(self.app, "external_provider"):
                try:
                    url = self.app.external_provider.get_image_url_from_scryfall(scryfall_id)
                except Exception:
                    url = None
        if not url:
            self.show_error("Aucune image disponible pour cette carte.")
            return

        try:
            resp = requests.get(url)
            resp.raise_for_status()
            pix = QPixmap()
            pix.loadFromData(resp.content)
        except Exception:
            self.show_error("Impossible de charger l'image de la carte.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(card.get("name", "Carte"))
        vbox = QVBoxLayout(dlg)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        if not pix.isNull():
            img_label.setPixmap(pix.scaledToWidth(480, Qt.SmoothTransformation))
        else:
            img_label.setText("Image indisponible")
        vbox.addWidget(img_label)
        dlg.resize(520, 720)
        dlg.exec()
    
    def setup_settings_tab(self):
        """Configure l'onglet des paramètres."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Paramètres d'export
        form_layout = QFormLayout()
        self.export_format = QComboBox()
        self.export_format.addItems(["TXT", "CSV", "Archidekt"])
        self.numb_deck_search = QComboBox()
        self.numb_deck_search.addItems(["Low", "Medium", "High"])
        self.numb_deck_search.setCurrentIndex(0)
        self.order_by = QComboBox()
        self.order_by.addItems(["Vues", "Mise à jour"])
        self.order_by.setCurrentIndex(0)

        self.numb_min_land = QSpinBox()
        self.numb_min_land.setRange(10, 50)
        self.numb_min_land.setValue(36)
        self.numb_max_land = QSpinBox()
        self.numb_max_land.setRange(10, 50)
        self.numb_max_land.setValue(38)

        self.numb_ramp = QSpinBox()
        self.numb_ramp.setRange(1, 30)
        self.numb_ramp.setValue(12)

        self.numb_draw = QSpinBox()
        self.numb_draw.setRange(1, 30)
        self.numb_draw.setValue(10)

        self.numb_removal = QSpinBox()
        self.numb_removal.setRange(1, 20)
        self.numb_removal.setValue(8)

        self.numb_boardwipe = QSpinBox()
        self.numb_boardwipe.setRange(1, 20)
        self.numb_boardwipe.setValue(4)

        self.numb_wincondition = QSpinBox()
        self.numb_wincondition.setRange(1, 20)
        self.numb_wincondition.setValue(6)

        form_layout.addRow("Format d'export:", self.export_format)
        form_layout.addRow("Nombre de decks à rechercher sur Archideckt:", self.numb_deck_search)
        form_layout.addRow("Filtrer les decks provenant d'Archidekt par:", self.order_by)
        form_layout.addRow("Nombre minimum de terrains:", self.numb_min_land)
        form_layout.addRow("Nombre maximum de terrains:", self.numb_max_land)
        form_layout.addRow("Nombre de ramp:", self.numb_ramp)
        form_layout.addRow("Nombre de draw:", self.numb_draw)
        form_layout.addRow("Nombre de removal:", self.numb_removal)
        form_layout.addRow("Nombre de boardwipe:", self.numb_boardwipe)
        form_layout.addRow("Nombre de wincondition:", self.numb_wincondition)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        self.tabs.addTab(tab, "Paramètres")
    
    def clear_deck_images(self):
        """Supprime les vignettes précédentes du deck."""
        while self.deck_images_grid.count():
            item = self.deck_images_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def show_deck_images(self, cards_data, external_provider):
        """Affiche les images du deck, 3 par ligne."""
        # Demande à l'utilisateur s'il souhaite charger les images
        reply = QMessageBox.question(
            self,
            "Afficher les images",
            "Voulez-vous afficher les images du deck ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self.clear_deck_images()
        self.card_index_to_widget = {}
        col_count = 3
        total = len(cards_data)
        self.cards_data = list(cards_data)
        self.roles_available = {str(c.get("role", "")).strip() for c in cards_data if c.get("role")}
        self.update_role_filter_options()
        self.missing_image_indices = []
        progress = QProgressDialog("Chargement des images...", "Annuler", 0, total, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        for idx, card in enumerate(cards_data):
            progress.setValue(idx)
            QApplication.processEvents()
            if progress.wasCanceled():
                break

            try:
                url = card.get("image_url")
                if not url:
                    scryfall_id = card.get("scryfall_id")
                    url = external_provider.get_image_url_from_scryfall(scryfall_id)
                if not url:
                    self.missing_image_indices.append(idx)
                    continue
                time.sleep(0.075)
                resp = requests.get(url)
                resp.raise_for_status()
                pix = QPixmap()
                pix.loadFromData(resp.content)
            except Exception:
                self.missing_image_indices.append(idx)
                continue

            label = QLabel()
            label.setPixmap(pix.scaledToWidth(240, Qt.SmoothTransformation))
            row = idx // col_count
            col = idx % col_count
            self.deck_images_grid.addWidget(label, row, col)
            self.card_index_to_widget[idx] = label
            self.card_index_to_pixmap[idx] = pix

        progress.setValue(total)
        self.apply_role_filter(self.deck_filter_role.currentText())

    def scroll_to_selected_image(self):
        """Scroll jusqu'à l'image correspondant à la sélection du deck."""
        row_index = self.deck_table.currentRow()
        widget = self.card_index_to_widget.get(row_index)
        if widget:
            self.deck_images_area.ensureWidgetVisible(widget, 20, 20)

    def update_preview_from_selection(self):
        """Met à jour l'aperçu grande image selon la sélection dans la liste."""
        if not self.preview_label:
            return
        row_index = self.deck_table.currentRow()
        pix = self.card_index_to_pixmap.get(row_index)
        if pix:
            self.preview_label.setPixmap(pix.scaledToWidth(360, Qt.SmoothTransformation))
        else:
            self.preview_label.setText("Aperçu")

    def update_commander_preview(self, commander_name: str):
        """Met à jour l'aperçu avec l'image du commandant choisi, y compris double-face."""
        if not commander_name:
            if self.preview_label:
                self.preview_label.setText("Aperçu")
            return

        def _load_pixmap(url: str) -> Optional[QPixmap]:
            try:
                resp = requests.get(url)
                resp.raise_for_status()
                pix = QPixmap()
                pix.loadFromData(resp.content)
                return pix if not pix.isNull() else None
            except Exception:
                return None

        def _get_face_urls(scryfall_id: str) -> list[str]:
            urls: list[str] = []
            try:
                data = self.app.external_provider.get_scryfall_data(scryfall_id)
            except Exception:
                return urls
            if not data:
                return urls
            if "image_uris" in data:
                image_uris = data["image_uris"]
                candidate = image_uris.get("normal") or image_uris.get("large") or image_uris.get("png")
                if candidate:
                    urls.append(candidate)
            for face in data.get("card_faces", []) or []:
                iu = face.get("image_uris") or {}
                candidate = iu.get("normal") or iu.get("large") or iu.get("png")
                if candidate:
                    urls.append(candidate)
            return urls

        card = self.app.collection_manager.get_card(commander_name)
        scryfall_id = card.get("scryfall_id") if card else None

        urls: list[str] = []
        if card and card.get("image_url"):
            urls.append(card["image_url"])
        if scryfall_id:
            fetched_urls = _get_face_urls(scryfall_id)
            for u in fetched_urls:
                if u not in urls:
                    urls.append(u)

        pixmaps = []
        urls.reverse()
        for url in urls:
            pix = _load_pixmap(url)
            if pix:
                pixmaps.append(pix)
            if len(pixmaps) >= 2:  # deux faces suffisent
                break

        if not pixmaps:
            if self.preview_label:
                self.preview_label.setText("Aperçu")
            return

        # Si deux faces, les afficher côte à côte; sinon afficher la seule image.
        if len(pixmaps) == 1:
            pix = pixmaps[0].scaledToWidth(360, Qt.SmoothTransformation)
        else:
            target_height = 360
            scaled = [p.scaledToHeight(target_height, Qt.SmoothTransformation) for p in pixmaps[:2]]
            total_width = sum(p.width() for p in scaled)
            pix = QPixmap(total_width, target_height)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            x = 0
            for p in scaled:
                painter.drawPixmap(x, 0, p)
                x += p.width()
            painter.end()

        if self.preview_label:
            self.preview_label.setPixmap(pix)

    def filter_deck_list(self, text: str):
        """Sélectionne la première carte correspondant au filtre et scroll (tableau deck)."""
        text = text.strip().lower()
        if not text:
            if self.deck_table.rowCount():
                self.deck_table.setCurrentCell(0, 0)
                self.scroll_to_selected_image()
            return
        for i in range(self.deck_table.rowCount()):
            if self.deck_table.isRowHidden(i):
                continue
            row_text = " ".join([
                self.deck_table.item(i, c).text() if self.deck_table.item(i, c) else ""
                for c in range(self.deck_table.columnCount())
            ]).lower()
            if text in row_text:
                self.deck_table.setCurrentCell(i, 0)
                self.scroll_to_selected_image()
                break

    def apply_role_filter(self, role: str):
        """Filtre les images et lignes par rôle (Ramp, Draw, Removal, etc.)."""
        if role == "Toutes" or not self.cards_data:
            for idx in range(self.deck_table.rowCount()):
                self.deck_table.setRowHidden(idx, False)
                widget = self.card_index_to_widget.get(idx)
                if widget:
                    widget.setVisible(True)
            self.filtered_deck_cards = list(self.cards_data)
            return
        role_lower = role.lower()
        visible_cards = []
        for idx, card in enumerate(self.cards_data):
            item_role = str(card.get("role", "")).lower()
            keep = role_lower in item_role
            self.deck_table.setRowHidden(idx, not keep)
            widget = self.card_index_to_widget.get(idx)
            if widget:
                widget.setVisible(keep)
            if keep:
                visible_cards.append(card)
        self.filtered_deck_cards = visible_cards

    def update_role_filter_options(self):
        """Met à jour la liste des rôles disponibles dans le filtre."""
        current = self.deck_filter_role.currentText()
        self.deck_filter_role.blockSignals(True)
        self.deck_filter_role.clear()
        self.deck_filter_role.addItem("Toutes")
        for role in sorted(r for r in self.roles_available if r):
            self.deck_filter_role.addItem(role)
        # rétablir sélection si possible
        idx = self.deck_filter_role.findText(current)
        if idx != -1:
            self.deck_filter_role.setCurrentIndex(idx)
        else:
            self.deck_filter_role.setCurrentIndex(0)
        self.deck_filter_role.blockSignals(False)

    def show_error(self, message):
        """Affiche un message d'erreur."""
        QMessageBox.critical(self, "Erreur", message)
    
    def show_info(self, message):
        """Affiche un message d'information."""
        QMessageBox.information(self, "Information", message)
    
    def get_open_file_name(self, title, file_filter):
        """Ouvre une boîte de dialogue pour sélectionner un fichier."""
        return QFileDialog.getOpenFileName(
            self, title, "", file_filter
        )[0]
    
    def get_csv_path_for_import_in_db(self):
        file_path = self.get_open_file_name(
            "Importer une collection", "CSV files (*.csv)"
        )
        import_type = QInputDialog.getItem(
            self, 
            "Type de format de l'import", 
            "Import depuis:", 
            ["ManaBox - Collection", "Moxfield"]
        )[0]
        return file_path, import_type

    def get_save_file_name(self, title, default_name, file_filter):
        """Ouvre une boîte de dialogue pour enregistrer un fichier."""
        return QFileDialog.getSaveFileName(
            self, title, default_name, file_filter
        )[0]

    def get_numb_deck_search(self):
        return self.numb_deck_search.currentText()

    def get_export_format(self):
        return self.export_format.currentText()

    def set_length_of_eventual_list(self, length: int, numb_decks: int, total_num_decks: int):
        self.label_deck_found_list.setText(f"Liste des cartes éventuelles ({length} {"cartes trouvées" if length > 1 else "carte trouvée"} dans {numb_decks} decks sur {total_num_decks} disponibles):")

    def set_length_and_score_of_deck_list(self, length: int, mean_score: float):
        self.label_deck_list.setText(f"Deck ({length} cartes) avec un score moyen de {mean_score:.2f}")

    # --- Construction tab helpers ---
    def set_eventual_cards(self, cards: List[Dict]):
        """Alimente le tableau des cartes éventuelles."""
        self.eventual_cards_data = cards or []
        self.filtered_eventual_cards = self.eventual_cards_data
        self.deck_found_table.setRowCount(len(self.filtered_eventual_cards))
        for row, card in enumerate(self.filtered_eventual_cards):
            values = [
                card.get("name", ""),
                str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", ""),
                card.get("types", ""),
                str(card.get("edhrec_rank", "")),
                str(card.get("occurence", "")),
                str(card.get("defaultCategory", "")),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignCenter)
                self.deck_found_table.setItem(row, col, item)

    def set_deck_cards(self, cards: List[Dict]):
        """Alimente le tableau du deck et conserve l'ordre pour images/filtre."""
        self.deck_cards_data = cards or []
        self.cards_data = self.deck_cards_data  # utilisé par apply_role_filter
        self.filtered_deck_cards = self.deck_cards_data
        self.deck_table.setRowCount(len(self.deck_cards_data))
        for row, card in enumerate(self.deck_cards_data):
            values = [
                card.get("name", ""),
                card.get("types", "") or "-",
                card.get("role", "") or "-",
                f"{float(card.get('score', 0)):.2f}",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 3:
                    item.setTextAlignment(Qt.AlignCenter)
                self.deck_table.setItem(row, col, item)
        # reset role filter to all
        self.deck_filter_role.blockSignals(True)
        self.deck_filter_role.setCurrentIndex(0)
        self.deck_filter_role.blockSignals(False)
        self.apply_role_filter(self.deck_filter_role.currentText())

    def show_card_context_menu(self, pos, source: str = "deck"):
        """Menu contextuel pour ouvrir l'image (deck ou éventuelles)."""
        if source == "deck":
            row = self.deck_table.rowAt(pos.y())
            target_cards = self.deck_cards_data
            table = self.deck_table
        elif source == "eventual":
            row = self.deck_found_table.rowAt(pos.y())
            target_cards = self.filtered_eventual_cards
            table = self.deck_found_table
        else:
            return
        if row is None or row < 0 or row >= len(target_cards):
            return
        menu = QMenu(self)
        action_open = menu.addAction("Ouvrir l'image de la carte")
        action = menu.exec_(table.mapToGlobal(pos))
        if action == action_open:
            card = target_cards[row]
            self.open_card_image_dialog(card)
