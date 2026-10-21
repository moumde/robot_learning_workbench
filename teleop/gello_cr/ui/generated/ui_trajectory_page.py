# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'trajectory_page.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QSpinBox, QStackedWidget, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_TrajectoryPanel(object):
    def setupUi(self, TrajectoryPanel):
        if not TrajectoryPanel.objectName():
            TrajectoryPanel.setObjectName(u"TrajectoryPanel")
        TrajectoryPanel.resize(1120, 640)
        TrajectoryPanel.setMinimumSize(QSize(0, 260))
        self.trajectory_root_layout = QHBoxLayout(TrajectoryPanel)
        self.trajectory_root_layout.setSpacing(12)
        self.trajectory_root_layout.setObjectName(u"trajectory_root_layout")
        self.trajectory_root_layout.setContentsMargins(0, 0, 0, 0)
        self.trajectory_library_panel = QFrame(TrajectoryPanel)
        self.trajectory_library_panel.setObjectName(u"trajectory_library_panel")
        self.trajectory_library_panel.setMinimumSize(QSize(212, 0))
        self.trajectory_library_panel.setMaximumSize(QSize(280, 16777215))
        self.trajectory_library_layout = QVBoxLayout(self.trajectory_library_panel)
        self.trajectory_library_layout.setSpacing(10)
        self.trajectory_library_layout.setObjectName(u"trajectory_library_layout")
        self.trajectory_library_layout.setContentsMargins(12, 12, 12, 12)
        self.trajectory_library_header = QHBoxLayout()
        self.trajectory_library_header.setSpacing(10)
        self.trajectory_library_header.setObjectName(u"trajectory_library_header")
        self.trajectory_library_header.setContentsMargins(0, 0, 0, 0)
        self.trajectory_library_title = QLabel(self.trajectory_library_panel)
        self.trajectory_library_title.setObjectName(u"trajectory_library_title")
        self.trajectory_library_title.setWordWrap(True)

        self.trajectory_library_header.addWidget(self.trajectory_library_title)

        self.trajectory_refresh_button = QPushButton(self.trajectory_library_panel)
        self.trajectory_refresh_button.setObjectName(u"trajectory_refresh_button")

        self.trajectory_library_header.addWidget(self.trajectory_refresh_button)

        self.trajectory_library_header.setStretch(0, 1)

        self.trajectory_library_layout.addLayout(self.trajectory_library_header)

        self.trajectory_library_count = QLabel(self.trajectory_library_panel)
        self.trajectory_library_count.setObjectName(u"trajectory_library_count")
        self.trajectory_library_count.setWordWrap(True)

        self.trajectory_library_layout.addWidget(self.trajectory_library_count)

        self.trajectory_saved_list = QListWidget(self.trajectory_library_panel)
        self.trajectory_saved_list.setObjectName(u"trajectory_saved_list")
        self.trajectory_saved_list.setWordWrap(True)
        self.trajectory_saved_list.setSelectionMode(QAbstractItemView.SingleSelection)

        self.trajectory_library_layout.addWidget(self.trajectory_saved_list)

        self.trajectory_import_group = QGroupBox(self.trajectory_library_panel)
        self.trajectory_import_group.setObjectName(u"trajectory_import_group")
        self.trajectory_import_layout = QVBoxLayout(self.trajectory_import_group)
        self.trajectory_import_layout.setSpacing(8)
        self.trajectory_import_layout.setObjectName(u"trajectory_import_layout")
        self.trajectory_import_layout.setContentsMargins(8, 8, 8, 8)
        self.trajectory_import_json_button = QPushButton(self.trajectory_import_group)
        self.trajectory_import_json_button.setObjectName(u"trajectory_import_json_button")

        self.trajectory_import_layout.addWidget(self.trajectory_import_json_button)

        self.trajectory_episode_row = QHBoxLayout()
        self.trajectory_episode_row.setSpacing(10)
        self.trajectory_episode_row.setObjectName(u"trajectory_episode_row")
        self.trajectory_episode_row.setContentsMargins(0, 0, 0, 0)
        self.trajectory_episode_label = QLabel(self.trajectory_import_group)
        self.trajectory_episode_label.setObjectName(u"trajectory_episode_label")
        self.trajectory_episode_label.setWordWrap(True)

        self.trajectory_episode_row.addWidget(self.trajectory_episode_label)

        self.trajectory_episode_spin = QSpinBox(self.trajectory_import_group)
        self.trajectory_episode_spin.setObjectName(u"trajectory_episode_spin")
        self.trajectory_episode_spin.setMaximum(1000000)

        self.trajectory_episode_row.addWidget(self.trajectory_episode_spin)


        self.trajectory_import_layout.addLayout(self.trajectory_episode_row)

        self.trajectory_import_episode_button = QPushButton(self.trajectory_import_group)
        self.trajectory_import_episode_button.setObjectName(u"trajectory_import_episode_button")

        self.trajectory_import_layout.addWidget(self.trajectory_import_episode_button)

        self.trajectory_import_hint = QLabel(self.trajectory_import_group)
        self.trajectory_import_hint.setObjectName(u"trajectory_import_hint")
        self.trajectory_import_hint.setWordWrap(True)

        self.trajectory_import_layout.addWidget(self.trajectory_import_hint)


        self.trajectory_library_layout.addWidget(self.trajectory_import_group)


        self.trajectory_root_layout.addWidget(self.trajectory_library_panel)

        self.trajectory_workspace = QWidget(TrajectoryPanel)
        self.trajectory_workspace.setObjectName(u"trajectory_workspace")
        self.trajectory_workspace_layout = QVBoxLayout(self.trajectory_workspace)
        self.trajectory_workspace_layout.setSpacing(12)
        self.trajectory_workspace_layout.setObjectName(u"trajectory_workspace_layout")
        self.trajectory_workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.trajectory_content_scroll = QScrollArea(self.trajectory_workspace)
        self.trajectory_content_scroll.setObjectName(u"trajectory_content_scroll")
        self.trajectory_content_scroll.setWidgetResizable(True)
        self.trajectory_content_scroll.setFrameShape(QFrame.NoFrame)
        self.trajectory_content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.trajectory_content = QWidget()
        self.trajectory_content.setObjectName(u"trajectory_content")
        self.trajectory_content.setGeometry(QRect(0, 0, 860, 520))
        self.trajectory_content_layout = QHBoxLayout(self.trajectory_content)
        self.trajectory_content_layout.setSpacing(12)
        self.trajectory_content_layout.setObjectName(u"trajectory_content_layout")
        self.trajectory_content_layout.setContentsMargins(0, 0, 0, 0)
        self.trajectory_center_stack = QStackedWidget(self.trajectory_content)
        self.trajectory_center_stack.setObjectName(u"trajectory_center_stack")
        self.trajectory_record_center = QFrame()
        self.trajectory_record_center.setObjectName(u"trajectory_record_center")
        self.trajectory_record_center_layout = QVBoxLayout(self.trajectory_record_center)
        self.trajectory_record_center_layout.setSpacing(16)
        self.trajectory_record_center_layout.setObjectName(u"trajectory_record_center_layout")
        self.trajectory_record_center_layout.setContentsMargins(18, 18, 18, 18)
        self.trajectory_record_title = QLabel(self.trajectory_record_center)
        self.trajectory_record_title.setObjectName(u"trajectory_record_title")
        self.trajectory_record_title.setWordWrap(True)

        self.trajectory_record_center_layout.addWidget(self.trajectory_record_title)

        self.trajectory_record_indicator = QLabel(self.trajectory_record_center)
        self.trajectory_record_indicator.setObjectName(u"trajectory_record_indicator")
        self.trajectory_record_indicator.setWordWrap(True)

        self.trajectory_record_center_layout.addWidget(self.trajectory_record_indicator)

        self.trajectory_status_label = QLabel(self.trajectory_record_center)
        self.trajectory_status_label.setObjectName(u"trajectory_status_label")
        self.trajectory_status_label.setWordWrap(True)

        self.trajectory_record_center_layout.addWidget(self.trajectory_status_label)

        self.trajectory_record_metrics = QHBoxLayout()
        self.trajectory_record_metrics.setSpacing(10)
        self.trajectory_record_metrics.setObjectName(u"trajectory_record_metrics")
        self.trajectory_record_metrics.setContentsMargins(0, 0, 0, 0)
        self.trajectory_frames_metric = QWidget(self.trajectory_record_center)
        self.trajectory_frames_metric.setObjectName(u"trajectory_frames_metric")
        self.trajectory_frames_layout = QVBoxLayout(self.trajectory_frames_metric)
        self.trajectory_frames_layout.setSpacing(4)
        self.trajectory_frames_layout.setObjectName(u"trajectory_frames_layout")
        self.trajectory_frames_layout.setContentsMargins(0, 0, 0, 0)
        self.trajectory_frames_label = QLabel(self.trajectory_frames_metric)
        self.trajectory_frames_label.setObjectName(u"trajectory_frames_label")
        self.trajectory_frames_label.setWordWrap(True)

        self.trajectory_frames_layout.addWidget(self.trajectory_frames_label)

        self.trajectory_frames_value = QLabel(self.trajectory_frames_metric)
        self.trajectory_frames_value.setObjectName(u"trajectory_frames_value")
        self.trajectory_frames_value.setWordWrap(True)

        self.trajectory_frames_layout.addWidget(self.trajectory_frames_value)


        self.trajectory_record_metrics.addWidget(self.trajectory_frames_metric)

        self.trajectory_elapsed_metric = QWidget(self.trajectory_record_center)
        self.trajectory_elapsed_metric.setObjectName(u"trajectory_elapsed_metric")
        self.trajectory_elapsed_layout = QVBoxLayout(self.trajectory_elapsed_metric)
        self.trajectory_elapsed_layout.setSpacing(4)
        self.trajectory_elapsed_layout.setObjectName(u"trajectory_elapsed_layout")
        self.trajectory_elapsed_layout.setContentsMargins(0, 0, 0, 0)
        self.trajectory_elapsed_label = QLabel(self.trajectory_elapsed_metric)
        self.trajectory_elapsed_label.setObjectName(u"trajectory_elapsed_label")
        self.trajectory_elapsed_label.setWordWrap(True)

        self.trajectory_elapsed_layout.addWidget(self.trajectory_elapsed_label)

        self.trajectory_elapsed_value = QLabel(self.trajectory_elapsed_metric)
        self.trajectory_elapsed_value.setObjectName(u"trajectory_elapsed_value")
        self.trajectory_elapsed_value.setWordWrap(True)

        self.trajectory_elapsed_layout.addWidget(self.trajectory_elapsed_value)


        self.trajectory_record_metrics.addWidget(self.trajectory_elapsed_metric)

        self.trajectory_record_metrics.setStretch(0, 1)
        self.trajectory_record_metrics.setStretch(1, 1)

        self.trajectory_record_center_layout.addLayout(self.trajectory_record_metrics)

        self.trajectory_record_context = QLabel(self.trajectory_record_center)
        self.trajectory_record_context.setObjectName(u"trajectory_record_context")
        self.trajectory_record_context.setWordWrap(True)

        self.trajectory_record_center_layout.addWidget(self.trajectory_record_context)

        self.trajectory_record_guidance = QLabel(self.trajectory_record_center)
        self.trajectory_record_guidance.setObjectName(u"trajectory_record_guidance")
        self.trajectory_record_guidance.setWordWrap(True)

        self.trajectory_record_center_layout.addWidget(self.trajectory_record_guidance)

        self.trajectory_record_space = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.trajectory_record_center_layout.addItem(self.trajectory_record_space)

        self.trajectory_center_stack.addWidget(self.trajectory_record_center)
        self.trajectory_replay_center = QFrame()
        self.trajectory_replay_center.setObjectName(u"trajectory_replay_center")
        self.trajectory_replay_center_layout = QVBoxLayout(self.trajectory_replay_center)
        self.trajectory_replay_center_layout.setSpacing(10)
        self.trajectory_replay_center_layout.setObjectName(u"trajectory_replay_center_layout")
        self.trajectory_replay_center_layout.setContentsMargins(14, 14, 14, 14)
        self.trajectory_preview_summary = QLabel(self.trajectory_replay_center)
        self.trajectory_preview_summary.setObjectName(u"trajectory_preview_summary")
        self.trajectory_preview_summary.setWordWrap(True)

        self.trajectory_replay_center_layout.addWidget(self.trajectory_preview_summary)

        self.trajectory_preview_hint = QLabel(self.trajectory_replay_center)
        self.trajectory_preview_hint.setObjectName(u"trajectory_preview_hint")
        self.trajectory_preview_hint.setWordWrap(True)

        self.trajectory_replay_center_layout.addWidget(self.trajectory_preview_hint)

        self.trajectory_preview_warnings = QLabel(self.trajectory_replay_center)
        self.trajectory_preview_warnings.setObjectName(u"trajectory_preview_warnings")
        self.trajectory_preview_warnings.setWordWrap(True)

        self.trajectory_replay_center_layout.addWidget(self.trajectory_preview_warnings)

        self.trajectory_preview_tabs = QTabWidget(self.trajectory_replay_center)
        self.trajectory_preview_tabs.setObjectName(u"trajectory_preview_tabs")
        self.trajectory_preview_overview = QWidget()
        self.trajectory_preview_overview.setObjectName(u"trajectory_preview_overview")
        self.trajectory_overview_layout = QVBoxLayout(self.trajectory_preview_overview)
        self.trajectory_overview_layout.setSpacing(8)
        self.trajectory_overview_layout.setObjectName(u"trajectory_overview_layout")
        self.trajectory_overview_layout.setContentsMargins(4, 4, 4, 4)
        self.trajectory_joint_table = QTableWidget(self.trajectory_preview_overview)
        if (self.trajectory_joint_table.columnCount() < 5):
            self.trajectory_joint_table.setColumnCount(5)
        __qtablewidgetitem = QTableWidgetItem()
        self.trajectory_joint_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.trajectory_joint_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.trajectory_joint_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.trajectory_joint_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.trajectory_joint_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        if (self.trajectory_joint_table.rowCount() < 6):
            self.trajectory_joint_table.setRowCount(6)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.trajectory_joint_table.setVerticalHeaderItem(0, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.trajectory_joint_table.setVerticalHeaderItem(1, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.trajectory_joint_table.setVerticalHeaderItem(2, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.trajectory_joint_table.setVerticalHeaderItem(3, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.trajectory_joint_table.setVerticalHeaderItem(4, __qtablewidgetitem9)
        __qtablewidgetitem10 = QTableWidgetItem()
        self.trajectory_joint_table.setVerticalHeaderItem(5, __qtablewidgetitem10)
        self.trajectory_joint_table.setObjectName(u"trajectory_joint_table")
        self.trajectory_joint_table.setRowCount(6)
        self.trajectory_joint_table.setColumnCount(5)
        self.trajectory_joint_table.setAlternatingRowColors(True)
        self.trajectory_joint_table.setMinimumSize(QSize(0, 236))
        self.trajectory_joint_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.trajectory_joint_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.trajectory_joint_table.setFocusPolicy(Qt.NoFocus)

        self.trajectory_overview_layout.addWidget(self.trajectory_joint_table)

        self.trajectory_tcp_hand_info = QLabel(self.trajectory_preview_overview)
        self.trajectory_tcp_hand_info.setObjectName(u"trajectory_tcp_hand_info")
        self.trajectory_tcp_hand_info.setWordWrap(True)

        self.trajectory_overview_layout.addWidget(self.trajectory_tcp_hand_info)

        self.trajectory_preview_tabs.addTab(self.trajectory_preview_overview, "")
        self.trajectory_preview_details = QWidget()
        self.trajectory_preview_details.setObjectName(u"trajectory_preview_details")
        self.trajectory_details_layout = QVBoxLayout(self.trajectory_preview_details)
        self.trajectory_details_layout.setSpacing(10)
        self.trajectory_details_layout.setObjectName(u"trajectory_details_layout")
        self.trajectory_details_layout.setContentsMargins(4, 4, 4, 4)
        self.trajectory_preview_text = QPlainTextEdit(self.trajectory_preview_details)
        self.trajectory_preview_text.setObjectName(u"trajectory_preview_text")
        self.trajectory_preview_text.setReadOnly(True)

        self.trajectory_details_layout.addWidget(self.trajectory_preview_text)

        self.trajectory_preview_tabs.addTab(self.trajectory_preview_details, "")

        self.trajectory_replay_center_layout.addWidget(self.trajectory_preview_tabs)

        self.trajectory_replay_center_layout.setStretch(3, 1)
        self.trajectory_center_stack.addWidget(self.trajectory_replay_center)

        self.trajectory_content_layout.addWidget(self.trajectory_center_stack)

        self.trajectory_parameters_stack = QStackedWidget(self.trajectory_content)
        self.trajectory_parameters_stack.setObjectName(u"trajectory_parameters_stack")
        self.trajectory_parameters_stack.setMinimumSize(QSize(210, 0))
        self.trajectory_parameters_stack.setMaximumSize(QSize(244, 16777215))
        self.trajectory_record_parameters = QFrame()
        self.trajectory_record_parameters.setObjectName(u"trajectory_record_parameters")
        self.trajectory_record_parameters_layout = QVBoxLayout(self.trajectory_record_parameters)
        self.trajectory_record_parameters_layout.setSpacing(12)
        self.trajectory_record_parameters_layout.setObjectName(u"trajectory_record_parameters_layout")
        self.trajectory_record_parameters_layout.setContentsMargins(14, 14, 14, 14)
        self.trajectory_record_parameters_title = QLabel(self.trajectory_record_parameters)
        self.trajectory_record_parameters_title.setObjectName(u"trajectory_record_parameters_title")
        self.trajectory_record_parameters_title.setWordWrap(True)

        self.trajectory_record_parameters_layout.addWidget(self.trajectory_record_parameters_title)

        self.trajectory_record_name_label = QLabel(self.trajectory_record_parameters)
        self.trajectory_record_name_label.setObjectName(u"trajectory_record_name_label")
        self.trajectory_record_name_label.setWordWrap(True)

        self.trajectory_record_parameters_layout.addWidget(self.trajectory_record_name_label)

        self.trajectory_record_name = QLineEdit(self.trajectory_record_parameters)
        self.trajectory_record_name.setObjectName(u"trajectory_record_name")

        self.trajectory_record_parameters_layout.addWidget(self.trajectory_record_name)

        self.trajectory_record_name_hint = QLabel(self.trajectory_record_parameters)
        self.trajectory_record_name_hint.setObjectName(u"trajectory_record_name_hint")
        self.trajectory_record_name_hint.setWordWrap(True)

        self.trajectory_record_parameters_layout.addWidget(self.trajectory_record_name_hint)

        self.trajectory_record_parameters_space = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.trajectory_record_parameters_layout.addItem(self.trajectory_record_parameters_space)

        self.trajectory_parameters_stack.addWidget(self.trajectory_record_parameters)
        self.trajectory_replay_parameters = QFrame()
        self.trajectory_replay_parameters.setObjectName(u"trajectory_replay_parameters")
        self.trajectory_replay_parameters_layout = QVBoxLayout(self.trajectory_replay_parameters)
        self.trajectory_replay_parameters_layout.setSpacing(12)
        self.trajectory_replay_parameters_layout.setObjectName(u"trajectory_replay_parameters_layout")
        self.trajectory_replay_parameters_layout.setContentsMargins(14, 14, 14, 14)
        self.trajectory_replay_parameters_title = QLabel(self.trajectory_replay_parameters)
        self.trajectory_replay_parameters_title.setObjectName(u"trajectory_replay_parameters_title")
        self.trajectory_replay_parameters_title.setWordWrap(True)

        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_replay_parameters_title)

        self.trajectory_mode_label = QLabel(self.trajectory_replay_parameters)
        self.trajectory_mode_label.setObjectName(u"trajectory_mode_label")
        self.trajectory_mode_label.setWordWrap(True)

        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_mode_label)

        self.trajectory_mode_combo = QComboBox(self.trajectory_replay_parameters)
        self.trajectory_mode_combo.addItem("")
        self.trajectory_mode_combo.addItem("")
        self.trajectory_mode_combo.setObjectName(u"trajectory_mode_combo")

        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_mode_combo)

        self.trajectory_mode_hint = QLabel(self.trajectory_replay_parameters)
        self.trajectory_mode_hint.setObjectName(u"trajectory_mode_hint")
        self.trajectory_mode_hint.setWordWrap(True)

        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_mode_hint)

        self.trajectory_replay_values = QFormLayout()
        self.trajectory_replay_values.setSpacing(8)
        self.trajectory_replay_values.setObjectName(u"trajectory_replay_values")
        self.trajectory_replay_values.setContentsMargins(0, 0, 0, 0)
        self.trajectory_speed_label = QLabel(self.trajectory_replay_parameters)
        self.trajectory_speed_label.setObjectName(u"trajectory_speed_label")

        self.trajectory_replay_values.setWidget(0, QFormLayout.ItemRole.LabelRole, self.trajectory_speed_label)

        self.trajectory_speed_spin = QDoubleSpinBox(self.trajectory_replay_parameters)
        self.trajectory_speed_spin.setObjectName(u"trajectory_speed_spin")
        self.trajectory_speed_spin.setDecimals(2)
        self.trajectory_speed_spin.setMinimum(0.100000000000000)
        self.trajectory_speed_spin.setMaximum(2.000000000000000)
        self.trajectory_speed_spin.setSingleStep(0.100000000000000)
        self.trajectory_speed_spin.setValue(1.000000000000000)

        self.trajectory_replay_values.setWidget(0, QFormLayout.ItemRole.FieldRole, self.trajectory_speed_spin)

        self.trajectory_repeat_label = QLabel(self.trajectory_replay_parameters)
        self.trajectory_repeat_label.setObjectName(u"trajectory_repeat_label")

        self.trajectory_replay_values.setWidget(1, QFormLayout.ItemRole.LabelRole, self.trajectory_repeat_label)

        self.trajectory_repeat_spin = QSpinBox(self.trajectory_replay_parameters)
        self.trajectory_repeat_spin.setObjectName(u"trajectory_repeat_spin")
        self.trajectory_repeat_spin.setMinimum(1)
        self.trajectory_repeat_spin.setMaximum(1000)
        self.trajectory_repeat_spin.setValue(1)

        self.trajectory_replay_values.setWidget(1, QFormLayout.ItemRole.FieldRole, self.trajectory_repeat_spin)


        self.trajectory_replay_parameters_layout.addLayout(self.trajectory_replay_values)

        self.trajectory_channels_label = QLabel(self.trajectory_replay_parameters)
        self.trajectory_channels_label.setObjectName(u"trajectory_channels_label")
        self.trajectory_channels_label.setWordWrap(True)

        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_channels_label)

        self.trajectory_channels_layout = QHBoxLayout()
        self.trajectory_channels_layout.setSpacing(10)
        self.trajectory_channels_layout.setObjectName(u"trajectory_channels_layout")
        self.trajectory_channels_layout.setContentsMargins(0, 0, 0, 0)
        self.trajectory_arm_check = QCheckBox(self.trajectory_replay_parameters)
        self.trajectory_arm_check.setObjectName(u"trajectory_arm_check")
        self.trajectory_arm_check.setChecked(True)

        self.trajectory_channels_layout.addWidget(self.trajectory_arm_check)

        self.trajectory_hand_check = QCheckBox(self.trajectory_replay_parameters)
        self.trajectory_hand_check.setObjectName(u"trajectory_hand_check")
        self.trajectory_hand_check.setChecked(True)

        self.trajectory_channels_layout.addWidget(self.trajectory_hand_check)


        self.trajectory_replay_parameters_layout.addLayout(self.trajectory_channels_layout)

        self.trajectory_joint_group = QGroupBox(self.trajectory_replay_parameters)
        self.trajectory_joint_group.setObjectName(u"trajectory_joint_group")
        self.trajectory_joint_layout = QGridLayout(self.trajectory_joint_group)
        self.trajectory_joint_layout.setSpacing(8)
        self.trajectory_joint_layout.setObjectName(u"trajectory_joint_layout")
        self.trajectory_joint_layout.setContentsMargins(8, 8, 8, 8)
        self.trajectory_joint_checks_0 = QCheckBox(self.trajectory_joint_group)
        self.trajectory_joint_checks_0.setObjectName(u"trajectory_joint_checks_0")
        self.trajectory_joint_checks_0.setChecked(True)

        self.trajectory_joint_layout.addWidget(self.trajectory_joint_checks_0, 0, 0, 1, 1)

        self.trajectory_joint_checks_1 = QCheckBox(self.trajectory_joint_group)
        self.trajectory_joint_checks_1.setObjectName(u"trajectory_joint_checks_1")
        self.trajectory_joint_checks_1.setChecked(True)

        self.trajectory_joint_layout.addWidget(self.trajectory_joint_checks_1, 0, 1, 1, 1)

        self.trajectory_joint_checks_2 = QCheckBox(self.trajectory_joint_group)
        self.trajectory_joint_checks_2.setObjectName(u"trajectory_joint_checks_2")
        self.trajectory_joint_checks_2.setChecked(True)

        self.trajectory_joint_layout.addWidget(self.trajectory_joint_checks_2, 0, 2, 1, 1)

        self.trajectory_joint_checks_3 = QCheckBox(self.trajectory_joint_group)
        self.trajectory_joint_checks_3.setObjectName(u"trajectory_joint_checks_3")
        self.trajectory_joint_checks_3.setChecked(True)

        self.trajectory_joint_layout.addWidget(self.trajectory_joint_checks_3, 1, 0, 1, 1)

        self.trajectory_joint_checks_4 = QCheckBox(self.trajectory_joint_group)
        self.trajectory_joint_checks_4.setObjectName(u"trajectory_joint_checks_4")
        self.trajectory_joint_checks_4.setChecked(True)

        self.trajectory_joint_layout.addWidget(self.trajectory_joint_checks_4, 1, 1, 1, 1)

        self.trajectory_joint_checks_5 = QCheckBox(self.trajectory_joint_group)
        self.trajectory_joint_checks_5.setObjectName(u"trajectory_joint_checks_5")
        self.trajectory_joint_checks_5.setChecked(True)

        self.trajectory_joint_layout.addWidget(self.trajectory_joint_checks_5, 1, 2, 1, 1)


        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_joint_group)

        self.trajectory_replay_safety_hint = QLabel(self.trajectory_replay_parameters)
        self.trajectory_replay_safety_hint.setObjectName(u"trajectory_replay_safety_hint")
        self.trajectory_replay_safety_hint.setWordWrap(True)

        self.trajectory_replay_parameters_layout.addWidget(self.trajectory_replay_safety_hint)

        self.trajectory_replay_parameters_space = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.trajectory_replay_parameters_layout.addItem(self.trajectory_replay_parameters_space)

        self.trajectory_parameters_stack.addWidget(self.trajectory_replay_parameters)

        self.trajectory_content_layout.addWidget(self.trajectory_parameters_stack)

        self.trajectory_content_layout.setStretch(0, 1)
        self.trajectory_content_scroll.setWidget(self.trajectory_content)

        self.trajectory_workspace_layout.addWidget(self.trajectory_content_scroll)

        self.trajectory_actions_stack = QStackedWidget(self.trajectory_workspace)
        self.trajectory_actions_stack.setObjectName(u"trajectory_actions_stack")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.trajectory_actions_stack.sizePolicy().hasHeightForWidth())
        self.trajectory_actions_stack.setSizePolicy(sizePolicy)
        self.trajectory_record_actions = QFrame()
        self.trajectory_record_actions.setObjectName(u"trajectory_record_actions")
        self.trajectory_record_actions_layout = QHBoxLayout(self.trajectory_record_actions)
        self.trajectory_record_actions_layout.setSpacing(8)
        self.trajectory_record_actions_layout.setObjectName(u"trajectory_record_actions_layout")
        self.trajectory_record_actions_layout.setContentsMargins(10, 10, 10, 10)
        self.trajectory_record_action_hint = QLabel(self.trajectory_record_actions)
        self.trajectory_record_action_hint.setObjectName(u"trajectory_record_action_hint")
        self.trajectory_record_action_hint.setWordWrap(True)

        self.trajectory_record_actions_layout.addWidget(self.trajectory_record_action_hint)

        self.trajectory_record_action_space = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.trajectory_record_actions_layout.addItem(self.trajectory_record_action_space)

        self.trajectory_record_button = QPushButton(self.trajectory_record_actions)
        self.trajectory_record_button.setObjectName(u"trajectory_record_button")

        self.trajectory_record_actions_layout.addWidget(self.trajectory_record_button)

        self.trajectory_finish_button = QPushButton(self.trajectory_record_actions)
        self.trajectory_finish_button.setObjectName(u"trajectory_finish_button")

        self.trajectory_record_actions_layout.addWidget(self.trajectory_finish_button)

        self.trajectory_save_button = QPushButton(self.trajectory_record_actions)
        self.trajectory_save_button.setObjectName(u"trajectory_save_button")

        self.trajectory_record_actions_layout.addWidget(self.trajectory_save_button)

        self.trajectory_cancel_button = QPushButton(self.trajectory_record_actions)
        self.trajectory_cancel_button.setObjectName(u"trajectory_cancel_button")

        self.trajectory_record_actions_layout.addWidget(self.trajectory_cancel_button)

        self.trajectory_actions_stack.addWidget(self.trajectory_record_actions)
        self.trajectory_replay_actions = QFrame()
        self.trajectory_replay_actions.setObjectName(u"trajectory_replay_actions")
        self.trajectory_replay_actions_layout = QHBoxLayout(self.trajectory_replay_actions)
        self.trajectory_replay_actions_layout.setSpacing(8)
        self.trajectory_replay_actions_layout.setObjectName(u"trajectory_replay_actions_layout")
        self.trajectory_replay_actions_layout.setContentsMargins(10, 10, 10, 10)
        self.trajectory_replay_action_hint = QLabel(self.trajectory_replay_actions)
        self.trajectory_replay_action_hint.setObjectName(u"trajectory_replay_action_hint")
        self.trajectory_replay_action_hint.setWordWrap(True)

        self.trajectory_replay_actions_layout.addWidget(self.trajectory_replay_action_hint)

        self.trajectory_replay_action_space = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.trajectory_replay_actions_layout.addItem(self.trajectory_replay_action_space)

        self.trajectory_preview_button = QPushButton(self.trajectory_replay_actions)
        self.trajectory_preview_button.setObjectName(u"trajectory_preview_button")

        self.trajectory_replay_actions_layout.addWidget(self.trajectory_preview_button)

        self.trajectory_play_button = QPushButton(self.trajectory_replay_actions)
        self.trajectory_play_button.setObjectName(u"trajectory_play_button")

        self.trajectory_replay_actions_layout.addWidget(self.trajectory_play_button)

        self.trajectory_actions_stack.addWidget(self.trajectory_replay_actions)

        self.trajectory_workspace_layout.addWidget(self.trajectory_actions_stack)

        self.trajectory_workspace_layout.setStretch(0, 1)

        self.trajectory_root_layout.addWidget(self.trajectory_workspace)

        self.trajectory_root_layout.setStretch(1, 1)

        self.retranslateUi(TrajectoryPanel)

        self.trajectory_center_stack.setCurrentIndex(1)
        self.trajectory_preview_tabs.setCurrentIndex(0)
        self.trajectory_parameters_stack.setCurrentIndex(1)
        self.trajectory_actions_stack.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(TrajectoryPanel)
    # setupUi

    def retranslateUi(self, TrajectoryPanel):
        self.trajectory_library_panel.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_library_title.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8f68\u8ff9\u5e93", None))
        self.trajectory_library_title.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"sectionTitle", None))
        self.trajectory_refresh_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5237\u65b0", None))
        self.trajectory_refresh_button.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"quiet", None))
        self.trajectory_library_count.setText(QCoreApplication.translate("TrajectoryPanel", u"0 \u6761\u8f68\u8ff9", None))
        self.trajectory_library_count.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_saved_list.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"trajectoryLibrary", None))
        self.trajectory_import_group.setTitle(QCoreApplication.translate("TrajectoryPanel", u"\u5bfc\u5165\u8f68\u8ff9", None))
        self.trajectory_import_json_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5bfc\u5165\u65e7 JSON", None))
        self.trajectory_episode_label.setText(QCoreApplication.translate("TrajectoryPanel", u"Episode", None))
