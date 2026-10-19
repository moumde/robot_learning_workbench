from __future__ import annotations

import html
from typing import Callable

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCloseEvent, QDoubleValidator, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hmi.trainui.models import ConfigInfo, DatasetInfo, RunMode, TrainState, TrainingMetrics
from hmi.trainui.views.config_details import ConfigDetailsDialog
from hmi.trainui.widgets.metric_plot import MetricPlot


STATE_TEXT = {
    TrainState.IDLE: "空闲",
    TrainState.VALIDATING: "校验中",
    TrainState.STARTING: "启动中",
    TrainState.RUNNING: "训练中",
    TrainState.STOPPING: "停止中",
    TrainState.FINISHED: "已完成",
    TrainState.FAILED: "失败",
}


class NoWheelSpinBox(QSpinBox):
    """滚动页面时，不让鼠标滚轮误改训练参数。"""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        event.ignore()


class NoWheelComboBox(QComboBox):
    """滚动页面时，不让鼠标滚轮误切换配置或数据集。"""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        event.ignore()


def _spin(minimum: int, maximum: int) -> QSpinBox:
    widget = NoWheelSpinBox()
    widget.setRange(minimum, maximum)
    widget.setGroupSeparatorShown(True)
    widget.setMinimumWidth(150)
    return widget


def _configure_form(form: QFormLayout) -> None:
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(9)


