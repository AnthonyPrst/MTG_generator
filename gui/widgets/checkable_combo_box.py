"""CheckableComboBox - ComboBox avec sélection multiple via checkboxes."""

from typing import List
from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QPixmap, QPainter, QStandardItemModel, QStandardItem, QColor, QBrush
from PySide6.QtCore import Qt, Signal


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
