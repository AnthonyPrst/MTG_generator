"""Thème visuel centralisé de l'application."""

DARK_THEME = """
    QWidget {
        background-color: #0d1117;
        color: #e6edf3;
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 13px;
    }

    /* ── Onglets ───────────────────────────────────────────── */
    QTabWidget::pane {
        border: 1px solid #21262d;
        border-radius: 8px;
        background: #0d1117;
    }
    QTabBar::tab {
        background: #161b22;
        border: 1px solid #21262d;
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-weight: 500;
        color: #8b949e;
    }
    QTabBar::tab:selected {
        background: #1c2128;
        border-bottom-color: #1c2128;
        color: #e6edf3;
        border-top: 2px solid #2563eb;
    }
    QTabBar::tab:hover:!selected {
        background: #1a2332;
        color: #c9d1d9;
    }

    /* ── Boutons principaux ────────────────────────────────── */
    QPushButton {
        background: #21262d;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 7px 14px;
        font-weight: 500;
    }
    QPushButton:hover {
        background: #30363d;
        border-color: #8b949e;
        color: #e6edf3;
    }
    QPushButton:pressed {
        background: #161b22;
    }
    QPushButton:disabled {
        background: #161b22;
        color: #484f58;
        border-color: #21262d;
    }

    QPushButton#primary {
        background: #238636;
        color: white;
        border-color: #2ea043;
    }
    QPushButton#primary:hover {
        background: #2ea043;
    }
    QPushButton#primary:pressed {
        background: #196c2e;
    }

    QPushButton#accent {
        background: #1f6feb;
        color: white;
        border-color: #388bfd;
    }
    QPushButton#accent:hover {
        background: #388bfd;
    }
    QPushButton#accent:pressed {
        background: #1158c7;
    }

    QPushButton#danger {
        background: #da3633;
        color: white;
        border-color: #f85149;
    }
    QPushButton#danger:hover {
        background: #f85149;
    }
    QPushButton#danger:pressed {
        background: #b91c1c;
    }

    /* ── Champs de saisie ──────────────────────────────────── */
    QLineEdit, QComboBox, QTextEdit, QSpinBox {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 6px 10px;
        color: #e6edf3;
        selection-background-color: #1f6feb;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border-color: #388bfd;
        background: #0d1117;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox::down-arrow {
        width: 12px;
        height: 12px;
    }
    QComboBox QAbstractItemView {
        background: #161b22;
        border: 1px solid #30363d;
        selection-background-color: #1f6feb;
        outline: none;
    }

    /* ── Tableaux ──────────────────────────────────────────── */
    QTableWidget {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
        gridline-color: #21262d;
        alternate-background-color: #111620;
    }
    QTableWidget::item {
        padding: 4px 8px;
    }
    QTableWidget::item:selected {
        background: #1f3a6e;
        color: #e6edf3;
    }
    QTableWidget::item:hover {
        background: #1c2128;
    }
    QHeaderView::section {
        background: #161b22;
        border: none;
        border-right: 1px solid #21262d;
        border-bottom: 1px solid #21262d;
        padding: 8px 10px;
        font-weight: 600;
        color: #8b949e;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 0.5px;
    }
    QHeaderView::section:first {
        border-top-left-radius: 6px;
    }
    QHeaderView::section:last {
        border-top-right-radius: 6px;
        border-right: none;
    }

    /* ── Scrollbars ────────────────────────────────────────── */
    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #30363d;
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover { background: #484f58; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal {
        background: transparent;
        height: 8px;
        margin: 0;
    }
    QScrollBar::handle:horizontal {
        background: #30363d;
        border-radius: 4px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover { background: #484f58; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

    /* ── Progress ──────────────────────────────────────────── */
    QProgressBar {
        border: 1px solid #21262d;
        border-radius: 6px;
        background: #161b22;
        height: 8px;
        text-align: center;
        color: transparent;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1f6feb,stop:1 #388bfd);
        border-radius: 6px;
    }

    /* ── Séparateurs ───────────────────────────────────────── */
    QSplitter::handle {
        background: #21262d;
        width: 1px;
        height: 1px;
    }
    QSplitter::handle:hover {
        background: #388bfd;
    }

    /* ── Groupes ───────────────────────────────────────────── */
    QGroupBox {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        margin-top: 20px;
        padding: 16px 12px 12px 12px;
        font-weight: 600;
        color: #c9d1d9;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        left: 12px;
        color: #8b949e;
        font-size: 11px;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }

    /* ── Tooltips ──────────────────────────────────────────── */
    QToolTip {
        background: #1c2128;
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }

    /* ── Status bar ────────────────────────────────────────── */
    QStatusBar {
        background: #161b22;
        border-top: 1px solid #21262d;
        color: #8b949e;
        font-size: 12px;
    }

    /* ── CheckBox ──────────────────────────────────────────── */
    QCheckBox {
        spacing: 8px;
        color: #c9d1d9;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #30363d;
        border-radius: 4px;
        background: #0d1117;
    }
    QCheckBox::indicator:checked {
        background: #1f6feb;
        border-color: #388bfd;
    }

    /* ── Labels spéciaux ──────────────────────────────────── */
    QLabel#sectionTitle {
        font-size: 11px;
        font-weight: 700;
        color: #8b949e;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    QLabel#cardPreview {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
    }
    QLabel#statsValue {
        font-size: 22px;
        font-weight: 700;
        color: #e6edf3;
    }
    QLabel#badgeGreen {
        background: #1a3a1a;
        color: #3fb950;
        border: 1px solid #238636;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 600;
    }
    QLabel#badgeBlue {
        background: #0d2045;
        color: #388bfd;
        border: 1px solid #1f6feb;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 600;
    }
    QLabel#badgeYellow {
        background: #2d1f00;
        color: #d29922;
        border: 1px solid #9e6a03;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 600;
    }
    QWidget#sidebar {
        background: #161b22;
        border-right: 1px solid #21262d;
    }
    QWidget#statsPanel {
        background: #161b22;
        border-left: 1px solid #21262d;
    }
    QWidget#card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
    }
    QWidget#toolbar {
        background: #161b22;
        border-bottom: 1px solid #21262d;
    }
"""
