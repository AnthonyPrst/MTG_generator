from functools import partial
from pathlib import Path
import time
import requests
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
        self.deck_found_list = QListWidget()
        self.deck_found_list.setAlternatingRowColors(True)
        self.export_deck_found_list = QPushButton("Exporter la listes des cartes éventuelles")
        # Liste des cartes du deck
        self.label_deck_list = QLabel("Deck:")
        self.deck_list = QListWidget()
        self.deck_list.setAlternatingRowColors(True)
        self.export_deck_list = QPushButton("Exporter la listes des cartes du deck")
        self.export_deck_list.setMinimumHeight(40)
        self.deck_list.itemClicked.connect(self.scroll_to_selected_image)
        self.deck_list.itemSelectionChanged.connect(self.update_preview_from_selection)
        self.deck_search = QLineEdit()
        self.deck_search.setPlaceholderText("Rechercher une carte dans le deck...")
        self.deck_search.textChanged.connect(self.filter_deck_list)
        self.reload_missing_btn = QPushButton("Recharger les images manquantes")
        self.reload_missing_btn.clicked.connect(self.reload_missing_images)
        
        layout1.addLayout(form_layout)
        layout1.addWidget(self.search_commander_btn)
        layout1.addWidget(self.label_deck_found_list)
        layout1.addWidget(self.deck_found_list)
        layout1.addWidget(self.export_deck_found_list)
        layout1.addWidget(self.build_btn)
        layout1.addWidget(self.label_deck_list)
        layout1.addWidget(self.deck_search)
        layout1.addWidget(self.deck_list)
        layout1.addWidget(self.export_deck_list)
        layout1.addWidget(self.reload_missing_btn)

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
        btn_layout = QVBoxLayout()
        self.import_btn = QPushButton("Importer une collection")
        self.export_btn = QPushButton("Exporter la collection")
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.export_btn)
        
        # Liste de la collection
        self.label_collection = QLabel("Nom / Couleur / Type / Quantité / Nom du set / Numéro de la carte")
        self.collection_list = QListWidget()
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.label_collection)
        layout.addWidget(self.collection_list)

        self.import_btn.clicked.connect(self.app.import_collection)
        self.export_btn.clicked.connect(self.app.export_collection)
        
        self.tabs.addTab(tab, "Ma Collection")
    
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

    def scroll_to_selected_image(self, item):
        """Scroll jusqu'à l'image correspondant à l'item sélectionné dans la liste du deck."""
        row_index = self.deck_list.row(item)
        widget = self.card_index_to_widget.get(row_index)
        if widget:
            self.deck_images_area.ensureWidgetVisible(widget, 20, 20)

    def update_preview_from_selection(self):
        """Met à jour l'aperçu grande image selon la sélection dans la liste."""
        if not self.preview_label:
            return
        row_index = self.deck_list.currentRow()
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
        """Sélectionne la première carte correspondant au filtre et scroll."""
        text = text.strip().lower()
        if not text:
            if self.deck_list.count():
                self.deck_list.setCurrentRow(0)
            return
        for i in range(self.deck_list.count()):
            item = self.deck_list.item(i)
            if text in item.text().lower():
                self.deck_list.setCurrentItem(item)
                self.scroll_to_selected_image(item)
                break

    def apply_role_filter(self, role: str):
        """Filtre les images par rôle (Ramp, Draw, Removal, etc.)."""
        if role == "Toutes" or not self.cards_data:
            for idx in range(self.deck_list.count()):
                self.deck_list.item(idx).setHidden(False)
                widget = self.card_index_to_widget.get(idx)
                if widget:
                    widget.setVisible(True)
            return
        role_lower = role.lower()
        for idx, card in enumerate(self.cards_data):
            item = self.deck_list.item(idx)
            item_role = str(card.get("role", "")).lower()
            item.setHidden(role_lower not in item_role)
            widget = self.card_index_to_widget.get(idx)
            if widget:
                widget.setVisible(role_lower in item_role)

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

    def reload_missing_images(self):
        """Recharge uniquement les images manquantes."""
        if not self.missing_image_indices:
            self.show_info("Aucune image manquante à recharger.")
            return
        if not self.cards_data:
            return
        col_count = 3
        external_provider = self.app.external_provider
        still_missing = []
        for idx in list(self.missing_image_indices):
            card = self.cards_data[idx]
            url = card.get("image_url")
            if not url:
                scryfall_id = card.get("scryfall_id")
                url = external_provider.get_image_url_from_scryfall(scryfall_id)
            if not url:
                still_missing.append(idx)
                continue
            try:
                time.sleep(0.075)
                resp = requests.get(url)
                resp.raise_for_status()
                pix = QPixmap()
                pix.loadFromData(resp.content)
            except Exception:
                still_missing.append(idx)
                continue

            row = idx // col_count
            col = idx % col_count
            label = self.card_index_to_widget.get(idx)
            if label is None:
                label = QLabel()
                self.deck_images_grid.addWidget(label, row, col)
                self.card_index_to_widget[idx] = label
            label.setPixmap(pix.scaledToWidth(240, Qt.SmoothTransformation))
            self.card_index_to_pixmap[idx] = pix

        self.missing_image_indices = still_missing
        if still_missing:
            self.show_info(f"Images restantes manquantes : {len(still_missing)}")
        else:
            self.show_info("Toutes les images manquantes ont été rechargées.")

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
