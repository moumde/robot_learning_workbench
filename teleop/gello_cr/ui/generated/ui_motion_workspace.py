# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'motion_workspace.ui'
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
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QStackedWidget, QVBoxLayout, QWidget)

class Ui_MotionWorkspace(object):
    def setupUi(self, MotionWorkspace):
        if not MotionWorkspace.objectName():
            MotionWorkspace.setObjectName(u"MotionWorkspace")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(MotionWorkspace.sizePolicy().hasHeightForWidth())
        MotionWorkspace.setSizePolicy(sizePolicy)
        self.motion_layout = QVBoxLayout(MotionWorkspace)
        self.motion_layout.setSpacing(8)
        self.motion_layout.setObjectName(u"motion_layout")
        self.motion_layout.setContentsMargins(0, 0, 0, 0)
        self.motion_modes = QHBoxLayout()
        self.motion_modes.setObjectName(u"motion_modes")
        self.motion_record_mode_button = QPushButton(MotionWorkspace)
        self.motion_mode_group = QButtonGroup(MotionWorkspace)
        self.motion_mode_group.setObjectName(u"motion_mode_group")
        self.motion_mode_group.addButton(self.motion_record_mode_button)
        self.motion_record_mode_button.setObjectName(u"motion_record_mode_button")
        self.motion_record_mode_button.setCheckable(True)
        self.motion_record_mode_button.setProperty(u"role", u"modeTab")

        self.motion_modes.addWidget(self.motion_record_mode_button)

        self.motion_replay_mode_button = QPushButton(MotionWorkspace)
        self.motion_mode_group.addButton(self.motion_replay_mode_button)
        self.motion_replay_mode_button.setObjectName(u"motion_replay_mode_button")
        self.motion_replay_mode_button.setCheckable(True)
        self.motion_replay_mode_button.setChecked(True)
        self.motion_replay_mode_button.setProperty(u"role", u"modeTab")

        self.motion_modes.addWidget(self.motion_replay_mode_button)

        self.motion_plan_mode_button = QPushButton(MotionWorkspace)
        self.motion_mode_group.addButton(self.motion_plan_mode_button)
        self.motion_plan_mode_button.setObjectName(u"motion_plan_mode_button")
        self.motion_plan_mode_button.setCheckable(True)
        self.motion_plan_mode_button.setProperty(u"role", u"modeTab")

        self.motion_modes.addWidget(self.motion_plan_mode_button)

        self.motion_mode_spacer = QSpacerItem(30, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.motion_modes.addItem(self.motion_mode_spacer)


        self.motion_layout.addLayout(self.motion_modes)

        self.motion_mode_hint = QLabel(MotionWorkspace)
        self.motion_mode_hint.setObjectName(u"motion_mode_hint")
        self.motion_mode_hint.setProperty(u"role", u"mutedText")
        self.motion_mode_hint.setWordWrap(True)

        self.motion_layout.addWidget(self.motion_mode_hint)

        self.motion_splitter = QSplitter(MotionWorkspace)
        self.motion_splitter.setObjectName(u"motion_splitter")
        self.motion_splitter.setOrientation(Qt.Horizontal)
        self.motion_splitter.setChildrenCollapsible(False)
        self.motion_library_host = QWidget(self.motion_splitter)
        self.motion_library_host.setObjectName(u"motion_library_host")
        self.motion_library_host.setMinimumSize(QSize(180, 0))
        self.motion_library_host.setMaximumSize(QSize(320, 16777215))
        self.motion_library_layout = QVBoxLayout(self.motion_library_host)
        self.motion_library_layout.setObjectName(u"motion_library_layout")
        self.motion_library_layout.setContentsMargins(0, 0, 0, 0)
        self.motion_splitter.addWidget(self.motion_library_host)
        self.motion_editor_stack = QStackedWidget(self.motion_splitter)
        self.motion_editor_stack.setObjectName(u"motion_editor_stack")
        sizePolicy.setHeightForWidth(self.motion_editor_stack.sizePolicy().hasHeightForWidth())
        self.motion_editor_stack.setSizePolicy(sizePolicy)
        self.motion_trajectory_host = QWidget()
        self.motion_trajectory_host.setObjectName(u"motion_trajectory_host")
        self.motion_trajectory_layout = QVBoxLayout(self.motion_trajectory_host)
        self.motion_trajectory_layout.setObjectName(u"motion_trajectory_layout")
        self.motion_trajectory_layout.setContentsMargins(0, 0, 0, 0)
        self.motion_editor_stack.addWidget(self.motion_trajectory_host)
        self.motion_planning_host = QWidget()
        self.motion_planning_host.setObjectName(u"motion_planning_host")
        self.motion_planning_layout = QVBoxLayout(self.motion_planning_host)
        self.motion_planning_layout.setObjectName(u"motion_planning_layout")
        self.motion_planning_layout.setContentsMargins(0, 0, 0, 0)
        self.motion_editor_stack.addWidget(self.motion_planning_host)
        self.motion_splitter.addWidget(self.motion_editor_stack)

        self.motion_layout.addWidget(self.motion_splitter)

        self.motion_layout.setStretch(2, 1)

        self.retranslateUi(MotionWorkspace)

        QMetaObject.connectSlotsByName(MotionWorkspace)
    # setupUi

    def retranslateUi(self, MotionWorkspace):
        self.motion_record_mode_button.setText(QCoreApplication.translate("MotionWorkspace", u"\u8f68\u8ff9\u5f55\u5236", None))
        self.motion_replay_mode_button.setText(QCoreApplication.translate("MotionWorkspace", u"\u8f68\u8ff9\u56de\u653e", None))
        self.motion_plan_mode_button.setText(QCoreApplication.translate("MotionWorkspace", u"\u8d70\u70b9\u89c4\u5212", None))
        self.motion_mode_hint.setText(QCoreApplication.translate("MotionWorkspace", u"\u4ece\u5de6\u4fa7\u9009\u8f68\u8ff9\uff0c\u9884\u89c8\u540e\u660e\u786e\u5f00\u59cb\u56de\u653e\u3002", None))
        pass
    # retranslateUi
