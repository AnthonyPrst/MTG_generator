"""Panneau de statistiques du deck (courbe de mana, rôles, power level)."""

from typing import Dict, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont


class ClickableClippedImageLabel(QLabel):
    """QLabel cliquable qui clip son contenu pour ne jamais déborder."""
    clicked = Signal()

    def __init__(self, fixed_height: int, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(fixed_height)
        self.setMinimumHeight(fixed_height)
        self.setMaximumHeight(fixed_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._max_h = fixed_height - 10  # marge interne
        self._original_pixmap = None
        self.setCursor(Qt.PointingHandCursor)

    def setPixmapScaled(self, pixmap: QPixmap):
        """Affiche le pixmap en le scalant pour qu'il rentre dans la hauteur fixe."""
        self._original_pixmap = pixmap
        if pixmap and not pixmap.isNull():
            max_w = self.width() - 10 if self.width() > 10 else 240
            scaled = pixmap.scaled(
                max_w,
                self._max_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.setPixmap(scaled)
        else:
            self.setPixmap(QPixmap())

    def get_original_pixmap(self) -> Optional[QPixmap]:
        return self._original_pixmap

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._original_pixmap:
            self.clicked.emit()


class ClippedImageLabel(QLabel):
    """QLabel qui clip son contenu pour ne jamais déborder (non cliquable)."""
    def __init__(self, fixed_height: int, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(fixed_height)
        self.setMinimumHeight(fixed_height)
        self.setMaximumHeight(fixed_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._max_h = fixed_height - 10

    def setPixmapScaled(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            max_w = self.width() - 10 if self.width() > 10 else 240
            scaled = pixmap.scaled(max_w, self._max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
        else:
            self.setPixmap(QPixmap())

from gui.widgets.card_image import ClickableImage


class SectionTitle(QLabel):
    """Label titre de section avec style standardisé."""
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName("sectionTitle")
        self.setFixedHeight(24)


class Divider(QFrame):
    """Séparateur horizontal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setStyleSheet("color: #21262d;")
        self.setFixedHeight(1)


class PowerLevelBadge(QLabel):
    """Badge affichant le power level du deck."""
    def __init__(self, parent=None):
        super().__init__("—", parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(36)
        self._apply_neutral()

    def _apply_neutral(self):
        self.setStyleSheet("""
            background: #1c2128;
            color: #8b949e;
            border: 1px solid #30363d;
            border-radius: 18px;
            font-size: 14px;
            font-weight: 700;
            padding: 0 16px;
        """)

    def set_power(self, level: int, tier: str):
        if level >= 8:
            bg, fg, border = "#1a0d2e", "#a371f7", "#8957e5"
        elif level >= 6:
            bg, fg, border = "#0a2a0a", "#3fb950", "#238636"
        elif level >= 4:
            bg, fg, border = "#0d1f40", "#388bfd", "#1f6feb"
        else:
            bg, fg, border = "#2d0d0d", "#f85149", "#da3633"

        self.setStyleSheet(f"""
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 18px;
            font-size: 14px;
            font-weight: 700;
            padding: 0 16px;
        """)
        self.setText(f"⚡ {level}/10  ·  {tier}")


class ManaCurveWidget(QWidget):
    """Histogramme natif Qt pour la courbe de mana."""

    barClicked = Signal(int, int)
    resetRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(150)
        self.setMinimumHeight(150)
        self.setMaximumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setObjectName("cardPreview")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(
            "Cliquez sur une barre pour filtrer les cartes de ce coût\n"
            "Double-clic pour réinitialiser le filtre"
        )
        self._buckets = {k: 0 for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]}
        self._bar_regions: list[tuple[QRectF, int, int]] = []

    def set_buckets(self, buckets: Optional[Dict[str, int]]):
        if buckets:
            self._buckets = {k: int(buckets.get(k, 0)) for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]}
        else:
            self._buckets = {k: 0 for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]}
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        for rect, cmc, value in self._bar_regions:
            if rect.contains(event.position()):
                self.barClicked.emit(cmc, value)
                return

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resetRequested.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.fillRect(rect, QColor("#161b22"))
        painter.setPen(QPen(QColor("#30363d"), 1))
        painter.drawRoundedRect(QRectF(rect), 10, 10)

        values = [self._buckets[k] for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]]
        labels = ["0", "1", "2", "3", "4", "5", "6", "7+"]
        max_value = max(values) if any(values) else 1

        left = rect.left() + 14
        right = rect.right() - 10
        top = rect.top() + 12
        bottom = rect.bottom() - 24
        chart_height = max(20, bottom - top)
        chart_width = max(20, right - left)
        slot_width = chart_width / max(1, len(values))
        bar_width = min(24, slot_width * 0.62)

        painter.setPen(QPen(QColor("#21262d"), 1))
        painter.drawLine(left, bottom, right, bottom)

        label_font = QFont(painter.font())
        label_font.setPointSize(8)
        value_font = QFont(painter.font())
        value_font.setPointSize(8)
        value_font.setBold(True)

        self._bar_regions = []
        for idx, value in enumerate(values):
            bar_left = left + idx * slot_width + (slot_width - bar_width) / 2
            height_ratio = value / max_value if max_value else 0
            bar_height = max(4, chart_height * height_ratio) if value > 0 else 4
            bar_rect = QRectF(bar_left, bottom - bar_height, bar_width, bar_height)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#1f6feb")))
            painter.drawRoundedRect(bar_rect, 5, 5)

            painter.setFont(value_font)
            painter.setPen(QColor("#c9d1d9"))
            painter.drawText(
                QRectF(bar_left - 8, bar_rect.top() - 14, bar_width + 16, 12),
                Qt.AlignCenter,
                str(value),
            )

            painter.setFont(label_font)
            painter.setPen(QColor("#8b949e"))
            painter.drawText(
                QRectF(bar_left - 8, bottom + 6, bar_width + 16, 12),
                Qt.AlignCenter,
                labels[idx],
            )
            self._bar_regions.append((bar_rect, 7 if labels[idx] == "7+" else int(labels[idx]), value))


class DistributionBarsWidget(QWidget):
    """Widget Qt natif pour afficher une répartition sous forme de barres."""

    itemClicked = Signal(str)
    resetRequested = Signal()

    def __init__(self, fixed_height: int, parent=None):
        super().__init__(parent)
        self._base_height = fixed_height
        self.setFixedHeight(fixed_height)
        self.setMinimumHeight(fixed_height)
        self.setMaximumHeight(fixed_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setObjectName("cardPreview")
        self.setCursor(Qt.PointingHandCursor)
        self._items: list[tuple[str, str, int, str]] = []
        self._regions: list[tuple[QRectF, str]] = []

    def set_items(self, items: list[tuple[str, str, int, str]]):
        self._items = items
        visible_count = len([1 for _, _, value, _ in items if value > 0])
        desired_height = max(self._base_height, 26 + visible_count * 22)
        self.setFixedHeight(desired_height)
        self.setMinimumHeight(desired_height)
        self.setMaximumHeight(desired_height)
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        for rect, key in self._regions:
            if rect.contains(event.position()):
                self.itemClicked.emit(key)
                return

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resetRequested.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.fillRect(rect, QColor("#161b22"))
        painter.setPen(QPen(QColor("#30363d"), 1))
        painter.drawRoundedRect(QRectF(rect), 10, 10)

        if not self._items:
            painter.setPen(QColor("#8b949e"))
            painter.drawText(rect, Qt.AlignCenter, "Aucune donnée")
            return

        visible_items = [(key, label, value, color) for key, label, value, color in self._items if value > 0]
        if not visible_items:
            painter.setPen(QColor("#8b949e"))
            painter.drawText(rect, Qt.AlignCenter, "Aucune donnée")
            return

        total = sum(value for _, _, value, _ in visible_items) or 1
        top = rect.top() + 10
        row_height = max(18, (rect.height() - 14) / len(visible_items))
        label_width = max(72, int(rect.width() * 0.28))
        value_width = 44
        bar_left = rect.left() + label_width + 10
        bar_right = rect.right() - value_width - 8
        bar_width = max(20, bar_right - bar_left)

        label_font = QFont(painter.font())
        label_font.setPointSize(8)
        value_font = QFont(painter.font())
        value_font.setPointSize(8)
        value_font.setBold(True)

        self._regions = []
        for idx, (key, label, value, color) in enumerate(visible_items):
            row_top = top + idx * row_height
            bar_top = row_top + 9
            fill_width = max(8, bar_width * (value / total))

            painter.setFont(label_font)
            painter.setPen(QColor("#c9d1d9"))
            painter.drawText(QRectF(rect.left() + 8, row_top, label_width - 4, 18), Qt.AlignVCenter | Qt.AlignLeft, label)

            track_rect = QRectF(bar_left, bar_top, bar_width, 10)
            fill_rect = QRectF(bar_left, bar_top, fill_width, 10)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#21262d"))
            painter.drawRoundedRect(track_rect, 5, 5)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(fill_rect, 5, 5)

            painter.setFont(value_font)
            painter.setPen(QColor("#8b949e"))
            painter.drawText(QRectF(bar_right + 6, row_top, value_width, 18), Qt.AlignVCenter | Qt.AlignRight, str(value))
            self._regions.append((QRectF(rect.left() + 8, row_top, rect.width() - 16, 20), key))


class StatsPanel(QWidget):
    """Panneau droit : aperçu commandant, courbe de mana, stats rôles et couleurs."""

    mana_curve_clicked = Signal(int, int)
    mana_curve_reset = Signal()
    role_distribution_clicked = Signal(str)
    role_distribution_reset = Signal()
    rarity_distribution_clicked = Signal(str)
    rarity_distribution_reset = Signal()
    color_distribution_clicked = Signal(str)
    color_distribution_reset = Signal()
    commander_image_clicked = Signal()  # Pour ouvrir le dialog holographique

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsPanel")
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Aperçu commandant ──────────────────────────────────────
        root.addWidget(SectionTitle("Commandant"))
        self.preview_label = ClickableClippedImageLabel(220)
        self.preview_label.setObjectName("cardPreview")
        self.preview_label.setText("Sélectionnez un commandant")
        self.preview_label.setWordWrap(True)
        self.preview_label.setToolTip("Cliquez pour agrandir")
        self.preview_label.clicked.connect(self.commander_image_clicked)
        root.addWidget(self.preview_label)

        # EDHRec info (sous l'image, pas dessus)
        self.commander_rank_label = QLabel("")
        self.commander_rank_label.setAlignment(Qt.AlignCenter)
        self.commander_rank_label.setFixedHeight(24)
        self.commander_rank_label.setStyleSheet("""
            background: #2d1f00;
            color: #d29922;
            border: 1px solid #9e6a03;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 10px;
        """)
        self.commander_rank_label.setVisible(False)
        root.addWidget(self.commander_rank_label)

        self.commander_type_label = QLabel("")
        self.commander_type_label.setAlignment(Qt.AlignCenter)
        self.commander_type_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.commander_type_label.setFixedHeight(18)
        root.addWidget(self.commander_type_label)

        root.addWidget(Divider())

        # ── Power Level ────────────────────────────────────────────
        root.addWidget(SectionTitle("Power Level"))
        self.power_badge = PowerLevelBadge()
        self.power_detail = QLabel("")
        self.power_detail.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.power_detail.setAlignment(Qt.AlignCenter)
        root.addWidget(self.power_badge)
        root.addWidget(self.power_detail)

        root.addWidget(Divider())

        # ── Courbe de mana ─────────────────────────────────────
        root.addWidget(SectionTitle("Courbe de Mana"))
        self.mana_curve_widget = ManaCurveWidget()
        self.mana_curve_widget.barClicked.connect(self.mana_curve_clicked)
        self.mana_curve_widget.resetRequested.connect(self.mana_curve_reset)
        root.addWidget(self.mana_curve_widget)

        self.mana_filter_badge = QLabel("")
        self.mana_filter_badge.setObjectName("badgeBlue")
        self.mana_filter_badge.setAlignment(Qt.AlignCenter)
        self.mana_filter_badge.setVisible(False)
        root.addWidget(self.mana_filter_badge)

        root.addWidget(Divider())

        # ── Répartition des rôles ──────────────────────────────
        root.addWidget(SectionTitle("Répartition des Rôles"))
        self.roles_widget = DistributionBarsWidget(150)
        self.roles_widget.itemClicked.connect(self.role_distribution_clicked)
        self.roles_widget.resetRequested.connect(self.role_distribution_reset)
        root.addWidget(self.roles_widget)

        self.goals_title = SectionTitle("Objectifs du Deck")
        root.addWidget(self.goals_title)
        self.goals_summary_label = QLabel("")
        self.goals_summary_label.setWordWrap(True)
        self.goals_summary_label.setStyleSheet("color: #c9d1d9; font-size: 11px; line-height: 1.35;")
        self.goals_summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.goals_summary_label.setVisible(False)
        root.addWidget(self.goals_summary_label)

        root.addWidget(Divider())

        root.addWidget(SectionTitle("Répartition des Raretés"))
        self.rarities_widget = DistributionBarsWidget(132)
        self.rarities_widget.itemClicked.connect(self.rarity_distribution_clicked)
        self.rarities_widget.resetRequested.connect(self.rarity_distribution_reset)
        root.addWidget(self.rarities_widget)

        root.addWidget(Divider())

        # ── Répartition des couleurs ───────────────────────────
        root.addWidget(SectionTitle("Répartition des Couleurs"))
        self.colors_widget = DistributionBarsWidget(132)
        self.colors_widget.itemClicked.connect(self.color_distribution_clicked)
        self.colors_widget.resetRequested.connect(self.color_distribution_reset)
        root.addWidget(self.colors_widget)

        self.stats_summary_label = QLabel("")
        self.stats_summary_label.setWordWrap(True)
        self.stats_summary_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.stats_summary_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.stats_summary_label)

        root.addStretch()

    # ── API publique ───────────────────────────────────────────────

    def set_commander_preview(self, pixmap: Optional[QPixmap]):
        if pixmap and not pixmap.isNull():
            self.preview_label.setPixmapScaled(pixmap)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Sélectionnez un commandant")

    def set_commander_info(self, rank_text: str, type_text: str):
        if rank_text:
            self.commander_rank_label.setText(rank_text)
            self.commander_rank_label.setVisible(True)
        else:
            self.commander_rank_label.setVisible(False)
        self.commander_type_label.setText(type_text)

    def set_power_level(self, power_data: dict):
        if not power_data:
            self.power_badge._apply_neutral()
            self.power_badge.setText("—")
            self.power_detail.setText("")
            return
        level = power_data.get("power_level", 0)
        tier = power_data.get("tier", "N/A")
        staples = power_data.get("staples_count", 0)
        cmc = power_data.get("cmc_average", 0)
        self.power_badge.set_power(level, tier)
        self.power_detail.setText(f"{staples} staples  ·  CMC moyen {cmc:.2f}")

    def set_graphs(self, summary: Optional[dict]):
        summary = summary or {}
        self.mana_curve_widget.set_buckets(summary.get("buckets"))
        self.goals_summary_label.setText(_format_goals_summary(summary))
        self.goals_summary_label.setVisible(bool(self.goals_summary_label.text().strip()))

        role_palette = {
            "Ramp": "#3fb950",
            "Draw": "#79c0ff",
            "Removal": "#e06030",
            "Finisher": "#bc8cff",
            "Land": "#8b6914",
            "Other": "#8b949e",
        }
        roles = summary.get("roles", {})
        role_items = [
            (role, role, int(value), role_palette.get(role, "#c9d1d9"))
            for role, value in sorted(roles.items(), key=lambda item: (-item[1], item[0]))
        ]
        self.roles_widget.set_items(role_items)

        rarity_palette = {
            "Mythic": "#e06030",
            "Rare": "#d29922",
            "Uncommon": "#79c0ff",
            "Common": "#8b949e",
            "Special": "#bc8cff",
            "Unknown": "#6e7681",
        }
        rarities = summary.get("rarities", {})
        rarity_items = [
            (rarity.lower(), rarity, int(value), rarity_palette.get(rarity, "#c9d1d9"))
            for rarity, value in sorted(rarities.items(), key=lambda item: (-item[1], item[0]))
        ]
        self.rarities_widget.set_items(rarity_items)

        color_palette = {
            "W": ("☀ Blanc", "#f0f0e0"),
            "U": ("💧 Bleu", "#5ba4cf"),
            "B": ("💀 Noir", "#a0a0b0"),
            "R": ("🔥 Rouge", "#e06030"),
            "G": ("🌲 Vert", "#4caf50"),
            "C": ("◇ Incolore", "#8b949e"),
        }
        colors = summary.get("colors", {})
        color_items = [
            (key, color_palette[key][0], int(colors.get(key, 0)), color_palette[key][1])
            for key in ["W", "U", "B", "R", "G", "C"]
        ]
        self.colors_widget.set_items(color_items)

    def show_mana_filter(self, cmc: Optional[int]):
        if cmc is None:
            self.mana_filter_badge.setVisible(False)
        else:
            label = "7+" if cmc == 7 else str(cmc)
            self.mana_filter_badge.setText(f"Filtre actif : CMC {label}  ·  double-clic pour annuler")
            self.mana_filter_badge.setVisible(True)

    def set_stats_text(self, stats_text: str):
        self.stats_summary_label.setText(stats_text)


def _goal_status(current: int, target: int) -> str:
    if current >= target:
        return "OK"
    if current >= max(0, target - 1):
        return "Proche"
    return "Bas"


def _format_goals_summary(summary: Optional[dict]) -> str:
    summary = summary or {}
    targets = summary.get("targets") or {}
    role_targets = targets.get("roles") or {}
    roles = summary.get("roles") or {}
    lands = int(summary.get("lands", 0) or 0)
    lines: list[str] = []

    lands_min = targets.get("lands_min")
    lands_max = targets.get("lands_max")
    if lands_min is not None and lands_max is not None:
        if lands < lands_min:
            land_status = "Bas"
        elif lands > lands_max:
            land_status = "Haut"
        else:
            land_status = "OK"
        lines.append(f"Terrains : {lands} / cible {lands_min}-{lands_max}  ·  {land_status}")

    for role in ["Ramp", "Draw", "Removal", "Finisher"]:
        if role not in role_targets:
            continue
        target = int(role_targets.get(role, 0) or 0)
        current = int(roles.get(role, 0) or 0)
        status = _goal_status(current, target)
        lines.append(f"{role} : {current} / {target}  ·  {status}")

    return "\n".join(lines)
