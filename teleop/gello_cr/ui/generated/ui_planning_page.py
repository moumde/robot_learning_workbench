# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'planning_page.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDoubleSpinBox,
    QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_PlanningPanel(object):
    def setupUi(self, PlanningPanel):
        if not PlanningPanel.objectName():
            PlanningPanel.setObjectName(u"PlanningPanel")
        PlanningPanel.resize(860, 460)
        PlanningPanel.setProperty(u"density", u"compact")
        self.planning_page_layout = QVBoxLayout(PlanningPanel)
        self.planning_page_layout.setSpacing(8)
        self.planning_page_layout.setObjectName(u"planning_page_layout")
        self.planning_page_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_workspace_layout = QHBoxLayout()
        self.planning_workspace_layout.setSpacing(10)
        self.planning_workspace_layout.setObjectName(u"planning_workspace_layout")
        self.planning_editor_panel = QWidget(PlanningPanel)
        self.planning_editor_panel.setObjectName(u"planning_editor_panel")
        self.planning_editor_layout = QVBoxLayout(self.planning_editor_panel)
        self.planning_editor_layout.setSpacing(4)
        self.planning_editor_layout.setObjectName(u"planning_editor_layout")
        self.planning_editor_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_result_state = QLabel(self.planning_editor_panel)
        self.planning_result_state.setObjectName(u"planning_result_state")
        self.planning_result_state.setWordWrap(True)
        self.planning_result_state.setProperty(u"role", u"sectionTitle")

        self.planning_editor_layout.addWidget(self.planning_result_state)

        self.planning_result_summary = QLabel(self.planning_editor_panel)
        self.planning_result_summary.setObjectName(u"planning_result_summary")
        self.planning_result_summary.setWordWrap(True)
        self.planning_result_summary.setProperty(u"role", u"mutedText")

        self.planning_editor_layout.addWidget(self.planning_result_summary)

        self.planning_editor_tabs = QTabWidget(self.planning_editor_panel)
        self.planning_editor_tabs.setObjectName(u"planning_editor_tabs")
        self.planning_targets_tab = QWidget()
        self.planning_targets_tab.setObjectName(u"planning_targets_tab")
        self.planning_targets_tab_layout = QVBoxLayout(self.planning_targets_tab)
        self.planning_targets_tab_layout.setObjectName(u"planning_targets_tab_layout")
        self.planning_targets_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_editor_scroll = QScrollArea(self.planning_targets_tab)
        self.planning_editor_scroll.setObjectName(u"planning_editor_scroll")
        self.planning_editor_scroll.setFrameShape(QFrame.NoFrame)
        self.planning_editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.planning_editor_scroll.setWidgetResizable(True)
        self.planning_editor_content = QWidget()
        self.planning_editor_content.setObjectName(u"planning_editor_content")
        self.planning_target_content_layout = QVBoxLayout(self.planning_editor_content)
        self.planning_target_content_layout.setSpacing(6)
        self.planning_target_content_layout.setObjectName(u"planning_target_content_layout")
        self.planning_target_content_layout.setContentsMargins(8, 8, 8, 8)
        self.planning_target_group = QGroupBox(self.planning_editor_content)
        self.planning_target_group.setObjectName(u"planning_target_group")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.planning_target_group.sizePolicy().hasHeightForWidth())
        self.planning_target_group.setSizePolicy(sizePolicy)
        self.planning_target_grid = QGridLayout(self.planning_target_group)
        self.planning_target_grid.setObjectName(u"planning_target_grid")
        self.planning_target_grid.setHorizontalSpacing(8)
        self.planning_target_grid.setVerticalSpacing(4)
        self.planning_target_grid.setContentsMargins(6, 4, 6, 4)
        self.planning_target_labels_0 = QLabel(self.planning_target_group)
        self.planning_target_labels_0.setObjectName(u"planning_target_labels_0")

        self.planning_target_grid.addWidget(self.planning_target_labels_0, 0, 0, 1, 1)

        self.planning_target_spins_0 = QDoubleSpinBox(self.planning_target_group)
        self.planning_target_spins_0.setObjectName(u"planning_target_spins_0")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.planning_target_spins_0.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_0.setSizePolicy(sizePolicy1)
        self.planning_target_spins_0.setMinimumSize(QSize(80, 0))
        self.planning_target_spins_0.setDecimals(3)
        self.planning_target_spins_0.setMinimum(-100000.000000000000000)
        self.planning_target_spins_0.setMaximum(100000.000000000000000)

        self.planning_target_grid.addWidget(self.planning_target_spins_0, 0, 1, 1, 1)

        self.planning_target_labels_1 = QLabel(self.planning_target_group)
        self.planning_target_labels_1.setObjectName(u"planning_target_labels_1")

        self.planning_target_grid.addWidget(self.planning_target_labels_1, 0, 2, 1, 1)

        self.planning_target_spins_1 = QDoubleSpinBox(self.planning_target_group)
        self.planning_target_spins_1.setObjectName(u"planning_target_spins_1")
        sizePolicy1.setHeightForWidth(self.planning_target_spins_1.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_1.setSizePolicy(sizePolicy1)
        self.planning_target_spins_1.setMinimumSize(QSize(80, 0))
        self.planning_target_spins_1.setDecimals(3)
        self.planning_target_spins_1.setMinimum(-100000.000000000000000)
        self.planning_target_spins_1.setMaximum(100000.000000000000000)

        self.planning_target_grid.addWidget(self.planning_target_spins_1, 0, 3, 1, 1)

        self.planning_target_labels_2 = QLabel(self.planning_target_group)
        self.planning_target_labels_2.setObjectName(u"planning_target_labels_2")

        self.planning_target_grid.addWidget(self.planning_target_labels_2, 0, 4, 1, 1)

        self.planning_target_spins_2 = QDoubleSpinBox(self.planning_target_group)
        self.planning_target_spins_2.setObjectName(u"planning_target_spins_2")
        sizePolicy1.setHeightForWidth(self.planning_target_spins_2.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_2.setSizePolicy(sizePolicy1)
        self.planning_target_spins_2.setMinimumSize(QSize(80, 0))
        self.planning_target_spins_2.setDecimals(3)
        self.planning_target_spins_2.setMinimum(-100000.000000000000000)
        self.planning_target_spins_2.setMaximum(100000.000000000000000)

        self.planning_target_grid.addWidget(self.planning_target_spins_2, 0, 5, 1, 1)

        self.planning_target_labels_3 = QLabel(self.planning_target_group)
        self.planning_target_labels_3.setObjectName(u"planning_target_labels_3")

        self.planning_target_grid.addWidget(self.planning_target_labels_3, 1, 0, 1, 1)

        self.planning_target_spins_3 = QDoubleSpinBox(self.planning_target_group)
        self.planning_target_spins_3.setObjectName(u"planning_target_spins_3")
        sizePolicy1.setHeightForWidth(self.planning_target_spins_3.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_3.setSizePolicy(sizePolicy1)
        self.planning_target_spins_3.setMinimumSize(QSize(80, 0))
        self.planning_target_spins_3.setDecimals(3)
        self.planning_target_spins_3.setMinimum(-100000.000000000000000)
        self.planning_target_spins_3.setMaximum(100000.000000000000000)

        self.planning_target_grid.addWidget(self.planning_target_spins_3, 1, 1, 1, 1)

        self.planning_target_labels_4 = QLabel(self.planning_target_group)
        self.planning_target_labels_4.setObjectName(u"planning_target_labels_4")

        self.planning_target_grid.addWidget(self.planning_target_labels_4, 1, 2, 1, 1)

        self.planning_target_spins_4 = QDoubleSpinBox(self.planning_target_group)
        self.planning_target_spins_4.setObjectName(u"planning_target_spins_4")
        sizePolicy1.setHeightForWidth(self.planning_target_spins_4.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_4.setSizePolicy(sizePolicy1)
        self.planning_target_spins_4.setMinimumSize(QSize(80, 0))
        self.planning_target_spins_4.setDecimals(3)
        self.planning_target_spins_4.setMinimum(-100000.000000000000000)
        self.planning_target_spins_4.setMaximum(100000.000000000000000)

        self.planning_target_grid.addWidget(self.planning_target_spins_4, 1, 3, 1, 1)

        self.planning_target_labels_5 = QLabel(self.planning_target_group)
        self.planning_target_labels_5.setObjectName(u"planning_target_labels_5")

        self.planning_target_grid.addWidget(self.planning_target_labels_5, 1, 4, 1, 1)

        self.planning_target_spins_5 = QDoubleSpinBox(self.planning_target_group)
        self.planning_target_spins_5.setObjectName(u"planning_target_spins_5")
        sizePolicy1.setHeightForWidth(self.planning_target_spins_5.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_5.setSizePolicy(sizePolicy1)
        self.planning_target_spins_5.setMinimumSize(QSize(80, 0))
        self.planning_target_spins_5.setDecimals(3)
        self.planning_target_spins_5.setMinimum(-100000.000000000000000)
        self.planning_target_spins_5.setMaximum(100000.000000000000000)

        self.planning_target_grid.addWidget(self.planning_target_spins_5, 1, 5, 1, 1)

        self.planning_target_grid.setColumnStretch(1, 1)
        self.planning_target_grid.setColumnStretch(3, 1)
        self.planning_target_grid.setColumnStretch(5, 1)

        self.planning_target_content_layout.addWidget(self.planning_target_group)

        self.planning_waypoint_panel = QWidget(self.planning_editor_content)
        self.planning_waypoint_panel.setObjectName(u"planning_waypoint_panel")
        self.planning_waypoint_layout = QVBoxLayout(self.planning_waypoint_panel)
        self.planning_waypoint_layout.setSpacing(4)
        self.planning_waypoint_layout.setObjectName(u"planning_waypoint_layout")
        self.planning_waypoint_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_waypoint_heading = QLabel(self.planning_waypoint_panel)
        self.planning_waypoint_heading.setObjectName(u"planning_waypoint_heading")
        self.planning_waypoint_heading.setWordWrap(False)
        self.planning_waypoint_heading.setProperty(u"role", u"previewTitle")

        self.planning_waypoint_layout.addWidget(self.planning_waypoint_heading)

        self.planning_waypoint_tools = QHBoxLayout()
        self.planning_waypoint_tools.setSpacing(4)
        self.planning_waypoint_tools.setObjectName(u"planning_waypoint_tools")
        self.planning_add_button = QPushButton(self.planning_waypoint_panel)
        self.planning_add_button.setObjectName(u"planning_add_button")

        self.planning_waypoint_tools.addWidget(self.planning_add_button)

        self.planning_delete_button = QPushButton(self.planning_waypoint_panel)
        self.planning_delete_button.setObjectName(u"planning_delete_button")

        self.planning_waypoint_tools.addWidget(self.planning_delete_button)

        self.planning_up_button = QPushButton(self.planning_waypoint_panel)
        self.planning_up_button.setObjectName(u"planning_up_button")

        self.planning_waypoint_tools.addWidget(self.planning_up_button)

        self.planning_down_button = QPushButton(self.planning_waypoint_panel)
        self.planning_down_button.setObjectName(u"planning_down_button")

        self.planning_waypoint_tools.addWidget(self.planning_down_button)

        self.planning_waypoint_tools.setStretch(0, 1)

        self.planning_waypoint_layout.addLayout(self.planning_waypoint_tools)

        self.planning_table = QTableWidget(self.planning_waypoint_panel)
        if (self.planning_table.columnCount() < 9):
            self.planning_table.setColumnCount(9)
        __qtablewidgetitem = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(7, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.planning_table.setHorizontalHeaderItem(8, __qtablewidgetitem8)
        self.planning_table.setObjectName(u"planning_table")
        self.planning_table.setMinimumSize(QSize(0, 110))
        self.planning_table.setAlternatingRowColors(True)
        self.planning_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.planning_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.planning_table.setEditTriggers(QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed|QAbstractItemView.AnyKeyPressed)
        self.planning_table.setRowCount(0)
        self.planning_table.setColumnCount(9)
        self.planning_table.horizontalHeader().setMinimumSectionSize(64)
        self.planning_table.horizontalHeader().setDefaultSectionSize(78)
        self.planning_table.verticalHeader().setDefaultSectionSize(28)

        self.planning_waypoint_layout.addWidget(self.planning_table)

        self.planning_waypoint_layout.setStretch(2, 1)

        self.planning_target_content_layout.addWidget(self.planning_waypoint_panel)

        self.planning_target_content_layout.setStretch(1, 1)
        self.planning_editor_scroll.setWidget(self.planning_editor_content)

        self.planning_targets_tab_layout.addWidget(self.planning_editor_scroll)

        self.planning_editor_tabs.addTab(self.planning_targets_tab, "")
        self.planning_result_tab = QWidget()
        self.planning_result_tab.setObjectName(u"planning_result_tab")
        self.planning_result_layout = QVBoxLayout(self.planning_result_tab)
        self.planning_result_layout.setSpacing(6)
        self.planning_result_layout.setObjectName(u"planning_result_layout")
        self.planning_result_layout.setContentsMargins(8, 8, 8, 8)
        self.planning_result_caption = QLabel(self.planning_result_tab)
        self.planning_result_caption.setObjectName(u"planning_result_caption")
        self.planning_result_caption.setWordWrap(True)
        self.planning_result_caption.setProperty(u"role", u"previewTitle")

        self.planning_result_layout.addWidget(self.planning_result_caption)

        self.planning_preview_text = QPlainTextEdit(self.planning_result_tab)
        self.planning_preview_text.setObjectName(u"planning_preview_text")
        self.planning_preview_text.setReadOnly(True)

        self.planning_result_layout.addWidget(self.planning_preview_text)

        self.planning_editor_tabs.addTab(self.planning_result_tab, "")

        self.planning_editor_layout.addWidget(self.planning_editor_tabs)

        self.planning_editor_layout.setStretch(2, 1)

        self.planning_workspace_layout.addWidget(self.planning_editor_panel)

        self.planning_parameter_panel = QFrame(PlanningPanel)
        self.planning_parameter_panel.setObjectName(u"planning_parameter_panel")
        self.planning_parameter_panel.setMinimumSize(QSize(210, 0))
        self.planning_parameter_panel.setMaximumSize(QSize(228, 16777215))
        self.planning_parameter_panel.setProperty(u"role", u"surfacePanel")
        self.planning_parameter_layout = QVBoxLayout(self.planning_parameter_panel)
        self.planning_parameter_layout.setObjectName(u"planning_parameter_layout")
        self.planning_parameter_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_parameter_scroll = QScrollArea(self.planning_parameter_panel)
        self.planning_parameter_scroll.setObjectName(u"planning_parameter_scroll")
        self.planning_parameter_scroll.setFrameShape(QFrame.NoFrame)
        self.planning_parameter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.planning_parameter_scroll.setWidgetResizable(True)
        self.planning_parameter_content = QWidget()
        self.planning_parameter_content.setObjectName(u"planning_parameter_content")
        self.planning_parameter_content_layout = QVBoxLayout(self.planning_parameter_content)
        self.planning_parameter_content_layout.setSpacing(8)
        self.planning_parameter_content_layout.setObjectName(u"planning_parameter_content_layout")
        self.planning_parameter_content_layout.setContentsMargins(10, 10, 10, 10)
        self.planning_parameter_heading = QLabel(self.planning_parameter_content)
        self.planning_parameter_heading.setObjectName(u"planning_parameter_heading")
        self.planning_parameter_heading.setProperty(u"role", u"sectionTitle")

        self.planning_parameter_content_layout.addWidget(self.planning_parameter_heading)

        self.planning_parameter_form = QFormLayout()
        self.planning_parameter_form.setObjectName(u"planning_parameter_form")
        self.planning_parameter_form.setHorizontalSpacing(6)
        self.planning_parameter_form.setVerticalSpacing(8)
        self.planning_parameter_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.planning_mode_label = QLabel(self.planning_parameter_content)
        self.planning_mode_label.setObjectName(u"planning_mode_label")

        self.planning_parameter_form.setWidget(0, QFormLayout.ItemRole.LabelRole, self.planning_mode_label)

        self.planning_mode_combo = QComboBox(self.planning_parameter_content)
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.setObjectName(u"planning_mode_combo")

        self.planning_parameter_form.setWidget(0, QFormLayout.ItemRole.FieldRole, self.planning_mode_combo)

        self.planning_name_label = QLabel(self.planning_parameter_content)
        self.planning_name_label.setObjectName(u"planning_name_label")

        self.planning_parameter_form.setWidget(1, QFormLayout.ItemRole.LabelRole, self.planning_name_label)

        self.planning_name_edit = QLineEdit(self.planning_parameter_content)
        self.planning_name_edit.setObjectName(u"planning_name_edit")

        self.planning_parameter_form.setWidget(1, QFormLayout.ItemRole.FieldRole, self.planning_name_edit)

        self.planning_speed_label = QLabel(self.planning_parameter_content)
        self.planning_speed_label.setObjectName(u"planning_speed_label")

        self.planning_parameter_form.setWidget(2, QFormLayout.ItemRole.LabelRole, self.planning_speed_label)

        self.planning_speed_spin = QDoubleSpinBox(self.planning_parameter_content)
        self.planning_speed_spin.setObjectName(u"planning_speed_spin")
        self.planning_speed_spin.setDecimals(1)
        self.planning_speed_spin.setMinimum(1.000000000000000)
        self.planning_speed_spin.setMaximum(100.000000000000000)
        self.planning_speed_spin.setValue(30.000000000000000)

        self.planning_parameter_form.setWidget(2, QFormLayout.ItemRole.FieldRole, self.planning_speed_spin)


        self.planning_parameter_content_layout.addLayout(self.planning_parameter_form)

        self.planning_offline_panel = QWidget(self.planning_parameter_content)
        self.planning_offline_panel.setObjectName(u"planning_offline_panel")
        self.planning_offline_layout = QVBoxLayout(self.planning_offline_panel)
        self.planning_offline_layout.setSpacing(4)
        self.planning_offline_layout.setObjectName(u"planning_offline_layout")
        self.planning_offline_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_offline_label = QLabel(self.planning_offline_panel)
        self.planning_offline_label.setObjectName(u"planning_offline_label")

        self.planning_offline_layout.addWidget(self.planning_offline_label)

        self.planning_offline_start = QLineEdit(self.planning_offline_panel)
        self.planning_offline_start.setObjectName(u"planning_offline_start")

        self.planning_offline_layout.addWidget(self.planning_offline_start)


        self.planning_parameter_content_layout.addWidget(self.planning_offline_panel)

        self.planning_read_button = QPushButton(self.planning_parameter_content)
        self.planning_read_button.setObjectName(u"planning_read_button")

        self.planning_parameter_content_layout.addWidget(self.planning_read_button)

        self.planning_add_current_button = QPushButton(self.planning_parameter_content)
        self.planning_add_current_button.setObjectName(u"planning_add_current_button")

        self.planning_parameter_content_layout.addWidget(self.planning_add_current_button)

        self.planning_target_help = QLabel(self.planning_parameter_content)
        self.planning_target_help.setObjectName(u"planning_target_help")
        self.planning_target_help.setWordWrap(True)
        self.planning_target_help.setProperty(u"role", u"mutedText")

        self.planning_parameter_content_layout.addWidget(self.planning_target_help)

        self.planning_collision_notice = QLabel(self.planning_parameter_content)
        self.planning_collision_notice.setObjectName(u"planning_collision_notice")
        self.planning_collision_notice.setWordWrap(True)
        self.planning_collision_notice.setProperty(u"role", u"mutedText")

        self.planning_parameter_content_layout.addWidget(self.planning_collision_notice)

        self.planning_parameter_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.planning_parameter_content_layout.addItem(self.planning_parameter_spacer)

        self.planning_parameter_scroll.setWidget(self.planning_parameter_content)

        self.planning_parameter_layout.addWidget(self.planning_parameter_scroll)


        self.planning_workspace_layout.addWidget(self.planning_parameter_panel)

        self.planning_workspace_layout.setStretch(0, 1)

        self.planning_page_layout.addLayout(self.planning_workspace_layout)

        self.planning_action_bar = QFrame(PlanningPanel)
        self.planning_action_bar.setObjectName(u"planning_action_bar")
        self.planning_action_layout = QHBoxLayout(self.planning_action_bar)
        self.planning_action_layout.setSpacing(8)
        self.planning_action_layout.setObjectName(u"planning_action_layout")
        self.planning_action_layout.setContentsMargins(0, 0, 0, 0)
        self.planning_status_label = QLabel(self.planning_action_bar)
        self.planning_status_label.setObjectName(u"planning_status_label")
        self.planning_status_label.setWordWrap(True)
        self.planning_status_label.setProperty(u"role", u"mutedText")

        self.planning_action_layout.addWidget(self.planning_status_label)

        self.planning_plan_button = QPushButton(self.planning_action_bar)
        self.planning_plan_button.setObjectName(u"planning_plan_button")
        self.planning_plan_button.setMinimumSize(QSize(96, 32))
        self.planning_plan_button.setProperty(u"role", u"primary")

        self.planning_action_layout.addWidget(self.planning_plan_button)

        self.planning_execute_button = QPushButton(self.planning_action_bar)
        self.planning_execute_button.setObjectName(u"planning_execute_button")
        self.planning_execute_button.setEnabled(False)
        self.planning_execute_button.setMinimumSize(QSize(96, 32))

        self.planning_action_layout.addWidget(self.planning_execute_button)

        self.planning_save_button = QPushButton(self.planning_action_bar)
        self.planning_save_button.setObjectName(u"planning_save_button")
        self.planning_save_button.setEnabled(False)
        self.planning_save_button.setMinimumSize(QSize(108, 32))

        self.planning_action_layout.addWidget(self.planning_save_button)

        self.planning_action_layout.setStretch(0, 1)

        self.planning_page_layout.addWidget(self.planning_action_bar)

        self.planning_page_layout.setStretch(0, 1)

        self.retranslateUi(PlanningPanel)

        self.planning_editor_tabs.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(PlanningPanel)
    # setupUi

    def retranslateUi(self, PlanningPanel):
        self.planning_result_state.setText(QCoreApplication.translate("PlanningPanel", u"\u7b49\u5f85\u751f\u6210\u89c4\u5212", None))
        self.planning_result_summary.setText(QCoreApplication.translate("PlanningPanel", u"\u7f16\u8f91\u76ee\u6807\u540e\u751f\u6210\u89c4\u5212\uff0c\u53ef\u67e5\u770b\u5b9e\u9645\u5e27\u6570\u3001\u65f6\u957f\u4e0e\u7aef\u70b9\u3002", None))
        self.planning_target_group.setTitle(QCoreApplication.translate("PlanningPanel", u"\u76ee\u6807\u5173\u8282", None))
        self.planning_target_labels_0.setText(QCoreApplication.translate("PlanningPanel", u"J1 \u00b0", None))
        self.planning_target_labels_1.setText(QCoreApplication.translate("PlanningPanel", u"J2 \u00b0", None))
        self.planning_target_labels_2.setText(QCoreApplication.translate("PlanningPanel", u"J3 \u00b0", None))
        self.planning_target_labels_3.setText(QCoreApplication.translate("PlanningPanel", u"J4 \u00b0", None))
        self.planning_target_labels_4.setText(QCoreApplication.translate("PlanningPanel", u"J5 \u00b0", None))
        self.planning_target_labels_5.setText(QCoreApplication.translate("PlanningPanel", u"J6 \u00b0", None))
        self.planning_waypoint_heading.setText(QCoreApplication.translate("PlanningPanel", u"\u8def\u70b9\u5217\u8868 \u00b7 \u6309\u884c\u7f16\u8f91 TCP \u4e0e\u8fd0\u52a8\u65b9\u5f0f", None))
        self.planning_add_button.setText(QCoreApplication.translate("PlanningPanel", u"\u6dfb\u52a0\u76ee\u6807\u4e3a\u8def\u70b9", None))
        self.planning_delete_button.setText(QCoreApplication.translate("PlanningPanel", u"\u5220\u9664", None))
        self.planning_up_button.setText(QCoreApplication.translate("PlanningPanel", u"\u4e0a\u79fb", None))
        self.planning_down_button.setText(QCoreApplication.translate("PlanningPanel", u"\u4e0b\u79fb", None))
        ___qtablewidgetitem = self.planning_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("PlanningPanel", u"X mm", None))
        ___qtablewidgetitem1 = self.planning_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("PlanningPanel", u"Y mm", None))
        ___qtablewidgetitem2 = self.planning_table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("PlanningPanel", u"Z mm", None))
        ___qtablewidgetitem3 = self.planning_table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("PlanningPanel", u"Rx \u00b0", None))
        ___qtablewidgetitem4 = self.planning_table.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("PlanningPanel", u"Ry \u00b0", None))
        ___qtablewidgetitem5 = self.planning_table.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("PlanningPanel", u"Rz \u00b0", None))
        ___qtablewidgetitem6 = self.planning_table.horizontalHeaderItem(6)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("PlanningPanel", u"\u8fd0\u52a8\u65b9\u5f0f", None))
        ___qtablewidgetitem7 = self.planning_table.horizontalHeaderItem(7)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("PlanningPanel", u"\u901f\u5ea6 %", None))
        ___qtablewidgetitem8 = self.planning_table.horizontalHeaderItem(8)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("PlanningPanel", u"\u505c\u7559 s", None))
