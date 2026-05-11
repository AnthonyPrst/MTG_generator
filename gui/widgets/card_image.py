"""Widgets liés à l'affichage des images de cartes avec effets holographiques."""

import requests
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QLabel, QDialog, QVBoxLayout, QPushButton, QGraphicsDropShadowEffect,
    QWidget, QHBoxLayout,
)
from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPixmap, QColor, QPainter, QLinearGradient, QBrush


class ClickableImage(QLabel):
    """QLabel qui émet un signal au clic avec les coordonnées."""
    clicked = Signal(int, int)
    doubleClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(event.pos().x(), event.pos().y())

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()


class HolographicCard(QLabel):
    """Carte avec effet holographique 3D qui réagit à la souris."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._base_pixmap = pixmap
        self._rotation_x = 0.0
        self._rotation_y = 0.0
        self._shine_x = 0.5
        self._shine_y = 0.5
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

        # Ombre portée dynamique
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(40)
        self._shadow.setColor(QColor(0, 0, 0, 180))
        self._shadow.setOffset(0, 10)
        self.setGraphicsEffect(self._shadow)

        self._update_display()

    def _update_display(self):
        """Met à jour l'affichage avec l'effet de brillance."""
        if self._base_pixmap.isNull():
            return

        # Créer une copie pour dessiner le reflet
        result = QPixmap(self._base_pixmap.size())
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Dessiner l'image de base
        painter.drawPixmap(0, 0, self._base_pixmap)

        # Effet de brillance holographique
        w, h = result.width(), result.height()
        shine_center_x = int(self._shine_x * w)
        shine_center_y = int(self._shine_y * h)

        # Gradient radial simulé avec un gradient linéaire diagonal
        gradient = QLinearGradient(
            shine_center_x - 100, shine_center_y - 100,
            shine_center_x + 100, shine_center_y + 100
        )
        gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.4, QColor(255, 255, 255, 60))
        gradient.setColorAt(0.5, QColor(200, 220, 255, 100))
        gradient.setColorAt(0.6, QColor(255, 200, 255, 60))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        painter.end()
        self.setPixmap(result)

    def mouseMoveEvent(self, event):
        """Calcule la rotation et le reflet selon la position de la souris."""
        pos = event.pos()
        w, h = self.width(), self.height()

        # Normaliser la position (-1 à 1)
        norm_x = (pos.x() / w - 0.5) * 2
        norm_y = (pos.y() / h - 0.5) * 2

        # Rotation (max ±15 degrés)
        self._rotation_y = norm_x * 15
        self._rotation_x = -norm_y * 15

        # Position du reflet
        self._shine_x = pos.x() / w
        self._shine_y = pos.y() / h

        # Appliquer la transformation CSS-like via stylesheet
        self._apply_transform()
        self._update_display()

        # Ombre dynamique
        shadow_x = norm_x * 20
        shadow_y = 10 + norm_y * 10
        self._shadow.setOffset(shadow_x, shadow_y)

    def leaveEvent(self, event):
        """Reset la rotation quand la souris quitte."""
        self._rotation_x = 0
        self._rotation_y = 0
        self._shine_x = 0.5
        self._shine_y = 0.5
        self._apply_transform()
        self._update_display()
        self._shadow.setOffset(0, 10)

    def _apply_transform(self):
        """Applique la transformation 3D via stylesheet (perspective)."""
        # PySide6 ne supporte pas les transforms 3D CSS directement,
        # on simule avec un léger scale et une ombre
        scale = 1.0 + abs(self._rotation_x) * 0.002 + abs(self._rotation_y) * 0.002
        # On ne peut pas faire de vraie rotation 3D en QSS, mais l'effet visuel
        # est créé par le gradient de brillance qui bouge


class HolographicCardDialog(QDialog):
    """Dialog moderne avec carte holographique interactive."""

    def __init__(self, pixmap: QPixmap, card_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(card_name)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d1117, stop:0.5 #161b22, stop:1 #0d1117);
                border: 1px solid #30363d;
                border-radius: 16px;
            }
            QPushButton {
                background: #238636;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #2ea043;
            }
            QLabel#cardName {
                color: #e6edf3;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#hint {
                color: #8b949e;
                font-size: 11px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Titre
        title = QLabel(card_name)
        title.setObjectName("cardName")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Carte holographique
        scaled = pixmap.scaledToWidth(400, Qt.SmoothTransformation)
        self.card = HolographicCard(scaled)
        self.card.setFixedSize(scaled.width() + 20, scaled.height() + 20)
        layout.addWidget(self.card, alignment=Qt.AlignCenter)

        # Hint
        hint = QLabel("✨ Bougez la souris sur la carte pour l'effet holographique")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # Bouton fermer
        close_btn = QPushButton("Fermer")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        self.adjustSize()
        self.setFixedSize(self.size())


def open_card_image_dialog(parent, card: Dict, external_provider=None):
    """Ouvre une fenêtre avec l'image de la carte avec effet holographique."""
    if not card:
        return

    url = card.get("image_url")
    if not url and external_provider:
        scryfall_id = card.get("scryfall_id")
        if scryfall_id:
            try:
                url = external_provider.get_image_url_from_scryfall(scryfall_id)
            except Exception:
                url = None

    if not url:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(parent, "Image", "Aucune image disponible pour cette carte.")
        return

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        pix = QPixmap()
        pix.loadFromData(resp.content)
    except Exception:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(parent, "Image", "Impossible de charger l'image de la carte.")
        return

    if pix.isNull():
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(parent, "Image", "Image invalide.")
        return

    dlg = HolographicCardDialog(pix, card.get("name", "Carte"), parent)
    dlg.exec()


def open_card_image_dialog_from_pixmap(parent, pixmap: QPixmap, card_name: str):
    """Ouvre le dialog holographique directement depuis un QPixmap."""
    if pixmap.isNull():
        return
    dlg = HolographicCardDialog(pixmap, card_name, parent)
    dlg.exec()
