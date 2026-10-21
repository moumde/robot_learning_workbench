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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
    QWidget)

class Ui_RobotStatusPage(object):
    def setupUi(self, RobotStatusPage):
        if not RobotStatusPage.objectName():
            RobotStatusPage.setObjectName(u"RobotStatusPage")
        RobotStatusPage.resize(966, 511)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(RobotStatusPage.sizePolicy().hasHeightForWidth())
        RobotStatusPage.setSizePolicy(sizePolicy)
        self.robot_page_layout = QVBoxLayout(RobotStatusPage)
        self.robot_page_layout.setSpacing(8)
        self.robot_page_layout.setObjectName(u"robot_page_layout")
        self.robot_page_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_content_scroll = QScrollArea(RobotStatusPage)
        self.robot_content_scroll.setObjectName(u"robot_content_scroll")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.robot_content_scroll.sizePolicy().hasHeightForWidth())
        self.robot_content_scroll.setSizePolicy(sizePolicy1)
        self.robot_content_scroll.setFrameShape(QFrame.NoFrame)
        self.robot_content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.robot_content_scroll.setWidgetResizable(True)
        self.robot_content_widget = QWidget()
        self.robot_content_widget.setObjectName(u"robot_content_widget")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.robot_content_widget.sizePolicy().hasHeightForWidth())
        self.robot_content_widget.setSizePolicy(sizePolicy2)
        self.robot_content_layout = QVBoxLayout(self.robot_content_widget)
        self.robot_content_layout.setSpacing(8)
        self.robot_content_layout.setObjectName(u"robot_content_layout")
        self.robot_content_layout.setContentsMargins(0, 0, 8, 8)
        self.robot_header_layout = QHBoxLayout()
        self.robot_header_layout.setSpacing(8)
        self.robot_header_layout.setObjectName(u"robot_header_layout")
        self.robot_header_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_identity_layout = QVBoxLayout()
        self.robot_identity_layout.setSpacing(2)
        self.robot_identity_layout.setObjectName(u"robot_identity_layout")
        self.robot_identity_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_identity_label = QLabel(self.robot_content_widget)
        self.robot_identity_label.setObjectName(u"robot_identity_label")
        self.robot_identity_label.setProperty(u"role", u"sectionTitle")
        self.robot_identity_label.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_identity_label.sizePolicy().hasHeightForWidth())
        self.robot_identity_label.setSizePolicy(sizePolicy2)

        self.robot_identity_layout.addWidget(self.robot_identity_label)

        self.robot_endpoint_label = QLabel(self.robot_content_widget)
        self.robot_endpoint_label.setObjectName(u"robot_endpoint_label")
        self.robot_endpoint_label.setProperty(u"role", u"mutedText")
        self.robot_endpoint_label.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_endpoint_label.sizePolicy().hasHeightForWidth())
        self.robot_endpoint_label.setSizePolicy(sizePolicy2)

        self.robot_identity_layout.addWidget(self.robot_endpoint_label)


        self.robot_header_layout.addLayout(self.robot_identity_layout)

        self.robot_connection_button = QPushButton(self.robot_content_widget)
        self.robot_connection_button.setObjectName(u"robot_connection_button")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.robot_connection_button.sizePolicy().hasHeightForWidth())
        self.robot_connection_button.setSizePolicy(sizePolicy3)
        self.robot_connection_button.setProperty(u"role", u"quiet")

        self.robot_header_layout.addWidget(self.robot_connection_button)

        self.robot_header_layout.setStretch(0, 1)

        self.robot_content_layout.addLayout(self.robot_header_layout)

        self.robot_summary_grid = QGridLayout()
        self.robot_summary_grid.setSpacing(8)
        self.robot_summary_grid.setObjectName(u"robot_summary_grid")
        self.robot_summary_grid.setContentsMargins(0, 0, 0, 0)
        self.robot_connection_summary = QWidget(self.robot_content_widget)
        self.robot_connection_summary.setObjectName(u"robot_connection_summary")
        self.robot_connection_layout = QHBoxLayout(self.robot_connection_summary)
        self.robot_connection_layout.setSpacing(8)
        self.robot_connection_layout.setObjectName(u"robot_connection_layout")
        self.robot_connection_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_connection_label = QLabel(self.robot_connection_summary)
        self.robot_connection_label.setObjectName(u"robot_connection_label")
        self.robot_connection_label.setProperty(u"role", u"mutedText")
        self.robot_connection_label.setMinimumSize(QSize(72, 0))

        self.robot_connection_layout.addWidget(self.robot_connection_label)

        self.robot_connection_value = QLabel(self.robot_connection_summary)
        self.robot_connection_value.setObjectName(u"robot_connection_value")
        self.robot_connection_value.setProperty(u"role", u"statusPill")
        self.robot_connection_value.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_connection_value.sizePolicy().hasHeightForWidth())
        self.robot_connection_value.setSizePolicy(sizePolicy2)
        self.robot_connection_value.setAlignment(Qt.AlignCenter)

        self.robot_connection_layout.addWidget(self.robot_connection_value)

        self.robot_connection_layout.setStretch(1, 1)

        self.robot_summary_grid.addWidget(self.robot_connection_summary, 0, 0, 1, 1)

        self.robot_servo_summary = QWidget(self.robot_content_widget)
        self.robot_servo_summary.setObjectName(u"robot_servo_summary")
        self.robot_servo_layout = QHBoxLayout(self.robot_servo_summary)
        self.robot_servo_layout.setSpacing(8)
        self.robot_servo_layout.setObjectName(u"robot_servo_layout")
        self.robot_servo_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_servo_label = QLabel(self.robot_servo_summary)
        self.robot_servo_label.setObjectName(u"robot_servo_label")
        self.robot_servo_label.setProperty(u"role", u"mutedText")
        self.robot_servo_label.setMinimumSize(QSize(72, 0))

        self.robot_servo_layout.addWidget(self.robot_servo_label)

        self.robot_servo_value = QLabel(self.robot_servo_summary)
        self.robot_servo_value.setObjectName(u"robot_servo_value")
        self.robot_servo_value.setProperty(u"role", u"statusPill")
        self.robot_servo_value.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_servo_value.sizePolicy().hasHeightForWidth())
        self.robot_servo_value.setSizePolicy(sizePolicy2)
        self.robot_servo_value.setAlignment(Qt.AlignCenter)

        self.robot_servo_layout.addWidget(self.robot_servo_value)

        self.robot_servo_layout.setStretch(1, 1)

        self.robot_summary_grid.addWidget(self.robot_servo_summary, 0, 1, 1, 1)

        self.robot_motion_summary = QWidget(self.robot_content_widget)
        self.robot_motion_summary.setObjectName(u"robot_motion_summary")
        self.robot_motion_layout = QHBoxLayout(self.robot_motion_summary)
        self.robot_motion_layout.setSpacing(8)
        self.robot_motion_layout.setObjectName(u"robot_motion_layout")
        self.robot_motion_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_motion_label = QLabel(self.robot_motion_summary)
        self.robot_motion_label.setObjectName(u"robot_motion_label")
        self.robot_motion_label.setProperty(u"role", u"mutedText")
        self.robot_motion_label.setMinimumSize(QSize(72, 0))

        self.robot_motion_layout.addWidget(self.robot_motion_label)

        self.robot_motion_value = QLabel(self.robot_motion_summary)
        self.robot_motion_value.setObjectName(u"robot_motion_value")
        self.robot_motion_value.setProperty(u"role", u"statusPill")
        self.robot_motion_value.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_motion_value.sizePolicy().hasHeightForWidth())
        self.robot_motion_value.setSizePolicy(sizePolicy2)
        self.robot_motion_value.setAlignment(Qt.AlignCenter)

        self.robot_motion_layout.addWidget(self.robot_motion_value)

        self.robot_motion_layout.setStretch(1, 1)

        self.robot_summary_grid.addWidget(self.robot_motion_summary, 0, 2, 1, 1)

        self.robot_master_summary = QWidget(self.robot_content_widget)
        self.robot_master_summary.setObjectName(u"robot_master_summary")
        self.robot_master_layout = QHBoxLayout(self.robot_master_summary)
        self.robot_master_layout.setSpacing(8)
        self.robot_master_layout.setObjectName(u"robot_master_layout")
        self.robot_master_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_master_label = QLabel(self.robot_master_summary)
        self.robot_master_label.setObjectName(u"robot_master_label")
        self.robot_master_label.setProperty(u"role", u"mutedText")
        self.robot_master_label.setMinimumSize(QSize(72, 0))

        self.robot_master_layout.addWidget(self.robot_master_label)

        self.robot_master_value = QLabel(self.robot_master_summary)
        self.robot_master_value.setObjectName(u"robot_master_value")
        self.robot_master_value.setProperty(u"role", u"statusPill")
        self.robot_master_value.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_master_value.sizePolicy().hasHeightForWidth())
        self.robot_master_value.setSizePolicy(sizePolicy2)
        self.robot_master_value.setAlignment(Qt.AlignCenter)

        self.robot_master_layout.addWidget(self.robot_master_value)

        self.robot_master_layout.setStretch(1, 1)

        self.robot_summary_grid.addWidget(self.robot_master_summary, 1, 0, 1, 1)

        self.robot_hand_summary = QWidget(self.robot_content_widget)
        self.robot_hand_summary.setObjectName(u"robot_hand_summary")
        self.robot_hand_layout = QHBoxLayout(self.robot_hand_summary)
        self.robot_hand_layout.setSpacing(8)
        self.robot_hand_layout.setObjectName(u"robot_hand_layout")
        self.robot_hand_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_hand_label = QLabel(self.robot_hand_summary)
        self.robot_hand_label.setObjectName(u"robot_hand_label")
        self.robot_hand_label.setProperty(u"role", u"mutedText")
        self.robot_hand_label.setMinimumSize(QSize(72, 0))

        self.robot_hand_layout.addWidget(self.robot_hand_label)

        self.robot_hand_value = QLabel(self.robot_hand_summary)
        self.robot_hand_value.setObjectName(u"robot_hand_value")
        self.robot_hand_value.setProperty(u"role", u"statusPill")
        self.robot_hand_value.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_hand_value.sizePolicy().hasHeightForWidth())
        self.robot_hand_value.setSizePolicy(sizePolicy2)
        self.robot_hand_value.setAlignment(Qt.AlignCenter)

        self.robot_hand_layout.addWidget(self.robot_hand_value)

        self.robot_hand_layout.setStretch(1, 1)

        self.robot_summary_grid.addWidget(self.robot_hand_summary, 1, 1, 1, 1)

        self.robot_recording_summary = QWidget(self.robot_content_widget)
        self.robot_recording_summary.setObjectName(u"robot_recording_summary")
        self.robot_recording_layout = QHBoxLayout(self.robot_recording_summary)
        self.robot_recording_layout.setSpacing(8)
        self.robot_recording_layout.setObjectName(u"robot_recording_layout")
        self.robot_recording_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_recording_label = QLabel(self.robot_recording_summary)
        self.robot_recording_label.setObjectName(u"robot_recording_label")
        self.robot_recording_label.setProperty(u"role", u"mutedText")
        self.robot_recording_label.setMinimumSize(QSize(72, 0))

        self.robot_recording_layout.addWidget(self.robot_recording_label)

        self.robot_recording_value = QLabel(self.robot_recording_summary)
        self.robot_recording_value.setObjectName(u"robot_recording_value")
        self.robot_recording_value.setProperty(u"role", u"statusPill")
        self.robot_recording_value.setWordWrap(True)
        sizePolicy2.setHeightForWidth(self.robot_recording_value.sizePolicy().hasHeightForWidth())
        self.robot_recording_value.setSizePolicy(sizePolicy2)
        self.robot_recording_value.setAlignment(Qt.AlignCenter)

        self.robot_recording_layout.addWidget(self.robot_recording_value)

        self.robot_recording_layout.setStretch(1, 1)

        self.robot_summary_grid.addWidget(self.robot_recording_summary, 1, 2, 1, 1)

        self.robot_summary_grid.setColumnStretch(0, 1)
        self.robot_summary_grid.setColumnStretch(1, 1)
        self.robot_summary_grid.setColumnStretch(2, 1)

        self.robot_content_layout.addLayout(self.robot_summary_grid)

        self.robot_fault_layout = QVBoxLayout()
        self.robot_fault_layout.setSpacing(4)
        self.robot_fault_layout.setObjectName(u"robot_fault_layout")
        self.robot_fault_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_fault_banner = QLabel(self.robot_content_widget)
        self.robot_fault_banner.setObjectName(u"robot_fault_banner")
        self.robot_fault_banner.setProperty(u"role", u"faultBanner")
        self.robot_fault_banner.setWordWrap(True)
        self.robot_fault_banner.setVisible(False)

        self.robot_fault_layout.addWidget(self.robot_fault_banner)

        self.robot_fault_code = QLabel(self.robot_content_widget)
        self.robot_fault_code.setObjectName(u"robot_fault_code")
        self.robot_fault_code.setProperty(u"role", u"mutedText")
        self.robot_fault_code.setWordWrap(True)
        self.robot_fault_code.setVisible(False)

        self.robot_fault_layout.addWidget(self.robot_fault_code)

        self.robot_fault_hint = QLabel(self.robot_content_widget)
        self.robot_fault_hint.setObjectName(u"robot_fault_hint")
        self.robot_fault_hint.setProperty(u"role", u"mutedText")
        self.robot_fault_hint.setWordWrap(True)
        self.robot_fault_hint.setVisible(False)

        self.robot_fault_layout.addWidget(self.robot_fault_hint)


        self.robot_content_layout.addLayout(self.robot_fault_layout)

        self.robot_feedback_hint = QLabel(self.robot_content_widget)
        self.robot_feedback_hint.setObjectName(u"robot_feedback_hint")
        self.robot_feedback_hint.setProperty(u"role", u"mutedText")
        self.robot_feedback_hint.setWordWrap(True)

        self.robot_content_layout.addWidget(self.robot_feedback_hint)

        self.robot_positions_layout = QHBoxLayout()
        self.robot_positions_layout.setSpacing(12)
        self.robot_positions_layout.setObjectName(u"robot_positions_layout")
        self.robot_positions_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_joint_layout_column = QVBoxLayout()
        self.robot_joint_layout_column.setSpacing(4)
        self.robot_joint_layout_column.setObjectName(u"robot_joint_layout_column")
        self.robot_joint_layout_column.setContentsMargins(0, 0, 0, 0)
        self.robot_joint_heading = QLabel(self.robot_content_widget)
        self.robot_joint_heading.setObjectName(u"robot_joint_heading")
        self.robot_joint_heading.setProperty(u"role", u"sectionTitle")

        self.robot_joint_layout_column.addWidget(self.robot_joint_heading)

        self.robot_joint_table = QTableWidget(self.robot_content_widget)
        if (self.robot_joint_table.columnCount() < 2):
            self.robot_joint_table.setColumnCount(2)
        __qtablewidgetitem = QTableWidgetItem()
        self.robot_joint_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.robot_joint_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        if (self.robot_joint_table.rowCount() < 6):
            self.robot_joint_table.setRowCount(6)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.robot_joint_table.setItem(0, 0, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        __qtablewidgetitem3.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_joint_table.setItem(0, 1, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.robot_joint_table.setItem(1, 0, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        __qtablewidgetitem5.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_joint_table.setItem(1, 1, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.robot_joint_table.setItem(2, 0, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        __qtablewidgetitem7.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_joint_table.setItem(2, 1, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.robot_joint_table.setItem(3, 0, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        __qtablewidgetitem9.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_joint_table.setItem(3, 1, __qtablewidgetitem9)
        __qtablewidgetitem10 = QTableWidgetItem()
        self.robot_joint_table.setItem(4, 0, __qtablewidgetitem10)
        __qtablewidgetitem11 = QTableWidgetItem()
        __qtablewidgetitem11.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_joint_table.setItem(4, 1, __qtablewidgetitem11)
        __qtablewidgetitem12 = QTableWidgetItem()
        self.robot_joint_table.setItem(5, 0, __qtablewidgetitem12)
        __qtablewidgetitem13 = QTableWidgetItem()
        __qtablewidgetitem13.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_joint_table.setItem(5, 1, __qtablewidgetitem13)
        self.robot_joint_table.setObjectName(u"robot_joint_table")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.robot_joint_table.sizePolicy().hasHeightForWidth())
        self.robot_joint_table.setSizePolicy(sizePolicy4)
        self.robot_joint_table.setMinimumSize(QSize(260, 186))
        self.robot_joint_table.setMaximumSize(QSize(16777215, 186))
        self.robot_joint_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.robot_joint_table.setAlternatingRowColors(True)
        self.robot_joint_table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.robot_joint_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.robot_joint_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.robot_joint_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.robot_joint_table.setShowGrid(True)
        self.robot_joint_table.setWordWrap(False)
        self.robot_joint_table.setRowCount(6)
        self.robot_joint_table.setColumnCount(2)
        self.robot_joint_table.horizontalHeader().setDefaultSectionSize(110)
        self.robot_joint_table.horizontalHeader().setStretchLastSection(True)
        self.robot_joint_table.verticalHeader().setVisible(False)
        self.robot_joint_table.verticalHeader().setMinimumSectionSize(24)
        self.robot_joint_table.verticalHeader().setDefaultSectionSize(24)

        self.robot_joint_layout_column.addWidget(self.robot_joint_table)


        self.robot_positions_layout.addLayout(self.robot_joint_layout_column)

        self.robot_tcp_layout_column = QVBoxLayout()
        self.robot_tcp_layout_column.setSpacing(4)
        self.robot_tcp_layout_column.setObjectName(u"robot_tcp_layout_column")
        self.robot_tcp_layout_column.setContentsMargins(0, 0, 0, 0)
        self.robot_tcp_heading = QLabel(self.robot_content_widget)
        self.robot_tcp_heading.setObjectName(u"robot_tcp_heading")
        self.robot_tcp_heading.setProperty(u"role", u"sectionTitle")

        self.robot_tcp_layout_column.addWidget(self.robot_tcp_heading)

        self.robot_tcp_table = QTableWidget(self.robot_content_widget)
        if (self.robot_tcp_table.columnCount() < 2):
            self.robot_tcp_table.setColumnCount(2)
        __qtablewidgetitem14 = QTableWidgetItem()
        self.robot_tcp_table.setHorizontalHeaderItem(0, __qtablewidgetitem14)
        __qtablewidgetitem15 = QTableWidgetItem()
        self.robot_tcp_table.setHorizontalHeaderItem(1, __qtablewidgetitem15)
        if (self.robot_tcp_table.rowCount() < 6):
            self.robot_tcp_table.setRowCount(6)
        __qtablewidgetitem16 = QTableWidgetItem()
        self.robot_tcp_table.setItem(0, 0, __qtablewidgetitem16)
        __qtablewidgetitem17 = QTableWidgetItem()
        __qtablewidgetitem17.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_tcp_table.setItem(0, 1, __qtablewidgetitem17)
        __qtablewidgetitem18 = QTableWidgetItem()
        self.robot_tcp_table.setItem(1, 0, __qtablewidgetitem18)
        __qtablewidgetitem19 = QTableWidgetItem()
        __qtablewidgetitem19.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_tcp_table.setItem(1, 1, __qtablewidgetitem19)
        __qtablewidgetitem20 = QTableWidgetItem()
        self.robot_tcp_table.setItem(2, 0, __qtablewidgetitem20)
        __qtablewidgetitem21 = QTableWidgetItem()
        __qtablewidgetitem21.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_tcp_table.setItem(2, 1, __qtablewidgetitem21)
        __qtablewidgetitem22 = QTableWidgetItem()
        self.robot_tcp_table.setItem(3, 0, __qtablewidgetitem22)
        __qtablewidgetitem23 = QTableWidgetItem()
        __qtablewidgetitem23.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_tcp_table.setItem(3, 1, __qtablewidgetitem23)
        __qtablewidgetitem24 = QTableWidgetItem()
        self.robot_tcp_table.setItem(4, 0, __qtablewidgetitem24)
        __qtablewidgetitem25 = QTableWidgetItem()
        __qtablewidgetitem25.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_tcp_table.setItem(4, 1, __qtablewidgetitem25)
        __qtablewidgetitem26 = QTableWidgetItem()
        self.robot_tcp_table.setItem(5, 0, __qtablewidgetitem26)
        __qtablewidgetitem27 = QTableWidgetItem()
        __qtablewidgetitem27.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.robot_tcp_table.setItem(5, 1, __qtablewidgetitem27)
        self.robot_tcp_table.setObjectName(u"robot_tcp_table")
        sizePolicy4.setHeightForWidth(self.robot_tcp_table.sizePolicy().hasHeightForWidth())
        self.robot_tcp_table.setSizePolicy(sizePolicy4)
        self.robot_tcp_table.setMinimumSize(QSize(260, 186))
        self.robot_tcp_table.setMaximumSize(QSize(16777215, 186))
        self.robot_tcp_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.robot_tcp_table.setAlternatingRowColors(True)
        self.robot_tcp_table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.robot_tcp_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.robot_tcp_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.robot_tcp_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.robot_tcp_table.setShowGrid(True)
        self.robot_tcp_table.setWordWrap(False)
        self.robot_tcp_table.setRowCount(6)
        self.robot_tcp_table.setColumnCount(2)
        self.robot_tcp_table.horizontalHeader().setDefaultSectionSize(110)
        self.robot_tcp_table.horizontalHeader().setStretchLastSection(True)
        self.robot_tcp_table.verticalHeader().setVisible(False)
        self.robot_tcp_table.verticalHeader().setMinimumSectionSize(24)
        self.robot_tcp_table.verticalHeader().setDefaultSectionSize(24)

        self.robot_tcp_layout_column.addWidget(self.robot_tcp_table)


        self.robot_positions_layout.addLayout(self.robot_tcp_layout_column)

        self.robot_positions_layout.setStretch(0, 1)
        self.robot_positions_layout.setStretch(1, 1)

        self.robot_content_layout.addLayout(self.robot_positions_layout)

        self.robot_details_toggle_layout = QHBoxLayout()
        self.robot_details_toggle_layout.setSpacing(8)
        self.robot_details_toggle_layout.setObjectName(u"robot_details_toggle_layout")
        self.robot_details_toggle_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_details_toggle = QToolButton(self.robot_content_widget)
        self.robot_details_toggle.setObjectName(u"robot_details_toggle")
        sizePolicy3.setHeightForWidth(self.robot_details_toggle.sizePolicy().hasHeightForWidth())
        self.robot_details_toggle.setSizePolicy(sizePolicy3)
        self.robot_details_toggle.setCheckable(True)
        self.robot_details_toggle.setChecked(False)
        self.robot_details_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.robot_details_toggle.setArrowType(Qt.RightArrow)

        self.robot_details_toggle_layout.addWidget(self.robot_details_toggle)

        self.robot_details_toggle_spacer = QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.robot_details_toggle_layout.addItem(self.robot_details_toggle_spacer)


        self.robot_content_layout.addLayout(self.robot_details_toggle_layout)

        self.robot_technical_panel = QWidget(self.robot_content_widget)
        self.robot_technical_panel.setObjectName(u"robot_technical_panel")
        self.robot_technical_panel.setVisible(False)
        self.robot_technical_layout = QVBoxLayout(self.robot_technical_panel)
        self.robot_technical_layout.setSpacing(6)
        self.robot_technical_layout.setObjectName(u"robot_technical_layout")
        self.robot_technical_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_details = QPlainTextEdit(self.robot_technical_panel)
        self.robot_details.setObjectName(u"robot_details")
        sizePolicy4.setHeightForWidth(self.robot_details.sizePolicy().hasHeightForWidth())
        self.robot_details.setSizePolicy(sizePolicy4)
        self.robot_details.setMinimumSize(QSize(0, 96))
        self.robot_details.setMaximumSize(QSize(16777215, 140))
        self.robot_details.setReadOnly(True)
        self.robot_details.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.robot_technical_layout.addWidget(self.robot_details)

        self.robot_details_actions_layout = QHBoxLayout()
        self.robot_details_actions_layout.setSpacing(8)
        self.robot_details_actions_layout.setObjectName(u"robot_details_actions_layout")
        self.robot_details_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_copy_details_spacer = QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.robot_details_actions_layout.addItem(self.robot_copy_details_spacer)

        self.robot_copy_details_button = QPushButton(self.robot_technical_panel)
        self.robot_copy_details_button.setObjectName(u"robot_copy_details_button")
        sizePolicy3.setHeightForWidth(self.robot_copy_details_button.sizePolicy().hasHeightForWidth())
        self.robot_copy_details_button.setSizePolicy(sizePolicy3)
        self.robot_copy_details_button.setProperty(u"role", u"quiet")

        self.robot_details_actions_layout.addWidget(self.robot_copy_details_button)


        self.robot_technical_layout.addLayout(self.robot_details_actions_layout)


        self.robot_content_layout.addWidget(self.robot_technical_panel)

        self.robot_content_spacer = QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.robot_content_layout.addItem(self.robot_content_spacer)

        self.robot_content_scroll.setWidget(self.robot_content_widget)

        self.robot_page_layout.addWidget(self.robot_content_scroll)

        self.robot_actions_layout = QHBoxLayout()
        self.robot_actions_layout.setSpacing(8)
        self.robot_actions_layout.setObjectName(u"robot_actions_layout")
        self.robot_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.robot_refresh_button = QPushButton(RobotStatusPage)
        self.robot_refresh_button.setObjectName(u"robot_refresh_button")
        sizePolicy3.setHeightForWidth(self.robot_refresh_button.sizePolicy().hasHeightForWidth())
        self.robot_refresh_button.setSizePolicy(sizePolicy3)
        self.robot_refresh_button.setProperty(u"role", u"primary")

        self.robot_actions_layout.addWidget(self.robot_refresh_button)

        self.robot_actions_spacer = QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.robot_actions_layout.addItem(self.robot_actions_spacer)

        self.robot_reset_fault_button = QPushButton(RobotStatusPage)
        self.robot_reset_fault_button.setObjectName(u"robot_reset_fault_button")
        sizePolicy3.setHeightForWidth(self.robot_reset_fault_button.sizePolicy().hasHeightForWidth())
        self.robot_reset_fault_button.setSizePolicy(sizePolicy3)

        self.robot_actions_layout.addWidget(self.robot_reset_fault_button)

        self.robot_reset_estop_button = QPushButton(RobotStatusPage)
        self.robot_reset_estop_button.setObjectName(u"robot_reset_estop_button")
        sizePolicy3.setHeightForWidth(self.robot_reset_estop_button.sizePolicy().hasHeightForWidth())
        self.robot_reset_estop_button.setSizePolicy(sizePolicy3)

        self.robot_actions_layout.addWidget(self.robot_reset_estop_button)


        self.robot_page_layout.addLayout(self.robot_actions_layout)

        self.robot_page_layout.setStretch(0, 1)

        self.retranslateUi(RobotStatusPage)

        QMetaObject.connectSlotsByName(RobotStatusPage)
    # setupUi

    def retranslateUi(self, RobotStatusPage):
        self.robot_identity_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u673a\u5668\u4eba", None))
        self.robot_endpoint_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u8fde\u63a5\u4fe1\u606f\u672a\u8bfb\u53d6", None))
        self.robot_connection_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u524d\u5f80\u8bbe\u5907\u8fde\u63a5", None))
#if QT_CONFIG(tooltip)
        self.robot_connection_button.setToolTip(QCoreApplication.translate("RobotStatusPage", u"\u6253\u5f00\u8bbe\u5907\u8fde\u63a5\u9875\u9762", None))
#endif // QT_CONFIG(tooltip)
        self.robot_connection_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u673a\u5668\u4eba\u8fde\u63a5", None))
        self.robot_connection_value.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_servo_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u4f3a\u670d\u72b6\u6001", None))
        self.robot_servo_value.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_motion_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u8fd0\u52a8\u72b6\u6001", None))
        self.robot_motion_value.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_master_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u4e3b\u63a7\u8bbe\u5907", None))
        self.robot_master_value.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_hand_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u7075\u5de7\u624b", None))
        self.robot_hand_value.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_recording_label.setText(QCoreApplication.translate("RobotStatusPage", u"\u5f55\u5236\u72b6\u6001", None))
        self.robot_recording_value.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_fault_banner.setText(QCoreApplication.translate("RobotStatusPage", u"\u6682\u65e0\u6545\u969c", None))
        self.robot_fault_code.setText("")
        self.robot_fault_hint.setText("")
        self.robot_feedback_hint.setText(QCoreApplication.translate("RobotStatusPage", u"\u4f4d\u7f6e\u53cd\u9988\u4e3a\u624b\u52a8\u8bfb\u53d6\u7684\u5feb\u7167\uff1b\u70b9\u51fb\u201c\u8bfb\u53d6\u673a\u5668\u4eba\u53cd\u9988\u201d\u66f4\u65b0\u3002", None))
        self.robot_joint_heading.setText(QCoreApplication.translate("RobotStatusPage", u"\u5173\u8282\u4f4d\u7f6e", None))
        ___qtablewidgetitem = self.robot_joint_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("RobotStatusPage", u"\u5173\u8282", None))
        ___qtablewidgetitem1 = self.robot_joint_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("RobotStatusPage", u"\u89d2\u5ea6 (\u00b0)", None))

        __sortingEnabled = self.robot_joint_table.isSortingEnabled()
        self.robot_joint_table.setSortingEnabled(False)
        ___qtablewidgetitem2 = self.robot_joint_table.item(0, 0)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("RobotStatusPage", u"J1", None))
        ___qtablewidgetitem3 = self.robot_joint_table.item(0, 1)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem4 = self.robot_joint_table.item(1, 0)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("RobotStatusPage", u"J2", None))
        ___qtablewidgetitem5 = self.robot_joint_table.item(1, 1)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem6 = self.robot_joint_table.item(2, 0)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("RobotStatusPage", u"J3", None))
        ___qtablewidgetitem7 = self.robot_joint_table.item(2, 1)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem8 = self.robot_joint_table.item(3, 0)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("RobotStatusPage", u"J4", None))
        ___qtablewidgetitem9 = self.robot_joint_table.item(3, 1)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem10 = self.robot_joint_table.item(4, 0)
        ___qtablewidgetitem10.setText(QCoreApplication.translate("RobotStatusPage", u"J5", None))
        ___qtablewidgetitem11 = self.robot_joint_table.item(4, 1)
        ___qtablewidgetitem11.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem12 = self.robot_joint_table.item(5, 0)
        ___qtablewidgetitem12.setText(QCoreApplication.translate("RobotStatusPage", u"J6", None))
        ___qtablewidgetitem13 = self.robot_joint_table.item(5, 1)
        ___qtablewidgetitem13.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_joint_table.setSortingEnabled(__sortingEnabled)

