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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox,
    QWidget)

class Ui_TrajectoryPanel(object):
    def setupUi(self, TrajectoryPanel):
        if not TrajectoryPanel.objectName():
            TrajectoryPanel.setObjectName(u"TrajectoryPanel")
        TrajectoryPanel.setMinimumSize(QSize(0, 216))
        TrajectoryPanel.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(TrajectoryPanel.sizePolicy().hasHeightForWidth())
        TrajectoryPanel.setSizePolicy(sizePolicy)
        TrajectoryPanel.setProperty(u"density", u"compact")
        self.trajectory_GridLayout_1 = QGridLayout(TrajectoryPanel)
        self.trajectory_GridLayout_1.setObjectName(u"trajectory_GridLayout_1")
        self.trajectory_GridLayout_1.setHorizontalSpacing(4)
        self.trajectory_GridLayout_1.setVerticalSpacing(4)
        self.trajectory_GridLayout_1.setContentsMargins(6, 6, 6, 6)
        self.trajectory_HBoxLayout_1 = QHBoxLayout()
        self.trajectory_HBoxLayout_1.setSpacing(4)
        self.trajectory_HBoxLayout_1.setObjectName(u"trajectory_HBoxLayout_1")
        self.trajectory_HBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.trajectory_Label_1 = QLabel(TrajectoryPanel)
        self.trajectory_Label_1.setObjectName(u"trajectory_Label_1")
        sizePolicy.setHeightForWidth(self.trajectory_Label_1.sizePolicy().hasHeightForWidth())
        self.trajectory_Label_1.setSizePolicy(sizePolicy)
        self.trajectory_Label_1.setWordWrap(False)
        self.trajectory_Label_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_Label_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_1.addWidget(self.trajectory_Label_1)

        self.trajectory_record_name = QLineEdit(TrajectoryPanel)
        self.trajectory_record_name.setObjectName(u"trajectory_record_name")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.trajectory_record_name.sizePolicy().hasHeightForWidth())
        self.trajectory_record_name.setSizePolicy(sizePolicy1)

        self.trajectory_HBoxLayout_1.addWidget(self.trajectory_record_name)

        self.trajectory_record_button = QPushButton(TrajectoryPanel)
        self.trajectory_record_button.setObjectName(u"trajectory_record_button")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.trajectory_record_button.sizePolicy().hasHeightForWidth())
        self.trajectory_record_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_1.addWidget(self.trajectory_record_button)

        self.trajectory_finish_button = QPushButton(TrajectoryPanel)
        self.trajectory_finish_button.setObjectName(u"trajectory_finish_button")
        sizePolicy2.setHeightForWidth(self.trajectory_finish_button.sizePolicy().hasHeightForWidth())
        self.trajectory_finish_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_1.addWidget(self.trajectory_finish_button)

        self.trajectory_save_button = QPushButton(TrajectoryPanel)
        self.trajectory_save_button.setObjectName(u"trajectory_save_button")
        sizePolicy2.setHeightForWidth(self.trajectory_save_button.sizePolicy().hasHeightForWidth())
        self.trajectory_save_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_1.addWidget(self.trajectory_save_button)

        self.trajectory_cancel_button = QPushButton(TrajectoryPanel)
        self.trajectory_cancel_button.setObjectName(u"trajectory_cancel_button")
        sizePolicy2.setHeightForWidth(self.trajectory_cancel_button.sizePolicy().hasHeightForWidth())
        self.trajectory_cancel_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_1.addWidget(self.trajectory_cancel_button)


        self.trajectory_GridLayout_1.addLayout(self.trajectory_HBoxLayout_1, 0, 0, 1, 2)

        self.trajectory_HBoxLayout_2 = QHBoxLayout()
        self.trajectory_HBoxLayout_2.setSpacing(4)
        self.trajectory_HBoxLayout_2.setObjectName(u"trajectory_HBoxLayout_2")
        self.trajectory_HBoxLayout_2.setContentsMargins(0, 0, 0, 0)
        self.trajectory_Label_2 = QLabel(TrajectoryPanel)
        self.trajectory_Label_2.setObjectName(u"trajectory_Label_2")
        sizePolicy.setHeightForWidth(self.trajectory_Label_2.sizePolicy().hasHeightForWidth())
        self.trajectory_Label_2.setSizePolicy(sizePolicy)
        self.trajectory_Label_2.setWordWrap(False)
        self.trajectory_Label_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_Label_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_Label_2)

        self.trajectory_saved_combo = QComboBox(TrajectoryPanel)
        self.trajectory_saved_combo.setObjectName(u"trajectory_saved_combo")
        self.trajectory_saved_combo.setMinimumSize(QSize(210, 0))
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.trajectory_saved_combo.sizePolicy().hasHeightForWidth())
        self.trajectory_saved_combo.setSizePolicy(sizePolicy3)
        self.trajectory_saved_combo.setEditable(False)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_saved_combo)

        self.trajectory_refresh_button = QPushButton(TrajectoryPanel)
        self.trajectory_refresh_button.setObjectName(u"trajectory_refresh_button")
        sizePolicy2.setHeightForWidth(self.trajectory_refresh_button.sizePolicy().hasHeightForWidth())
        self.trajectory_refresh_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_refresh_button)

        self.trajectory_import_json_button = QPushButton(TrajectoryPanel)
        self.trajectory_import_json_button.setObjectName(u"trajectory_import_json_button")
        sizePolicy2.setHeightForWidth(self.trajectory_import_json_button.sizePolicy().hasHeightForWidth())
        self.trajectory_import_json_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_import_json_button)

        self.trajectory_import_episode_button = QPushButton(TrajectoryPanel)
        self.trajectory_import_episode_button.setObjectName(u"trajectory_import_episode_button")
        sizePolicy2.setHeightForWidth(self.trajectory_import_episode_button.sizePolicy().hasHeightForWidth())
        self.trajectory_import_episode_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_import_episode_button)

        self.trajectory_Label_3 = QLabel(TrajectoryPanel)
        self.trajectory_Label_3.setObjectName(u"trajectory_Label_3")
        sizePolicy.setHeightForWidth(self.trajectory_Label_3.sizePolicy().hasHeightForWidth())
        self.trajectory_Label_3.setSizePolicy(sizePolicy)
        self.trajectory_Label_3.setWordWrap(False)
        self.trajectory_Label_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_Label_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_Label_3)

        self.trajectory_episode_spin = QSpinBox(TrajectoryPanel)
        self.trajectory_episode_spin.setObjectName(u"trajectory_episode_spin")
        sizePolicy2.setHeightForWidth(self.trajectory_episode_spin.sizePolicy().hasHeightForWidth())
        self.trajectory_episode_spin.setSizePolicy(sizePolicy2)
        self.trajectory_episode_spin.setMinimum(0)
        self.trajectory_episode_spin.setMaximum(1000000)
        self.trajectory_episode_spin.setSingleStep(1)
        self.trajectory_episode_spin.setValue(0)

        self.trajectory_HBoxLayout_2.addWidget(self.trajectory_episode_spin)

        self.trajectory_HBoxLayout_2.setStretch(1, 1)

        self.trajectory_GridLayout_1.addLayout(self.trajectory_HBoxLayout_2, 1, 0, 1, 2)

        self.trajectory_HBoxLayout_3 = QHBoxLayout()
        self.trajectory_HBoxLayout_3.setSpacing(4)
        self.trajectory_HBoxLayout_3.setObjectName(u"trajectory_HBoxLayout_3")
        self.trajectory_HBoxLayout_3.setContentsMargins(0, 0, 0, 0)
        self.trajectory_mode_combo = QComboBox(TrajectoryPanel)
        self.trajectory_mode_combo.addItem("")
        self.trajectory_mode_combo.addItem("")
        self.trajectory_mode_combo.setObjectName(u"trajectory_mode_combo")
        sizePolicy3.setHeightForWidth(self.trajectory_mode_combo.sizePolicy().hasHeightForWidth())
        self.trajectory_mode_combo.setSizePolicy(sizePolicy3)
        self.trajectory_mode_combo.setEditable(False)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_mode_combo)

        self.trajectory_Label_4 = QLabel(TrajectoryPanel)
        self.trajectory_Label_4.setObjectName(u"trajectory_Label_4")
        sizePolicy.setHeightForWidth(self.trajectory_Label_4.sizePolicy().hasHeightForWidth())
        self.trajectory_Label_4.setSizePolicy(sizePolicy)
        self.trajectory_Label_4.setWordWrap(False)
        self.trajectory_Label_4.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_Label_4.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_Label_4)

        self.trajectory_speed_spin = QDoubleSpinBox(TrajectoryPanel)
        self.trajectory_speed_spin.setObjectName(u"trajectory_speed_spin")
        sizePolicy2.setHeightForWidth(self.trajectory_speed_spin.sizePolicy().hasHeightForWidth())
        self.trajectory_speed_spin.setSizePolicy(sizePolicy2)
        self.trajectory_speed_spin.setDecimals(2)
        self.trajectory_speed_spin.setMinimum(0.100000000000000)
        self.trajectory_speed_spin.setMaximum(2.000000000000000)
        self.trajectory_speed_spin.setSingleStep(0.100000000000000)
        self.trajectory_speed_spin.setValue(1.000000000000000)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_speed_spin)

        self.trajectory_Label_5 = QLabel(TrajectoryPanel)
        self.trajectory_Label_5.setObjectName(u"trajectory_Label_5")
        sizePolicy.setHeightForWidth(self.trajectory_Label_5.sizePolicy().hasHeightForWidth())
        self.trajectory_Label_5.setSizePolicy(sizePolicy)
        self.trajectory_Label_5.setWordWrap(False)
        self.trajectory_Label_5.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_Label_5.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_Label_5)

        self.trajectory_repeat_spin = QSpinBox(TrajectoryPanel)
        self.trajectory_repeat_spin.setObjectName(u"trajectory_repeat_spin")
        sizePolicy2.setHeightForWidth(self.trajectory_repeat_spin.sizePolicy().hasHeightForWidth())
        self.trajectory_repeat_spin.setSizePolicy(sizePolicy2)
        self.trajectory_repeat_spin.setMinimum(1)
        self.trajectory_repeat_spin.setMaximum(1000)
        self.trajectory_repeat_spin.setSingleStep(1)
        self.trajectory_repeat_spin.setValue(1)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_repeat_spin)

        self.trajectory_arm_check = QCheckBox(TrajectoryPanel)
        self.trajectory_arm_check.setObjectName(u"trajectory_arm_check")
        sizePolicy2.setHeightForWidth(self.trajectory_arm_check.sizePolicy().hasHeightForWidth())
        self.trajectory_arm_check.setSizePolicy(sizePolicy2)
        self.trajectory_arm_check.setCheckable(True)
        self.trajectory_arm_check.setChecked(True)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_arm_check)

        self.trajectory_hand_check = QCheckBox(TrajectoryPanel)
        self.trajectory_hand_check.setObjectName(u"trajectory_hand_check")
        sizePolicy2.setHeightForWidth(self.trajectory_hand_check.sizePolicy().hasHeightForWidth())
        self.trajectory_hand_check.setSizePolicy(sizePolicy2)
        self.trajectory_hand_check.setCheckable(True)
        self.trajectory_hand_check.setChecked(True)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_hand_check)

        self.trajectory_preview_button = QPushButton(TrajectoryPanel)
        self.trajectory_preview_button.setObjectName(u"trajectory_preview_button")
        sizePolicy2.setHeightForWidth(self.trajectory_preview_button.sizePolicy().hasHeightForWidth())
        self.trajectory_preview_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_preview_button)

        self.trajectory_play_button = QPushButton(TrajectoryPanel)
        self.trajectory_play_button.setObjectName(u"trajectory_play_button")
        sizePolicy2.setHeightForWidth(self.trajectory_play_button.sizePolicy().hasHeightForWidth())
        self.trajectory_play_button.setSizePolicy(sizePolicy2)

        self.trajectory_HBoxLayout_3.addWidget(self.trajectory_play_button)


        self.trajectory_GridLayout_1.addLayout(self.trajectory_HBoxLayout_3, 2, 0, 1, 2)

        self.trajectory_HBoxLayout_4 = QHBoxLayout()
        self.trajectory_HBoxLayout_4.setSpacing(4)
        self.trajectory_HBoxLayout_4.setObjectName(u"trajectory_HBoxLayout_4")
        self.trajectory_HBoxLayout_4.setContentsMargins(0, 0, 0, 0)
        self.trajectory_Label_6 = QLabel(TrajectoryPanel)
        self.trajectory_Label_6.setObjectName(u"trajectory_Label_6")
        sizePolicy.setHeightForWidth(self.trajectory_Label_6.sizePolicy().hasHeightForWidth())
        self.trajectory_Label_6.setSizePolicy(sizePolicy)
        self.trajectory_Label_6.setWordWrap(False)
        self.trajectory_Label_6.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_Label_6.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_Label_6)

        self.trajectory_joint_checks_0 = QCheckBox(TrajectoryPanel)
        self.trajectory_joint_checks_0.setObjectName(u"trajectory_joint_checks_0")
        sizePolicy2.setHeightForWidth(self.trajectory_joint_checks_0.sizePolicy().hasHeightForWidth())
        self.trajectory_joint_checks_0.setSizePolicy(sizePolicy2)
        self.trajectory_joint_checks_0.setCheckable(True)
        self.trajectory_joint_checks_0.setChecked(True)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_joint_checks_0)

        self.trajectory_joint_checks_1 = QCheckBox(TrajectoryPanel)
        self.trajectory_joint_checks_1.setObjectName(u"trajectory_joint_checks_1")
        sizePolicy2.setHeightForWidth(self.trajectory_joint_checks_1.sizePolicy().hasHeightForWidth())
        self.trajectory_joint_checks_1.setSizePolicy(sizePolicy2)
        self.trajectory_joint_checks_1.setCheckable(True)
        self.trajectory_joint_checks_1.setChecked(True)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_joint_checks_1)

        self.trajectory_joint_checks_2 = QCheckBox(TrajectoryPanel)
        self.trajectory_joint_checks_2.setObjectName(u"trajectory_joint_checks_2")
        sizePolicy2.setHeightForWidth(self.trajectory_joint_checks_2.sizePolicy().hasHeightForWidth())
        self.trajectory_joint_checks_2.setSizePolicy(sizePolicy2)
        self.trajectory_joint_checks_2.setCheckable(True)
        self.trajectory_joint_checks_2.setChecked(True)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_joint_checks_2)

        self.trajectory_joint_checks_3 = QCheckBox(TrajectoryPanel)
        self.trajectory_joint_checks_3.setObjectName(u"trajectory_joint_checks_3")
        sizePolicy2.setHeightForWidth(self.trajectory_joint_checks_3.sizePolicy().hasHeightForWidth())
        self.trajectory_joint_checks_3.setSizePolicy(sizePolicy2)
        self.trajectory_joint_checks_3.setCheckable(True)
        self.trajectory_joint_checks_3.setChecked(True)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_joint_checks_3)

        self.trajectory_joint_checks_4 = QCheckBox(TrajectoryPanel)
        self.trajectory_joint_checks_4.setObjectName(u"trajectory_joint_checks_4")
        sizePolicy2.setHeightForWidth(self.trajectory_joint_checks_4.sizePolicy().hasHeightForWidth())
        self.trajectory_joint_checks_4.setSizePolicy(sizePolicy2)
        self.trajectory_joint_checks_4.setCheckable(True)
        self.trajectory_joint_checks_4.setChecked(True)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_joint_checks_4)

        self.trajectory_joint_checks_5 = QCheckBox(TrajectoryPanel)
        self.trajectory_joint_checks_5.setObjectName(u"trajectory_joint_checks_5")
        sizePolicy2.setHeightForWidth(self.trajectory_joint_checks_5.sizePolicy().hasHeightForWidth())
        self.trajectory_joint_checks_5.setSizePolicy(sizePolicy2)
        self.trajectory_joint_checks_5.setCheckable(True)
        self.trajectory_joint_checks_5.setChecked(True)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_joint_checks_5)

        self.trajectory_status_label = QLabel(TrajectoryPanel)
        self.trajectory_status_label.setObjectName(u"trajectory_status_label")
        sizePolicy.setHeightForWidth(self.trajectory_status_label.sizePolicy().hasHeightForWidth())
        self.trajectory_status_label.setSizePolicy(sizePolicy)
        self.trajectory_status_label.setWordWrap(False)
        self.trajectory_status_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.trajectory_status_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.trajectory_HBoxLayout_4.addWidget(self.trajectory_status_label)

        self.trajectory_HBoxLayout_4.setStretch(7, 1)

        self.trajectory_GridLayout_1.addLayout(self.trajectory_HBoxLayout_4, 3, 0, 1, 2)

        self.trajectory_preview_text = QPlainTextEdit(TrajectoryPanel)
        self.trajectory_preview_text.setObjectName(u"trajectory_preview_text")
        self.trajectory_preview_text.setMinimumSize(QSize(0, 64))
        self.trajectory_preview_text.setMaximumSize(QSize(16777215, 92))
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.trajectory_preview_text.sizePolicy().hasHeightForWidth())
        self.trajectory_preview_text.setSizePolicy(sizePolicy4)
        self.trajectory_preview_text.setReadOnly(True)

        self.trajectory_GridLayout_1.addWidget(self.trajectory_preview_text, 4, 0, 1, 2)


        self.retranslateUi(TrajectoryPanel)

        self.trajectory_saved_combo.setCurrentIndex(-1)
        self.trajectory_mode_combo.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(TrajectoryPanel)
    # setupUi

    def retranslateUi(self, TrajectoryPanel):
        self.trajectory_Label_1.setText(QCoreApplication.translate("TrajectoryPanel", u"\u540d\u79f0", None))
        self.trajectory_record_name.setText("")
        self.trajectory_record_name.setPlaceholderText(QCoreApplication.translate("TrajectoryPanel", u"\u8f68\u8ff9\u540d\u79f0\uff0c\u5982 motor_pick_demo_01", None))
        self.trajectory_record_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5f00\u59cb\u8bb0\u5f55", None))
        self.trajectory_finish_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u505c\u6b62\u5e76\u4fdd\u5b58", None))
        self.trajectory_save_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u91cd\u8bd5\u4fdd\u5b58", None))
        self.trajectory_cancel_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u53d6\u6d88\u8bb0\u5f55", None))
        self.trajectory_Label_2.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5df2\u4fdd\u5b58", None))
        self.trajectory_refresh_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5237\u65b0", None))
        self.trajectory_import_json_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5bfc\u5165\u65e7 JSON", None))
        self.trajectory_import_episode_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u5bfc\u5165 LeRobot", None))
        self.trajectory_Label_3.setText(QCoreApplication.translate("TrajectoryPanel", u"Episode", None))
        self.trajectory_episode_spin.setSuffix("")
        self.trajectory_mode_combo.setItemText(0, QCoreApplication.translate("TrajectoryPanel", u"\u76f8\u5bf9 Relative", None))
        self.trajectory_mode_combo.setItemText(1, QCoreApplication.translate("TrajectoryPanel", u"\u7edd\u5bf9 Absolute", None))

