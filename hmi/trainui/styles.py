STYLE_SHEET = """
QMainWindow {
    background: #f7f8fa;
}

QWidget {
    color: #1f2937;
}

QGroupBox {
    font-weight: 600;
    background: #ffffff;
    border: 1px solid #d8dde6;
    border-radius: 9px;
    margin-top: 11px;
    padding-top: 9px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    padding: 0 5px;
    color: #111827;
}

QLabel#SubtleText {
    color: #6b7280;
}

QLabel#ConnectionBadge,
QLabel#StatusBadge {
    font-weight: 700;
    padding: 5px 11px;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    background: #ffffff;
}

QLabel#SchemaStatus,
QLabel#NormStatus {
    font-weight: 700;
    padding: 3px 7px;
    border-radius: 7px;
}

QLabel#SchemaStatus[status="ready"],
QLabel#NormStatus[ready="true"] {
    color: #166534;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
}

QLabel#SchemaStatus[status="error"] {
    color: #9a3412;
    background: #fff7ed;
    border: 1px solid #fed7aa;
}

QLabel#SchemaStatus[status="idle"],
QLabel#NormStatus[ready="false"] {
    color: #4b5563;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
}

QLabel#StepLabel,
QLabel#DatasetSummary {
    font-weight: 600;
}

QLabel#MetricCaption {
    color: #4b5563;
    font-weight: 600;
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    min-height: 30px;
    padding: 2px 7px;
    background: #ffffff;
    border: 1px solid #cfd5df;
    border-radius: 5px;
    selection-background-color: #2563eb;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #2563eb;
}

QLineEdit[readOnly="true"] {
    background: #f8fafc;
}

QTextBrowser {
    background: #fbfcfe;
    border: 1px solid #d8dde6;
    border-radius: 6px;
    padding: 5px;
}

QPushButton {
    min-height: 31px;
    padding: 3px 12px;
    background: #ffffff;
    border: 1px solid #cfd5df;
    border-radius: 5px;
}

QPushButton:hover:enabled {
    background: #f3f4f6;
}

QPushButton#PrimaryButton {
    font-weight: 700;
    color: #ffffff;
    background: #2563eb;
    border: 1px solid #2563eb;
}

QPushButton#PrimaryButton:hover:enabled {
    background: #1d4ed8;
}

QPushButton:disabled {
    color: #9ca3af;
    background: #f3f4f6;
}

QToolButton {
    min-height: 30px;
    padding: 2px 4px;
    font-weight: 600;
    color: #374151;
}

QFrame#ControlBar {
    background: #f7f8fa;
    border-top: 1px solid #d8dde6;
}

QPlainTextEdit {
    font-family: monospace;
    background: #ffffff;
    border: 1px solid #d8dde6;
    border-radius: 6px;
}

QProgressBar {
    background: #eef1f5;
    border: 1px solid #d8dde6;
    border-radius: 5px;
    text-align: center;
    min-height: 22px;
}

QProgressBar::chunk {
    background: #2563eb;
    border-radius: 4px;
}

QScrollArea {
    border: none;
    background: transparent;
}
"""
