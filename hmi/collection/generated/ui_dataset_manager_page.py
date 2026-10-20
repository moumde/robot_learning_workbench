# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dataset_manager_page.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QSizePolicy, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

class Ui_DatasetManagerPage(object):
    def setupUi(self, DatasetManagerPage):
        if not DatasetManagerPage.objectName():
            DatasetManagerPage.setObjectName(u"DatasetManagerPage")
        DatasetManagerPage.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(DatasetManagerPage.sizePolicy().hasHeightForWidth())
        DatasetManagerPage.setSizePolicy(sizePolicy)
        self.dataset_VBoxLayout_1 = QVBoxLayout(DatasetManagerPage)
        self.dataset_VBoxLayout_1.setSpacing(6)
        self.dataset_VBoxLayout_1.setObjectName(u"dataset_VBoxLayout_1")
        self.dataset_VBoxLayout_1.setContentsMargins(11, 11, 11, 11)
        self.dataset_HBoxLayout_1 = QHBoxLayout()
        self.dataset_HBoxLayout_1.setSpacing(6)
        self.dataset_HBoxLayout_1.setObjectName(u"dataset_HBoxLayout_1")
        self.dataset_HBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.dataset_Label_1 = QLabel(DatasetManagerPage)
        self.dataset_Label_1.setObjectName(u"dataset_Label_1")
        sizePolicy.setHeightForWidth(self.dataset_Label_1.sizePolicy().hasHeightForWidth())
        self.dataset_Label_1.setSizePolicy(sizePolicy)
        self.dataset_Label_1.setWordWrap(False)
        self.dataset_Label_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.dataset_Label_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.dataset_HBoxLayout_1.addWidget(self.dataset_Label_1)

        self.dataset_root_edit = QLineEdit(DatasetManagerPage)
        self.dataset_root_edit.setObjectName(u"dataset_root_edit")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.dataset_root_edit.sizePolicy().hasHeightForWidth())
        self.dataset_root_edit.setSizePolicy(sizePolicy1)

        self.dataset_HBoxLayout_1.addWidget(self.dataset_root_edit)

        self.dataset_scan_button = QPushButton(DatasetManagerPage)
        self.dataset_scan_button.setObjectName(u"dataset_scan_button")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.dataset_scan_button.sizePolicy().hasHeightForWidth())
        self.dataset_scan_button.setSizePolicy(sizePolicy2)

        self.dataset_HBoxLayout_1.addWidget(self.dataset_scan_button)

        self.dataset_validate_button = QPushButton(DatasetManagerPage)
        self.dataset_validate_button.setObjectName(u"dataset_validate_button")
        sizePolicy2.setHeightForWidth(self.dataset_validate_button.sizePolicy().hasHeightForWidth())
        self.dataset_validate_button.setSizePolicy(sizePolicy2)

        self.dataset_HBoxLayout_1.addWidget(self.dataset_validate_button)


        self.dataset_VBoxLayout_1.addLayout(self.dataset_HBoxLayout_1)

        self.dataset_active_label = QLabel(DatasetManagerPage)
        self.dataset_active_label.setObjectName(u"dataset_active_label")
        sizePolicy.setHeightForWidth(self.dataset_active_label.sizePolicy().hasHeightForWidth())
        self.dataset_active_label.setSizePolicy(sizePolicy)
        self.dataset_active_label.setWordWrap(False)
        self.dataset_active_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.dataset_active_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.dataset_VBoxLayout_1.addWidget(self.dataset_active_label)

        self.dataset_table = QTableWidget(DatasetManagerPage)
        if (self.dataset_table.columnCount() < 6):
            self.dataset_table.setColumnCount(6)
        __qtablewidgetitem = QTableWidgetItem()
        self.dataset_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.dataset_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.dataset_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.dataset_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.dataset_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.dataset_table.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        self.dataset_table.setObjectName(u"dataset_table")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.dataset_table.sizePolicy().hasHeightForWidth())
        self.dataset_table.setSizePolicy(sizePolicy3)
        self.dataset_table.setRowCount(0)
        self.dataset_table.setColumnCount(6)
        self.dataset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dataset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.dataset_VBoxLayout_1.addWidget(self.dataset_table)

        self.dataset_details = QPlainTextEdit(DatasetManagerPage)
        self.dataset_details.setObjectName(u"dataset_details")
        self.dataset_details.setMaximumSize(QSize(16777215, 115))
        sizePolicy3.setHeightForWidth(self.dataset_details.sizePolicy().hasHeightForWidth())
        self.dataset_details.setSizePolicy(sizePolicy3)
        self.dataset_details.setReadOnly(True)

        self.dataset_VBoxLayout_1.addWidget(self.dataset_details)

        self.dataset_Label_2 = QLabel(DatasetManagerPage)
        self.dataset_Label_2.setObjectName(u"dataset_Label_2")
        sizePolicy.setHeightForWidth(self.dataset_Label_2.sizePolicy().hasHeightForWidth())
        self.dataset_Label_2.setSizePolicy(sizePolicy)
        self.dataset_Label_2.setWordWrap(False)
        self.dataset_Label_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.dataset_Label_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.dataset_VBoxLayout_1.addWidget(self.dataset_Label_2)

        self.dataset_recovery = QWidget(DatasetManagerPage)
        self.dataset_recovery.setObjectName(u"dataset_recovery")
        self.dataset_recovery_layout = QVBoxLayout(self.dataset_recovery)
        self.dataset_recovery_layout.setObjectName(u"dataset_recovery_layout")
        self.dataset_recovery_layout.setContentsMargins(0, 0, 0, 0)

        self.dataset_VBoxLayout_1.addWidget(self.dataset_recovery)


        self.retranslateUi(DatasetManagerPage)

        QMetaObject.connectSlotsByName(DatasetManagerPage)
    # setupUi

    def retranslateUi(self, DatasetManagerPage):
        self.dataset_Label_1.setText(QCoreApplication.translate("DatasetManagerPage", u"\u6570\u636e\u96c6\u76ee\u5f55", None))
        self.dataset_root_edit.setText("")
        self.dataset_root_edit.setPlaceholderText("")
        self.dataset_scan_button.setText(QCoreApplication.translate("DatasetManagerPage", u"\u626b\u63cf\u6570\u636e\u96c6", None))
        self.dataset_validate_button.setText(QCoreApplication.translate("DatasetManagerPage", u"\u6821\u9a8c\u6240\u9009\u6570\u636e\u96c6", None))
        self.dataset_active_label.setText("")
        ___qtablewidgetitem = self.dataset_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("DatasetManagerPage", u"Task / Dataset", None))
        ___qtablewidgetitem1 = self.dataset_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("DatasetManagerPage", u"Format", None))
        ___qtablewidgetitem2 = self.dataset_table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("DatasetManagerPage", u"Episodes", None))
        ___qtablewidgetitem3 = self.dataset_table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("DatasetManagerPage", u"Frames", None))
        ___qtablewidgetitem4 = self.dataset_table.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("DatasetManagerPage", u"Created At", None))
        ___qtablewidgetitem5 = self.dataset_table.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("DatasetManagerPage", u"Status", None))
        self.dataset_details.setPlaceholderText("")
        self.dataset_Label_2.setText(QCoreApplication.translate("DatasetManagerPage", u"\u672a\u5b8c\u6210\u6279\u6b21\u4e0e Partial Episode", None))
        pass
    # retranslateUi