#if QT_CONFIG(accessibility)
        self.robot_joint_table.setAccessibleName(QCoreApplication.translate("RobotStatusPage", u"\u5173\u8282\u4f4d\u7f6e", None))
#endif // QT_CONFIG(accessibility)
        self.robot_tcp_heading.setText(QCoreApplication.translate("RobotStatusPage", u"TCP \u4f4d\u59ff", None))
        ___qtablewidgetitem14 = self.robot_tcp_table.horizontalHeaderItem(0)
        ___qtablewidgetitem14.setText(QCoreApplication.translate("RobotStatusPage", u"\u5206\u91cf", None))
        ___qtablewidgetitem15 = self.robot_tcp_table.horizontalHeaderItem(1)
        ___qtablewidgetitem15.setText(QCoreApplication.translate("RobotStatusPage", u"\u4f4d\u7f6e / \u89d2\u5ea6", None))

        __sortingEnabled1 = self.robot_tcp_table.isSortingEnabled()
        self.robot_tcp_table.setSortingEnabled(False)
        ___qtablewidgetitem16 = self.robot_tcp_table.item(0, 0)
        ___qtablewidgetitem16.setText(QCoreApplication.translate("RobotStatusPage", u"X (mm)", None))
        ___qtablewidgetitem17 = self.robot_tcp_table.item(0, 1)
        ___qtablewidgetitem17.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem18 = self.robot_tcp_table.item(1, 0)
        ___qtablewidgetitem18.setText(QCoreApplication.translate("RobotStatusPage", u"Y (mm)", None))
        ___qtablewidgetitem19 = self.robot_tcp_table.item(1, 1)
        ___qtablewidgetitem19.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem20 = self.robot_tcp_table.item(2, 0)
        ___qtablewidgetitem20.setText(QCoreApplication.translate("RobotStatusPage", u"Z (mm)", None))
        ___qtablewidgetitem21 = self.robot_tcp_table.item(2, 1)
        ___qtablewidgetitem21.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem22 = self.robot_tcp_table.item(3, 0)
        ___qtablewidgetitem22.setText(QCoreApplication.translate("RobotStatusPage", u"Rx (\u00b0)", None))
        ___qtablewidgetitem23 = self.robot_tcp_table.item(3, 1)
        ___qtablewidgetitem23.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem24 = self.robot_tcp_table.item(4, 0)
        ___qtablewidgetitem24.setText(QCoreApplication.translate("RobotStatusPage", u"Ry (\u00b0)", None))
        ___qtablewidgetitem25 = self.robot_tcp_table.item(4, 1)
        ___qtablewidgetitem25.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        ___qtablewidgetitem26 = self.robot_tcp_table.item(5, 0)
        ___qtablewidgetitem26.setText(QCoreApplication.translate("RobotStatusPage", u"Rz (\u00b0)", None))
        ___qtablewidgetitem27 = self.robot_tcp_table.item(5, 1)
        ___qtablewidgetitem27.setText(QCoreApplication.translate("RobotStatusPage", u"\u672a\u8bfb\u53d6", None))
        self.robot_tcp_table.setSortingEnabled(__sortingEnabled1)