#if QT_CONFIG(tooltip)
        self.trajectory_mode_combo.setToolTip(QCoreApplication.translate("TrajectoryPanel", u"\u76f8\u5bf9\uff1a\u4ece\u5f53\u524d\u4f4d\u7f6e\u590d\u73b0\u4f4d\u79fb\uff1b\u7edd\u5bf9\uff1a\u5148\u7528 3 \u79d2\u8fc7\u6e21\u5230\u8f68\u8ff9\u8d77\u70b9", None))
#endif // QT_CONFIG(tooltip)
        self.trajectory_Label_4.setText(QCoreApplication.translate("TrajectoryPanel", u"\u901f\u5ea6", None))
        self.trajectory_speed_spin.setSuffix(QCoreApplication.translate("TrajectoryPanel", u"\u00d7", None))
        self.trajectory_Label_5.setText(QCoreApplication.translate("TrajectoryPanel", u"\u6b21\u6570", None))
        self.trajectory_repeat_spin.setSuffix("")
        self.trajectory_arm_check.setText(QCoreApplication.translate("TrajectoryPanel", u"Arm", None))
        self.trajectory_hand_check.setText(QCoreApplication.translate("TrajectoryPanel", u"Hand", None))
        self.trajectory_preview_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u9884\u89c8", None))
        self.trajectory_play_button.setText(QCoreApplication.translate("TrajectoryPanel", u"\u56de\u653e", None))
        self.trajectory_Label_6.setText(QCoreApplication.translate("TrajectoryPanel", u"\u56de\u653e\u5173\u8282", None))
        self.trajectory_joint_checks_0.setText(QCoreApplication.translate("TrajectoryPanel", u"J1", None))
        self.trajectory_joint_checks_1.setText(QCoreApplication.translate("TrajectoryPanel", u"J2", None))
        self.trajectory_joint_checks_2.setText(QCoreApplication.translate("TrajectoryPanel", u"J3", None))
        self.trajectory_joint_checks_3.setText(QCoreApplication.translate("TrajectoryPanel", u"J4", None))
        self.trajectory_joint_checks_4.setText(QCoreApplication.translate("TrajectoryPanel", u"J5", None))
        self.trajectory_joint_checks_5.setText(QCoreApplication.translate("TrajectoryPanel", u"J6", None))
        self.trajectory_status_label.setText(QCoreApplication.translate("TrajectoryPanel", u"\u672a\u5f55\u5236", None))
        self.trajectory_preview_text.setPlaceholderText(QCoreApplication.translate("TrajectoryPanel", u"\u9009\u62e9\u8f68\u8ff9\u540e\u70b9\u51fb\u9884\u89c8\uff1a\u65f6\u957f\u3001\u5173\u8282\u8303\u56f4\u4e0e\u901f\u5ea6\u3001TCP \u548c Hand \u8303\u56f4", None))
        pass
    # retranslateUi