#if QT_CONFIG(tooltip)
        self.trajectory_episode_spin.setToolTip(QCoreApplication.translate("TrajectoryPanel", u"\u9009\u62e9\u8981\u4ece LeRobot \u6570\u636e\u96c6\u5bfc\u5165\u7684 Episode \u7d22\u5f15", None))
#endif // QT_CONFIG(tooltip)
        self.trajectory_import_episode_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5bfc\u5165 LeRobot Episode", None))
        self.trajectory_import_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5bfc\u5165\u540e\u5728\u5e93\u4e2d\u9009\u62e9\uff0c\u518d\u9884\u89c8\u8f68\u8ff9\u3002", None))
        self.trajectory_import_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_record_center.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_record_title.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f55\u5236\u5de5\u4f5c\u533a", None))
        self.trajectory_record_title.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"sectionTitle", None))
        self.trajectory_record_indicator.setText(QCoreApplication.translate("TrajectoryPanel", u"REC \u00b7 \u51c6\u5907\u5f55\u5236", None))
        self.trajectory_record_indicator.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"metricValue", None))
        self.trajectory_status_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u672a\u5f55\u5236 \u00b7 0 \u5e27 \u00b7 0.00 s", None))
        self.trajectory_status_label.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"stateHeadline", None))
        self.trajectory_frames_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5df2\u91c7\u96c6\u5e27\u6570", None))
        self.trajectory_frames_label.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"metricLabel", None))
        self.trajectory_frames_value.setText(QCoreApplication.translate("TrajectoryPanel", u"\u2014", None))
        self.trajectory_frames_value.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"metricValue", None))
        self.trajectory_elapsed_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f55\u5236\u65f6\u957f", None))
        self.trajectory_elapsed_label.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"metricLabel", None))
        self.trajectory_elapsed_value.setText(QCoreApplication.translate("TrajectoryPanel", u"\u2014", None))
        self.trajectory_elapsed_value.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"metricValue", None))
        self.trajectory_record_context.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8f93\u5165\u540d\u79f0\u540e\u5f00\u59cb\u8bb0\u5f55\u3002\u91c7\u96c6\u5f53\u524d\u63a7\u5236\u6d41\u7a0b\u4e2d\u7684\u673a\u5668\u4eba\u4e0e Hand \u72b6\u6001\u6216\u6307\u4ee4\u3002", None))
        self.trajectory_record_context.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_record_guidance.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f55\u5236\u671f\u95f4\u53ef\u7ee7\u7eed\u64cd\u4f5c\u9065\u64cd\u3002\u5b8c\u6210\u540e\u70b9\u51fb\u201c\u505c\u6b62\u5e76\u4fdd\u5b58\u201d\uff1b\u4fdd\u5b58\u5931\u8d25\u65f6\u53ef\u91cd\u8bd5\uff0c\u6216\u53d6\u6d88\u672c\u6b21\u8bb0\u5f55\u3002", None))
        self.trajectory_record_guidance.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_replay_center.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_preview_summary.setText(QCoreApplication.translate("TrajectoryPanel", u"\u9009\u62e9\u8f68\u8ff9\u4ee5\u67e5\u770b\u9884\u89c8", None))
        self.trajectory_preview_summary.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"sectionTitle", None))
        self.trajectory_preview_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u4ece\u5de6\u4fa7\u8f68\u8ff9\u5e93\u9009\u62e9\u4e00\u6761\u8f68\u8ff9\uff0c\u7136\u540e\u70b9\u51fb\u201c\u8bfb\u53d6\u9884\u89c8\u201d\u3002", None))
        self.trajectory_preview_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_preview_warnings.setText("")
        self.trajectory_preview_warnings.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"stateHeadline", None))
        ___qtablewidgetitem = self.trajectory_joint_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8d77\u70b9 (\u00b0)", None))
        ___qtablewidgetitem1 = self.trajectory_joint_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("TrajectoryPanel", u"\u7ec8\u70b9 (\u00b0)", None))
        ___qtablewidgetitem2 = self.trajectory_joint_table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8303\u56f4 (\u00b0)", None))
        ___qtablewidgetitem3 = self.trajectory_joint_table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5cf0\u503c\u901f\u5ea6 (\u00b0/s)", None))
        ___qtablewidgetitem4 = self.trajectory_joint_table.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("TrajectoryPanel", u"\u6700\u5927\u6b65\u957f (\u00b0)", None))
        ___qtablewidgetitem5 = self.trajectory_joint_table.verticalHeaderItem(0)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("TrajectoryPanel", u"J1", None))
        ___qtablewidgetitem6 = self.trajectory_joint_table.verticalHeaderItem(1)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("TrajectoryPanel", u"J2", None))
        ___qtablewidgetitem7 = self.trajectory_joint_table.verticalHeaderItem(2)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("TrajectoryPanel", u"J3", None))
        ___qtablewidgetitem8 = self.trajectory_joint_table.verticalHeaderItem(3)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("TrajectoryPanel", u"J4", None))
        ___qtablewidgetitem9 = self.trajectory_joint_table.verticalHeaderItem(4)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("TrajectoryPanel", u"J5", None))
        ___qtablewidgetitem10 = self.trajectory_joint_table.verticalHeaderItem(5)
        ___qtablewidgetitem10.setText(QCoreApplication.translate("TrajectoryPanel", u"J6", None))
        self.trajectory_tcp_hand_info.setText(QCoreApplication.translate("TrajectoryPanel", u"TCP / Hand\uff1a\u8bfb\u53d6\u9884\u89c8\u540e\u663e\u793a\u53ef\u7528\u8303\u56f4\u3002", None))
        self.trajectory_tcp_hand_info.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_preview_tabs.setTabText(self.trajectory_preview_tabs.indexOf(self.trajectory_preview_overview), QCoreApplication.translate("TrajectoryPanel", u"\u5173\u8282\u5bf9\u6bd4", None))
        self.trajectory_preview_text.setPlaceholderText(QCoreApplication.translate("TrajectoryPanel", u"\u8bfb\u53d6\u9884\u89c8\u540e\u663e\u793a\u539f\u59cb\u5355\u4f4d\u7684\u8be6\u7ec6\u7edf\u8ba1\u4e0e\u8b66\u544a\u3002", None))
        self.trajectory_preview_tabs.setTabText(self.trajectory_preview_tabs.indexOf(self.trajectory_preview_details), QCoreApplication.translate("TrajectoryPanel", u"\u53ea\u8bfb\u8be6\u60c5", None))
        self.trajectory_record_parameters.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_record_parameters_title.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f55\u5236\u53c2\u6570", None))
        self.trajectory_record_parameters_title.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"sectionTitle", None))
        self.trajectory_record_name_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8f68\u8ff9\u540d\u79f0", None))
        self.trajectory_record_name.setPlaceholderText(QCoreApplication.translate("TrajectoryPanel", u"\u4f8b\u5982 motor_pick_demo_01", None))
        self.trajectory_record_name_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u540d\u79f0\u7528\u4e8e\u5728\u8f68\u8ff9\u5e93\u4e2d\u8bc6\u522b\u672c\u6b21\u8bb0\u5f55\u3002\u5f00\u59cb\u540e\u540d\u79f0\u5c06\u9501\u5b9a\u3002", None))
        self.trajectory_record_name_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_replay_parameters.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_replay_parameters_title.setText(QCoreApplication.translate("TrajectoryPanel", u"\u56de\u653e\u53c2\u6570", None))
        self.trajectory_replay_parameters_title.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"sectionTitle", None))
        self.trajectory_mode_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5b9a\u4f4d\u6a21\u5f0f", None))
        self.trajectory_mode_combo.setItemText(0, QCoreApplication.translate("TrajectoryPanel", u"\u76f8\u5bf9 Relative", None))
        self.trajectory_mode_combo.setItemText(1, QCoreApplication.translate("TrajectoryPanel", u"\u7edd\u5bf9 Absolute", None))

