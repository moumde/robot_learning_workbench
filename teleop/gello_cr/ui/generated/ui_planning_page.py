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
    QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QWidget)

class Ui_PlanningPanel(object):
    def setupUi(self, PlanningPanel):
        if not PlanningPanel.objectName():
            PlanningPanel.setObjectName(u"PlanningPanel")
        PlanningPanel.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(PlanningPanel.sizePolicy().hasHeightForWidth())
        PlanningPanel.setSizePolicy(sizePolicy)
        PlanningPanel.setProperty(u"density", u"compact")
        self.planning_GridLayout_1 = QGridLayout(PlanningPanel)
        self.planning_GridLayout_1.setObjectName(u"planning_GridLayout_1")
        self.planning_GridLayout_1.setHorizontalSpacing(6)
        self.planning_GridLayout_1.setVerticalSpacing(6)
        self.planning_GridLayout_1.setContentsMargins(6, 6, 6, 6)
        self.planning_HBoxLayout_1 = QHBoxLayout()
        self.planning_HBoxLayout_1.setSpacing(6)
        self.planning_HBoxLayout_1.setObjectName(u"planning_HBoxLayout_1")
        self.planning_HBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.planning_Label_1 = QLabel(PlanningPanel)
        self.planning_Label_1.setObjectName(u"planning_Label_1")
        sizePolicy.setHeightForWidth(self.planning_Label_1.sizePolicy().hasHeightForWidth())
        self.planning_Label_1.setSizePolicy(sizePolicy)
        self.planning_Label_1.setWordWrap(False)
        self.planning_Label_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_Label_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_1.addWidget(self.planning_Label_1)

        self.planning_mode_combo = QComboBox(PlanningPanel)
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.addItem("")
        self.planning_mode_combo.setObjectName(u"planning_mode_combo")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.planning_mode_combo.sizePolicy().hasHeightForWidth())
        self.planning_mode_combo.setSizePolicy(sizePolicy1)
        self.planning_mode_combo.setEditable(False)

        self.planning_HBoxLayout_1.addWidget(self.planning_mode_combo)

        self.planning_Label_2 = QLabel(PlanningPanel)
        self.planning_Label_2.setObjectName(u"planning_Label_2")
        sizePolicy.setHeightForWidth(self.planning_Label_2.sizePolicy().hasHeightForWidth())
        self.planning_Label_2.setSizePolicy(sizePolicy)
        self.planning_Label_2.setWordWrap(False)
        self.planning_Label_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_Label_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_1.addWidget(self.planning_Label_2)

        self.planning_name_edit = QLineEdit(PlanningPanel)
        self.planning_name_edit.setObjectName(u"planning_name_edit")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.planning_name_edit.sizePolicy().hasHeightForWidth())
        self.planning_name_edit.setSizePolicy(sizePolicy2)

        self.planning_HBoxLayout_1.addWidget(self.planning_name_edit)

        self.planning_Label_3 = QLabel(PlanningPanel)
        self.planning_Label_3.setObjectName(u"planning_Label_3")
        sizePolicy.setHeightForWidth(self.planning_Label_3.sizePolicy().hasHeightForWidth())
        self.planning_Label_3.setSizePolicy(sizePolicy)
        self.planning_Label_3.setWordWrap(False)
        self.planning_Label_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_Label_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_1.addWidget(self.planning_Label_3)

        self.planning_speed_spin = QDoubleSpinBox(PlanningPanel)
        self.planning_speed_spin.setObjectName(u"planning_speed_spin")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.planning_speed_spin.sizePolicy().hasHeightForWidth())
        self.planning_speed_spin.setSizePolicy(sizePolicy3)
        self.planning_speed_spin.setDecimals(2)
        self.planning_speed_spin.setMinimum(1.000000000000000)
        self.planning_speed_spin.setMaximum(100.000000000000000)
        self.planning_speed_spin.setSingleStep(1.000000000000000)
        self.planning_speed_spin.setValue(30.000000000000000)

        self.planning_HBoxLayout_1.addWidget(self.planning_speed_spin)


        self.planning_GridLayout_1.addLayout(self.planning_HBoxLayout_1, 0, 0, 1, 2)

        self.planning_offline_start = QLineEdit(PlanningPanel)
        self.planning_offline_start.setObjectName(u"planning_offline_start")
        sizePolicy2.setHeightForWidth(self.planning_offline_start.sizePolicy().hasHeightForWidth())
        self.planning_offline_start.setSizePolicy(sizePolicy2)

        self.planning_GridLayout_1.addWidget(self.planning_offline_start, 6, 0, 1, 2)

        self.planning_HBoxLayout_2 = QHBoxLayout()
        self.planning_HBoxLayout_2.setSpacing(6)
        self.planning_HBoxLayout_2.setObjectName(u"planning_HBoxLayout_2")
        self.planning_HBoxLayout_2.setContentsMargins(0, 0, 0, 0)
        self.planning_target_labels_0 = QLabel(PlanningPanel)
        self.planning_target_labels_0.setObjectName(u"planning_target_labels_0")
        sizePolicy.setHeightForWidth(self.planning_target_labels_0.sizePolicy().hasHeightForWidth())
        self.planning_target_labels_0.setSizePolicy(sizePolicy)
        self.planning_target_labels_0.setWordWrap(False)
        self.planning_target_labels_0.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_target_labels_0.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_labels_0)

        self.planning_target_spins_0 = QDoubleSpinBox(PlanningPanel)
        self.planning_target_spins_0.setObjectName(u"planning_target_spins_0")
        sizePolicy3.setHeightForWidth(self.planning_target_spins_0.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_0.setSizePolicy(sizePolicy3)
        self.planning_target_spins_0.setDecimals(3)
        self.planning_target_spins_0.setMinimum(-100000.000000000000000)
        self.planning_target_spins_0.setMaximum(100000.000000000000000)
        self.planning_target_spins_0.setSingleStep(1.000000000000000)
        self.planning_target_spins_0.setValue(0.000000000000000)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_spins_0)

        self.planning_target_labels_1 = QLabel(PlanningPanel)
        self.planning_target_labels_1.setObjectName(u"planning_target_labels_1")
        sizePolicy.setHeightForWidth(self.planning_target_labels_1.sizePolicy().hasHeightForWidth())
        self.planning_target_labels_1.setSizePolicy(sizePolicy)
        self.planning_target_labels_1.setWordWrap(False)
        self.planning_target_labels_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_target_labels_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_labels_1)

        self.planning_target_spins_1 = QDoubleSpinBox(PlanningPanel)
        self.planning_target_spins_1.setObjectName(u"planning_target_spins_1")
        sizePolicy3.setHeightForWidth(self.planning_target_spins_1.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_1.setSizePolicy(sizePolicy3)
        self.planning_target_spins_1.setDecimals(3)
        self.planning_target_spins_1.setMinimum(-100000.000000000000000)
        self.planning_target_spins_1.setMaximum(100000.000000000000000)
        self.planning_target_spins_1.setSingleStep(1.000000000000000)
        self.planning_target_spins_1.setValue(0.000000000000000)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_spins_1)

        self.planning_target_labels_2 = QLabel(PlanningPanel)
        self.planning_target_labels_2.setObjectName(u"planning_target_labels_2")
        sizePolicy.setHeightForWidth(self.planning_target_labels_2.sizePolicy().hasHeightForWidth())
        self.planning_target_labels_2.setSizePolicy(sizePolicy)
        self.planning_target_labels_2.setWordWrap(False)
        self.planning_target_labels_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_target_labels_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_labels_2)

        self.planning_target_spins_2 = QDoubleSpinBox(PlanningPanel)
        self.planning_target_spins_2.setObjectName(u"planning_target_spins_2")
        sizePolicy3.setHeightForWidth(self.planning_target_spins_2.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_2.setSizePolicy(sizePolicy3)
        self.planning_target_spins_2.setDecimals(3)
        self.planning_target_spins_2.setMinimum(-100000.000000000000000)
        self.planning_target_spins_2.setMaximum(100000.000000000000000)
        self.planning_target_spins_2.setSingleStep(1.000000000000000)
        self.planning_target_spins_2.setValue(0.000000000000000)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_spins_2)

        self.planning_target_labels_3 = QLabel(PlanningPanel)
        self.planning_target_labels_3.setObjectName(u"planning_target_labels_3")
        sizePolicy.setHeightForWidth(self.planning_target_labels_3.sizePolicy().hasHeightForWidth())
        self.planning_target_labels_3.setSizePolicy(sizePolicy)
        self.planning_target_labels_3.setWordWrap(False)
        self.planning_target_labels_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_target_labels_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_labels_3)

        self.planning_target_spins_3 = QDoubleSpinBox(PlanningPanel)
        self.planning_target_spins_3.setObjectName(u"planning_target_spins_3")
        sizePolicy3.setHeightForWidth(self.planning_target_spins_3.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_3.setSizePolicy(sizePolicy3)
        self.planning_target_spins_3.setDecimals(3)
        self.planning_target_spins_3.setMinimum(-100000.000000000000000)
        self.planning_target_spins_3.setMaximum(100000.000000000000000)
        self.planning_target_spins_3.setSingleStep(1.000000000000000)
        self.planning_target_spins_3.setValue(0.000000000000000)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_spins_3)

        self.planning_target_labels_4 = QLabel(PlanningPanel)
        self.planning_target_labels_4.setObjectName(u"planning_target_labels_4")
        sizePolicy.setHeightForWidth(self.planning_target_labels_4.sizePolicy().hasHeightForWidth())
        self.planning_target_labels_4.setSizePolicy(sizePolicy)
        self.planning_target_labels_4.setWordWrap(False)
        self.planning_target_labels_4.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_target_labels_4.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_labels_4)

        self.planning_target_spins_4 = QDoubleSpinBox(PlanningPanel)
        self.planning_target_spins_4.setObjectName(u"planning_target_spins_4")
        sizePolicy3.setHeightForWidth(self.planning_target_spins_4.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_4.setSizePolicy(sizePolicy3)
        self.planning_target_spins_4.setDecimals(3)
        self.planning_target_spins_4.setMinimum(-100000.000000000000000)
        self.planning_target_spins_4.setMaximum(100000.000000000000000)
        self.planning_target_spins_4.setSingleStep(1.000000000000000)
        self.planning_target_spins_4.setValue(0.000000000000000)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_spins_4)

        self.planning_target_labels_5 = QLabel(PlanningPanel)
        self.planning_target_labels_5.setObjectName(u"planning_target_labels_5")
        sizePolicy.setHeightForWidth(self.planning_target_labels_5.sizePolicy().hasHeightForWidth())
        self.planning_target_labels_5.setSizePolicy(sizePolicy)
        self.planning_target_labels_5.setWordWrap(False)
        self.planning_target_labels_5.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_target_labels_5.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_labels_5)

        self.planning_target_spins_5 = QDoubleSpinBox(PlanningPanel)
        self.planning_target_spins_5.setObjectName(u"planning_target_spins_5")
        sizePolicy3.setHeightForWidth(self.planning_target_spins_5.sizePolicy().hasHeightForWidth())
        self.planning_target_spins_5.setSizePolicy(sizePolicy3)
        self.planning_target_spins_5.setDecimals(3)
        self.planning_target_spins_5.setMinimum(-100000.000000000000000)
        self.planning_target_spins_5.setMaximum(100000.000000000000000)
        self.planning_target_spins_5.setSingleStep(1.000000000000000)
        self.planning_target_spins_5.setValue(0.000000000000000)

        self.planning_HBoxLayout_2.addWidget(self.planning_target_spins_5)


        self.planning_GridLayout_1.addLayout(self.planning_HBoxLayout_2, 1, 0, 1, 2)

        self.planning_table = QTableWidget(PlanningPanel)
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
        self.planning_table.setVisible(False)
        self.planning_table.setMinimumSize(QSize(0, 110))
        self.planning_table.setMaximumSize(QSize(16777215, 170))
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.planning_table.sizePolicy().hasHeightForWidth())
        self.planning_table.setSizePolicy(sizePolicy4)
        self.planning_table.setRowCount(0)
        self.planning_table.setColumnCount(9)
        self.planning_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.planning_table.setEditTriggers(QAbstractItemView.DoubleClicked|QAbstractItemView.EditKeyPressed|QAbstractItemView.AnyKeyPressed)

        self.planning_GridLayout_1.addWidget(self.planning_table, 2, 0, 1, 2)

        self.planning_HBoxLayout_3 = QHBoxLayout()
        self.planning_HBoxLayout_3.setSpacing(6)
        self.planning_HBoxLayout_3.setObjectName(u"planning_HBoxLayout_3")
        self.planning_HBoxLayout_3.setContentsMargins(0, 0, 0, 0)
        self.planning_read_button = QPushButton(PlanningPanel)
        self.planning_read_button.setObjectName(u"planning_read_button")
        sizePolicy3.setHeightForWidth(self.planning_read_button.sizePolicy().hasHeightForWidth())
        self.planning_read_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_3.addWidget(self.planning_read_button)

        self.planning_add_current_button = QPushButton(PlanningPanel)
        self.planning_add_current_button.setObjectName(u"planning_add_current_button")
        sizePolicy3.setHeightForWidth(self.planning_add_current_button.sizePolicy().hasHeightForWidth())
        self.planning_add_current_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_3.addWidget(self.planning_add_current_button)

        self.planning_add_button = QPushButton(PlanningPanel)
        self.planning_add_button.setObjectName(u"planning_add_button")
        sizePolicy3.setHeightForWidth(self.planning_add_button.sizePolicy().hasHeightForWidth())
        self.planning_add_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_3.addWidget(self.planning_add_button)

        self.planning_delete_button = QPushButton(PlanningPanel)
        self.planning_delete_button.setObjectName(u"planning_delete_button")
        sizePolicy3.setHeightForWidth(self.planning_delete_button.sizePolicy().hasHeightForWidth())
        self.planning_delete_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_3.addWidget(self.planning_delete_button)

        self.planning_up_button = QPushButton(PlanningPanel)
        self.planning_up_button.setObjectName(u"planning_up_button")
        sizePolicy3.setHeightForWidth(self.planning_up_button.sizePolicy().hasHeightForWidth())
        self.planning_up_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_3.addWidget(self.planning_up_button)

        self.planning_down_button = QPushButton(PlanningPanel)
        self.planning_down_button.setObjectName(u"planning_down_button")
        sizePolicy3.setHeightForWidth(self.planning_down_button.sizePolicy().hasHeightForWidth())
        self.planning_down_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_3.addWidget(self.planning_down_button)


        self.planning_GridLayout_1.addLayout(self.planning_HBoxLayout_3, 3, 0, 1, 2)

        self.planning_HBoxLayout_4 = QHBoxLayout()
        self.planning_HBoxLayout_4.setSpacing(6)
        self.planning_HBoxLayout_4.setObjectName(u"planning_HBoxLayout_4")
        self.planning_HBoxLayout_4.setContentsMargins(0, 0, 0, 0)
        self.planning_plan_button = QPushButton(PlanningPanel)
        self.planning_plan_button.setObjectName(u"planning_plan_button")
        sizePolicy3.setHeightForWidth(self.planning_plan_button.sizePolicy().hasHeightForWidth())
        self.planning_plan_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_4.addWidget(self.planning_plan_button)

        self.planning_execute_button = QPushButton(PlanningPanel)
        self.planning_execute_button.setObjectName(u"planning_execute_button")
        self.planning_execute_button.setEnabled(False)
        sizePolicy3.setHeightForWidth(self.planning_execute_button.sizePolicy().hasHeightForWidth())
        self.planning_execute_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_4.addWidget(self.planning_execute_button)

        self.planning_save_button = QPushButton(PlanningPanel)
        self.planning_save_button.setObjectName(u"planning_save_button")
        self.planning_save_button.setEnabled(False)
        sizePolicy3.setHeightForWidth(self.planning_save_button.sizePolicy().hasHeightForWidth())
        self.planning_save_button.setSizePolicy(sizePolicy3)

        self.planning_HBoxLayout_4.addWidget(self.planning_save_button)

        self.planning_status_label = QLabel(PlanningPanel)
        self.planning_status_label.setObjectName(u"planning_status_label")
        sizePolicy.setHeightForWidth(self.planning_status_label.sizePolicy().hasHeightForWidth())
        self.planning_status_label.setSizePolicy(sizePolicy)
        self.planning_status_label.setWordWrap(False)
        self.planning_status_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.planning_status_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.planning_HBoxLayout_4.addWidget(self.planning_status_label)


        self.planning_GridLayout_1.addLayout(self.planning_HBoxLayout_4, 4, 0, 1, 2)

        self.planning_preview_text = QPlainTextEdit(PlanningPanel)
        self.planning_preview_text.setObjectName(u"planning_preview_text")
        self.planning_preview_text.setMinimumSize(QSize(0, 150))
        sizePolicy4.setHeightForWidth(self.planning_preview_text.sizePolicy().hasHeightForWidth())
        self.planning_preview_text.setSizePolicy(sizePolicy4)
        self.planning_preview_text.setReadOnly(True)

        self.planning_GridLayout_1.addWidget(self.planning_preview_text, 5, 0, 1, 2)


        self.retranslateUi(PlanningPanel)

        self.planning_mode_combo.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(PlanningPanel)
    # setupUi

    def retranslateUi(self, PlanningPanel):
        self.planning_Label_1.setText(QCoreApplication.translate("PlanningPanel", u"\u6a21\u5f0f", None))
        self.planning_mode_combo.setItemText(0, QCoreApplication.translate("PlanningPanel", u"Joint PTP", None))
        self.planning_mode_combo.setItemText(1, QCoreApplication.translate("PlanningPanel", u"TCP PTP", None))
        self.planning_mode_combo.setItemText(2, QCoreApplication.translate("PlanningPanel", u"TCP Linear", None))
        self.planning_mode_combo.setItemText(3, QCoreApplication.translate("PlanningPanel", u"Waypoints", None))

        self.planning_Label_2.setText(QCoreApplication.translate("PlanningPanel", u"\u540d\u79f0", None))
        self.planning_name_edit.setText(QCoreApplication.translate("PlanningPanel", u"Planned motion", None))
        self.planning_name_edit.setPlaceholderText("")
        self.planning_Label_3.setText(QCoreApplication.translate("PlanningPanel", u"\u901f\u5ea6", None))
        self.planning_speed_spin.setSuffix(QCoreApplication.translate("PlanningPanel", u" %", None))