class MainWindow(QMainWindow):
    refresh_datasets_requested = Signal()
    config_changed = Signal(str)
    dataset_changed = Signal(str)
    experiment_changed = Signal(str)
    compute_norm_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    force_stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("机器人学习工作台 · 训练界面")
        self.resize(1420, 920)
        self.setMinimumSize(1120, 760)
        self.close_handler: Callable[[], bool] | None = None
        self._current_config: ConfigInfo | None = None

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)
        self.setCentralWidget(root)

        self._build_header(root_layout)

        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.setChildrenCollapsible(False)

        horizontal = QSplitter(Qt.Orientation.Horizontal)
        horizontal.setChildrenCollapsible(False)
        horizontal.addWidget(self._build_left_panel())
        horizontal.addWidget(self._build_right_panel())
        horizontal.setStretchFactor(0, 0)
        horizontal.setStretchFactor(1, 1)
        horizontal.setSizes([540, 860])

        vertical.addWidget(horizontal)
        vertical.addWidget(self._build_log_panel())
        vertical.setStretchFactor(0, 1)
        vertical.setStretchFactor(1, 0)
        vertical.setSizes([680, 210])
        root_layout.addWidget(vertical, 1)

    # ------------------------------------------------------------------
    # 顶层布局
    # ------------------------------------------------------------------
    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        title = QLabel("模型训练")
        font = title.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        title.setFont(font)

        subtitle = QLabel("OpenPI 训练控制台")
        subtitle.setObjectName("SubtleText")

        stack = QVBoxLayout()
        stack.setSpacing(0)
        stack.addWidget(title)
        stack.addWidget(subtitle)

        self.framework_status = QLabel("OpenPI · 未连接")
        self.framework_status.setObjectName("ConnectionBadge")

        row.addLayout(stack)
        row.addStretch(1)
        row.addWidget(self.framework_status, 0, Qt.AlignmentFlag.AlignTop)
        parent_layout.addLayout(row)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(470)
        panel.setMaximumWidth(700)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 训练配置 / 数据集 / 数据结构 / 归一化状态固定显示，永远不被滚动隐藏。
        layout.addWidget(self._build_readiness_card(), 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content = QWidget()
        self.left_layout = QVBoxLayout(content)
        self.left_layout.setContentsMargins(0, 0, 6, 0)
        self.left_layout.setSpacing(9)

        self._build_experiment_settings()
        self._build_training_params()
        self._build_data_details()
        self._build_advanced()
        self.left_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._build_control_bar(), 0)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        self.right_layout = QVBoxLayout(panel)
        self.right_layout.setContentsMargins(8, 0, 0, 0)
        self.right_layout.setSpacing(10)
        self._build_status()
        return panel

    def _build_log_panel(self) -> QWidget:
        box = QGroupBox("训练日志")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        hint = QLabel("最近 5000 行 · 原始 OpenPI 日志同步保存到 logs/trainui/")
        hint.setObjectName("SubtleText")
        clear = QPushButton("清空")
        clear.setFixedWidth(74)
        clear.clicked.connect(lambda: self.log.clear())
        header.addWidget(hint)
        header.addStretch(1)
        header.addWidget(clear)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.document().setMaximumBlockCount(5000)
        self.log.setMinimumHeight(130)

        layout.addLayout(header)
        layout.addWidget(self.log)
        return box

    # ------------------------------------------------------------------
    # 左侧：固定状态区
    # ------------------------------------------------------------------
    def _build_readiness_card(self) -> QGroupBox:
        box = QGroupBox("训练配置与数据状态")
        form = QFormLayout(box)
        _configure_form(form)

        self.framework = QLabel("OpenPI")
        form.addRow("训练框架", self.framework)

        config_row = QWidget()
        config_layout = QHBoxLayout(config_row)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(6)

        self.config_combo = NoWheelComboBox()
        self.config_combo.setMinimumContentsLength(22)
        self.config_combo.currentIndexChanged.connect(
            lambda _index: self.config_changed.emit(str(self.config_combo.currentData() or ""))
        )
        self.config_details_button = QPushButton("完整配置")
        self.config_details_button.setFixedWidth(86)
        self.config_details_button.clicked.connect(self._show_config_details)
        config_layout.addWidget(self.config_combo, 1)
        config_layout.addWidget(self.config_details_button)
        form.addRow("训练配置", config_row)

        dataset_row = QWidget()
        dataset_layout = QHBoxLayout(dataset_row)
        dataset_layout.setContentsMargins(0, 0, 0, 0)
        dataset_layout.setSpacing(6)
        self.dataset_combo = NoWheelComboBox()
        self.dataset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dataset_combo.setMinimumContentsLength(20)
        self.dataset_combo.currentIndexChanged.connect(
            lambda _index: self.dataset_changed.emit(str(self.dataset_combo.currentData() or ""))
        )
        refresh = QPushButton("刷新")
        refresh.setFixedWidth(66)
        refresh.clicked.connect(self.refresh_datasets_requested)
        dataset_layout.addWidget(self.dataset_combo, 1)
        dataset_layout.addWidget(refresh)
        form.addRow("训练数据集", dataset_row)

        schema_row = QWidget()
        schema_layout = QHBoxLayout(schema_row)
        schema_layout.setContentsMargins(0, 0, 0, 0)
        schema_layout.setSpacing(6)
        self.schema_status = QLabel("○ 未检查")
        self.schema_status.setObjectName("SchemaStatus")
        self.data_details_button = QPushButton("查看详情")
        self.data_details_button.setFixedWidth(86)
        self.data_details_button.setCheckable(True)
        self.data_details_button.toggled.connect(self._toggle_data_details)
        schema_layout.addWidget(self.schema_status)
        schema_layout.addStretch(1)
        schema_layout.addWidget(self.data_details_button)
        form.addRow("数据集结构", schema_row)

        norm_row = QWidget()
        norm_layout = QHBoxLayout(norm_row)
        norm_layout.setContentsMargins(0, 0, 0, 0)
        norm_layout.setSpacing(6)
        self.norm_status = QLabel("○ 未检查")
        self.norm_status.setObjectName("NormStatus")
        self.compute_norm_button = QPushButton("计算归一化统计")
        self.compute_norm_button.setMinimumWidth(126)
        self.compute_norm_button.clicked.connect(self.compute_norm_requested)
        norm_layout.addWidget(self.norm_status)
        norm_layout.addStretch(1)
        norm_layout.addWidget(self.compute_norm_button)
        form.addRow("归一化统计", norm_row)

        return box

    # ------------------------------------------------------------------
    # 左侧：滚动参数区
    # ------------------------------------------------------------------
    def _build_experiment_settings(self) -> None:
        box = QGroupBox("模型与实验")
        form = QFormLayout(box)
        _configure_form(form)

        self.model_label = QLabel("—")
        form.addRow("模型类型", self.model_label)

        self.data_config_label = QLabel("—")
        self.data_config_label.setWordWrap(True)
        form.addRow("数据配置", self.data_config_label)

        self.model_shape_label = QLabel("—")
        form.addRow("模型动作规格", self.model_shape_label)

        self.schedule_label = QLabel("—")
        form.addRow("学习率策略", self.schedule_label)

        self.optimizer_label = QLabel("—")
        form.addRow("优化器", self.optimizer_label)

        self.init_label = QLineEdit()
        self.init_label.setReadOnly(True)
        form.addRow("初始化模型", self.init_label)

        self.exp_name = QLineEdit()
        self.exp_name.setPlaceholderText("例如：pick_place_lora_v1")
        self.exp_name.textChanged.connect(self.experiment_changed)
        form.addRow("实验名称", self.exp_name)

        self.run_mode = NoWheelComboBox()
        self.run_mode.addItem("新训练（目录必须不存在）", RunMode.NEW.value)
        self.run_mode.addItem("从最新检查点继续", RunMode.RESUME.value)
        self.run_mode.addItem("覆盖同名实验", RunMode.OVERWRITE.value)
        form.addRow("启动方式", self.run_mode)

        self.left_layout.addWidget(box)

    def _build_training_params(self) -> None:
        box = QGroupBox("基础训练参数")
        form = QFormLayout(box)
        _configure_form(form)

        self.steps = _spin(1, 100_000_000)
        form.addRow("训练步数", self.steps)

        self.batch_size = _spin(1, 65536)
        form.addRow("批大小", self.batch_size)

        self.peak_lr = QLineEdit()
        self.peak_lr.setMinimumWidth(150)
        self.peak_lr.setValidator(QDoubleValidator(1e-12, 10.0, 12, self))
        form.addRow("峰值学习率", self.peak_lr)

        self.save_interval = _spin(1, 100_000_000)
        form.addRow("检查点保存间隔", self.save_interval)

        # 曲线的数据点来自 OpenPI 的 metric log。把它放到基础参数区，
        # 避免短训练时用户看不到为何损失曲线更新很慢。
        self.log_interval = _spin(1, 100_000_000)
        self.log_interval.setToolTip("OpenPI 每隔多少步输出一次 loss / grad_norm / param_norm")
        form.addRow("指标记录间隔", self.log_interval)

        self.left_layout.addWidget(box)

    def _build_data_details(self) -> None:
        self.data_details = QGroupBox("数据与归一化详情")
        layout = QVBoxLayout(self.data_details)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(7)

        self.dataset_summary = QLabel("尚未选择数据集")
        self.dataset_summary.setWordWrap(True)
        self.dataset_summary.setObjectName("DatasetSummary")

        self.dataset_info = QTextBrowser()
        self.dataset_info.setReadOnly(True)
        self.dataset_info.setOpenExternalLinks(False)
        self.dataset_info.setMinimumHeight(112)
        self.dataset_info.setMaximumHeight(185)
        self.dataset_info.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dataset_info.setPlaceholderText("等待数据集检查…")

        path_caption = QLabel("归一化统计路径")
        path_caption.setObjectName("SubtleText")
        self.norm_path = QLineEdit()
        self.norm_path.setReadOnly(True)
        self.norm_path.setPlaceholderText("norm_stats.json 路径")

        layout.addWidget(self.dataset_summary)
        layout.addWidget(self.dataset_info)
        layout.addWidget(path_caption)
        layout.addWidget(self.norm_path)

        self.data_details.setVisible(False)
        self.left_layout.addWidget(self.data_details)

    def _build_advanced(self) -> None:
        self.advanced_button = QToolButton()
        self.advanced_button.setText("▶ 高级设置")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setChecked(False)
        self.advanced_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.advanced_button.toggled.connect(self._toggle_advanced)
        self.left_layout.addWidget(self.advanced_button)

        self.advanced = QGroupBox("高级训练参数")
        form = QFormLayout(self.advanced)
        _configure_form(form)

        self.warmup_steps = _spin(0, 100_000_000)
        form.addRow("预热步数", self.warmup_steps)

        self.decay_steps = _spin(1, 100_000_000)
        form.addRow("学习率衰减步数", self.decay_steps)

        self.decay_lr = QLineEdit()
        self.decay_lr.setValidator(QDoubleValidator(1e-12, 10.0, 12, self))
        form.addRow("衰减后学习率", self.decay_lr)

        self.keep_period = _spin(0, 100_000_000)
        self.keep_period.setSpecialValueText("禁用")
        form.addRow("长期保留间隔", self.keep_period)

        self.num_workers = _spin(0, 128)
        form.addRow("数据加载进程数", self.num_workers)

        self.seed = _spin(0, 2_147_483_647)
        form.addRow("随机种子", self.seed)

        self.fsdp_devices = _spin(1, 64)
        form.addRow("FSDP 设备数", self.fsdp_devices)

        self.clip_grad = QLineEdit()
        self.clip_grad.setValidator(QDoubleValidator(1e-12, 1e9, 12, self))
        form.addRow("梯度裁剪阈值", self.clip_grad)

        self.wandb = QCheckBox("启用 Weights & Biases (W&B)")
        form.addRow("实验跟踪", self.wandb)

        self.advanced.setVisible(False)
        self.left_layout.addWidget(self.advanced)

    def _build_control_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("ControlBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.start_button = QPushButton("开始训练")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.setMinimumHeight(38)

        self.stop_button = QPushButton("停止训练")
        self.stop_button.setMinimumHeight(38)
        self.stop_button.setEnabled(False)

        self.force_stop_button = QPushButton("强制结束")
        self.force_stop_button.setMinimumHeight(38)
        self.force_stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.force_stop_button.clicked.connect(self.force_stop_requested)

        layout.addWidget(self.start_button, 2)
        layout.addWidget(self.stop_button, 1)
        layout.addWidget(self.force_stop_button, 1)
        return bar

    # ------------------------------------------------------------------
    # 右侧：运行状态
    # ------------------------------------------------------------------
    def _build_status(self) -> None:
        box = QGroupBox("训练状态")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.state_label = QLabel(STATE_TEXT[TrainState.IDLE])
        self.state_label.setObjectName("StatusBadge")
        self.step_label = QLabel("训练进度 — / —")
        self.step_label.setObjectName("StepLabel")
        header.addWidget(self.state_label)
        header.addStretch(1)
        header.addWidget(self.step_label)
        layout.addLayout(header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("0.0%")
        self.progress.setMinimumHeight(24)
        layout.addWidget(self.progress)

        metrics = QGroupBox("训练指标")
        metric_layout = QHBoxLayout(metrics)
        metric_layout.setContentsMargins(12, 12, 12, 12)
        metric_layout.setSpacing(28)

        self.loss_value = QLabel("—")
        self.grad_value = QLabel("—")
        self.param_value = QLabel("—")

        for caption, value_widget in (
            ("损失", self.loss_value),
            ("梯度范数", self.grad_value),
            ("参数范数", self.param_value),
        ):
            item = QWidget()
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(2)
            label = QLabel(caption)
            label.setObjectName("MetricCaption")
            value_font = value_widget.font()
            value_font.setBold(True)
            value_font.setPointSize(value_font.pointSize() + 1)
            value_widget.setFont(value_font)
            item_layout.addWidget(label)
            item_layout.addWidget(value_widget)
            metric_layout.addWidget(item)
        metric_layout.addStretch(1)
        layout.addWidget(metrics)

        self.loss_plot = MetricPlot()
        self.loss_plot.setMinimumHeight(250)
        layout.addWidget(self.loss_plot, 1)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        cards.addWidget(self._build_gpu_card(), 1)
        cards.addWidget(self._build_checkpoint_card(), 1)
        layout.addLayout(cards)

        self.right_layout.addWidget(box, 1)

    def _build_gpu_card(self) -> QGroupBox:
        gpu = QGroupBox("GPU 状态")
        form = QFormLayout(gpu)
        _configure_form(form)
        form.setVerticalSpacing(6)

        self.gpu_name = QLabel("检测中…")
        self.gpu_name.setWordWrap(True)
        self.gpu_memory = QLabel("—")
        self.gpu_util = QLabel("—")
        self.gpu_temp = QLabel("—")
        form.addRow("设备", self.gpu_name)
        form.addRow("显存", self.gpu_memory)
        form.addRow("利用率", self.gpu_util)
        form.addRow("温度", self.gpu_temp)
        return gpu

    def _build_checkpoint_card(self) -> QGroupBox:
        ckpt = QGroupBox("检查点")
        form = QFormLayout(ckpt)
        _configure_form(form)
        form.setVerticalSpacing(6)

        self.checkpoint_path = QLineEdit()
        self.checkpoint_path.setReadOnly(True)
        self.latest_checkpoint = QLabel("—")
        form.addRow("实验目录", self.checkpoint_path)
        form.addRow("最新检查点", self.latest_checkpoint)
        return ckpt

    # ------------------------------------------------------------------
    # 交互与公开接口
    # ------------------------------------------------------------------
    def _show_config_details(self) -> None:
        if self._current_config is None:
            self.warn("完整配置", "当前尚未加载 OpenPI 训练配置。")
            return
        dialog = ConfigDetailsDialog(self._current_config, self)
        dialog.exec()

    def _toggle_data_details(self, checked: bool) -> None:
        self.data_details.setVisible(checked)
        self.data_details_button.setText("收起详情" if checked else "查看详情")

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced.setVisible(checked)
        self.advanced_button.setText("▼ 高级设置" if checked else "▶ 高级设置")

    def populate_config_names(self, names: list[str], preferred: str | None = None) -> None:
        """Populate registry names only; no TrainConfig is materialized here."""
        self.config_combo.blockSignals(True)
        self.config_combo.clear()
        self.config_combo.addItem("请选择训练配置…", "")
        self.config_combo.setItemData(
            0,
            "这里只读取 OpenPI 注册表中的名称；选择一个配置后才解析其详细内容。",
            Qt.ItemDataRole.ToolTipRole,
        )
        preferred_index = 0
        for name in names:
            index = self.config_combo.count()
            self.config_combo.addItem(name, name)
            self.config_combo.setItemData(
                index,
                "选择后才读取该 TrainConfig 的模型、数据管线、优化器和完整配置。",
                Qt.ItemDataRole.ToolTipRole,
            )
            if preferred and name == preferred:
                preferred_index = index
        self.config_combo.setCurrentIndex(preferred_index)
        self.config_combo.blockSignals(False)

    def show_config_unselected(self) -> None:
        self._current_config = None
        self.framework_status.setText("OpenPI · 就绪")
        self.model_label.setText("请选择训练配置")
        self.data_config_label.setText("—")
        self.model_shape_label.setText("—")
        self.schedule_label.setText("—")
        self.optimizer_label.setText("—")
        self.init_label.setText("—")
        self.config_details_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.compute_norm_button.setEnabled(False)
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        self.dataset_combo.addItem("请先选择训练配置", "")
        self.dataset_combo.setEnabled(False)
        self.dataset_combo.blockSignals(False)
        self.schema_status.setText("○ 等待配置")
        self.norm_status.setText("○ 等待配置")
        self.dataset_summary.setText("选择配置后才读取 DataConfig 与数据契约。")

    # Compatibility helper for older tests/callers.  TrainController v1.6 uses
    # populate_config_names() and never serializes all ConfigInfo objects.
    def populate_configs(self, configs: list[ConfigInfo], preferred: str | None = None) -> None:
        self.populate_config_names([config.name for config in configs], preferred=preferred)

    def show_config_loading(self, name: str) -> None:
        self._current_config = None
        self.framework_status.setText("OpenPI · 正在加载当前配置")
        self.model_label.setText("正在加载…")
        self.data_config_label.setText("正在加载…")
        self.model_shape_label.setText("—")
        self.schedule_label.setText("—")
        self.optimizer_label.setText("—")
        self.init_label.setText("—")
        self.config_details_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.compute_norm_button.setEnabled(False)
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        self.dataset_combo.addItem("正在读取当前配置…", "")
        self.dataset_combo.setEnabled(False)
        self.dataset_combo.blockSignals(False)
        self.schema_status.setText("○ 等待配置")
        self.norm_status.setText("○ 等待配置")
        self.dataset_summary.setText(f"正在解析 {name}")

    def show_config_error(self, name: str, message: str) -> None:
        self._current_config = None
        self.framework_status.setText("OpenPI · 配置错误")
        self.model_label.setText("—")
        self.data_config_label.setText("—")
        self.model_shape_label.setText("—")
        self.schedule_label.setText("—")
        self.optimizer_label.setText("—")
        self.init_label.setText("—")
        self.config_details_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.compute_norm_button.setEnabled(False)
        self.dataset_combo.setEnabled(False)
        self.schema_status.setText("⚠ 配置读取失败")
        self.norm_status.setText("—")
        self.dataset_summary.setText(name or "当前配置")
        self.dataset_info.setPlainText(message)

    def apply_config(self, config: ConfigInfo) -> None:
        self._current_config = config
        self.config_details_button.setEnabled(True)
        self.start_button.setEnabled(config.runnable)
        self.framework_status.setText("OpenPI · 就绪")
        self.model_label.setText(config.model_label or config.model_class)
        self.data_config_label.setText(config.data_factory or "—")

        shape_parts = []
        if config.action_dim is not None:
            shape_parts.append(f"动作维度 {config.action_dim}")
        if config.action_horizon is not None:
            shape_parts.append(f"动作时域 {config.action_horizon}")
        self.model_shape_label.setText(" · ".join(shape_parts) if shape_parts else "由模型配置决定")
        self.schedule_label.setText(config.lr_schedule_type or "—")
        self.optimizer_label.setText(config.optimizer_type or "—")

        self.init_label.setText(config.initialization_label)
        self.init_label.setToolTip(config.weight_path or config.weight_loader_class)
        self.init_label.setCursorPosition(0)

        self.exp_name.setText(config.default_exp_name or f"{config.name}_ui")
        self.steps.setValue(config.num_train_steps)
        self.batch_size.setValue(config.batch_size)
        self.save_interval.setValue(config.save_interval)
        self.log_interval.setValue(config.log_interval)
        self.keep_period.setValue(config.keep_period or 0)
        self.num_workers.setValue(config.num_workers)
        self.seed.setValue(config.seed)
        self.fsdp_devices.setValue(config.fsdp_devices)
        self.wandb.setChecked(config.wandb_enabled)

        self._set_optional_line(self.peak_lr, config.peak_lr)
        self._set_optional_spin(self.warmup_steps, config.warmup_steps)
        self._set_optional_spin(self.decay_steps, config.decay_steps)
        self._set_optional_line(self.decay_lr, config.decay_lr)
        self._set_optional_line(self.clip_grad, config.clip_gradient_norm)

        tooltip = "\n".join(config.inspect_warnings) if config.inspect_warnings else "查看 OpenPI 注册的完整 TrainConfig"
        self.config_details_button.setToolTip(tooltip)

    @staticmethod
    def _set_optional_line(widget: QLineEdit, value: float | None) -> None:
        widget.setEnabled(value is not None)
        widget.setText("" if value is None else f"{value:.8g}")
        widget.setPlaceholderText("当前配置不包含此参数" if value is None else "")

    @staticmethod
    def _set_optional_spin(widget: QSpinBox, value: int | None) -> None:
        widget.setEnabled(value is not None)
        if value is not None:
            widget.setValue(value)
        widget.setToolTip("当前配置不包含此参数" if value is None else "")

    def populate_datasets(self, datasets: list[DatasetInfo], preferred: str | None = None) -> None:
        previous = preferred or str(self.dataset_combo.currentData() or "")
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        selected = -1
        for index, dataset in enumerate(datasets):
            if dataset.source == "config-missing":
                label = f"{dataset.repo_id}  [配置默认 · 本地缺失]"
            elif dataset.source == "config-remote":
                label = f"{dataset.repo_id}  [配置默认 · 远程/外部]"
            else:
                label = dataset.repo_id
            self.dataset_combo.addItem(label, dataset.repo_id)
            if dataset.repo_id == previous:
                selected = index
        if datasets:
            self.dataset_combo.setCurrentIndex(selected if selected >= 0 else 0)
        self.dataset_combo.blockSignals(False)

    def show_dataset(self, dataset: DatasetInfo | None) -> None:
        if dataset is None:
            self.schema_status.setText("○ 由配置决定")
            self.schema_status.setProperty("status", "idle")
            self._refresh_widget_style(self.schema_status)
            self.dataset_summary.setText("当前训练配置没有可在本地切换的数据集。")
            self.dataset_info.setHtml(
                "<p>该配置的数据源由 OpenPI TrainConfig 自身决定。"
                "可点击上方 <b>完整配置</b> 查看 DataConfig、repo_id、repack transforms 等全部字段。</p>"
            )
            return

        self.dataset_summary.setText(dataset.summary or dataset.repo_id)
        self.dataset_summary.setToolTip(str(dataset.path))

        parts: list[str] = []
        if dataset.errors:
            self.schema_status.setText("⚠ 不兼容")
            self.schema_status.setProperty("status", "error")
            items = "".join(f"<li>{html.escape(error)}</li>" for error in dataset.errors)
            parts.append("<p><b>数据结构不匹配</b></p><ul>" + items + "</ul>")
        elif dataset.source == "config-remote":
            self.schema_status.setText("○ 远程数据源 · 未本地验证")
            self.schema_status.setProperty("status", "idle")
            parts.append(
                "<p><b>该 repo_id 来自当前 OpenPI 配置，本地没有 meta/info.json。</b>"
                " TrainUI 将保留原始 config，由 OpenPI 在运行时解析远程/外部数据源。</p>"
            )
        elif dataset.source == "config-missing":
            self.schema_status.setText("⚠ 配置数据集缺失")
            self.schema_status.setProperty("status", "error")
            parts.append(
                "<p><b>当前 config 指向了一个本地风格的数据集名称，但工作区里没有对应的 meta/info.json。</b></p>"
            )
        else:
            self.schema_status.setText("✓ 已通过自动检查")
            self.schema_status.setProperty("status", "ready")
            parts.append("<p><b>✓ 已通过当前配置能够静态推导的检查。</b></p>")

        if dataset.warnings:
            warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in dataset.warnings)
            parts.append("<p>说明：</p><ul>" + warning_items + "</ul>")

        if dataset.features:
            parts.append(
                f"<p>本地 meta/info.json 共包含 {len(dataset.features)} 个 feature。"
                "字段要求来自所选 config，而不是机器人名称硬编码。</p>"
            )

        self.dataset_info.setHtml("".join(parts))
        self._refresh_widget_style(self.schema_status)

    def show_norm(
        self,
        path: str,
        ready: bool,
        supported: bool = True,
        blocked: bool = False,
    ) -> None:
        self.compute_norm_button.setEnabled(supported and not blocked)
        if blocked:
            self.norm_status.setText("⚠ 数据集不可用")
            self.norm_status.setProperty("ready", "false")
            self.compute_norm_button.setText("无法计算")
            self.norm_path.setText(path)
        elif not supported:
            self.norm_status.setText("— 由配置管理")
            self.norm_status.setProperty("ready", "unknown")
            self.compute_norm_button.setText("不适用")
            self.norm_path.setText(path or "由 OpenPI 配置决定")
        else:
            self.norm_status.setText("✓ 已就绪" if ready else "○ 缺失")
            self.norm_status.setProperty("ready", "true" if ready else "false")
            self.compute_norm_button.setText("重新计算" if ready else "计算归一化统计")
            self.norm_path.setText(path)
        self._refresh_widget_style(self.norm_status)
        self.norm_path.setToolTip(path)
        self.norm_path.setCursorPosition(0)

    def set_dataset_selector_mode(self, enabled: bool, label: str = "") -> None:
        self.dataset_combo.setEnabled(enabled)
        if not enabled:
            self.dataset_combo.blockSignals(True)
            self.dataset_combo.clear()
            self.dataset_combo.addItem(label or "由配置决定", "")
            self.dataset_combo.blockSignals(False)

    def form_values(self) -> dict:
        return {
            "exp_name": self.exp_name.text().strip(),
            "num_train_steps": self.steps.value(),
            "batch_size": self.batch_size.value(),
            "peak_lr": self.peak_lr.text().strip() if self.peak_lr.isEnabled() else None,
            "save_interval": self.save_interval.value(),
            "log_interval": self.log_interval.value(),
            "run_mode": str(self.run_mode.currentData()),
            "warmup_steps": self.warmup_steps.value() if self.warmup_steps.isEnabled() else None,
            "decay_steps": self.decay_steps.value() if self.decay_steps.isEnabled() else None,
            "decay_lr": self.decay_lr.text().strip() if self.decay_lr.isEnabled() else None,
            "keep_period": self.keep_period.value(),
            "num_workers": self.num_workers.value(),
            "seed": self.seed.value(),
            "fsdp_devices": self.fsdp_devices.value(),
            "clip_gradient_norm": self.clip_grad.text().strip() if self.clip_grad.isEnabled() else None,
            "wandb_enabled": self.wandb.isChecked(),
        }

    def set_state(self, state: TrainState) -> None:
        self.state_label.setText(STATE_TEXT.get(state, state.value))
        self.state_label.setProperty("state", state.value)
        self._refresh_widget_style(self.state_label)

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.config_combo.setEnabled(not running)
        self.dataset_combo.setEnabled((not running) and bool(self._current_config and self._current_config.dataset_override_supported))
        self.exp_name.setEnabled(not running)
        self.run_mode.setEnabled(not running)
        self.compute_norm_button.setEnabled(not running)

    def enable_force_stop(self, enabled: bool) -> None:
        self.force_stop_button.setEnabled(enabled)

    def reset_metrics(self, total_steps: int) -> None:
        self.loss_plot.clear()
        self.loss_value.setText("—")
        self.grad_value.setText("—")
        self.param_value.setText("—")
        self.progress.setValue(0)
        self.progress.setFormat("0.0%")
        self.step_label.setText(f"训练进度 0 / {total_steps:,}")

    def update_progress(self, completed: int, total_steps: int) -> None:
        total_steps = max(1, int(total_steps))
        completed = min(max(0, int(completed)), total_steps)
        fraction = completed / total_steps
        self.progress.setValue(round(fraction * 1000))
        self.progress.setFormat(f"{fraction * 100:.1f}%")
        self.step_label.setText(f"训练进度 {completed:,} / {total_steps:,}")

    def update_metrics(self, metrics: TrainingMetrics) -> None:
        # 进度条由 tqdm 的 Progress on 行驱动，不能再由 log_interval 较稀疏的
        # metric 行反向覆盖，否则会出现训练已到 60% 而 UI 又退回 0% 的现象。
        if "loss" in metrics.values:
            value = metrics.values["loss"]
            self.loss_value.setText(f"{value:.6g}")
            self.loss_plot.add_point(metrics.step, value)
        if "grad_norm" in metrics.values:
            self.grad_value.setText(f"{metrics.values['grad_norm']:.6g}")
        if "param_norm" in metrics.values:
            self.param_value.setText(f"{metrics.values['param_norm']:.6g}")

    def mark_training_complete(self, total_steps: int) -> None:
        self.update_progress(total_steps, total_steps)

    def update_gpu(self, gpus: list[dict]) -> None:
        if not gpus:
            self.gpu_name.setText("未检测到 NVIDIA GPU")
            self.gpu_memory.setText("—")
            self.gpu_util.setText("—")
            self.gpu_temp.setText("—")
            return
        gpu = gpus[0]
        self.gpu_name.setText(f"GPU {gpu['index']} · {gpu['name']}")
        used = gpu["memory_used_mb"] / 1024
        total = gpu["memory_total_mb"] / 1024
        self.gpu_memory.setText(f"{used:.1f} / {total:.1f} GiB")
        self.gpu_util.setText(f"{gpu['utilization']}%")
        self.gpu_temp.setText(f"{gpu['temperature_c']} °C")
        if len(gpus) > 1:
            self.gpu_name.setToolTip(
                "\n".join(f"GPU {g['index']}: {g['name']}" for g in gpus)
            )

    def update_checkpoint(self, path: str, latest_step: int | None) -> None:
        self.checkpoint_path.setText(path)
        self.checkpoint_path.setToolTip(path)
        self.checkpoint_path.setCursorPosition(0)
        self.latest_checkpoint.setText("—" if latest_step is None else f"第 {latest_step:,} 步")

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def confirm(self, title: str, message: str) -> bool:
        result = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Yes

    @staticmethod
    def _refresh_widget_style(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self.close_handler is not None and not self.close_handler():
            event.ignore()
            return
        event.accept()
