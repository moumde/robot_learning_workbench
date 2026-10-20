# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'robot_status_page.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QPlainTextEdit, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_RobotStatusPage(object):
    def setupUi(self, RobotStatusPage):
        if not RobotStatusPage.objectName():
            RobotStatusPage.setObjectName(u"RobotStatusPage")
        RobotStatusPage.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(RobotStatusPage.sizePolicy().hasHeightForWidth())
        RobotStatusPage.setSizePolicy(sizePolicy)
        self.robot_VBoxLayout_1 = QVBoxLayout(RobotStatusPage)
        self.robot_VBoxLayout_1.setSpacing(6)
        self.robot_VBoxLayout_1.setObjectName(u"robot_VBoxLayout_1")
        self.robot_VBoxLayout_1.setContentsMargins(11, 11, 11, 11)
        self.robot_details = QPlainTextEdit(RobotStatusPage)
        self.robot_details.setObjectName(u"robot_details")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.robot_details.sizePolicy().hasHeightForWidth())
        self.robot_details.setSizePolicy(sizePolicy1)
        self.robot_details.setReadOnly(True)

        self.robot_VBoxLayout_1.addWidget(self.robot_details)

        self.robot_HBoxLayout_1 = QHBoxLayout()
        self.robot_HBoxLayout_1.setSpacing(6)
        self.robot_HBoxLayout_1.setObjectName(u"robot_HBoxLayout_1")
        self.robot_HBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.robot_refresh_button = QPushButton(RobotStatusPage)
        self.robot_refresh_button.setObjectName(u"robot_refresh_button")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.robot_refresh_button.sizePolicy().hasHeightForWidth())
        self.robot_refresh_button.setSizePolicy(sizePolicy2)

        self.robot_HBoxLayout_1.addWidget(self.robot_refresh_button)

        self.robot_reset_fault_button = QPushButton(RobotStatusPage)
        self.robot_reset_fault_button.setObjectName(u"robot_reset_fault_button")
        sizePolicy2.setHeightForWidth(self.robot_reset_fault_button.sizePolicy().hasHeightForWidth())
        self.robot_reset_fault_button.setSizePolicy(sizePolicy2)

        self.robot_HBoxLayout_1.addWidget(self.robot_reset_fault_button)

        self.robot_reset_estop_button = QPushButton(RobotStatusPage)
        self.robot_reset_estop_button.setObjectName(u"robot_reset_estop_button")
        sizePolicy2.setHeightForWidth(self.robot_reset_estop_button.sizePolicy().hasHeightForWidth())
        self.robot_reset_estop_button.setSizePolicy(sizePolicy2)

        self.robot_HBoxLayout_1.addWidget(self.robot_reset_estop_button)


        self.robot_VBoxLayout_1.addLayout(self.robot_HBoxLayout_1)


        self.retranslateUi(RobotStatusPage)

        QMetaObject.connectSlotsByName(RobotStatusPage)
    # setupUi

    def retranslateUi(self, RobotStatusPage):
        self.robot_details.setPlaceholderText("")
        self.robot_refresh_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u8bfb\u53d6\u673a\u5668\u4eba\u53cd\u9988", None))
        self.robot_reset_fault_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u590d\u4f4d\u6545\u969c", None))
        self.robot_reset_estop_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u89e3\u9664\u8f6f\u4ef6\u6025\u505c", None))
        pass
    # retranslateUi