#if QT_CONFIG(tooltip)
        self.planning_offline_start.setToolTip(QCoreApplication.translate("PlanningPanel", u"\u79bb\u7ebf\u89c4\u5212\u8d77\u70b9 J1\u2013J6\uff0c\u9017\u53f7\u5206\u9694\uff0c\u5355\u4f4d \u00b0\uff1b\u8fde\u63a5\u540e\u9700\u91cd\u65b0\u89c4\u5212\u3002", None))
#endif // QT_CONFIG(tooltip)
        self.planning_offline_start.setText(QCoreApplication.translate("PlanningPanel", u"0, 0, 0, 0, 0, 0", None))
        self.planning_offline_start.setPlaceholderText("")
        self.planning_target_labels_0.setText(QCoreApplication.translate("PlanningPanel", u"J1 \u00b0", None))
        self.planning_target_spins_0.setSuffix("")
        self.planning_target_labels_1.setText(QCoreApplication.translate("PlanningPanel", u"J2 \u00b0", None))
        self.planning_target_spins_1.setSuffix("")
        self.planning_target_labels_2.setText(QCoreApplication.translate("PlanningPanel", u"J3 \u00b0", None))
        self.planning_target_spins_2.setSuffix("")
        self.planning_target_labels_3.setText(QCoreApplication.translate("PlanningPanel", u"J4 \u00b0", None))
        self.planning_target_spins_3.setSuffix("")
        self.planning_target_labels_4.setText(QCoreApplication.translate("PlanningPanel", u"J5 \u00b0", None))
        self.planning_target_spins_4.setSuffix("")
        self.planning_target_labels_5.setText(QCoreApplication.translate("PlanningPanel", u"J6 \u00b0", None))
        self.planning_target_spins_5.setSuffix("")
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
        ___qtablewidgetitem6.setText(QCoreApplication.translate("PlanningPanel", u"Mode", None))
        ___qtablewidgetitem7 = self.planning_table.horizontalHeaderItem(7)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("PlanningPanel", u"\u901f\u5ea6 %", None))
        ___qtablewidgetitem8 = self.planning_table.horizontalHeaderItem(8)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("PlanningPanel", u"\u505c\u7559 s", None))
        self.planning_read_button.setText(QCoreApplication.translate("PlanningPanel", u"\u8bfb\u53d6\u5f53\u524d\u4f4d\u7f6e", None))
        self.planning_add_current_button.setText(QCoreApplication.translate("PlanningPanel", u"\u6dfb\u52a0\u5f53\u524d\u4f4d\u7f6e", None))
        self.planning_add_button.setText(QCoreApplication.translate("PlanningPanel", u"\u6dfb\u52a0 Waypoint", None))
        self.planning_delete_button.setText(QCoreApplication.translate("PlanningPanel", u"\u5220\u9664", None))
        self.planning_up_button.setText(QCoreApplication.translate("PlanningPanel", u"\u4e0a\u79fb", None))
        self.planning_down_button.setText(QCoreApplication.translate("PlanningPanel", u"\u4e0b\u79fb", None))
        self.planning_plan_button.setText(QCoreApplication.translate("PlanningPanel", u"\u89c4\u5212 / \u9884\u89c8", None))
        self.planning_execute_button.setText(QCoreApplication.translate("PlanningPanel", u"\u6267\u884c", None))
        self.planning_save_button.setText(QCoreApplication.translate("PlanningPanel", u"\u4fdd\u5b58\u5230\u8f68\u8ff9\u5e93", None))
        self.planning_status_label.setText(QCoreApplication.translate("PlanningPanel", u"IDLE", None))
        self.planning_preview_text.setPlaceholderText("")
        pass
    # retranslateUi
