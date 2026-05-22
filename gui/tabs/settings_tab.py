"""Onglet Paramètres — groupes visuels, sync Scryfall, à propos."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QProgressBar,
    QGroupBox, QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, Signal
from mtg.constants import VERSION, CONTACT, YOUTUBE_URL


class SettingsTab(QWidget):
    """Onglet Paramètres + À propos."""

    sync_requested = Signal()
    language_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        # Layout racine sur self (unique)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll area pour tout le contenu
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        root_layout.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # ── Langue & Interface ────────────────────────────────────────────────
        grp_lang = QGroupBox("Interface")
        lang_form = QFormLayout(grp_lang)
        lang_form.setSpacing(12)
        lang_form.setLabelAlignment(Qt.AlignRight)

        self.language_label = QLabel("Langue:")
        self.language_select = QComboBox()
        self.language_select.addItems(["Français", "English"])
        self.language_select.setFixedWidth(160)
        self.language_select.currentTextChanged.connect(self._on_language_changed)
        lang_form.addRow(self.language_label, self.language_select)

        self.export_format_label = QLabel("Format d'export:")
        self.export_format = QComboBox()
        self.export_format.addItems(["TXT", "CSV", "Archidekt"])
        self.export_format.setFixedWidth(160)
        lang_form.addRow(self.export_format_label, self.export_format)

        layout.addWidget(grp_lang)

        # ── Recherche Archidekt ────────────────────────────────────────────────
        grp_archidekt = QGroupBox("Recherche Archidekt")
        arch_form = QFormLayout(grp_archidekt)
        arch_form.setSpacing(12)
        arch_form.setLabelAlignment(Qt.AlignRight)

        self.numb_deck_search_label = QLabel("Nombre de decks:")
        self.numb_deck_search = QComboBox()
        self.numb_deck_search.addItems(["Low", "Medium", "High"])
        self.numb_deck_search.setFixedWidth(160)
        arch_form.addRow(self.numb_deck_search_label, self.numb_deck_search)

        self.order_by_label = QLabel("Trier par:")
        self.order_by = QComboBox()
        self.order_by.addItems(["Vues", "Mise à jour"])
        self.order_by.setFixedWidth(160)
        arch_form.addRow(self.order_by_label, self.order_by)

        layout.addWidget(grp_archidekt)

        # ── Composition du deck ────────────────────────────────────────────────
        grp_deck = QGroupBox("Composition du Deck")
        deck_form = QFormLayout(grp_deck)
        deck_form.setSpacing(12)
        deck_form.setLabelAlignment(Qt.AlignRight)

        def make_spin(min_v, max_v, default):
            s = QSpinBox()
            s.setRange(min_v, max_v)
            s.setValue(default)
            s.setFixedWidth(80)
            return s

        self.numb_min_land_label = QLabel("Terrains minimum:")
        self.numb_min_land = make_spin(10, 50, 36)
        deck_form.addRow(self.numb_min_land_label, self.numb_min_land)

        self.numb_max_land_label = QLabel("Terrains maximum:")
        self.numb_max_land = make_spin(10, 50, 38)
        deck_form.addRow(self.numb_max_land_label, self.numb_max_land)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #21262d;")
        deck_form.addRow(sep)

        self.numb_ramp_label = QLabel("Ramp:")
        self.numb_ramp = make_spin(1, 30, 12)
        deck_form.addRow(self.numb_ramp_label, self.numb_ramp)

        self.numb_draw_label = QLabel("Draw:")
        self.numb_draw = make_spin(1, 30, 10)
        deck_form.addRow(self.numb_draw_label, self.numb_draw)

        self.numb_removal_label = QLabel("Removal:")
        self.numb_removal = make_spin(1, 20, 8)
        deck_form.addRow(self.numb_removal_label, self.numb_removal)

        self.numb_wincondition_label = QLabel("Win conditions:")
        self.numb_wincondition = make_spin(1, 20, 6)
        deck_form.addRow(self.numb_wincondition_label, self.numb_wincondition)

        layout.addWidget(grp_deck)

        # ── Synchronisation Scryfall ───────────────────────────────────────────
        grp_scryfall = QGroupBox("Données Scryfall")
        sc_layout = QVBoxLayout(grp_scryfall)
        sc_layout.setSpacing(10)

        self.sync_status_label = QLabel("Statut : Non synchronisé")
        self.sync_status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        sc_layout.addWidget(self.sync_status_label)

        self.sync_progress_bar = QProgressBar()
        self.sync_progress_bar.setRange(0, 100)
        self.sync_progress_bar.setValue(0)
        self.sync_progress_bar.setTextVisible(False)
        self.sync_progress_bar.setFixedHeight(6)
        self.sync_progress_bar.setVisible(False)
        sc_layout.addWidget(self.sync_progress_bar)

        self.sync_download_info = QLabel("")
        self.sync_download_info.setStyleSheet("color: #388bfd; font-size: 11px;")
        self.sync_download_info.setVisible(False)
        sc_layout.addWidget(self.sync_download_info)

        self.sync_scryfall_btn = QPushButton("☁  Synchroniser les données Scryfall")
        self.sync_scryfall_btn.setObjectName("accent")
        self.sync_scryfall_btn.setMinimumHeight(36)
        self.sync_scryfall_btn.clicked.connect(self.sync_requested)
        sc_layout.addWidget(self.sync_scryfall_btn)

        layout.addWidget(grp_scryfall)

        # ── À propos ───────────────────────────────────────────────────────────
        grp_about = QGroupBox("À propos")
        ab_layout = QVBoxLayout(grp_about)
        ab_layout.setSpacing(6)

        self.about_title_label = QLabel("Créé par : ManaLab")
        self.about_title_label.setStyleSheet("font-weight: 600; color: #c9d1d9;")
        self.about_subtitle_label = QLabel(f"Version : {VERSION}")
        self.about_subtitle_label.setStyleSheet("color: #8b949e;")
        self.about_contact_label = QLabel(f"Contact : {CONTACT}")
        self.about_contact_label.setStyleSheet("color: #8b949e;")
        self.about_youtube_label = QLabel(
            f'<a href="{YOUTUBE_URL}" style="color: #58a6ff; text-decoration: none;">Chaîne YouTube : ManaLab-FR</a>'
        )
        self.about_youtube_label.setOpenExternalLinks(True)
        self.about_youtube_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.about_youtube_label.setStyleSheet("color: #58a6ff;")

        for lbl in (self.about_title_label, self.about_subtitle_label, self.about_contact_label, self.about_youtube_label):
            ab_layout.addWidget(lbl)

        layout.addWidget(grp_about)
        layout.addStretch()

        scroll.setWidget(content)

    def _on_language_changed(self, text: str):
        code = "en" if "English" in text else "fr"
        self.language_changed.emit(code)

    # ─────────────────────────────────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────────────────────────────────

    def get_language_code(self) -> str:
        return "en" if "English" in self.language_select.currentText() else "fr"

    def set_sync_status(self, has_data: bool, size_mb: str = "", last_update: str = ""):
        if has_data:
            self.sync_status_label.setText(
                f"✓  Synchronisé  ·  {size_mb} MB  ·  Mis à jour le {last_update[:10]}"
            )
            self.sync_status_label.setStyleSheet("color: #3fb950; font-size: 12px;")
        else:
            self.sync_status_label.setText("✗  Non synchronisé")
            self.sync_status_label.setStyleSheet("color: #8b949e; font-size: 12px;")

    def set_sync_loading(self, loading: bool):
        self.sync_scryfall_btn.setEnabled(not loading)
        self.sync_scryfall_btn.setText(
            "Synchronisation en cours…" if loading else "☁  Synchroniser les données Scryfall"
        )
        self.sync_progress_bar.setVisible(loading)
        self.sync_download_info.setVisible(loading)

    def update_sync_progress(self, percent: int, info_text: str):
        if percent >= 0:
            self.sync_progress_bar.setRange(0, 100)
            self.sync_progress_bar.setValue(percent)
        else:
            self.sync_progress_bar.setRange(0, 0)
        self.sync_download_info.setText(info_text)

    def apply_translations(self, t: dict, lang: str):
        self.language_label.setText(t.get("language_label", "Langue:"))
        self.export_format_label.setText(t.get("export_format_label", "Format d'export:"))
        self.numb_deck_search_label.setText(t.get("numb_deck_search_label", "Nombre de decks:"))
        self.order_by_label.setText(t.get("order_by_label", "Trier par:"))
        self.numb_min_land_label.setText(t.get("numb_min_land_label", "Terrains min:"))
        self.numb_max_land_label.setText(t.get("numb_max_land_label", "Terrains max:"))
        self.numb_ramp_label.setText(t.get("numb_ramp_label", "Ramp:"))
        self.numb_draw_label.setText(t.get("numb_draw_label", "Draw:"))
        self.numb_removal_label.setText(t.get("numb_removal_label", "Removal:"))
        self.numb_wincondition_label.setText(t.get("numb_wincondition_label", "Win conditions:"))

        self.about_title_label.setText(t.get("about_title", "Créé par : ManaLab"))
        self.about_subtitle_label.setText(t.get("about_subtitle", f"Version : {VERSION}"))
        self.about_contact_label.setText(t.get("about_contact", f"Contact : {CONTACT}"))
        youtube_prefix = t.get("about_youtube", "Chaîne YouTube :")
        self.about_youtube_label.setText(
            f'<a href="{YOUTUBE_URL}" style="color: #58a6ff; text-decoration: none;">{youtube_prefix} ManaLab-FR</a>'
        )

        # Export format items
        self.export_format.blockSignals(True)
        current = self.export_format.currentText()
        self.export_format.clear()
        self.export_format.addItems(t.get("export_format_items", ["TXT", "CSV", "Archidekt"]))
        idx = self.export_format.findText(current)
        self.export_format.setCurrentIndex(idx if idx != -1 else 0)
        self.export_format.blockSignals(False)

        # Deck search items
        self.numb_deck_search.blockSignals(True)
        current_s = self.numb_deck_search.currentText()
        self.numb_deck_search.clear()
        self.numb_deck_search.addItems(t.get("numb_deck_search_items", ["Low", "Medium", "High"]))
        idx_s = self.numb_deck_search.findText(current_s)
        self.numb_deck_search.setCurrentIndex(idx_s if idx_s != -1 else 0)
        self.numb_deck_search.blockSignals(False)

        # Order by items
        self.order_by.blockSignals(True)
        current_o = self.order_by.currentText()
        self.order_by.clear()
        self.order_by.addItems(t.get("order_by_items", ["Vues", "Mise à jour"]))
        idx_o = self.order_by.findText(current_o)
        self.order_by.setCurrentIndex(idx_o if idx_o != -1 else 0)
        self.order_by.blockSignals(False)

        # Language selector
        self.language_select.blockSignals(True)
        self.language_select.clear()
        self.language_select.addItems([t.get("lang_fr", "Français"), t.get("lang_en", "English")])
        self.language_select.setCurrentIndex(1 if lang == "en" else 0)
        self.language_select.blockSignals(False)
