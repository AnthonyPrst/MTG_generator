"""Onglet Construction de deck — layout moderne avec sidebar + zone principale."""

from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
import time

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QComboBox, QScrollArea,
    QGridLayout, QGroupBox, QCheckBox, QCompleter, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QProgressDialog, QSizePolicy,
    QApplication, QTabWidget, QDialog, QStyledItemDelegate, QListView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QStandardItemModel, QStandardItem, QColor, QBrush

from gui.widgets.card_image import open_card_image_dialog
from gui.widgets.stats_panel import StatsPanel, SectionTitle


class CheckableComboBox(QComboBox):
    """ComboBox avec sélection multiple via checkboxes."""
    
    selection_changed = Signal(list)  # Émet la liste des items sélectionnés
    
    def __init__(self, placeholder: str = "Tous", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText(placeholder)
        self.lineEdit().setCursor(Qt.PointingHandCursor)
        
        # Style pour voir les checkboxes sur fond sombre
        self.view().setStyleSheet("""
            QListView {
                background: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
            }
            QListView::item {
                padding: 4px 8px 4px 6px;
                min-height: 24px;
            }
            QListView::item:hover {
                background: #30363d;
            }
            QAbstractItemView::indicator {
                width: 16px;
                height: 16px;
                margin-right: 6px;
            }
            QAbstractItemView::indicator:unchecked {
                border: 2px solid #484f58;
                background: #0d1117;
                border-radius: 3px;
            }
            QAbstractItemView::indicator:checked {
                border: 2px solid #238636;
                background: #238636;
                border-radius: 3px;
            }
            QAbstractItemView::item:selected {
                background: #1f3a6e;
                color: #e6edf3;
            }
        """)
        
        # Empêcher la fermeture du popup au clic
        self.view().pressed.connect(self._on_item_pressed)
        self.setMinimumWidth(100)
        
    def _on_item_pressed(self, index):
        item = self._model.itemFromIndex(index)
        if item and item.isCheckable():
            item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
            self._update_text()
            self.selection_changed.emit(self.get_checked_items())
    
    def _update_text(self):
        checked = self.get_checked_items()
        if not checked or len(checked) == self._model.rowCount():
            self.lineEdit().setText("")
            self.lineEdit().setPlaceholderText(self._placeholder)
        else:
            self.lineEdit().setText(", ".join(checked[:2]) + ("…" if len(checked) > 2 else ""))
    
    def add_items(self, items: List[str]):
        """Ajoute des items avec checkboxes."""
        self._model.clear()
        for text in items:
            item = QStandardItem(text)
            item.setCheckable(True)
            item.setCheckState(Qt.Unchecked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            self._model.appendRow(item)
        self._update_text()
    
    def get_checked_items(self) -> List[str]:
        """Retourne la liste des items cochés."""
        checked = []
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item and item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked
    
    def clear_selection(self):
        """Décoche tous les items."""
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._update_text()

    def set_checked_items(self, items: List[str]):
        targets = {str(item).strip().lower() for item in items}
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if not item:
                continue
            item.setCheckState(Qt.Checked if item.text().strip().lower() in targets else Qt.Unchecked)
        self._update_text()
        self.selection_changed.emit(self.get_checked_items())


class BuildTab(QWidget):
    """Onglet principal de construction de deck."""

    # Signaux vers MainWindow
    search_commander_requested = Signal()
    build_deck_requested = Signal()
    export_eventual_requested = Signal()
    export_deck_requested = Signal()
    load_exclusion_requested = Signal()
    show_recommendations_requested = Signal()
    commander_changed = Signal(str)
    strategy_changed = Signal(str)
    budget_changed = Signal(int)
    role_filter_changed = Signal(str)
    deck_search_changed = Signal(str)
    deck_search_enter = Signal()
    mana_curve_clicked = Signal(int, int)
    mana_curve_reset = Signal()

    def __init__(self, collection_manager, strategy_manager, scryfall_sync, parent=None):
        super().__init__(parent)
        self._collection_manager = collection_manager
        self._strategy_manager = strategy_manager
        self._scryfall_sync = scryfall_sync

        self.cards_data: List[Dict] = []
        self.deck_cards_data: List[Dict] = []
        self.filtered_deck_cards: List[Dict] = []
        self.filtered_eventual_cards: List[Dict] = []
        self.eventual_cards_data: List[Dict] = []
        self.card_index_to_widget: Dict[int, QLabel] = {}
        self.card_index_to_pixmap: Dict[int, QPixmap] = {}
        self.roles_available: set = set()
        self._mana_curve_data: Dict[int, int] = {}
        self._original_deck_cards: List[Dict] = []
        self._cmc_filter: Optional[int] = None

        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Construction UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Splitter principal ────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_stats_panel())

        splitter.setSizes([350, 700, 350])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        root.addWidget(splitter)

    def _build_sidebar(self) -> QWidget:
        """Sidebar gauche : commandant, stratégie, actions."""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(320)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Commandant ────────────────────────────────────────────────────────
        grp_commander = QGroupBox("Commandant")
        g_layout = QVBoxLayout(grp_commander)
        g_layout.setSpacing(8)

        self.commander_input = QComboBox()
        self.commander_input.setPlaceholderText("Nom du commandant...")
        self.commander_input.setEditable(True)
        self.commander_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.commander_input.currentTextChanged.connect(self.commander_changed)
        g_layout.addWidget(self.commander_input)

        self.search_commander_btn = QPushButton("🔍  Rechercher les decks")
        self.search_commander_btn.setObjectName("accent")
        self.search_commander_btn.setMinimumHeight(36)
        self.search_commander_btn.clicked.connect(self.search_commander_requested)
        g_layout.addWidget(self.search_commander_btn)

        layout.addWidget(grp_commander)

        # ── Stratégie ─────────────────────────────────────────────────────────
        grp_strategy = QGroupBox("Stratégie")
        s_layout = QVBoxLayout(grp_strategy)
        s_layout.setSpacing(8)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["Midrange", "Aggro", "Control", "Combo", "Budget"])
        self.strategy_combo.currentTextChanged.connect(self.strategy_changed)
        s_layout.addWidget(self.strategy_combo)

        self.strategy_info = QLabel("Deck équilibré, valeur à chaque étape")
        self.strategy_info.setWordWrap(True)
        self.strategy_info.setStyleSheet("color: #388bfd; font-size: 11px; font-style: italic;")
        s_layout.addWidget(self.strategy_info)

        self.budget_checkbox = QCheckBox("Mode Budget  (Communes / Peu communes)")
        self.budget_checkbox.stateChanged.connect(self.budget_changed)
        s_layout.addWidget(self.budget_checkbox)

        layout.addWidget(grp_strategy)

        # ── Recommandations Scryfall ──────────────────────────────────────────
        grp_rec = QGroupBox("Recommandations Scryfall")
        r_layout = QVBoxLayout(grp_rec)
        r_layout.setSpacing(6)

        self.recommendations_text = QLabel("Synchronisez Scryfall pour voir les recommandations")
        self.recommendations_text.setWordWrap(True)
        self.recommendations_text.setStyleSheet("color: #8b949e; font-size: 11px;")
        r_layout.addWidget(self.recommendations_text)

        self.btn_show_recommendations = QPushButton("Voir les cartes recommandées")
        self.btn_show_recommendations.setVisible(False)
        self.btn_show_recommendations.clicked.connect(self.show_recommendations_requested)
        r_layout.addWidget(self.btn_show_recommendations)

        layout.addWidget(grp_rec)

        # ── Construire le deck ────────────────────────────────────────────────
        self.build_btn = QPushButton("⚙  Construire le deck")
        self.build_btn.setObjectName("primary")
        self.build_btn.setMinimumHeight(40)
        self.build_btn.clicked.connect(self.build_deck_requested)
        layout.addWidget(self.build_btn)

        # ── Actions secondaires ───────────────────────────────────────────────
        grp_actions = QGroupBox("Actions")
        a_layout = QVBoxLayout(grp_actions)
        a_layout.setSpacing(6)

        self.load_exclusion_btn = QPushButton("📂  Charger un fichier d'exclusion")
        self.load_exclusion_btn.clicked.connect(self.load_exclusion_requested)
        a_layout.addWidget(self.load_exclusion_btn)

        self.export_deck_found_btn = QPushButton("⬇  Exporter les cartes éventuelles")
        self.export_deck_found_btn.clicked.connect(self.export_eventual_requested)
        a_layout.addWidget(self.export_deck_found_btn)

        self.export_deck_btn = QPushButton("⬇  Exporter le deck")
        self.export_deck_btn.clicked.connect(self.export_deck_requested)
        a_layout.addWidget(self.export_deck_btn)

        layout.addWidget(grp_actions)
        layout.addStretch()

        return sidebar

    def _build_center(self) -> QWidget:
        """Zone centrale : deux tableaux + galerie d'images."""
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        inner_splitter = QSplitter(Qt.Vertical)
        inner_splitter.setChildrenCollapsible(False)

        # ── Tableau cartes éventuelles ────────────────────────────────────────
        eventual_widget = QWidget()
        ev_layout = QVBoxLayout(eventual_widget)
        ev_layout.setContentsMargins(12, 12, 12, 6)
        ev_layout.setSpacing(8)

        ev_header = QHBoxLayout()
        self.label_deck_found_list = QLabel("CARTES ÉVENTUELLES")
        self.label_deck_found_list.setObjectName("sectionTitle")
        ev_header.addWidget(self.label_deck_found_list)
        ev_header.addStretch()
        ev_layout.addLayout(ev_header)

        self.deck_found_table = self._make_table(
            ["Nom", "Couleurs", "Types", "Rank", "Occurrences", "Catégorie"],
            stretch_cols=[0, 2, 5],
            content_cols=[1, 3, 4],
        )
        self.deck_found_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.deck_found_table.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, "eventual")
        )
        self.deck_found_table.doubleClicked.connect(
            lambda: self._on_table_double_click("eventual")
        )
        ev_layout.addWidget(self.deck_found_table)

        inner_splitter.addWidget(eventual_widget)

        # ── Tableau deck construit ────────────────────────────────────────────
        deck_widget = QWidget()
        dk_layout = QVBoxLayout(deck_widget)
        dk_layout.setContentsMargins(12, 6, 12, 6)
        dk_layout.setSpacing(8)

        dk_header = QHBoxLayout()
        self.label_deck_list = QLabel("DECK")
        self.label_deck_list.setObjectName("sectionTitle")
        dk_header.addWidget(self.label_deck_list)
        dk_header.addStretch()

        # Filtre rôle
        self.deck_filter_role = QComboBox()
        self.deck_filter_role.addItem("Toutes")
        self.deck_filter_role.setFixedWidth(110)
        self.deck_filter_role.currentTextChanged.connect(self.role_filter_changed)
        dk_header.addWidget(QLabel("Rôle:"))
        dk_header.addWidget(self.deck_filter_role)

        # Filtre édition (multi-sélection)
        self.deck_filter_set = CheckableComboBox("Toutes éditions")
        self.deck_filter_set.setFixedWidth(250)
        self.deck_filter_set.selection_changed.connect(self._apply_filters)
        dk_header.addWidget(QLabel("Set:"))
        dk_header.addWidget(self.deck_filter_set)

        # Filtre rareté (multi-sélection)
        self.deck_filter_rarity = CheckableComboBox("Toutes raretés")
        self.deck_filter_rarity.setFixedWidth(150)
        self.deck_filter_rarity.add_items(["mythic", "rare", "uncommon", "common"])
        self.deck_filter_rarity.selection_changed.connect(self._apply_filters)
        dk_header.addWidget(QLabel("Rareté:"))
        dk_header.addWidget(self.deck_filter_rarity)

        self.deck_filter_color = CheckableComboBox("Toutes couleurs")
        self.deck_filter_color.setFixedWidth(150)
        self.deck_filter_color.add_items(["W", "U", "B", "R", "G", "C"])
        self.deck_filter_color.selection_changed.connect(self._apply_filters)
        dk_header.addWidget(QLabel("Couleur:"))
        dk_header.addWidget(self.deck_filter_color)

        # Recherche
        self.deck_search = QLineEdit()
        self.deck_search.setPlaceholderText("Rechercher…")
        self.deck_search.setFixedWidth(150)
        self.deck_search.textChanged.connect(self.deck_search_changed)
        self.deck_search.returnPressed.connect(self.deck_search_enter)
        dk_header.addWidget(self.deck_search)

        dk_layout.addLayout(dk_header)

        self.deck_table = self._make_table(
            ["Nom", "Types", "Set", "Rareté", "Rôle", "Score"],
            stretch_cols=[0, 1],
            content_cols=[2, 3, 4, 5],
        )
        self.deck_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.deck_table.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(pos, "deck")
        )
        self.deck_table.doubleClicked.connect(
            lambda: self._on_table_double_click("deck")
        )
        self.deck_table.itemSelectionChanged.connect(self._update_preview_from_selection)
        self.deck_table.itemSelectionChanged.connect(self._scroll_to_selected_image)
        dk_layout.addWidget(self.deck_table)

        inner_splitter.addWidget(deck_widget)

        # ── Galerie d'images ──────────────────────────────────────────────────
        gallery_widget = QWidget()
        gal_layout = QVBoxLayout(gallery_widget)
        gal_layout.setContentsMargins(12, 6, 12, 12)
        gal_layout.setSpacing(6)

        gal_header = QHBoxLayout()
        gal_title = QLabel("GALERIE")
        gal_title.setObjectName("sectionTitle")
        gal_header.addWidget(gal_title)
        gal_header.addStretch()
        gal_layout.addLayout(gal_header)

        self.deck_images_area = QScrollArea()
        self.deck_images_area.setWidgetResizable(True)
        self.deck_images_area.setStyleSheet("border: none;")
        self.deck_images_container = QWidget()
        self.deck_images_grid = QGridLayout(self.deck_images_container)
        self.deck_images_grid.setContentsMargins(4, 4, 4, 4)
        self.deck_images_grid.setHorizontalSpacing(6)
        self.deck_images_grid.setVerticalSpacing(6)
        self.deck_images_area.setWidget(self.deck_images_container)
        gal_layout.addWidget(self.deck_images_area)

        inner_splitter.addWidget(gallery_widget)
        inner_splitter.setSizes([200, 250, 200])

        layout.addWidget(inner_splitter)
        return center

    def _build_stats_panel(self) -> StatsPanel:
        """Panneau droit — stats, graphiques, aperçu commandant."""
        self.stats_panel = StatsPanel()
        self.stats_panel.mana_curve_clicked.connect(self.mana_curve_clicked)
        self.stats_panel.mana_curve_reset.connect(self.mana_curve_reset)
        self.stats_panel.role_distribution_clicked.connect(self.apply_graph_role_filter)
        self.stats_panel.role_distribution_reset.connect(self.reset_graph_role_filter)
        self.stats_panel.rarity_distribution_clicked.connect(self.apply_graph_rarity_filter)
        self.stats_panel.rarity_distribution_reset.connect(self.reset_graph_rarity_filter)
        self.stats_panel.color_distribution_clicked.connect(self.apply_graph_color_filter)
        self.stats_panel.color_distribution_reset.connect(self.reset_graph_color_filter)
        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setFrameShape(QScrollArea.NoFrame)
        container.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container.setWidget(self.stats_panel)
        return container

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers internes
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_table(headers: list, stretch_cols: list, content_cols: list) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.StrongFocus)
        table.setSortingEnabled(True)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(30)
        header = table.horizontalHeader()
        for col in range(len(headers)):
            if col in stretch_cols:
                header.setSectionResizeMode(col, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        return table

    def _show_context_menu(self, pos, source: str):
        if source == "deck":
            row = self.deck_table.rowAt(pos.y())
            table = self.deck_table
            card = self._get_deck_card_by_row(row)
        else:
            row = self.deck_found_table.rowAt(pos.y())
            table = self.deck_found_table
            card = self._get_eventual_card_by_row(row)
        if not card:
            return
        menu = QMenu(self)
        action_img = menu.addAction("🖼  Voir l'image de la carte")
        action = menu.exec_(table.mapToGlobal(pos))
        if action == action_img:
            provider = getattr(self, "_external_provider", None)
            open_card_image_dialog(self, card, provider)

    def _on_table_double_click(self, source: str):
        if source == "eventual":
            row = self.deck_found_table.currentRow()
            card = self._get_eventual_card_by_row(row)
            if card:
                provider = getattr(self, "_external_provider", None)
                open_card_image_dialog(self, card, provider)
        elif source == "deck":
            row = self.deck_table.currentRow()
            card = self._get_deck_card_by_row(row)
            if card:
                provider = getattr(self, "_external_provider", None)
                open_card_image_dialog(self, card, provider)

    def _update_preview_from_selection(self):
        row = self.deck_table.currentRow()
        source_idx = self._get_source_index_from_row(self.deck_table, row)
        pix = self.card_index_to_pixmap.get(source_idx) if source_idx is not None else None
        if pix:
            self.stats_panel.set_commander_preview(pix)

    def _scroll_to_selected_image(self):
        row = self.deck_table.currentRow()
        source_idx = self._get_source_index_from_row(self.deck_table, row)
        widget = self.card_index_to_widget.get(source_idx) if source_idx is not None else None
        if widget:
            self.deck_images_area.ensureWidgetVisible(widget, 20, 20)

    # ─────────────────────────────────────────────────────────────────────────
    # API publique utilisée par MainWindow
    # ─────────────────────────────────────────────────────────────────────────

    def refresh_commander_candidates(self, candidates: list):
        current = self.commander_input.currentText()
        self.commander_input.blockSignals(True)
        self.commander_input.clear()
        self.commander_input.addItems(candidates)
        idx = self.commander_input.findText(current, Qt.MatchFixedString | Qt.MatchCaseSensitive)
        self.commander_input.setCurrentIndex(idx if idx >= 0 else 0)
        completer = QCompleter(candidates, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.commander_input.setCompleter(completer)
        self.commander_input.blockSignals(False)

    def set_eventual_cards(self, cards: List[Dict]):
        self.eventual_cards_data = cards or []
        self.filtered_eventual_cards = self.eventual_cards_data
        self.deck_found_table.setSortingEnabled(False)
        self.deck_found_table.setRowCount(len(self.filtered_eventual_cards))
        for row, card in enumerate(self.filtered_eventual_cards):
            colors_raw = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            color_tokens = [c.strip() for c in colors_raw.split(",") if c.strip()]
            occ = int(card.get("occurence", 0) or 0)
            rank = card.get("edhrec_rank", "")

            col0 = QTableWidgetItem(card.get("name", ""))
            col0.setData(Qt.UserRole, row)
            self.deck_found_table.setItem(row, 0, col0)

            col1 = QTableWidgetItem(_fmt_colors(color_tokens))
            col1.setTextAlignment(Qt.AlignCenter)
            col1.setForeground(QBrush(QColor(_color_fg(color_tokens))))
            self.deck_found_table.setItem(row, 1, col1)

            col2 = QTableWidgetItem(card.get("types", "") or "—")
            col2.setForeground(QBrush(QColor("#8b949e")))
            self.deck_found_table.setItem(row, 2, col2)

            col3 = QTableWidgetItem(str(rank))
            col3.setTextAlignment(Qt.AlignCenter)
            col3.setForeground(QBrush(QColor("#8b949e")))
            self.deck_found_table.setItem(row, 3, col3)

            col4 = QTableWidgetItem(str(occ))
            col4.setTextAlignment(Qt.AlignCenter)
            col4.setData(Qt.UserRole, occ)
            if occ >= 30:
                col4.setForeground(QBrush(QColor("#3fb950")))
            elif occ >= 15:
                col4.setForeground(QBrush(QColor("#79c0ff")))
            else:
                col4.setForeground(QBrush(QColor("#8b949e")))
            self.deck_found_table.setItem(row, 4, col4)

            col5 = QTableWidgetItem(str(card.get("defaultCategory", "")))
            col5.setForeground(QBrush(QColor(_category_color(str(card.get("defaultCategory", ""))))))
            self.deck_found_table.setItem(row, 5, col5)

        self.deck_found_table.setSortingEnabled(True)

    def set_deck_cards(self, cards: List[Dict]):
        self.deck_cards_data = cards or []
        self._original_deck_cards = self.deck_cards_data.copy()
        for idx, card in enumerate(self._original_deck_cards):
            card["_source_index"] = idx
        self.cards_data = self.deck_cards_data
        self.filtered_deck_cards = self.deck_cards_data

        self._mana_curve_data = {}
        for card in self.deck_cards_data:
            cmc = min(int(card.get("cmc", 0) or 0), 7)
            self._mana_curve_data[cmc] = self._mana_curve_data.get(cmc, 0) + 1

        # Extraire les rôles disponibles
        self.roles_available = {_normalize_role_label(str(c.get("role", "")).strip()) for c in self.deck_cards_data if c.get("role")}
        
        self._populate_deck_table(self.deck_cards_data)
        
        # Mettre à jour les options des filtres
        self.update_role_filter_options()
        self.deck_filter_rarity.clear_selection()
        self.deck_filter_color.clear_selection()
        
        self.deck_filter_role.blockSignals(True)
        self.deck_filter_role.setCurrentIndex(0)
        self.deck_filter_role.blockSignals(False)

    def _populate_deck_table(self, cards: List[Dict]):
        self.deck_table.setSortingEnabled(False)
        self.deck_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            rarity = (card.get("rarity", "") or "").capitalize()
            score = float(card.get("score", 0) or 0)
            role_label = _normalize_role_label(str(card.get("role", "") or "—"))

            col0 = QTableWidgetItem(card.get("name", ""))
            col0.setData(Qt.UserRole, int(card.get("_source_index", row)))
            self.deck_table.setItem(row, 0, col0)

            col1 = QTableWidgetItem(card.get("types", "") or "—")
            col1.setForeground(QBrush(QColor("#8b949e")))
            self.deck_table.setItem(row, 1, col1)

            col2 = QTableWidgetItem(card.get("set_name", "") or card.get("set_code", "") or "—")
            col2.setForeground(QBrush(QColor("#8b949e")))
            self.deck_table.setItem(row, 2, col2)

            col3 = QTableWidgetItem(rarity or "—")
            col3.setTextAlignment(Qt.AlignCenter)
            col3.setForeground(QBrush(QColor(_rarity_color(rarity))))
            self.deck_table.setItem(row, 3, col3)

            col4 = QTableWidgetItem(role_label)
            col4.setTextAlignment(Qt.AlignCenter)
            col4.setForeground(QBrush(QColor(_role_color(role_label))))
            self.deck_table.setItem(row, 4, col4)

            col5 = QTableWidgetItem(f"{score:.2f}")
            col5.setTextAlignment(Qt.AlignCenter)
            col5.setData(Qt.UserRole, score)
            if score >= 3.0:
                col5.setForeground(QBrush(QColor("#3fb950")))
            elif score >= 1.5:
                col5.setForeground(QBrush(QColor("#79c0ff")))
            else:
                col5.setForeground(QBrush(QColor("#8b949e")))
            self.deck_table.setItem(row, 5, col5)

        self.deck_table.setSortingEnabled(True)

    def apply_role_filter(self, role: str):
        """Applique le filtre rôle (appelé par le signal, déclenche _apply_filters)."""
        self._apply_filters()

    def _apply_filters(self, _=None):
        """Applique tous les filtres combinés (rôle, set, rareté)."""
        if not self.cards_data:
            return

        source_cards = self._original_deck_cards or self.cards_data
        
        # Récupérer les valeurs des filtres
        role = self.deck_filter_role.currentText()
        role_all = self.deck_filter_role.itemText(0)
        selected_sets = self.deck_filter_set.get_checked_items()
        selected_rarities = self.deck_filter_rarity.get_checked_items()
        selected_colors = self.deck_filter_color.get_checked_items()
        
        selected_rarities_lower = {r.lower() for r in selected_rarities}
        visible = []
        visible_source_indices: List[int] = []

        for row in range(self.deck_table.rowCount()):
            source_idx = self._get_source_index_from_row(self.deck_table, row)
            if source_idx is None or source_idx < 0 or source_idx >= len(source_cards):
                self.deck_table.setRowHidden(row, True)
                continue

            card = source_cards[source_idx]
            keep = True
            card_role = _normalize_role_label(str(card.get("role", "") or ""))
            
            # Filtre rôle
            if role != role_all:
                if role.lower() != card_role.lower():
                    keep = False
            
            # Filtre set (si sélection) - utilise set_name
            if keep and selected_sets:
                card_set = card.get("set_name", "") or card.get("set_code", "")
                if card_set not in selected_sets:
                    keep = False
            
            # Filtre rareté (si sélection)
            if keep and selected_rarities:
                card_rarity = card.get("rarity", "").lower()
                if card_rarity not in selected_rarities_lower:
                    keep = False

            if keep and selected_colors:
                card_colors = _extract_color_codes(card.get("colors", ""))
                if not any(color in card_colors for color in selected_colors):
                    keep = False
            
            self.deck_table.setRowHidden(row, not keep)
            if keep:
                visible.append(card)
                visible_source_indices.append(source_idx)
        
        self.filtered_deck_cards = visible
        self._reflow_visible_deck_images(visible_source_indices)

    def update_role_filter_options(self):
        """Met à jour les options des filtres rôle et set."""
        # Filtre rôle
        current = self.deck_filter_role.currentText()
        self.deck_filter_role.blockSignals(True)
        self.deck_filter_role.clear()
        self.deck_filter_role.addItem("Toutes")
        for role in sorted(r for r in self.roles_available if r):
            self.deck_filter_role.addItem(role)
        idx = self.deck_filter_role.findText(current)
        self.deck_filter_role.setCurrentIndex(idx if idx != -1 else 0)
        self.deck_filter_role.blockSignals(False)
        
        # Filtre set - extraire les sets uniques du deck (nom complet)
        sets_in_deck = set()
        for card in self.cards_data:
            set_name = card.get("set_name", "") or card.get("set_code", "")
            if set_name:
                sets_in_deck.add(set_name)
        self.deck_filter_set.add_items(sorted(sets_in_deck))

        colors_in_deck = set()
        for card in self.cards_data:
            colors_in_deck.update(_extract_color_codes(card.get("colors", "")))
        ordered_colors = [color for color in ["W", "U", "B", "R", "G", "C"] if color in colors_in_deck]
        self.deck_filter_color.add_items(ordered_colors)

    def apply_graph_role_filter(self, role: str):
        role = _normalize_role_label(role)
        current = self.deck_filter_role.currentText()
        idx = self.deck_filter_role.findText("Toutes")
        if current.lower() == role.lower():
            self.deck_filter_role.setCurrentIndex(idx if idx != -1 else 0)
            return
        idx = self.deck_filter_role.findText(role)
        if idx != -1:
            self.deck_filter_role.setCurrentIndex(idx)

    def reset_graph_role_filter(self):
        idx = self.deck_filter_role.findText("Toutes")
        self.deck_filter_role.setCurrentIndex(idx if idx != -1 else 0)

    def apply_graph_rarity_filter(self, rarity: str):
        rarity = rarity.strip().lower()
        checked = [item.lower() for item in self.deck_filter_rarity.get_checked_items()]
        if checked == [rarity]:
            self.deck_filter_rarity.clear_selection()
            self._apply_filters()
        else:
            self.deck_filter_rarity.set_checked_items([rarity])

    def reset_graph_rarity_filter(self):
        self.deck_filter_rarity.clear_selection()
        self._apply_filters()

    def apply_graph_color_filter(self, color: str):
        color = color.strip().upper()
        checked = [item.upper() for item in self.deck_filter_color.get_checked_items()]
        if checked == [color]:
            self.deck_filter_color.clear_selection()
            self._apply_filters()
        else:
            self.deck_filter_color.set_checked_items([color])

    def reset_graph_color_filter(self):
        self.deck_filter_color.clear_selection()
        self._apply_filters()

    def filter_deck_list(self, text: str):
        text = text.strip().lower()
        if not text:
            if self.deck_table.rowCount():
                self.deck_table.setCurrentCell(0, 0)
            return
        for i in range(self.deck_table.rowCount()):
            if self.deck_table.isRowHidden(i):
                continue
            row_text = " ".join(
                self.deck_table.item(i, c).text() if self.deck_table.item(i, c) else ""
                for c in range(self.deck_table.columnCount())
            ).lower()
            if text in row_text:
                self.deck_table.setCurrentCell(i, 0)
                self._scroll_to_selected_image()
                break

    def select_first_deck_match(self):
        text = self.deck_search.text().strip().lower()
        if not text:
            return
        for i in range(self.deck_table.rowCount()):
            if not self.deck_table.isRowHidden(i):
                self.deck_table.setCurrentCell(i, 0)
                self._scroll_to_selected_image()
                break

    def set_eventual_list_label(self, length: int, numb_decks: int, total: int):
        word = "cartes trouvées" if length > 1 else "carte trouvée"
        self.label_deck_found_list.setText(
            f"CARTES ÉVENTUELLES  —  {length} {word} dans {numb_decks} decks / {total} disponibles"
        )

    def set_deck_list_label(self, length: int, mean_score: float):
        self.label_deck_list.setText(f"DECK  —  {length} cartes  ·  score moyen {mean_score:.2f}")

    def set_strategy_info(self, description: str):
        self.strategy_info.setText(description)

    def set_search_btn_loading(self, loading: bool, text_normal: str, text_loading: str):
        self.search_commander_btn.setEnabled(not loading)
        self.search_commander_btn.setText(text_loading if loading else f"🔍  {text_normal}")

    def set_build_btn_loading(self, loading: bool, text_normal: str, text_loading: str):
        self.build_btn.setEnabled(not loading)
        self.build_btn.setText(text_loading if loading else f"⚙  {text_normal}")

    def clear_deck_images(self):
        while self.deck_images_grid.count():
            item = self.deck_images_grid.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

    def _get_source_index_from_row(self, table: QTableWidget, row: int) -> Optional[int]:
        if row < 0:
            return None
        item = table.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _get_deck_card_by_row(self, row: int) -> Optional[Dict]:
        source_idx = self._get_source_index_from_row(self.deck_table, row)
        source_cards = self._original_deck_cards or self.cards_data
        if source_idx is None or source_idx < 0 or source_idx >= len(source_cards):
            return None
        return source_cards[source_idx]

    def _get_eventual_card_by_row(self, row: int) -> Optional[Dict]:
        source_idx = self._get_source_index_from_row(self.deck_found_table, row)
        if source_idx is None or source_idx < 0 or source_idx >= len(self.filtered_eventual_cards):
            return None
        return self.filtered_eventual_cards[source_idx]

    def _reflow_visible_deck_images(self, visible_source_indices: List[int]):
        while self.deck_images_grid.count():
            self.deck_images_grid.takeAt(0)

        for widget in self.card_index_to_widget.values():
            widget.setVisible(False)

        col_count = getattr(self, "_deck_images_col_count", 4)
        for pos, source_idx in enumerate(visible_source_indices):
            widget = self.card_index_to_widget.get(source_idx)
            if not widget:
                continue
            widget.setVisible(True)
            r, c_col = divmod(pos, col_count)
            self.deck_images_grid.addWidget(widget, r, c_col)

    def show_deck_images(self, cards_data, external_provider):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Afficher les images",
            "Voulez-vous afficher les images du deck ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self._external_provider = external_provider
        self.clear_deck_images()
        self.card_index_to_widget = {}
        self.card_index_to_pixmap = {}
        col_count = 4
        self._deck_images_col_count = col_count
        total = len(cards_data)
        for idx, card in enumerate(cards_data):
            card.setdefault("_source_index", idx)
        self.cards_data = list(cards_data)
        self.roles_available = {str(c.get("role", "")).strip() for c in cards_data if c.get("role")}
        self.update_role_filter_options()

        progress = QProgressDialog("Chargement des images…", "Annuler", 0, total, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        # Récupérer le scryfall_sync pour les URLs depuis le bulk data (pas d'appel API)
        scryfall_sync = getattr(self, '_scryfall_sync', None)
        if not scryfall_sync:
            # Fallback: récupérer depuis le parent
            from gui.main_window import MainWindow
            parent = self.parent()
            while parent and not isinstance(parent, MainWindow):
                parent = parent.parent()
            if parent:
                scryfall_sync = getattr(parent, 'scryfall_sync', None)

        image_url_cache: Dict[str, Optional[str]] = {}
        image_url_cache_lock = Lock()
        scryfall_api_lock = Lock()
        last_scryfall_api_call = [0.0]

        def _is_uuid_like(identifier: str) -> bool:
            value = str(identifier or "").strip().lower()
            return len(value) in (32, 36) and all(c in "0123456789abcdef-" for c in value)

        def _get_exact_print_image_url(card: Dict) -> Optional[str]:
            if not external_provider:
                return None

            set_code = str(card.get("set_code") or "").strip()
            set_name = str(card.get("set_name") or "").strip()
            collector_number = str(card.get("collector_number") or "").strip()
            if not collector_number:
                return None

            with scryfall_api_lock:
                elapsed = time.time() - last_scryfall_api_call[0]
                if elapsed < 0.12:
                    time.sleep(0.12 - elapsed)

                url = external_provider.get_image_url_for_exact_print(
                    set_code,
                    collector_number,
                    set_name=set_name,
                )
                last_scryfall_api_call[0] = time.time()
                return url

        def _resolve_image_url(card: Dict) -> Optional[str]:
            card_name = str(card.get("name") or "").strip()
            scryfall_id = str(card.get("scryfall_id") or "").strip()
            set_code = str(card.get("set_code") or "").strip().lower()
            collector_number = str(card.get("collector_number") or "").strip().lower()
            base_url = str(card.get("image_url") or "").strip()

            cache_key = f"{card_name}|{scryfall_id}|{set_code}|{collector_number}|{base_url}"
            with image_url_cache_lock:
                if cache_key in image_url_cache:
                    return image_url_cache[cache_key]

            url = base_url or None
            has_exact_print = bool(set_code and collector_number)
            has_precise_scryfall_id = _is_uuid_like(scryfall_id)

            # Cas fiable: l'identifiant Scryfall pointe déjà vers un printing exact.
            if has_precise_scryfall_id:
                if not url and scryfall_sync:
                    url = scryfall_sync.get_image_url(scryfall_id=scryfall_id, card_name=card_name)
                if not url and external_provider:
                    try:
                        url = external_provider.get_image_url_from_scryfall(scryfall_id)
                    except Exception:
                        url = None
            else:
                # Cas ambigu (ex: fallback CardNexus): on ne consulte l'API que si
                # on a set + collector_number pour vérifier/corriger l'impression.
                if has_exact_print:
                    try:
                        exact_url = _get_exact_print_image_url(card)
                    except Exception:
                        exact_url = None

                    if exact_url and (not url or url != exact_url):
                        url = exact_url

                if not url and scryfall_sync:
                    url = scryfall_sync.get_image_url(card_name=card_name)

            with image_url_cache_lock:
                image_url_cache[cache_key] = url
            return url

        def fetch_image(idx_card):
            """Télécharge une image en limitant les appels API Scryfall aux cas nécessaires."""
            idx, card = idx_card
            try:
                url = _resolve_image_url(card)
                if not url:
                    return idx, card, None

                card["image_url"] = url

                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                return idx, card, resp.content
            except Exception:
                return idx, card, None

        # Chargement parallèle des images (HTTP vers scryfall.io)
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(fetch_image, (i, c)): i for i, c in enumerate(cards_data)}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                progress.setValue(completed)
                QApplication.processEvents()
                if progress.wasCanceled():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                results.append(future.result())

        # Trier par index original pour garder l'ordre
        results.sort(key=lambda x: x[0])

        # Créer les widgets dans le thread principal
        for idx, card, img_data in results:
            if img_data is None:
                continue
            pix = QPixmap()
            pix.loadFromData(img_data)
            if pix.isNull():
                continue

            label = QLabel()
            label.setPixmap(pix.scaledToWidth(200, Qt.SmoothTransformation))
            label.setToolTip(card.get("name", ""))
            label.setCursor(Qt.PointingHandCursor)
            label.mouseDoubleClickEvent = lambda e, c=card: open_card_image_dialog(self, c, external_provider)
            r, c_col = divmod(idx, col_count)
            self.deck_images_grid.addWidget(label, r, c_col)
            self.card_index_to_widget[idx] = label
            self.card_index_to_pixmap[idx] = pix

        progress.setValue(total)
        self.apply_role_filter(self.deck_filter_role.currentText())

    def apply_mana_filter(self, clicked_cmc: int):
        if self._cmc_filter == clicked_cmc:
            self.reset_mana_filter()
            return
        self._cmc_filter = clicked_cmc
        filtered = [
            c for c in self._original_deck_cards
            if min(int(c.get("cmc", 0) or 0), 7) == clicked_cmc
        ]
        self.deck_cards_data = filtered
        self.cards_data = filtered
        self.filtered_deck_cards = filtered
        self._populate_deck_table(filtered)
        self.update_role_filter_options()
        self._apply_filters()
        self.stats_panel.show_mana_filter(clicked_cmc)

    def reset_mana_filter(self):
        if not self._original_deck_cards:
            return
        self._cmc_filter = None
        self.deck_cards_data = self._original_deck_cards.copy()
        self.cards_data = self.deck_cards_data
        self.filtered_deck_cards = self.deck_cards_data
        self._populate_deck_table(self.deck_cards_data)
        self.update_role_filter_options()
        self._apply_filters()
        self.stats_panel.show_mana_filter(None)

    def get_commander_name(self) -> str:
        return self.commander_input.currentText()

    def get_strategy_name(self) -> str:
        return self.strategy_combo.currentText()

    def is_budget_mode(self) -> bool:
        return self.budget_checkbox.isChecked()

    def set_recommendations_text(self, text: str):
        self.recommendations_text.setText(text)

    def set_recommendations_visible(self, visible: bool):
        self.btn_show_recommendations.setVisible(visible)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers visuels tableau
# ─────────────────────────────────────────────────────────────────────────────

_COLOR_SYMBOLS = {"W": "☀", "U": "💧", "B": "💀", "R": "🔥", "G": "🌲"}
_COLOR_HEX = {
    "W": "#f0f0e0",
    "U": "#5ba4cf",
    "B": "#a0a0b0",
    "R": "#e06030",
    "G": "#4caf50",
}
_RARITY_HEX = {
    "Common": "#8b949e",
    "Uncommon": "#79c0ff",
    "Rare": "#d29922",
    "Mythic": "#e06030",
    "Special": "#bc8cff",
}
_ROLE_HEX = {
    "ramp": "#4caf50",
    "draw": "#5ba4cf",
    "removal": "#e06030",
    "boardwipe": "#da3633",
    "finisher": "#bc8cff",
    "land": "#8b6914",
    "utility": "#8b949e",
}
_CATEGORY_HEX = {
    "Ramp": "#4caf50",
    "Card Draw": "#5ba4cf",
    "Removal": "#e06030",
    "Board Wipe": "#da3633",
    "Finisher": "#bc8cff",
    "Land": "#8b6914",
    "Utility": "#8b949e",
    "Commander": "#d29922",
}


def _fmt_colors(tokens: list) -> str:
    if not tokens:
        return "—"
    return " ".join(_COLOR_SYMBOLS.get(t.upper(), t) for t in tokens)


def _color_fg(tokens: list) -> str:
    if not tokens:
        return "#8b949e"
    if len(tokens) == 1:
        return _COLOR_HEX.get(tokens[0].upper(), "#c9d1d9")
    return "#c9d1d9"


def _rarity_color(rarity: str) -> str:
    return _RARITY_HEX.get(rarity, "#8b949e")


def _role_color(role: str) -> str:
    return _ROLE_HEX.get(role.lower().strip(), "#c9d1d9")


def _category_color(category: str) -> str:
    return _CATEGORY_HEX.get(category.strip(), "#c9d1d9")


def _normalize_role_label(role: str) -> str:
    value = str(role or "").strip()
    if not value or value == "—":
        return "Other"

    normalized = value.lower().replace(" ", "").replace("-", "")
    aliases = {
        "ramp": "Ramp",
        "draw": "Draw",
        "carddraw": "Draw",
        "removal": "Removal",
        "interaction": "Removal",
        "boardwipe": "Boardwipe",
        "wipe": "Boardwipe",
        "finisher": "Finisher",
        "wincon": "Finisher",
        "wincondition": "Finisher",
        "land": "Land",
        "other": "Other",
    }
    return aliases.get(normalized, value.title())


def _extract_color_codes(raw_colors) -> list[str]:
    if isinstance(raw_colors, list):
        tokens = raw_colors
    else:
        text = str(raw_colors or "").replace("[", "").replace("]", "").replace("'", "")
        tokens = [part.strip() for part in text.split(",") if part.strip()]

    normalized = []
    for token in tokens:
        token_upper = str(token).strip().upper()
        if token_upper == "COLORLESS":
            token_upper = "C"
        if token_upper in {"W", "U", "B", "R", "G", "C"} and token_upper not in normalized:
            normalized.append(token_upper)
    return normalized
