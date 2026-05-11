"""Onglet Collection — toolbar moderne, filtres inline, tableau full-width."""

from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QSizePolicy, QFrame, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from gui.widgets.card_image import open_card_image_dialog
from gui.widgets.stats_panel import SectionTitle


class CollectionTab(QWidget):
    """Onglet de gestion de la collection."""

    import_requested = Signal()
    export_requested = Signal()
    delete_requested = Signal()
    filters_reset = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collection_cards: List[Dict] = []
        self.filtered_collection_cards: List[Dict] = []
        self._external_provider = None
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(56)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)
        tb_layout.setSpacing(8)

        self.import_btn = QPushButton("⬆  Importer")
        self.import_btn.setObjectName("accent")
        self.import_btn.setMinimumHeight(36)
        self.import_btn.clicked.connect(self.import_requested)
        tb_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("⬇  Exporter")
        self.export_btn.setMinimumHeight(36)
        self.export_btn.clicked.connect(self.export_requested)
        tb_layout.addWidget(self.export_btn)

        self.delete_btn = QPushButton("🗑  Supprimer")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setMinimumHeight(36)
        self.delete_btn.clicked.connect(self.delete_requested)
        tb_layout.addWidget(self.delete_btn)

        # Séparateur vertical
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #21262d;")
        sep.setFixedWidth(1)
        tb_layout.addWidget(sep)

        # Barre de recherche
        self.collection_search = QLineEdit()
        self.collection_search.setPlaceholderText("🔍  Rechercher par nom, set ou numéro…")
        self.collection_search.setMinimumHeight(36)
        self.collection_search.setMinimumWidth(240)
        self.collection_search.textChanged.connect(self.refresh_collection_list)
        tb_layout.addWidget(self.collection_search)

        # Filtre couleur
        self.collection_color_filter = QComboBox()
        self.collection_color_filter.addItem("Toutes les couleurs")
        self.collection_color_filter.setMinimumHeight(36)
        self.collection_color_filter.setFixedWidth(150)
        self.collection_color_filter.currentTextChanged.connect(self.refresh_collection_list)
        tb_layout.addWidget(self.collection_color_filter)

        # Filtre type
        self.collection_type_filter = QComboBox()
        self.collection_type_filter.addItem("Tous les types")
        self.collection_type_filter.setMinimumHeight(36)
        self.collection_type_filter.setFixedWidth(150)
        self.collection_type_filter.currentTextChanged.connect(self.refresh_collection_list)
        tb_layout.addWidget(self.collection_type_filter)

        self.clear_filters_btn = QPushButton("✕  Réinitialiser")
        self.clear_filters_btn.setMinimumHeight(36)
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        tb_layout.addWidget(self.clear_filters_btn)

        tb_layout.addStretch()

        root.addWidget(toolbar)

        # ── Résumé ────────────────────────────────────────────────────────────
        summary_bar = QWidget()
        summary_bar.setFixedHeight(32)
        sb_layout = QHBoxLayout(summary_bar)
        sb_layout.setContentsMargins(16, 4, 16, 4)

        self.collection_summary = QLabel("")
        self.collection_summary.setStyleSheet("color: #8b949e; font-size: 12px;")
        sb_layout.addWidget(self.collection_summary)
        sb_layout.addStretch()

        root.addWidget(summary_bar)

        # ── Tableau ───────────────────────────────────────────────────────────
        self.collection_table = QTableWidget()
        self.collection_table.setColumnCount(7)
        self.collection_table.setHorizontalHeaderLabels([
            "Nom", "Couleurs", "Types", "Qté", "Set", "Numéro", "Rareté",
        ])
        header = self.collection_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.collection_table.setAlternatingRowColors(True)
        self.collection_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.collection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.collection_table.verticalHeader().setVisible(False)
        self.collection_table.setShowGrid(False)
        self.collection_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.collection_table.customContextMenuRequested.connect(self._show_context_menu)
        self.collection_table.setSortingEnabled(True)
        self.collection_table.setWordWrap(False)
        self.collection_table.verticalHeader().setDefaultSectionSize(30)

        root.addWidget(self.collection_table)

    # ─────────────────────────────────────────────────────────────────────────
    # Données
    # ─────────────────────────────────────────────────────────────────────────

    def set_collection_cards(self, cards: List[Dict], external_provider=None):
        self.collection_cards = cards or []
        if external_provider:
            self._external_provider = external_provider
        self._update_filters()
        self.refresh_collection_list()

    def _update_filters(self):
        colors, types = set(), set()
        for card in self.collection_cards:
            colors_raw = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            for part in colors_raw.split(","):
                v = part.strip()
                if v:
                    colors.add(v)
            main_type = (card.get("types") or "").split(" — ")[0].strip()
            if main_type:
                types.add(main_type)

        for combo, items, default in (
            (self.collection_color_filter, sorted(colors), "Toutes les couleurs"),
            (self.collection_type_filter, sorted(types), "Tous les types"),
        ):
            combo.blockSignals(True)
            current = combo.currentText()
            combo.clear()
            combo.addItem(default)
            for item in items:
                combo.addItem(item)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx != -1 else 0)
            combo.blockSignals(False)

    def refresh_collection_list(self):
        query = self.collection_search.text().strip().lower()
        color_f = self.collection_color_filter.currentText()
        type_f = self.collection_type_filter.currentText()
        color_default = self.collection_color_filter.itemText(0)
        type_default = self.collection_type_filter.itemText(0)

        filtered: List[Dict] = []
        total_qty = 0

        for card in self.collection_cards:
            name = card.get("name", "")
            set_name = card.get("set_name", "")
            collector_number = str(card.get("collector_number", ""))
            colors_raw = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            types_field = card.get("types", "") or ""

            if query:
                if query not in " ".join([name, set_name, collector_number]).lower():
                    continue
            if color_f != color_default:
                tokens = {c.strip() for c in colors_raw.split(",") if c.strip()}
                if color_f not in tokens:
                    continue
            if type_f != type_default:
                if type_f.lower() not in types_field.lower():
                    continue

            filtered.append(card)
            total_qty += int(card.get("quantity", 0) or 0)

        self.filtered_collection_cards = filtered
        self.collection_table.setRowCount(len(filtered))

        self.collection_table.setSortingEnabled(False)
        for row, card in enumerate(filtered):
            colors_raw = str(card.get("colors", "")).replace("[", "").replace("]", "").replace("'", "")
            color_tokens = [c.strip() for c in colors_raw.split(",") if c.strip()]
            is_foil = bool(card.get("foil"))
            qty = int(card.get("quantity", 0) or 0)
            rarity = (card.get("rarity") or "").capitalize()

            name_text = ("✨ " if is_foil else "") + card.get("name", "")

            col0 = QTableWidgetItem(name_text)
            if is_foil:
                col0.setForeground(QBrush(QColor("#d29922")))
            self.collection_table.setItem(row, 0, col0)

            col1 = QTableWidgetItem(_format_color_symbols(color_tokens))
            col1.setTextAlignment(Qt.AlignCenter)
            col1.setForeground(QBrush(QColor(_color_label_color(color_tokens))))
            col1.setData(Qt.UserRole, colors_raw)
            self.collection_table.setItem(row, 1, col1)

            col2 = QTableWidgetItem(card.get("types", "") or "—")
            col2.setForeground(QBrush(QColor("#8b949e")))
            self.collection_table.setItem(row, 2, col2)

            col3 = QTableWidgetItem(str(qty))
            col3.setTextAlignment(Qt.AlignCenter)
            col3.setData(Qt.UserRole, qty)
            if qty >= 4:
                col3.setForeground(QBrush(QColor("#3fb950")))
            elif qty >= 2:
                col3.setForeground(QBrush(QColor("#79c0ff")))
            else:
                col3.setForeground(QBrush(QColor("#8b949e")))
            self.collection_table.setItem(row, 3, col3)

            col4 = QTableWidgetItem(card.get("set_name", ""))
            self.collection_table.setItem(row, 4, col4)

            col5 = QTableWidgetItem(str(card.get("collector_number", "")))
            col5.setTextAlignment(Qt.AlignCenter)
            col5.setForeground(QBrush(QColor("#8b949e")))
            self.collection_table.setItem(row, 5, col5)

            col6 = QTableWidgetItem(rarity)
            col6.setTextAlignment(Qt.AlignCenter)
            col6.setForeground(QBrush(QColor(_rarity_color(rarity))))
            self.collection_table.setItem(row, 6, col6)

        self.collection_table.setSortingEnabled(True)

        n_unique_names = len({c.get("name", "") for c in self.collection_cards})
        n_printings = len(self.collection_cards)
        shown = len(filtered)
        self.collection_summary.setText(
            f"{shown} impressions affichées  ·  {n_unique_names} noms distincts  ·  {total_qty} exemplaires au total"
        )

    def _clear_filters(self):
        self.collection_search.clear()
        self.collection_color_filter.setCurrentIndex(0)
        self.collection_type_filter.setCurrentIndex(0)
        self.refresh_collection_list()
        self.filters_reset.emit()

    # ─────────────────────────────────────────────────────────────────────────
    # Interactions
    # ─────────────────────────────────────────────────────────────────────────

    def _show_context_menu(self, pos):
        row = self.collection_table.rowAt(pos.y())
        if row < 0 or row >= len(self.filtered_collection_cards):
            return
        menu = QMenu(self)
        action_img = menu.addAction("🖼  Voir l'image de la carte")
        action = menu.exec_(self.collection_table.mapToGlobal(pos))
        if action == action_img:
            open_card_image_dialog(self, self.filtered_collection_cards[row], self._external_provider)

    # ─────────────────────────────────────────────────────────────────────────
    # i18n
    # ─────────────────────────────────────────────────────────────────────────

    def apply_translations(self, t: dict):
        self.import_btn.setText(f"⬆  {t.get('btn_import', 'Importer')}")
        self.export_btn.setText(f"⬇  {t.get('btn_export', 'Exporter')}")
        self.delete_btn.setText(f"🗑  {t.get('btn_delete', 'Supprimer')}")
        self.clear_filters_btn.setText(f"✕  {t.get('btn_reset_filters', 'Réinitialiser')}")
        self.collection_search.setPlaceholderText(
            f"🔍  {t.get('collection_search_placeholder', 'Rechercher…')}"
        )
        self._update_filters()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers couleurs
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


def _format_color_symbols(tokens: list) -> str:
    if not tokens:
        return "—"
    parts = [_COLOR_SYMBOLS.get(t.upper(), t) for t in tokens]
    return " ".join(parts)


def _color_label_color(tokens: list) -> str:
    if not tokens:
        return "#8b949e"
    if len(tokens) == 1:
        return _COLOR_HEX.get(tokens[0].upper(), "#c9d1d9")
    return "#c9d1d9"


def _rarity_color(rarity: str) -> str:
    return _RARITY_HEX.get(rarity, "#8b949e")
