from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from hmi.trainui.models import ConfigInfo


class ConfigDetailsDialog(QDialog):
    """Read-only tree of the exact selected OpenPI config and derived pipeline."""

    def __init__(self, config: ConfigInfo, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle(f"完整训练配置 · {config.name}")
        self.resize(940, 720)
        self.setMinimumSize(760, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(config.name)
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 3)
        title.setFont(font)

        subtitle = QLabel(
            f"模型: {config.model_class or '—'}    "
            f"数据配置: {config.data_factory or '—'}    "
            f"优化器: {config.optimizer_type or '—'}"
        )
        subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        text_stack = QVBoxLayout()
        text_stack.setSpacing(2)
        text_stack.addWidget(title)
        text_stack.addWidget(subtitle)
        header.addLayout(text_stack)
        header.addStretch(1)

        copy_button = QPushButton("复制 JSON")
        copy_button.clicked.connect(self._copy_json)
        header.addWidget(copy_button)
        layout.addLayout(header)

        if config.inspect_warnings:
            warning = QLabel("\n".join(f"⚠ {item}" for item in config.inspect_warnings))
            warning.setWordWrap(True)
            warning.setObjectName("ConfigWarning")
            layout.addWidget(warning)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["配置项", "值 / 类型"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setColumnWidth(0, 360)
        layout.addWidget(self.tree, 1)

        root = QTreeWidgetItem([config.name, "OpenPI TrainConfig"])
        self.tree.addTopLevelItem(root)
        self._append_value(root, config.config_tree)
        root.setExpanded(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _append_value(self, parent: QTreeWidgetItem, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, (dict, list, tuple)):
                    item = QTreeWidgetItem([str(key), self._container_label(child)])
                    parent.addChild(item)
                    self._append_value(item, child)
                else:
                    parent.addChild(QTreeWidgetItem([str(key), self._scalar_text(child)]))
            return

        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                if isinstance(child, (dict, list, tuple)):
                    item = QTreeWidgetItem([f"[{index}]", self._container_label(child)])
                    parent.addChild(item)
                    self._append_value(item, child)
                else:
                    parent.addChild(QTreeWidgetItem([f"[{index}]", self._scalar_text(child)]))
            return

        parent.addChild(QTreeWidgetItem(["值", self._scalar_text(value)]))

    @staticmethod
    def _container_label(value: Any) -> str:
        if isinstance(value, dict):
            class_name = value.get("__class__")
            return str(class_name) if class_name else f"对象 · {len(value)} 项"
        return f"列表 · {len(value)} 项"

    @staticmethod
    def _scalar_text(value: Any) -> str:
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "True" if value else "False"
        return str(value)

    def _copy_json(self) -> None:
        text = json.dumps(self._config.config_tree, ensure_ascii=False, indent=2)
        QGuiApplication.clipboard().setText(text)
