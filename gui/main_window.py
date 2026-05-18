"""Fenêtre principale — orchestrateur léger, délègue aux sous-onglets."""

import threading
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QApplication, QInputDialog, QMainWindow, QVBoxLayout, QWidget,
    QFileDialog, QMessageBox, QTabWidget, QDialog,
    QLabel, QPushButton,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QPainter, QIcon, QKeySequence as QKS

import requests

from mtg.constants import VERSION, CONTACT
from mtg.deck_strategies import DeckStrategy, StrategyManager, STRATEGY_PROFILES
from mtg.scryfall_sync import ScryfallSyncManager
from mtg.edhrec_analytics import EDHRecAnalytics

from gui.styles.theme import DARK_THEME
from gui.tabs.build_tab import BuildTab
from gui.tabs.collection_tab import CollectionTab
from gui.tabs.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    """Fenêtre principale — orchestrateur léger."""

    _sync_progress = Signal(int, int, int, float, str)
    _sync_finished = Signal(bool)
    _sync_error = Signal(str)
    _commander_info_ready = Signal(str, str)

    TRANSLATIONS = {
        "fr": {
            "window_title": "MTG Commander Deck Builder",
            "tab_build": "Construction",
            "tab_collection": "Ma Collection",
            "tab_settings": "Paramètres",
            "btn_search_commander": "Rechercher les decks",
            "btn_search_loading": "Chargement...",
            "btn_build": "Construire le deck",
            "btn_build_loading": "Génération...",
            "label_deck_found": "CARTES ÉVENTUELLES",
            "btn_export_eventual": "Exporter les cartes éventuelles",
            "btn_load_exclusion": "Charger un fichier d'exclusion",
            "label_deck": "DECK",
            "btn_export_deck": "Exporter le deck",
            "deck_search_placeholder": "Rechercher dans le deck…",
            "role_all": "Toutes",
            "stats_curve": "Courbe de mana",
            "stats_title": "Statistiques",
            "btn_import": "Importer",
            "btn_export": "Exporter",
            "btn_delete": "Supprimer",
            "btn_reset_filters": "Réinitialiser",
            "collection_search_placeholder": "Rechercher par nom, set ou numéro...",
            "language_label": "Langue:",
            "lang_fr": "Français",
            "lang_en": "English",
            "export_format_label": "Format d'export:",
            "export_format_items": ["TXT", "CSV", "Archidekt"],
            "numb_deck_search_label": "Nombre de decks:",
            "numb_deck_search_items": ["Faible", "Moyen", "Élevé"],
            "order_by_label": "Trier par:",
            "order_by_items": ["Vues", "Mise à jour"],
            "numb_min_land_label": "Terrains minimum:",
            "numb_max_land_label": "Terrains maximum:",
            "numb_ramp_label": "Ramp:",
            "numb_draw_label": "Draw:",
            "numb_removal_label": "Removal:",
            "numb_boardwipe_label": "Boardwipe:",
            "numb_wincondition_label": "Win conditions:",
            "about_title": "Créé par : ManaLab",
            "about_subtitle": f"Version : {VERSION}",
            "about_contact": f"Contact : {CONTACT}",
            "about_youtube": "Chaîne YouTube :",
        },
        "en": {
            "window_title": "MTG Commander Deck Builder",
            "tab_build": "Build",
            "tab_collection": "My Collection",
            "tab_settings": "Settings",
            "btn_search_commander": "Search decks",
            "btn_search_loading": "Loading...",
            "btn_build": "Build deck",
            "btn_build_loading": "Building...",
            "label_deck_found": "CANDIDATE CARDS",
            "btn_export_eventual": "Export candidate list",
            "btn_load_exclusion": "Load exclusion file",
            "label_deck": "DECK",
            "btn_export_deck": "Export deck",
            "deck_search_placeholder": "Search in deck…",
            "role_all": "All",
            "stats_curve": "Mana curve",
            "stats_title": "Statistics",
            "btn_import": "Import",
            "btn_export": "Export",
            "btn_delete": "Delete",
            "btn_reset_filters": "Reset",
            "collection_search_placeholder": "Search by name, set or number...",
            "language_label": "Language:",
            "lang_fr": "French",
            "lang_en": "English",
            "export_format_label": "Export format:",
            "export_format_items": ["TXT", "CSV", "Archidekt"],
            "numb_deck_search_label": "Number of decks:",
            "numb_deck_search_items": ["Low", "Medium", "High"],
            "order_by_label": "Sort by:",
            "order_by_items": ["Views", "Updated"],
            "numb_min_land_label": "Min lands:",
            "numb_max_land_label": "Max lands:",
            "numb_ramp_label": "Ramp:",
            "numb_draw_label": "Draw:",
            "numb_removal_label": "Removal:",
            "numb_boardwipe_label": "Boardwipe:",
            "numb_wincondition_label": "Win conditions:",
            "about_title": "Created by: ManaLab",
            "about_subtitle": f"Version : {VERSION}",
            "about_contact": f"Contact: {CONTACT}",
            "about_youtube": "YouTube channel:",
        },
    }

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.language = "fr"

        self.setWindowTitle(f"MTG Commander Deck Builder - Version {VERSION}")
        icon_path = Path(__file__).parent / "resource" / "icons8-boule-de-cristal-magique-100.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(1400, 800)
        self.resize(1980, 1200)

        # Services partagés
        self.scryfall_sync = ScryfallSyncManager()
        self.strategy_manager = StrategyManager(scryfall_sync=self.scryfall_sync)
        self.edhrec_analytics = EDHRecAnalytics()

        # Debounce commandant
        self._commander_info_timer = QTimer(self)
        self._commander_info_timer.setSingleShot(True)
        self._commander_info_timer.setInterval(500)
        self._commander_info_timer.timeout.connect(self._fetch_commander_info_debounced)
        self._pending_commander_name = ""
        self._commander_info_connected = False

        # Style global
        self.setStyleSheet(DARK_THEME)

        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Onglets
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # ── Onglet Construction ───────────────────────────────────────────
        candidates = self.app.collection_manager.get_commander_candidates(get_all=True)
        self.build_tab = BuildTab(
            self.app.collection_manager,
            self.strategy_manager,
            self.scryfall_sync,
        )
        self.build_tab.refresh_commander_candidates(candidates)
        self._connect_build_tab()
        self.tabs.addTab(self.build_tab, "Construction")

        # ── Onglet Collection ─────────────────────────────────────────────
        self.collection_tab = CollectionTab()
        self._connect_collection_tab()
        self.tabs.addTab(self.collection_tab, "Ma Collection")

        # ── Onglet Paramètres ─────────────────────────────────────────────
        self.settings_tab = SettingsTab()
        self._connect_settings_tab()
        self.tabs.addTab(self.settings_tab, "Paramètres")

        # Status bar
        self.statusBar().showMessage("Prêt")

        # Raccourcis
        self._setup_shortcuts()

        # Appliquer la langue par défaut
        self.apply_language(self.language)

        # Initialiser le statut Scryfall
        self._update_sync_status()

        # Aperçu commandant initial
        current_cmd = self.build_tab.get_commander_name()
        if current_cmd:
            self.update_commander_preview(current_cmd)

    # ─────────────────────────────────────────────────────────────────────
    # Connexions
    # ─────────────────────────────────────────────────────────────────────

    def _connect_build_tab(self):
        bt = self.build_tab
        bt.search_commander_requested.connect(self._on_search_commander)
        bt.build_deck_requested.connect(self._on_build_deck)
        bt.export_eventual_requested.connect(self.app.export_eventual_cards_list)
        bt.export_deck_requested.connect(self.app.export_deck_list)
        bt.load_exclusion_requested.connect(self.app.load_exclusion_list)
        bt.show_recommendations_requested.connect(self._show_recommendations_dialog)
        bt.commander_changed.connect(self.update_commander_preview)
        bt.commander_changed.connect(self._update_commander_info)
        bt.strategy_changed.connect(self._on_strategy_changed)
        bt.budget_changed.connect(self._on_budget_changed)
        bt.pauper_changed.connect(self._on_pauper_changed)
        bt.role_filter_changed.connect(bt.apply_role_filter)
        bt.deck_search_changed.connect(bt.filter_deck_list)
        bt.deck_search_enter.connect(bt.select_first_deck_match)
        bt.mana_curve_clicked.connect(self._on_mana_curve_click)
        bt.mana_curve_reset.connect(self._on_mana_curve_reset)
        bt.stats_panel.commander_image_clicked.connect(self._on_commander_image_click)

    def _connect_collection_tab(self):
        ct = self.collection_tab
        ct.import_requested.connect(self.app.import_collection)
        ct.export_requested.connect(self.app.export_collection)
        ct.delete_requested.connect(self.app.delete_collection)

    def _connect_settings_tab(self):
        st = self.settings_tab
        st.sync_requested.connect(self._on_sync_scryfall)
        st.language_changed.connect(self.app.set_language)
        self._sync_progress.connect(self._on_sync_progress)
        self._sync_finished.connect(self._on_sync_finished)
        self._sync_error.connect(self._on_sync_error)

    # ─────────────────────────────────────────────────────────────────────
    # Raccourcis clavier
    # ─────────────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        from PySide6.QtGui import QShortcut
        shortcuts = {
            "Ctrl+F": lambda: self.build_tab.deck_search.setFocus(),
            "Ctrl+1": lambda: self.tabs.setCurrentIndex(0),
            "Ctrl+2": lambda: self.tabs.setCurrentIndex(1),
            "Ctrl+3": lambda: self.tabs.setCurrentIndex(2),
            "Ctrl+R": self.build_tab.search_commander_btn.click,
            "Ctrl+B": self.build_tab.build_btn.click,
            "Ctrl+S": self.build_tab.export_deck_btn.click,
            "Ctrl+I": lambda: self.tabs.currentIndex() == 1 and self.collection_tab.import_btn.click(),
            "Escape": self._handle_escape,
            "F1": self._show_help_shortcuts,
        }
        for key, slot in shortcuts.items():
            sc = QShortcut(QKS(key), self)
            sc.activated.connect(slot)

    def _handle_escape(self):
        if self.build_tab.deck_search.hasFocus():
            self.build_tab.deck_search.clear()
        elif self.collection_tab.collection_search.hasFocus():
            self.collection_tab.collection_search.clear()
        elif self.build_tab.commander_input.hasFocus():
            self.build_tab.commander_input.clearEditText()

    def _show_help_shortcuts(self):
        help_text = """
        <h3>Raccourcis Clavier</h3>
        <table cellspacing="6">
        <tr><td><b>Ctrl+F</b></td><td>Focus recherche deck</td></tr>
        <tr><td><b>Ctrl+1/2/3</b></td><td>Changer d'onglet</td></tr>
        <tr><td><b>Ctrl+R</b></td><td>Rechercher les decks du commandant</td></tr>
        <tr><td><b>Ctrl+B</b></td><td>Construire le deck</td></tr>
        <tr><td><b>Ctrl+S</b></td><td>Exporter le deck</td></tr>
        <tr><td><b>Ctrl+I</b></td><td>Importer une collection</td></tr>
        <tr><td><b>Escape</b></td><td>Effacer la recherche active</td></tr>
        <tr><td><b>F1</b></td><td>Afficher cette aide</td></tr>
        </table>
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Raccourcis Clavier")
        msg.setTextFormat(Qt.RichText)
        msg.setText(help_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    # ─────────────────────────────────────────────────────────────────────
    # i18n
    # ─────────────────────────────────────────────────────────────────────

    def apply_language(self, lang: str):
        if lang not in self.TRANSLATIONS:
            lang = "fr"
        self.language = lang
        t = self.TRANSLATIONS[lang]

        self.setWindowTitle(t["window_title"])
        self.tabs.setTabText(0, t["tab_build"])
        self.tabs.setTabText(1, t["tab_collection"])
        self.tabs.setTabText(2, t["tab_settings"])

        self.collection_tab.apply_translations(t)
        self.settings_tab.apply_translations(t, lang)

    # ─────────────────────────────────────────────────────────────────────
    # Compatibilité avec app.py (API attendue)
    # ─────────────────────────────────────────────────────────────────────

    @property
    def commander_input(self):
        return self.build_tab.commander_input

    @property
    def numb_deck_search(self):
        return self.settings_tab.numb_deck_search

    @property
    def order_by(self):
        return self.settings_tab.order_by

    @property
    def numb_min_land(self):
        return self.settings_tab.numb_min_land

    @property
    def numb_max_land(self):
        return self.settings_tab.numb_max_land

    @property
    def numb_ramp(self):
        return self.settings_tab.numb_ramp

    @property
    def numb_draw(self):
        return self.settings_tab.numb_draw

    @property
    def numb_removal(self):
        return self.settings_tab.numb_removal

    @property
    def numb_boardwipe(self):
        return self.settings_tab.numb_boardwipe

    @property
    def numb_wincondition(self):
        return self.settings_tab.numb_wincondition

    @property
    def export_format(self):
        return self.settings_tab.export_format

    @property
    def deck_found_table(self):
        return self.build_tab.deck_found_table

    @property
    def deck_table(self):
        return self.build_tab.deck_table

    def get_numb_deck_search(self):
        return self.settings_tab.numb_deck_search.currentText()

    def get_export_format(self):
        return self.settings_tab.export_format.currentText()

    def get_strategy_manager(self) -> StrategyManager:
        return self.strategy_manager

    def is_budget_mode(self) -> bool:
        return self.build_tab.is_budget_mode()

    def get_current_strategy_params(self) -> dict:
        return self.strategy_manager.get_strategy_params()

    # ─────────────────────────────────────────────────────────────────────
    # Collection (appelé par app.py)
    # ─────────────────────────────────────────────────────────────────────

    def set_collection_cards(self, cards: List[Dict]):
        self.collection_tab.set_collection_cards(cards, getattr(self.app, "external_provider", None))

    def refresh_collection_list(self):
        self.collection_tab.refresh_collection_list()

    def refresh_commander_candidates(self):
        candidates = self.app.collection_manager.get_commander_candidates(get_all=True)
        self.build_tab.refresh_commander_candidates(candidates)
        current = self.build_tab.get_commander_name()
        self.update_commander_preview(current)

    def confirm_delete_collection(self) -> bool:
        reply = QMessageBox.question(
            self,
            "Supprimer la collection",
            "Cette action va supprimer toutes les cartes de la collection. Continuer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    # ─────────────────────────────────────────────────────────────────────
    # Build tab (appelé par app.py)
    # ─────────────────────────────────────────────────────────────────────

    def set_eventual_cards(self, cards: List[Dict]):
        self.build_tab.set_eventual_cards(cards)

    def set_deck_cards(self, cards: List[Dict]):
        self.build_tab.set_deck_cards(cards)

    def set_length_of_eventual_list(self, length: int, numb_decks: int, total: int):
        self.build_tab.set_eventual_list_label(length, numb_decks, total)

    def set_length_and_score_of_deck_list(self, length: int, mean_score: float):
        self.build_tab.set_deck_list_label(length, mean_score)

    def set_deck_stats(self, mana_curve_text: str, stats_text: str):
        self.build_tab.stats_panel.set_stats_text(stats_text)

    def set_deck_power_level(self, power_data: dict):
        self.build_tab.stats_panel.set_power_level(power_data)

    def set_deck_graphs(self, summary: dict):
        self.build_tab.stats_panel.set_graphs(summary)

    def show_deck_images(self, cards_data, external_provider):
        self.build_tab.show_deck_images(cards_data, external_provider)

    # ─────────────────────────────────────────────────────────────────────
    # Progress dialog (appelé par app.py)
    # ─────────────────────────────────────────────────────────────────────

    def show_progress(self, title: str, label: str, maximum: int = 0):
        from PySide6.QtWidgets import QProgressDialog
        self.progress_dialog = QProgressDialog(label, None, 0, maximum or 0, self)
        self.progress_dialog.setWindowTitle(title)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setRange(0, maximum if maximum and maximum > 0 else 0)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        QApplication.processEvents()

    def update_progress(self, value: int):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.setValue(value)
            QApplication.processEvents()

    def set_progress_label(self, text: str):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.setLabelText(text)

    def set_progress_range(self, minimum: int, maximum: int):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.setRange(minimum, maximum)

    def close_progress(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

    # ─────────────────────────────────────────────────────────────────────
    # Dialogs utilitaires
    # ─────────────────────────────────────────────────────────────────────

    def show_error(self, message: str):
        QMessageBox.critical(self, "Erreur", message)

    def show_info(self, message: str):
        QMessageBox.information(self, "Information", message)

    def get_open_file_name(self, title: str, file_filter: str) -> str:
        return QFileDialog.getOpenFileName(self, title, "", file_filter)[0]

    def get_save_file_name(self, title: str, default_name: str, file_filter: str) -> str:
        return QFileDialog.getSaveFileName(self, title, default_name, file_filter)[0]

    def get_csv_path_for_import_in_db(self):
        file_path = self.get_open_file_name("Importer une collection", "CSV files (*.csv)")
        if not file_path:
            return "", None
        import_type, accepted = QInputDialog.getItem(
            self,
            "Format d'import",
            "Import depuis:",
            ["Détection automatique", "ManaBox - Collection", "CardNexus"],
            0,
            False,
        )
        if not accepted:
            return "", None
        if import_type == "Détection automatique":
            import_type = None
        return file_path, import_type

    # ─────────────────────────────────────────────────────────────────────
    # Commandant — aperçu + info EDHRec
    # ─────────────────────────────────────────────────────────────────────

    def update_commander_preview(self, commander_name: str):
        if not commander_name:
            self.build_tab.stats_panel.set_commander_preview(None)
            return
        if not self.build_tab.is_known_commander_name(commander_name):
            self.build_tab.stats_panel.set_commander_preview(None)
            return

        def _load_pixmap(url: str) -> Optional[QPixmap]:
            try:
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                pix = QPixmap()
                pix.loadFromData(resp.content)
                return pix if not pix.isNull() else None
            except Exception:
                return None

        def _get_face_urls(scryfall_id: str) -> list:
            urls: list = []
            try:
                data = self.app.external_provider.get_scryfall_data(scryfall_id)
            except Exception:
                return urls
            if not data:
                return urls
            if "image_uris" in data:
                iu = data["image_uris"]
                candidate = iu.get("normal") or iu.get("large") or iu.get("png")
                if candidate:
                    urls.append(candidate)
            for face in data.get("card_faces", []) or []:
                iu = face.get("image_uris") or {}
                candidate = iu.get("normal") or iu.get("large") or iu.get("png")
                if candidate:
                    urls.append(candidate)
            return urls

        def _append_image_urls_from_card_data(data: Optional[Dict], target_urls: list):
            if not data:
                return
            if "image_uris" in data:
                iu = data["image_uris"] or {}
                candidate = iu.get("normal") or iu.get("large") or iu.get("png")
                if candidate and candidate not in target_urls:
                    target_urls.append(candidate)
            for face in data.get("card_faces", []) or []:
                iu = face.get("image_uris") or {}
                candidate = iu.get("normal") or iu.get("large") or iu.get("png")
                if candidate and candidate not in target_urls:
                    target_urls.append(candidate)

        card = self.app.collection_manager.get_card(commander_name)
        scryfall_id = card.get("scryfall_id") if card else None
        urls: list = []
        if card and card.get("image_url"):
            urls.append(card["image_url"])

        bulk_card = None
        try:
            if getattr(self, "scryfall_sync", None) and self.scryfall_sync.is_bulk_available():
                bulk_card = self.scryfall_sync.get_card_for_import(
                    scryfall_id=scryfall_id or "",
                    card_name=commander_name,
                )
        except Exception:
            bulk_card = None

        _append_image_urls_from_card_data(bulk_card, urls)

        if scryfall_id:
            for u in _get_face_urls(scryfall_id):
                if u not in urls:
                    urls.append(u)

        if not urls:
            try:
                remote_card = self.app.external_provider.get_scryfall_data(commander_name)
            except Exception:
                remote_card = None
            _append_image_urls_from_card_data(remote_card, urls)

        pixmaps = []
        urls.reverse()
        for url in urls:
            pix = _load_pixmap(url)
            if pix:
                pixmaps.append(pix)
            if len(pixmaps) >= 2:
                break

        if not pixmaps:
            self.build_tab.stats_panel.set_commander_preview(None)
            return

        if len(pixmaps) == 1:
            final_pix = pixmaps[0].scaledToWidth(280, Qt.SmoothTransformation)
        else:
            target_h = 360
            scaled = [p.scaledToHeight(target_h, Qt.SmoothTransformation) for p in pixmaps[:2]]
            total_w = sum(p.width() for p in scaled)
            final_pix = QPixmap(total_w, target_h)
            final_pix.fill(Qt.transparent)
            painter = QPainter(final_pix)
            x = 0
            for p in scaled:
                painter.drawPixmap(x, 0, p)
                x += p.width()
            painter.end()

        self.build_tab.stats_panel.set_commander_preview(final_pix)

    def _update_commander_info(self, commander_name: str):
        if not commander_name or not self.build_tab.is_known_commander_name(commander_name):
            self._commander_info_timer.stop()
            self.build_tab.stats_panel.set_commander_info("", "")
            self.build_tab.set_recommendations_text("Sélectionnez un commandant")
            self.build_tab.set_recommendations_visible(False)
            return
        self._pending_commander_name = commander_name
        self._commander_info_timer.start()
        self._update_recommendations(commander_name)

    def _fetch_commander_info_debounced(self):
        commander_name = self._pending_commander_name
        if not commander_name:
            return
        if not self._commander_info_connected:
            self._commander_info_ready.connect(self._apply_commander_info)
            self._commander_info_connected = True

        def fetch_data():
            try:
                data = self.edhrec_analytics.get_commander_data(commander_name)
                if data:
                    rank = data.get("edhrec_rank")
                    tier = self.edhrec_analytics.get_commander_tier(rank)
                    type_line = data.get("type_line", "")
                    popularity_text = f"#{rank} · {tier}" if rank else f"Tier {tier}"
                    self._commander_info_ready.emit(popularity_text, type_line)
            except Exception:
                pass

        threading.Thread(target=fetch_data, daemon=True).start()

    def _apply_commander_info(self, popularity_text: str, type_text: str):
        self.build_tab.stats_panel.set_commander_info(popularity_text, type_text)

    def _update_recommendations(self, commander_name: str):
        if not commander_name or not self.build_tab.is_known_commander_name(commander_name):
            self.build_tab.set_recommendations_text("Sélectionnez un commandant")
            self.build_tab.set_recommendations_visible(False)
            self._current_synergies = []
            return
        status = self.scryfall_sync.get_cache_status()
        if not status["has_oracle_cards"]:
            self.build_tab.set_recommendations_text(
                "Synchronisez Scryfall pour voir les recommandations"
            )
            self.build_tab.set_recommendations_visible(False)
            return
        commander_data = self.scryfall_sync.get_card_data(commander_name)
        if not commander_data:
            self.build_tab.set_recommendations_text("Commandant non trouvé dans le bulk")
            return
        synergies = self.strategy_manager.detect_commander_synergies(commander_data)
        if synergies:
            self.build_tab.set_recommendations_text(
                f"Synergies : {', '.join(synergies[:4])}"
            )
            self.build_tab.set_recommendations_visible(True)
            self._current_synergies = synergies
        else:
            staples = len(self.strategy_manager.get_staples_for_strategy())
            self.build_tab.set_recommendations_text(f"{staples} staples EDHRec disponibles")
            self.build_tab.set_recommendations_visible(True)
            self._current_synergies = []

    def _show_recommendations_dialog(self):
        from PySide6.QtWidgets import QTabWidget as QTW, QTableWidget, QTableWidgetItem
        dialog = QDialog(self)
        dialog.setWindowTitle("Recommandations — Scryfall Bulk")
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout(dialog)

        commander = self.build_tab.get_commander_name()
        title = QLabel(f"Recommandations pour {commander}")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #d29922;")
        layout.addWidget(title)

        tabs = QTW()
        staples_widget = QWidget()
        sl = QVBoxLayout(staples_widget)
        staples_list = self.strategy_manager.get_staples_for_strategy()
        st = QTableWidget()
        st.setColumnCount(2)
        st.setHorizontalHeaderLabels(["Carte", "Type"])
        st.setRowCount(min(20, len(staples_list)))
        for i, staple in enumerate(staples_list[:20]):
            st.setItem(i, 0, QTableWidgetItem(staple))
            cd = self.scryfall_sync.get_card_data(staple)
            type_line = cd.get("type_line", "Inconnu") if cd else "Inconnu"
            st.setItem(i, 1, QTableWidgetItem(type_line))
        sl.addWidget(QLabel("Top 20 Staples EDHRec"))
        sl.addWidget(st)
        tabs.addTab(staples_widget, "Staples")

        layout.addWidget(tabs)
        close_btn = QPushButton("Fermer")
        close_btn.setObjectName("accent")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    # ─────────────────────────────────────────────────────────────────────
    # Stratégie
    # ─────────────────────────────────────────────────────────────────────

    def _on_strategy_changed(self, strategy_name: str):
        strategy_map = {
            "Midrange": DeckStrategy.MIDRANGE,
            "Aggro": DeckStrategy.AGGRO,
            "Control": DeckStrategy.CONTROL,
            "Combo": DeckStrategy.COMBO,
            "Budget": DeckStrategy.BUDGET,
        }
        strategy = strategy_map.get(strategy_name, DeckStrategy.MIDRANGE)
        profile = self.strategy_manager.set_strategy(strategy)
        self.build_tab.set_strategy_info(profile.description)

        st = self.settings_tab
        st.numb_ramp.setValue(profile.ramp)
        st.numb_draw.setValue(profile.draw)
        st.numb_removal.setValue(profile.removal)
        st.numb_boardwipe.setValue(profile.boardwipe)
        st.numb_wincondition.setValue(profile.wincon)
        st.numb_min_land.setValue(profile.min_lands)
        st.numb_max_land.setValue(profile.max_lands)

        if strategy == DeckStrategy.BUDGET:
            self.build_tab.budget_checkbox.setChecked(True)

        self.statusBar().showMessage(f"Stratégie '{profile.name}' sélectionnée", 3000)

    def _on_budget_changed(self, state: int):
        enabled = state == 2
        self.strategy_manager.set_budget_mode(enabled)
        if enabled:
            self.statusBar().showMessage("Mode Budget activé", 3000)
        else:
            self.statusBar().showMessage("Mode Budget désactivé", 3000)

    def _on_pauper_changed(self, state: int):
        enabled = state == 2
        self.strategy_manager.set_pauper_mode(enabled)
        if enabled:
            self.statusBar().showMessage("Mode Pauper activé", 3000)
        else:
            self.statusBar().showMessage("Mode Pauper désactivé", 3000)

    # ─────────────────────────────────────────────────────────────────────
    # Mana curve interactivité
    # ─────────────────────────────────────────────────────────────────────

    def _on_mana_curve_click(self, cmc: int, value: int):
        if value <= 0:
            return
        self.build_tab.apply_mana_filter(cmc)

    def _on_mana_curve_reset(self):
        self.build_tab.reset_mana_filter()

    def _on_commander_image_click(self):
        """Ouvre le dialog holographique avec l'image du commandant."""
        from gui.widgets.card_image import open_card_image_dialog_from_pixmap
        pixmap = self.build_tab.stats_panel.preview_label.get_original_pixmap()
        if pixmap and not pixmap.isNull():
            commander_name = self.build_tab.get_commander_name()
            open_card_image_dialog_from_pixmap(self, pixmap, commander_name)

    # ─────────────────────────────────────────────────────────────────────
    # Actions deck
    # ─────────────────────────────────────────────────────────────────────

    def _on_search_commander(self):
        t = self.TRANSLATIONS.get(self.language, self.TRANSLATIONS["fr"])
        self.statusBar().showMessage("Recherche en cours…", 0)
        self.build_tab.set_search_btn_loading(True, t["btn_search_commander"], t["btn_search_loading"])
        try:
            self.app.get_decks_archidekt_from_commander()
        finally:
            self.build_tab.set_search_btn_loading(False, t["btn_search_commander"], t["btn_search_loading"])
            self.statusBar().showMessage("Recherche terminée", 3000)

    def _on_build_deck(self):
        t = self.TRANSLATIONS.get(self.language, self.TRANSLATIONS["fr"])
        self.statusBar().showMessage("Construction du deck en cours…", 0)
        self.build_tab.set_build_btn_loading(True, t["btn_build"], t["btn_build_loading"])
        try:
            self.app.build_deck()
        finally:
            self.build_tab.set_build_btn_loading(False, t["btn_build"], t["btn_build_loading"])
            self.statusBar().showMessage("Deck construit", 3000)

    # ─────────────────────────────────────────────────────────────────────
    # Scryfall sync
    # ─────────────────────────────────────────────────────────────────────

    def _update_sync_status(self):
        status = self.scryfall_sync.get_cache_status()
        self.settings_tab.set_sync_status(
            status["has_oracle_cards"],
            str(status.get("oracle_cards_size_mb", "")),
            str(status.get("last_update", "")),
        )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024**3):.2f} GB"
        elif size_bytes >= 1024 ** 2:
            return f"{size_bytes / (1024**2):.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        return f"{size_bytes} B"

    def _on_sync_progress(self, percent: int, downloaded: int, total: int, speed: float, message: str):
        if percent >= 0:
            remaining = total - downloaded if total > 0 else 0
            info = (
                f"{self._format_size(downloaded)} / {self._format_size(total)}"
                f"  ·  {speed:.1f} MB/s  ·  Reste {self._format_size(remaining)}"
            )
            self.settings_tab.update_sync_progress(percent, info)
            self.statusBar().showMessage(f"Téléchargement Scryfall : {percent}%", 0)
        elif percent == -1 and downloaded > 0:
            info = f"{self._format_size(downloaded)} téléchargés  ·  {speed:.1f} MB/s"
            self.settings_tab.update_sync_progress(-1, info)
        else:
            self.settings_tab.update_sync_progress(0, message or "Préparation…")

    def _on_sync_finished(self, success: bool):
        self.settings_tab.set_sync_loading(False)
        self._update_sync_status()
        msg = "Synchronisation Scryfall terminée" if success else "Échec de la synchronisation"
        self.statusBar().showMessage(msg, 5000)
        if success:
            self._update_recommendations(self.build_tab.get_commander_name())

    def _on_sync_error(self, error_msg: str):
        self.statusBar().showMessage(f"Erreur : {error_msg}", 5000)

    def _on_sync_scryfall(self):
        self.settings_tab.set_sync_loading(True)

        try:
            self._sync_progress.disconnect(self._on_sync_progress)
        except (RuntimeError, TypeError):
            pass
        try:
            self._sync_finished.disconnect(self._on_sync_finished)
        except (RuntimeError, TypeError):
            pass
        try:
            self._sync_error.disconnect(self._on_sync_error)
        except (RuntimeError, TypeError):
            pass

        self._sync_progress.connect(self._on_sync_progress)
        self._sync_finished.connect(self._on_sync_finished)
        self._sync_error.connect(self._on_sync_error)

        def progress_callback(percent, downloaded_bytes, total_bytes, speed_mbps, message):
            self._sync_progress.emit(
                int(percent), int(downloaded_bytes), int(total_bytes),
                float(speed_mbps), str(message)
            )

        def do_sync():
            try:
                success = self.scryfall_sync.sync(progress_callback=progress_callback)
                self._sync_finished.emit(success)
            except Exception as e:
                self._sync_error.emit(str(e))
                self._sync_finished.emit(False)

        threading.Thread(target=do_sync, daemon=True).start()