#if QT_CONFIG(accessibility)
        self.robot_tcp_table.setAccessibleName(QCoreApplication.translate("RobotStatusPage", u"TCP \u4f4d\u59ff", None))
#endif // QT_CONFIG(accessibility)
        self.robot_details_toggle.setText(QCoreApplication.translate("RobotStatusPage", u"\u6280\u672f\u8be6\u60c5", None))
#if QT_CONFIG(tooltip)
        self.robot_details_toggle.setToolTip(QCoreApplication.translate("RobotStatusPage", u"\u5c55\u5f00\u7248\u672c\u3001\u914d\u7f6e\u548c\u8bca\u65ad\u4fe1\u606f", None))
#endif // QT_CONFIG(tooltip)
        self.robot_details.setPlaceholderText(QCoreApplication.translate("RobotStatusPage", u"\u8bca\u65ad\u4fe1\u606f\u5c06\u5728\u6b64\u663e\u793a", None))
#if QT_CONFIG(accessibility)
        self.robot_details.setAccessibleName(QCoreApplication.translate("RobotStatusPage", u"\u673a\u5668\u4eba\u6280\u672f\u8be6\u60c5", None))
#endif // QT_CONFIG(accessibility)
        self.robot_copy_details_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u590d\u5236\u8bca\u65ad\u4fe1\u606f", None))
        self.robot_refresh_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u8bfb\u53d6\u673a\u5668\u4eba\u53cd\u9988", None))
#if QT_CONFIG(tooltip)
        self.robot_refresh_button.setToolTip(QCoreApplication.translate("RobotStatusPage", u"\u624b\u52a8\u8bfb\u53d6\u5173\u8282\u4f4d\u7f6e\u3001TCP \u4f4d\u59ff\u53ca\u673a\u5668\u4eba\u72b6\u6001", None))
#endif // QT_CONFIG(tooltip)
        self.robot_reset_fault_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u590d\u4f4d\u6545\u969c", None))
        self.robot_reset_estop_button.setText(QCoreApplication.translate("RobotStatusPage", u"\u89e3\u9664\u8f6f\u4ef6\u6025\u505c", None))
        pass
    # retranslateUi