#if QT_CONFIG(tooltip)
        self.trajectory_mode_combo.setToolTip(QCoreApplication.translate("TrajectoryPanel", u"\u76f8\u5bf9\uff1a\u4ece\u5f53\u524d\u4f4d\u7f6e\u590d\u73b0\u4f4d\u79fb\uff1b\u7edd\u5bf9\uff1a\u5148\u7528 3 \u79d2\u8fc7\u6e21\u5230\u8f68\u8ff9\u8d77\u70b9", None))
#endif // QT_CONFIG(tooltip)
        self.trajectory_mode_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u76f8\u5bf9\uff1a\u590d\u73b0\u4f4d\u79fb\n"
"\u7edd\u5bf9\uff1a\u7528 3 \u79d2\u8fc7\u6e21\u81f3\u8d77\u70b9", None))
        self.trajectory_mode_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_speed_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u901f\u5ea6\u500d\u7387", None))
        self.trajectory_speed_spin.setSuffix(QCoreApplication.translate("TrajectoryPanel", u"\u00d7", None))
        self.trajectory_repeat_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u91cd\u590d\u6b21\u6570", None))
        self.trajectory_channels_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u56de\u653e\u901a\u9053", None))
        self.trajectory_arm_check.setText(QCoreApplication.translate("TrajectoryPanel", u"Arm", None))
        self.trajectory_hand_check.setText(QCoreApplication.translate("TrajectoryPanel", u"Hand", None))
        self.trajectory_joint_group.setTitle(QCoreApplication.translate("TrajectoryPanel", u"\u5173\u8282\u63a9\u7801\uff08\u9ad8\u7ea7\uff09", None))
        self.trajectory_joint_checks_0.setText(QCoreApplication.translate("TrajectoryPanel", u"J1", None))
        self.trajectory_joint_checks_1.setText(QCoreApplication.translate("TrajectoryPanel", u"J2", None))
        self.trajectory_joint_checks_2.setText(QCoreApplication.translate("TrajectoryPanel", u"J3", None))
        self.trajectory_joint_checks_3.setText(QCoreApplication.translate("TrajectoryPanel", u"J4", None))
        self.trajectory_joint_checks_4.setText(QCoreApplication.translate("TrajectoryPanel", u"J5", None))
        self.trajectory_joint_checks_5.setText(QCoreApplication.translate("TrajectoryPanel", u"J6", None))
        self.trajectory_replay_safety_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u4ec5\u56de\u653e\u52fe\u9009\u7684\u901a\u9053\u4e0e\u5173\u8282\u3002Hand \u9700\u8981\u5df2\u8fde\u63a5\uff1b\u505c\u6b62\u8fd0\u52a8\u4e0e\u6025\u505c\u59cb\u7ec8\u4f4d\u4e8e\u5168\u5c40\u64cd\u4f5c\u533a\u3002", None))
        self.trajectory_replay_safety_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_record_actions.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_record_action_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8bb0\u5f55\u5f53\u524d\u64cd\u4f5c\u6d41\u7a0b", None))
        self.trajectory_record_action_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_record_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f00\u59cb\u8bb0\u5f55", None))
        self.trajectory_record_button.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"primary", None))
        self.trajectory_finish_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u505c\u6b62\u5e76\u4fdd\u5b58", None))
        self.trajectory_finish_button.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"primary", None))
        self.trajectory_save_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u91cd\u8bd5\u4fdd\u5b58", None))
        self.trajectory_cancel_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u53d6\u6d88\u8bb0\u5f55", None))
        self.trajectory_cancel_button.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"quiet", None))
        self.trajectory_replay_actions.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"surfacePanel", None))
        self.trajectory_replay_action_hint.setText(QCoreApplication.translate("TrajectoryPanel", u"\u9884\u89c8\u4ec5\u8bfb\u53d6\u7edf\u8ba1\u4fe1\u606f\uff0c\u4e0d\u9a71\u52a8\u673a\u5668\u4eba\u3002", None))
        self.trajectory_replay_action_hint.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"mutedText", None))
        self.trajectory_preview_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u8bfb\u53d6\u9884\u89c8", None))
        self.trajectory_play_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f00\u59cb\u56de\u653e", None))
        self.trajectory_play_button.setProperty(u"role", QCoreApplication.translate("TrajectoryPanel", u"primary", None))
        pass
    # retranslateUi