#if QT_CONFIG(tooltip)
        self.planning_table.setToolTip(QCoreApplication.translate("PlanningPanel", u"\u4f4d\u7f6e\u5355\u4f4d mm\uff0c\u59ff\u6001\u5355\u4f4d \u00b0\uff1b\u8fd0\u52a8\u65b9\u5f0f\u586b\u5199 ptp \u6216 linear\uff0c\u901f\u5ea6\u4e3a %\uff0c\u505c\u7559\u4e3a s\u3002\u53ef\u6a2a\u5411\u6eda\u52a8\u67e5\u770b\u5168\u90e8\u5217\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.planning_editor_tabs.setTabText(self.planning_editor_tabs.indexOf(self.planning_targets_tab), QCoreApplication.translate("PlanningPanel", u"\u76ee\u6807\u4e0e\u8def\u70b9", None))
        self.planning_result_caption.setText(QCoreApplication.translate("PlanningPanel", u"\u89c4\u5212\u8be6\u60c5 \u00b7 \u7aef\u70b9\u3001\u901f\u5ea6\u3001\u52a0\u901f\u5ea6\u4e0e\u5b9e\u9645\u9519\u8bef\u4fe1\u606f", None))
        self.planning_preview_text.setPlaceholderText(QCoreApplication.translate("PlanningPanel", u"\u751f\u6210\u89c4\u5212\u540e\uff0c\u5728\u6b64\u67e5\u770b\u5b9e\u9645\u7ed3\u679c\u3002", None))
        self.planning_editor_tabs.setTabText(self.planning_editor_tabs.indexOf(self.planning_result_tab), QCoreApplication.translate("PlanningPanel", u"\u89c4\u5212\u7ed3\u679c", None))
        self.planning_parameter_heading.setText(QCoreApplication.translate("PlanningPanel", u"\u89c4\u5212\u53c2\u6570", None))
        self.planning_mode_label.setText(QCoreApplication.translate("PlanningPanel", u"\u6a21\u5f0f", None))
        self.planning_mode_combo.setItemText(0, QCoreApplication.translate("PlanningPanel", u"Joint PTP", None))
        self.planning_mode_combo.setItemText(1, QCoreApplication.translate("PlanningPanel", u"TCP PTP", None))
        self.planning_mode_combo.setItemText(2, QCoreApplication.translate("PlanningPanel", u"TCP Linear", None))
        self.planning_mode_combo.setItemText(3, QCoreApplication.translate("PlanningPanel", u"Waypoints", None))

        self.planning_name_label.setText(QCoreApplication.translate("PlanningPanel", u"\u540d\u79f0", None))
        self.planning_name_edit.setText(QCoreApplication.translate("PlanningPanel", u"Planned motion", None))
        self.planning_speed_label.setText(QCoreApplication.translate("PlanningPanel", u"\u901f\u5ea6", None))
        self.planning_speed_spin.setSuffix(QCoreApplication.translate("PlanningPanel", u" %", None))
        self.planning_offline_label.setText(QCoreApplication.translate("PlanningPanel", u"\u79bb\u7ebf\u8d77\u70b9 \u00b7 J1\u2013J6 / \u00b0", None))
        self.planning_offline_start.setText(QCoreApplication.translate("PlanningPanel", u"0, 0, 0, 0, 0, 0", None))
#if QT_CONFIG(tooltip)
        self.planning_offline_start.setToolTip(QCoreApplication.translate("PlanningPanel", u"\u516d\u4e2a\u5173\u8282\u89d2\uff0c\u9017\u53f7\u5206\u9694\uff0c\u5355\u4f4d \u00b0\uff1b\u8fde\u63a5\u540e\u9700\u91cd\u65b0\u89c4\u5212\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.planning_read_button.setText(QCoreApplication.translate("PlanningPanel", u"\u8bfb\u53d6\u5f53\u524d\u4f4d\u7f6e\u5230\u76ee\u6807", None))
        self.planning_add_current_button.setText(QCoreApplication.translate("PlanningPanel", u"\u6dfb\u52a0\u5f53\u524d\u4f4d\u7f6e\u4e3a\u8def\u70b9", None))
        self.planning_target_help.setText(QCoreApplication.translate("PlanningPanel", u"Joint\uff1a\u8f93\u5165\u516d\u4e2a\u5173\u8282\u89d2\uff0c\u5355\u4f4d \u00b0\u3002", None))
        self.planning_collision_notice.setText(QCoreApplication.translate("PlanningPanel", u"\u8def\u5f84\u78b0\u649e\u9884\u68c0\uff1a\u672a\u5b9e\u73b0\uff08\u672a\u9a8c\u8bc1\u81ea\u78b0\u649e\u6216\u73af\u5883\u969c\u788d\u7269\uff09\u3002", None))
        self.planning_status_label.setText(QCoreApplication.translate("PlanningPanel", u"IDLE", None))
        self.planning_plan_button.setText(QCoreApplication.translate("PlanningPanel", u"\u751f\u6210\u89c4\u5212", None))
        self.planning_execute_button.setText(QCoreApplication.translate("PlanningPanel", u"\u6267\u884c\u89c4\u5212", None))
        self.planning_save_button.setText(QCoreApplication.translate("PlanningPanel", u"\u4fdd\u5b58\u4e3a\u8f68\u8ff9", None))
        pass
    # retranslateUi
