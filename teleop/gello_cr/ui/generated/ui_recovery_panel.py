# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'recovery_panel.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget)

class Ui_RecoveryPanel(object):
    def setupUi(self, RecoveryPanel):
        if not RecoveryPanel.objectName():
            RecoveryPanel.setObjectName(u"RecoveryPanel")
        RecoveryPanel.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(RecoveryPanel.sizePolicy().hasHeightForWidth())
        RecoveryPanel.setSizePolicy(sizePolicy)
        self.recovery_VBoxLayout_1 = QVBoxLayout(RecoveryPanel)
        self.recovery_VBoxLayout_1.setSpacing(6)
        self.recovery_VBoxLayout_1.setObjectName(u"recovery_VBoxLayout_1")
        self.recovery_VBoxLayout_1.setContentsMargins(11, 11, 11, 11)
        self.recovery_batches = QComboBox(RecoveryPanel)
        self.recovery_batches.setObjectName(u"recovery_batches")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.recovery_batches.sizePolicy().hasHeightForWidth())
        self.recovery_batches.setSizePolicy(sizePolicy1)
        self.recovery_batches.setEditable(False)

        self.recovery_VBoxLayout_1.addWidget(self.recovery_batches)

        self.recovery_summary = QLabel(RecoveryPanel)
        self.recovery_summary.setObjectName(u"recovery_summary")
        sizePolicy.setHeightForWidth(self.recovery_summary.sizePolicy().hasHeightForWidth())
        self.recovery_summary.setSizePolicy(sizePolicy)
        self.recovery_summary.setWordWrap(True)
        self.recovery_summary.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.recovery_summary.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.recovery_VBoxLayout_1.addWidget(self.recovery_summary)

        self.recovery_HBoxLayout_1 = QHBoxLayout()
        self.recovery_HBoxLayout_1.setSpacing(6)
        self.recovery_HBoxLayout_1.setObjectName(u"recovery_HBoxLayout_1")
        self.recovery_HBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.recovery_refresh_button = QPushButton(RecoveryPanel)
        self.recovery_refresh_button.setObjectName(u"recovery_refresh_button")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.recovery_refresh_button.sizePolicy().hasHeightForWidth())
        self.recovery_refresh_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_1.addWidget(self.recovery_refresh_button)

        self.recovery_resume_button = QPushButton(RecoveryPanel)
        self.recovery_resume_button.setObjectName(u"recovery_resume_button")
        sizePolicy2.setHeightForWidth(self.recovery_resume_button.sizePolicy().hasHeightForWidth())
        self.recovery_resume_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_1.addWidget(self.recovery_resume_button)

        self.recovery_finalize_button = QPushButton(RecoveryPanel)
        self.recovery_finalize_button.setObjectName(u"recovery_finalize_button")
        sizePolicy2.setHeightForWidth(self.recovery_finalize_button.sizePolicy().hasHeightForWidth())
        self.recovery_finalize_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_1.addWidget(self.recovery_finalize_button)

        self.recovery_discard_button = QPushButton(RecoveryPanel)
        self.recovery_discard_button.setObjectName(u"recovery_discard_button")
        sizePolicy2.setHeightForWidth(self.recovery_discard_button.sizePolicy().hasHeightForWidth())
        self.recovery_discard_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_1.addWidget(self.recovery_discard_button)


        self.recovery_VBoxLayout_1.addLayout(self.recovery_HBoxLayout_1)

        self.recovery_HBoxLayout_2 = QHBoxLayout()
        self.recovery_HBoxLayout_2.setSpacing(6)
        self.recovery_HBoxLayout_2.setObjectName(u"recovery_HBoxLayout_2")
        self.recovery_HBoxLayout_2.setContentsMargins(0, 0, 0, 0)
        self.recovery_partials = QComboBox(RecoveryPanel)
        self.recovery_partials.setObjectName(u"recovery_partials")
        sizePolicy1.setHeightForWidth(self.recovery_partials.sizePolicy().hasHeightForWidth())
        self.recovery_partials.setSizePolicy(sizePolicy1)
        self.recovery_partials.setEditable(False)

        self.recovery_HBoxLayout_2.addWidget(self.recovery_partials)

        self.recovery_failure_button = QPushButton(RecoveryPanel)
        self.recovery_failure_button.setObjectName(u"recovery_failure_button")
        sizePolicy2.setHeightForWidth(self.recovery_failure_button.sizePolicy().hasHeightForWidth())
        self.recovery_failure_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_2.addWidget(self.recovery_failure_button)

        self.recovery_discard_partial_button = QPushButton(RecoveryPanel)
        self.recovery_discard_partial_button.setObjectName(u"recovery_discard_partial_button")
        sizePolicy2.setHeightForWidth(self.recovery_discard_partial_button.sizePolicy().hasHeightForWidth())
        self.recovery_discard_partial_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_2.addWidget(self.recovery_discard_partial_button)

        self.recovery_HBoxLayout_2.setStretch(0, 1)

        self.recovery_VBoxLayout_1.addLayout(self.recovery_HBoxLayout_2)

        self.recovery_HBoxLayout_3 = QHBoxLayout()
        self.recovery_HBoxLayout_3.setSpacing(6)
        self.recovery_HBoxLayout_3.setObjectName(u"recovery_HBoxLayout_3")
        self.recovery_HBoxLayout_3.setContentsMargins(0, 0, 0, 0)
        self.recovery_suspend_button = QPushButton(RecoveryPanel)
        self.recovery_suspend_button.setObjectName(u"recovery_suspend_button")
        sizePolicy2.setHeightForWidth(self.recovery_suspend_button.sizePolicy().hasHeightForWidth())
        self.recovery_suspend_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_3.addWidget(self.recovery_suspend_button)

        self.recovery_discard_current_button = QPushButton(RecoveryPanel)
        self.recovery_discard_current_button.setObjectName(u"recovery_discard_current_button")
        sizePolicy2.setHeightForWidth(self.recovery_discard_current_button.sizePolicy().hasHeightForWidth())
        self.recovery_discard_current_button.setSizePolicy(sizePolicy2)

        self.recovery_HBoxLayout_3.addWidget(self.recovery_discard_current_button)


        self.recovery_VBoxLayout_1.addLayout(self.recovery_HBoxLayout_3)

        self.recovery_Label_1 = QLabel(RecoveryPanel)
        self.recovery_Label_1.setObjectName(u"recovery_Label_1")
        sizePolicy.setHeightForWidth(self.recovery_Label_1.sizePolicy().hasHeightForWidth())
        self.recovery_Label_1.setSizePolicy(sizePolicy)
        self.recovery_Label_1.setWordWrap(True)
        self.recovery_Label_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.recovery_Label_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.recovery_VBoxLayout_1.addWidget(self.recovery_Label_1)


        self.retranslateUi(RecoveryPanel)

        self.recovery_batches.setCurrentIndex(-1)
        self.recovery_partials.setCurrentIndex(-1)


        QMetaObject.connectSlotsByName(RecoveryPanel)
    # setupUi

    def retranslateUi(self, RecoveryPanel):
        self.recovery_summary.setText(QCoreApplication.translate("RecoveryPanel", u"\u6ca1\u6709\u672a\u5b8c\u6210\u6279\u6b21", None))
        self.recovery_refresh_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u5237\u65b0\u672a\u5b8c\u6210\u6279\u6b21", None))
        self.recovery_resume_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u7ee7\u7eed\u91c7\u96c6\uff08\u65b0\u5206\u6bb5\uff09", None))
        self.recovery_finalize_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u7ed3\u675f\u5e76\u5408\u5e76", None))
        self.recovery_discard_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u4e22\u5f03\u6240\u9009\u6279\u6b21", None))
        self.recovery_failure_button.setText(QCoreApplication.translate("RecoveryPanel", u"Partial \u4fdd\u7559\u4e3a Failure", None))
        self.recovery_discard_partial_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u4e22\u5f03 Partial", None))
        self.recovery_suspend_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u4fdd\u7559\u5f53\u524d\u6279\u6b21\uff0c\u7a0d\u540e\u7ee7\u7eed", None))
        self.recovery_discard_current_button.setText(QCoreApplication.translate("RecoveryPanel", u"\u4e22\u5f03\u5f53\u524d\u6279\u6b21", None))
        self.recovery_Label_1.setText(QCoreApplication.translate("RecoveryPanel", u"\u6062\u590d\u65f6\u81ea\u52a8\u91c7\u7528\u539f\u6279\u6b21\u683c\u5f0f\uff1b\u8bf7\u4fdd\u6301\u673a\u5668\u4eba\u4e0e\u91c7\u6837\u914d\u7f6e\u4e00\u81f4\u3002\u5408\u5e76\u540e\u4fdd\u7559\u539f\u5206\u6bb5\uff1b\u4e22\u5f03\u4ec5\u4f5c\u6807\u8bb0\uff0c\u4fdd\u7559 staging \u6587\u4ef6\u3002", None))
        pass
    # retranslateUi
