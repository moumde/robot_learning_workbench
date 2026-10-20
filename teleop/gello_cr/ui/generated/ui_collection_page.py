# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'collection_page.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpacerItem,
    QSpinBox, QSplitter, QToolButton, QVBoxLayout,
    QWidget)

class Ui_CollectionPage(object):
    def setupUi(self, CollectionPage):
        if not CollectionPage.objectName():
            CollectionPage.setObjectName(u"CollectionPage")
        CollectionPage.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(CollectionPage.sizePolicy().hasHeightForWidth())
        CollectionPage.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_1 = QVBoxLayout(CollectionPage)
        self.collection_VBoxLayout_1.setSpacing(6)
        self.collection_VBoxLayout_1.setObjectName(u"collection_VBoxLayout_1")
        self.collection_VBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.collection_Widget_1 = QWidget(CollectionPage)
        self.collection_Widget_1.setObjectName(u"collection_Widget_1")
        sizePolicy.setHeightForWidth(self.collection_Widget_1.sizePolicy().hasHeightForWidth())
        self.collection_Widget_1.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_2 = QVBoxLayout(self.collection_Widget_1)
        self.collection_VBoxLayout_2.setSpacing(6)
        self.collection_VBoxLayout_2.setObjectName(u"collection_VBoxLayout_2")
        self.collection_VBoxLayout_2.setContentsMargins(0, 0, 0, 0)
        self.collection_HBoxLayout_1 = QHBoxLayout()
        self.collection_HBoxLayout_1.setSpacing(6)
        self.collection_HBoxLayout_1.setObjectName(u"collection_HBoxLayout_1")
        self.collection_HBoxLayout_1.setContentsMargins(0, 0, 0, 0)
        self.collection_sectionTitle_1 = QLabel(self.collection_Widget_1)
        self.collection_sectionTitle_1.setObjectName(u"collection_sectionTitle_1")
        self.collection_sectionTitle_1.setProperty(u"role", u"sectionTitle")
        sizePolicy.setHeightForWidth(self.collection_sectionTitle_1.sizePolicy().hasHeightForWidth())
        self.collection_sectionTitle_1.setSizePolicy(sizePolicy)
        self.collection_sectionTitle_1.setWordWrap(True)
        self.collection_sectionTitle_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_sectionTitle_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_1.addWidget(self.collection_sectionTitle_1)

        self.collection_preparation_hint = QLabel(self.collection_Widget_1)
        self.collection_preparation_hint.setObjectName(u"collection_preparation_hint")
        self.collection_preparation_hint.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_preparation_hint.sizePolicy().hasHeightForWidth())
        self.collection_preparation_hint.setSizePolicy(sizePolicy)
        self.collection_preparation_hint.setWordWrap(True)
        self.collection_preparation_hint.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_preparation_hint.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_1.addWidget(self.collection_preparation_hint)

        self.collection_robot_selector = QComboBox(self.collection_Widget_1)
        self.collection_robot_selector.addItem("")
        self.collection_robot_selector.setObjectName(u"collection_robot_selector")
        self.collection_robot_selector.setEnabled(False)
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.collection_robot_selector.sizePolicy().hasHeightForWidth())
        self.collection_robot_selector.setSizePolicy(sizePolicy1)
        self.collection_robot_selector.setEditable(False)

        self.collection_HBoxLayout_1.addWidget(self.collection_robot_selector)

        self.collection_HBoxLayout_1.setStretch(1, 1)

        self.collection_VBoxLayout_2.addLayout(self.collection_HBoxLayout_1)

        self.collection_GridLayout_1 = QGridLayout()
        self.collection_GridLayout_1.setObjectName(u"collection_GridLayout_1")
        self.collection_GridLayout_1.setHorizontalSpacing(10)
        self.collection_GridLayout_1.setVerticalSpacing(6)
        self.collection_GridLayout_1.setContentsMargins(0, 0, 0, 0)
        self.collection_surfacePanel_1 = QFrame(self.collection_Widget_1)
        self.collection_surfacePanel_1.setObjectName(u"collection_surfacePanel_1")
        self.collection_surfacePanel_1.setProperty(u"role", u"surfacePanel")
        sizePolicy.setHeightForWidth(self.collection_surfacePanel_1.sizePolicy().hasHeightForWidth())
        self.collection_surfacePanel_1.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_3 = QVBoxLayout(self.collection_surfacePanel_1)
        self.collection_VBoxLayout_3.setSpacing(4)
        self.collection_VBoxLayout_3.setObjectName(u"collection_VBoxLayout_3")
        self.collection_VBoxLayout_3.setContentsMargins(10, 8, 10, 8)
        self.collection_eyebrow_1 = QLabel(self.collection_surfacePanel_1)
        self.collection_eyebrow_1.setObjectName(u"collection_eyebrow_1")
        self.collection_eyebrow_1.setProperty(u"role", u"eyebrow")
        sizePolicy.setHeightForWidth(self.collection_eyebrow_1.sizePolicy().hasHeightForWidth())
        self.collection_eyebrow_1.setSizePolicy(sizePolicy)
        self.collection_eyebrow_1.setWordWrap(True)
        self.collection_eyebrow_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_eyebrow_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_3.addWidget(self.collection_eyebrow_1)

        self.collection_stage_status_labels_0 = QLabel(self.collection_surfacePanel_1)
        self.collection_stage_status_labels_0.setObjectName(u"collection_stage_status_labels_0")
        self.collection_stage_status_labels_0.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_stage_status_labels_0.sizePolicy().hasHeightForWidth())
        self.collection_stage_status_labels_0.setSizePolicy(sizePolicy)
        self.collection_stage_status_labels_0.setWordWrap(True)
        self.collection_stage_status_labels_0.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_stage_status_labels_0.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_3.addWidget(self.collection_stage_status_labels_0)

        self.collection_HBoxLayout_2 = QHBoxLayout()
        self.collection_HBoxLayout_2.setSpacing(5)
        self.collection_HBoxLayout_2.setObjectName(u"collection_HBoxLayout_2")
        self.collection_HBoxLayout_2.setContentsMargins(0, 0, 0, 0)
        self.collection_connect_button = QPushButton(self.collection_surfacePanel_1)
        self.collection_connect_button.setObjectName(u"collection_connect_button")
        self.collection_connect_button.setProperty(u"role", u"quiet")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.collection_connect_button.sizePolicy().hasHeightForWidth())
        self.collection_connect_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_2.addWidget(self.collection_connect_button)

        self.collection_disconnect_button = QPushButton(self.collection_surfacePanel_1)
        self.collection_disconnect_button.setObjectName(u"collection_disconnect_button")
        self.collection_disconnect_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_disconnect_button.sizePolicy().hasHeightForWidth())
        self.collection_disconnect_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_2.addWidget(self.collection_disconnect_button)


        self.collection_VBoxLayout_3.addLayout(self.collection_HBoxLayout_2)


        self.collection_GridLayout_1.addWidget(self.collection_surfacePanel_1, 0, 0, 1, 1)

        self.collection_surfacePanel_2 = QFrame(self.collection_Widget_1)
        self.collection_surfacePanel_2.setObjectName(u"collection_surfacePanel_2")
        self.collection_surfacePanel_2.setProperty(u"role", u"surfacePanel")
        sizePolicy.setHeightForWidth(self.collection_surfacePanel_2.sizePolicy().hasHeightForWidth())
        self.collection_surfacePanel_2.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_4 = QVBoxLayout(self.collection_surfacePanel_2)
        self.collection_VBoxLayout_4.setSpacing(4)
        self.collection_VBoxLayout_4.setObjectName(u"collection_VBoxLayout_4")
        self.collection_VBoxLayout_4.setContentsMargins(10, 8, 10, 8)
        self.collection_input_heading = QHBoxLayout()
        self.collection_input_heading.setObjectName(u"collection_input_heading")
        self.collection_eyebrow_2 = QLabel(self.collection_surfacePanel_2)
        self.collection_eyebrow_2.setObjectName(u"collection_eyebrow_2")
        self.collection_eyebrow_2.setProperty(u"role", u"eyebrow")
        sizePolicy.setHeightForWidth(self.collection_eyebrow_2.sizePolicy().hasHeightForWidth())
        self.collection_eyebrow_2.setSizePolicy(sizePolicy)
        self.collection_eyebrow_2.setWordWrap(True)
        self.collection_eyebrow_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_eyebrow_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_input_heading.addWidget(self.collection_eyebrow_2)

        self.collection_control_source = QComboBox(self.collection_surfacePanel_2)
        self.collection_control_source.addItem("")
        self.collection_control_source.setObjectName(u"collection_control_source")
        self.collection_control_source.setEnabled(False)
        self.collection_control_source.setMinimumSize(QSize(86, 0))
        self.collection_control_source.setMaximumSize(QSize(86, 16777215))
        sizePolicy1.setHeightForWidth(self.collection_control_source.sizePolicy().hasHeightForWidth())
        self.collection_control_source.setSizePolicy(sizePolicy1)
        self.collection_control_source.setEditable(False)

        self.collection_input_heading.addWidget(self.collection_control_source)


        self.collection_VBoxLayout_4.addLayout(self.collection_input_heading)

        self.collection_stage_status_labels_1 = QLabel(self.collection_surfacePanel_2)
        self.collection_stage_status_labels_1.setObjectName(u"collection_stage_status_labels_1")
        self.collection_stage_status_labels_1.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_stage_status_labels_1.sizePolicy().hasHeightForWidth())
        self.collection_stage_status_labels_1.setSizePolicy(sizePolicy)
        self.collection_stage_status_labels_1.setWordWrap(True)
        self.collection_stage_status_labels_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_stage_status_labels_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_4.addWidget(self.collection_stage_status_labels_1)

        self.collection_HBoxLayout_3 = QHBoxLayout()
        self.collection_HBoxLayout_3.setSpacing(5)
        self.collection_HBoxLayout_3.setObjectName(u"collection_HBoxLayout_3")
        self.collection_HBoxLayout_3.setContentsMargins(0, 0, 0, 0)
        self.collection_prepare_devices_button = QPushButton(self.collection_surfacePanel_2)
        self.collection_prepare_devices_button.setObjectName(u"collection_prepare_devices_button")
        self.collection_prepare_devices_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_prepare_devices_button.sizePolicy().hasHeightForWidth())
        self.collection_prepare_devices_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_3.addWidget(self.collection_prepare_devices_button)


        self.collection_VBoxLayout_4.addLayout(self.collection_HBoxLayout_3)


        self.collection_GridLayout_1.addWidget(self.collection_surfacePanel_2, 0, 2, 1, 1)

        self.collection_surfacePanel_3 = QFrame(self.collection_Widget_1)
        self.collection_surfacePanel_3.setObjectName(u"collection_surfacePanel_3")
        self.collection_surfacePanel_3.setProperty(u"role", u"surfacePanel")
        sizePolicy.setHeightForWidth(self.collection_surfacePanel_3.sizePolicy().hasHeightForWidth())
        self.collection_surfacePanel_3.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_5 = QVBoxLayout(self.collection_surfacePanel_3)
        self.collection_VBoxLayout_5.setSpacing(4)
        self.collection_VBoxLayout_5.setObjectName(u"collection_VBoxLayout_5")
        self.collection_VBoxLayout_5.setContentsMargins(10, 8, 10, 8)
        self.collection_eyebrow_3 = QLabel(self.collection_surfacePanel_3)
        self.collection_eyebrow_3.setObjectName(u"collection_eyebrow_3")
        self.collection_eyebrow_3.setProperty(u"role", u"eyebrow")
        sizePolicy.setHeightForWidth(self.collection_eyebrow_3.sizePolicy().hasHeightForWidth())
        self.collection_eyebrow_3.setSizePolicy(sizePolicy)
        self.collection_eyebrow_3.setWordWrap(True)
        self.collection_eyebrow_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_eyebrow_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_5.addWidget(self.collection_eyebrow_3)

        self.collection_stage_status_labels_2 = QLabel(self.collection_surfacePanel_3)
        self.collection_stage_status_labels_2.setObjectName(u"collection_stage_status_labels_2")
        self.collection_stage_status_labels_2.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_stage_status_labels_2.sizePolicy().hasHeightForWidth())
        self.collection_stage_status_labels_2.setSizePolicy(sizePolicy)
        self.collection_stage_status_labels_2.setWordWrap(True)
        self.collection_stage_status_labels_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_stage_status_labels_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_5.addWidget(self.collection_stage_status_labels_2)

        self.collection_HBoxLayout_4 = QHBoxLayout()
        self.collection_HBoxLayout_4.setSpacing(5)
        self.collection_HBoxLayout_4.setObjectName(u"collection_HBoxLayout_4")
        self.collection_HBoxLayout_4.setContentsMargins(0, 0, 0, 0)
        self.collection_power_on_button = QPushButton(self.collection_surfacePanel_3)
        self.collection_power_on_button.setObjectName(u"collection_power_on_button")
        self.collection_power_on_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_power_on_button.sizePolicy().hasHeightForWidth())
        self.collection_power_on_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_4.addWidget(self.collection_power_on_button)

        self.collection_power_off_button = QPushButton(self.collection_surfacePanel_3)
        self.collection_power_off_button.setObjectName(u"collection_power_off_button")
        self.collection_power_off_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_power_off_button.sizePolicy().hasHeightForWidth())
        self.collection_power_off_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_4.addWidget(self.collection_power_off_button)


        self.collection_VBoxLayout_5.addLayout(self.collection_HBoxLayout_4)


        self.collection_GridLayout_1.addWidget(self.collection_surfacePanel_3, 0, 1, 1, 1)

        self.collection_surfacePanel_4 = QFrame(self.collection_Widget_1)
        self.collection_surfacePanel_4.setObjectName(u"collection_surfacePanel_4")
        self.collection_surfacePanel_4.setProperty(u"role", u"surfacePanel")
        sizePolicy.setHeightForWidth(self.collection_surfacePanel_4.sizePolicy().hasHeightForWidth())
        self.collection_surfacePanel_4.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_6 = QVBoxLayout(self.collection_surfacePanel_4)
        self.collection_VBoxLayout_6.setSpacing(4)
        self.collection_VBoxLayout_6.setObjectName(u"collection_VBoxLayout_6")
        self.collection_VBoxLayout_6.setContentsMargins(10, 8, 10, 8)
        self.collection_eyebrow_4 = QLabel(self.collection_surfacePanel_4)
        self.collection_eyebrow_4.setObjectName(u"collection_eyebrow_4")
        self.collection_eyebrow_4.setProperty(u"role", u"eyebrow")
        sizePolicy.setHeightForWidth(self.collection_eyebrow_4.sizePolicy().hasHeightForWidth())
        self.collection_eyebrow_4.setSizePolicy(sizePolicy)
        self.collection_eyebrow_4.setWordWrap(True)
        self.collection_eyebrow_4.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_eyebrow_4.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_6.addWidget(self.collection_eyebrow_4)

        self.collection_stage_status_labels_3 = QLabel(self.collection_surfacePanel_4)
        self.collection_stage_status_labels_3.setObjectName(u"collection_stage_status_labels_3")
        self.collection_stage_status_labels_3.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_stage_status_labels_3.sizePolicy().hasHeightForWidth())
        self.collection_stage_status_labels_3.setSizePolicy(sizePolicy)
        self.collection_stage_status_labels_3.setWordWrap(True)
        self.collection_stage_status_labels_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_stage_status_labels_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_6.addWidget(self.collection_stage_status_labels_3)

        self.collection_HBoxLayout_5 = QHBoxLayout()
        self.collection_HBoxLayout_5.setSpacing(5)
        self.collection_HBoxLayout_5.setObjectName(u"collection_HBoxLayout_5")
        self.collection_HBoxLayout_5.setContentsMargins(0, 0, 0, 0)
        self.collection_start_teleop_button = QPushButton(self.collection_surfacePanel_4)
        self.collection_start_teleop_button.setObjectName(u"collection_start_teleop_button")
        self.collection_start_teleop_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_start_teleop_button.sizePolicy().hasHeightForWidth())
        self.collection_start_teleop_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_5.addWidget(self.collection_start_teleop_button)

        self.collection_stop_teleop_button = QPushButton(self.collection_surfacePanel_4)
        self.collection_stop_teleop_button.setObjectName(u"collection_stop_teleop_button")
        self.collection_stop_teleop_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_stop_teleop_button.sizePolicy().hasHeightForWidth())
        self.collection_stop_teleop_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_5.addWidget(self.collection_stop_teleop_button)


        self.collection_VBoxLayout_6.addLayout(self.collection_HBoxLayout_5)


        self.collection_GridLayout_1.addWidget(self.collection_surfacePanel_4, 0, 3, 1, 1)

        self.collection_GridLayout_1.setColumnStretch(0, 1)
        self.collection_GridLayout_1.setColumnStretch(1, 1)
        self.collection_GridLayout_1.setColumnStretch(2, 1)
        self.collection_GridLayout_1.setColumnStretch(3, 1)

        self.collection_VBoxLayout_2.addLayout(self.collection_GridLayout_1)


        self.collection_VBoxLayout_1.addWidget(self.collection_Widget_1)

        self.collection_workspace_splitter = QSplitter(CollectionPage)
        self.collection_workspace_splitter.setObjectName(u"collection_workspace_splitter")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.collection_workspace_splitter.sizePolicy().hasHeightForWidth())
        self.collection_workspace_splitter.setSizePolicy(sizePolicy3)
        self.collection_workspace_splitter.setOrientation(Qt.Horizontal)
        self.collection_workspace_splitter.setChildrenCollapsible(False)
        self.collection_surfacePanel_5 = QFrame(self.collection_workspace_splitter)
        self.collection_surfacePanel_5.setObjectName(u"collection_surfacePanel_5")
        self.collection_surfacePanel_5.setProperty(u"role", u"surfacePanel")
        self.collection_surfacePanel_5.setMinimumSize(QSize(410, 0))
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(3)
        sizePolicy4.setVerticalStretch(3)
        sizePolicy4.setHeightForWidth(self.collection_surfacePanel_5.sizePolicy().hasHeightForWidth())
        self.collection_surfacePanel_5.setSizePolicy(sizePolicy4)
        self.collection_VBoxLayout_7 = QVBoxLayout(self.collection_surfacePanel_5)
        self.collection_VBoxLayout_7.setSpacing(5)
        self.collection_VBoxLayout_7.setObjectName(u"collection_VBoxLayout_7")
        self.collection_VBoxLayout_7.setContentsMargins(10, 10, 10, 10)
        self.collection_HBoxLayout_6 = QHBoxLayout()
        self.collection_HBoxLayout_6.setSpacing(5)
        self.collection_HBoxLayout_6.setObjectName(u"collection_HBoxLayout_6")
        self.collection_HBoxLayout_6.setContentsMargins(0, 0, 0, 0)
        self.collection_sectionTitle_2 = QLabel(self.collection_surfacePanel_5)
        self.collection_sectionTitle_2.setObjectName(u"collection_sectionTitle_2")
        self.collection_sectionTitle_2.setProperty(u"role", u"sectionTitle")
        sizePolicy.setHeightForWidth(self.collection_sectionTitle_2.sizePolicy().hasHeightForWidth())
        self.collection_sectionTitle_2.setSizePolicy(sizePolicy)
        self.collection_sectionTitle_2.setWordWrap(True)
        self.collection_sectionTitle_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_sectionTitle_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_6.addWidget(self.collection_sectionTitle_2)

        self.collection_start_cameras_button = QPushButton(self.collection_surfacePanel_5)
        self.collection_start_cameras_button.setObjectName(u"collection_start_cameras_button")
        self.collection_start_cameras_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_start_cameras_button.sizePolicy().hasHeightForWidth())
        self.collection_start_cameras_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_6.addWidget(self.collection_start_cameras_button)

        self.collection_stop_cameras_button = QPushButton(self.collection_surfacePanel_5)
        self.collection_stop_cameras_button.setObjectName(u"collection_stop_cameras_button")
        self.collection_stop_cameras_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_stop_cameras_button.sizePolicy().hasHeightForWidth())
        self.collection_stop_cameras_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_6.addWidget(self.collection_stop_cameras_button)

        self.collection_HBoxLayout_6.setStretch(0, 1)

        self.collection_VBoxLayout_7.addLayout(self.collection_HBoxLayout_6)

        self.collection_HBoxLayout_7 = QHBoxLayout()
        self.collection_HBoxLayout_7.setSpacing(5)
        self.collection_HBoxLayout_7.setObjectName(u"collection_HBoxLayout_7")
        self.collection_HBoxLayout_7.setContentsMargins(0, 0, 0, 0)
        self.collection_camera_hint = QLabel(self.collection_surfacePanel_5)
        self.collection_camera_hint.setObjectName(u"collection_camera_hint")
        self.collection_camera_hint.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_camera_hint.sizePolicy().hasHeightForWidth())
        self.collection_camera_hint.setSizePolicy(sizePolicy)
        self.collection_camera_hint.setWordWrap(True)
        self.collection_camera_hint.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_camera_hint.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_7.addWidget(self.collection_camera_hint)

        self.collection_HBoxLayout_7.setStretch(0, 1)

        self.collection_VBoxLayout_7.addLayout(self.collection_HBoxLayout_7)

        self.collection_Widget_2 = QWidget(self.collection_surfacePanel_5)
        self.collection_Widget_2.setObjectName(u"collection_Widget_2")
        sizePolicy.setHeightForWidth(self.collection_Widget_2.sizePolicy().hasHeightForWidth())
        self.collection_Widget_2.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_8 = QVBoxLayout(self.collection_Widget_2)
        self.collection_VBoxLayout_8.setSpacing(3)
        self.collection_VBoxLayout_8.setObjectName(u"collection_VBoxLayout_8")
        self.collection_VBoxLayout_8.setContentsMargins(0, 0, 0, 0)
        self.collection_preview_titles_0 = QLabel(self.collection_Widget_2)
        self.collection_preview_titles_0.setObjectName(u"collection_preview_titles_0")
        self.collection_preview_titles_0.setProperty(u"role", u"previewTitle")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.collection_preview_titles_0.sizePolicy().hasHeightForWidth())
        self.collection_preview_titles_0.setSizePolicy(sizePolicy5)
        self.collection_preview_titles_0.setWordWrap(False)
        self.collection_preview_titles_0.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_preview_titles_0.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_8.addWidget(self.collection_preview_titles_0)

        self.collection_base_preview = QLabel(self.collection_Widget_2)
        self.collection_base_preview.setObjectName(u"collection_base_preview")
        self.collection_base_preview.setProperty(u"role", u"previewImage")
        self.collection_base_preview.setMinimumSize(QSize(180, 130))
        self.collection_base_preview.setMaximumSize(QSize(16777215, 230))
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.collection_base_preview.sizePolicy().hasHeightForWidth())
        self.collection_base_preview.setSizePolicy(sizePolicy6)
        self.collection_base_preview.setWordWrap(False)
        self.collection_base_preview.setAlignment(Qt.AlignCenter)
        self.collection_base_preview.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_8.addWidget(self.collection_base_preview)

        self.collection_camera_metrics_0 = QLabel(self.collection_Widget_2)
        self.collection_camera_metrics_0.setObjectName(u"collection_camera_metrics_0")
        self.collection_camera_metrics_0.setProperty(u"role", u"mutedText")
        sizePolicy5.setHeightForWidth(self.collection_camera_metrics_0.sizePolicy().hasHeightForWidth())
        self.collection_camera_metrics_0.setSizePolicy(sizePolicy5)
        self.collection_camera_metrics_0.setWordWrap(False)
        self.collection_camera_metrics_0.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_camera_metrics_0.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_8.addWidget(self.collection_camera_metrics_0)

        self.collection_VBoxLayout_8.setStretch(1, 1)

        self.collection_VBoxLayout_7.addWidget(self.collection_Widget_2)

        self.collection_HBoxLayout_8 = QHBoxLayout()
        self.collection_HBoxLayout_8.setSpacing(12)
        self.collection_HBoxLayout_8.setObjectName(u"collection_HBoxLayout_8")
        self.collection_HBoxLayout_8.setContentsMargins(0, 0, 0, 0)
        self.collection_Widget_3 = QWidget(self.collection_surfacePanel_5)
        self.collection_Widget_3.setObjectName(u"collection_Widget_3")
        sizePolicy.setHeightForWidth(self.collection_Widget_3.sizePolicy().hasHeightForWidth())
        self.collection_Widget_3.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_9 = QVBoxLayout(self.collection_Widget_3)
        self.collection_VBoxLayout_9.setSpacing(3)
        self.collection_VBoxLayout_9.setObjectName(u"collection_VBoxLayout_9")
        self.collection_VBoxLayout_9.setContentsMargins(0, 0, 0, 0)
        self.collection_preview_titles_1 = QLabel(self.collection_Widget_3)
        self.collection_preview_titles_1.setObjectName(u"collection_preview_titles_1")
        self.collection_preview_titles_1.setProperty(u"role", u"previewTitle")
        sizePolicy5.setHeightForWidth(self.collection_preview_titles_1.sizePolicy().hasHeightForWidth())
        self.collection_preview_titles_1.setSizePolicy(sizePolicy5)
        self.collection_preview_titles_1.setWordWrap(False)
        self.collection_preview_titles_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_preview_titles_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_9.addWidget(self.collection_preview_titles_1)

        self.collection_wrist_preview = QLabel(self.collection_Widget_3)
        self.collection_wrist_preview.setObjectName(u"collection_wrist_preview")
        self.collection_wrist_preview.setProperty(u"role", u"previewImage")
        self.collection_wrist_preview.setMinimumSize(QSize(180, 65))
        self.collection_wrist_preview.setMaximumSize(QSize(16777215, 110))
        sizePolicy6.setHeightForWidth(self.collection_wrist_preview.sizePolicy().hasHeightForWidth())
        self.collection_wrist_preview.setSizePolicy(sizePolicy6)
        self.collection_wrist_preview.setWordWrap(False)
        self.collection_wrist_preview.setAlignment(Qt.AlignCenter)
        self.collection_wrist_preview.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_9.addWidget(self.collection_wrist_preview)

        self.collection_camera_metrics_1 = QLabel(self.collection_Widget_3)
        self.collection_camera_metrics_1.setObjectName(u"collection_camera_metrics_1")
        self.collection_camera_metrics_1.setProperty(u"role", u"mutedText")
        sizePolicy5.setHeightForWidth(self.collection_camera_metrics_1.sizePolicy().hasHeightForWidth())
        self.collection_camera_metrics_1.setSizePolicy(sizePolicy5)
        self.collection_camera_metrics_1.setWordWrap(False)
        self.collection_camera_metrics_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_camera_metrics_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_9.addWidget(self.collection_camera_metrics_1)

        self.collection_VBoxLayout_9.setStretch(1, 1)

        self.collection_HBoxLayout_8.addWidget(self.collection_Widget_3)

        self.collection_Widget_4 = QWidget(self.collection_surfacePanel_5)
        self.collection_Widget_4.setObjectName(u"collection_Widget_4")
        sizePolicy.setHeightForWidth(self.collection_Widget_4.sizePolicy().hasHeightForWidth())
        self.collection_Widget_4.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_10 = QVBoxLayout(self.collection_Widget_4)
        self.collection_VBoxLayout_10.setSpacing(3)
        self.collection_VBoxLayout_10.setObjectName(u"collection_VBoxLayout_10")
        self.collection_VBoxLayout_10.setContentsMargins(0, 0, 0, 0)
        self.collection_preview_titles_2 = QLabel(self.collection_Widget_4)
        self.collection_preview_titles_2.setObjectName(u"collection_preview_titles_2")
        self.collection_preview_titles_2.setProperty(u"role", u"previewTitle")
        sizePolicy5.setHeightForWidth(self.collection_preview_titles_2.sizePolicy().hasHeightForWidth())
        self.collection_preview_titles_2.setSizePolicy(sizePolicy5)
        self.collection_preview_titles_2.setWordWrap(False)
        self.collection_preview_titles_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_preview_titles_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_10.addWidget(self.collection_preview_titles_2)

        self.collection_roi_preview = QLabel(self.collection_Widget_4)
        self.collection_roi_preview.setObjectName(u"collection_roi_preview")
        self.collection_roi_preview.setProperty(u"role", u"previewImage")
        self.collection_roi_preview.setMinimumSize(QSize(180, 65))
        self.collection_roi_preview.setMaximumSize(QSize(16777215, 110))
        sizePolicy6.setHeightForWidth(self.collection_roi_preview.sizePolicy().hasHeightForWidth())
        self.collection_roi_preview.setSizePolicy(sizePolicy6)
        self.collection_roi_preview.setWordWrap(False)
        self.collection_roi_preview.setAlignment(Qt.AlignCenter)
        self.collection_roi_preview.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_10.addWidget(self.collection_roi_preview)

        self.collection_camera_metrics_2 = QLabel(self.collection_Widget_4)
        self.collection_camera_metrics_2.setObjectName(u"collection_camera_metrics_2")
        self.collection_camera_metrics_2.setProperty(u"role", u"mutedText")
        sizePolicy5.setHeightForWidth(self.collection_camera_metrics_2.sizePolicy().hasHeightForWidth())
        self.collection_camera_metrics_2.setSizePolicy(sizePolicy5)
        self.collection_camera_metrics_2.setWordWrap(False)
        self.collection_camera_metrics_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_camera_metrics_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_10.addWidget(self.collection_camera_metrics_2)

        self.collection_VBoxLayout_10.setStretch(1, 1)

        self.collection_HBoxLayout_8.addWidget(self.collection_Widget_4)

        self.collection_HBoxLayout_8.setStretch(0, 1)
        self.collection_HBoxLayout_8.setStretch(1, 1)

        self.collection_VBoxLayout_7.addLayout(self.collection_HBoxLayout_8)

        self.collection_VBoxLayout_7.setStretch(2, 2)
        self.collection_VBoxLayout_7.setStretch(3, 1)
        self.collection_workspace_splitter.addWidget(self.collection_surfacePanel_5)
        self.collection_surfacePanel_6 = QFrame(self.collection_workspace_splitter)
        self.collection_surfacePanel_6.setObjectName(u"collection_surfacePanel_6")
        self.collection_surfacePanel_6.setProperty(u"role", u"surfacePanel")
        self.collection_surfacePanel_6.setMinimumSize(QSize(345, 0))
        sizePolicy7 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy7.setHorizontalStretch(2)
        sizePolicy7.setVerticalStretch(2)
        sizePolicy7.setHeightForWidth(self.collection_surfacePanel_6.sizePolicy().hasHeightForWidth())
        self.collection_surfacePanel_6.setSizePolicy(sizePolicy7)
        self.collection_session_layout = QVBoxLayout(self.collection_surfacePanel_6)
        self.collection_session_layout.setSpacing(7)
        self.collection_session_layout.setObjectName(u"collection_session_layout")
        self.collection_session_layout.setContentsMargins(12, 10, 12, 10)
        self.collection_session_header_layout = QHBoxLayout()
        self.collection_session_header_layout.setSpacing(6)
        self.collection_session_header_layout.setObjectName(u"collection_session_header_layout")
        self.collection_session_header_layout.setContentsMargins(0, 0, 0, 0)
        self.collection_sectionTitle_3 = QLabel(self.collection_surfacePanel_6)
        self.collection_sectionTitle_3.setObjectName(u"collection_sectionTitle_3")
        self.collection_sectionTitle_3.setProperty(u"role", u"sectionTitle")
        sizePolicy.setHeightForWidth(self.collection_sectionTitle_3.sizePolicy().hasHeightForWidth())
        self.collection_sectionTitle_3.setSizePolicy(sizePolicy)
        self.collection_sectionTitle_3.setWordWrap(True)
        self.collection_sectionTitle_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_sectionTitle_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_session_header_layout.addWidget(self.collection_sectionTitle_3)

        self.collection_session_summary = QLabel(self.collection_surfacePanel_6)
        self.collection_session_summary.setObjectName(u"collection_session_summary")
        self.collection_session_summary.setProperty(u"role", u"mutedText")
        sizePolicy5.setHeightForWidth(self.collection_session_summary.sizePolicy().hasHeightForWidth())
        self.collection_session_summary.setSizePolicy(sizePolicy5)
        self.collection_session_summary.setWordWrap(False)
        self.collection_session_summary.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_session_summary.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_session_header_layout.addWidget(self.collection_session_summary)


        self.collection_session_layout.addLayout(self.collection_session_header_layout)

        self.collection_Widget_5 = QWidget(self.collection_surfacePanel_6)
        self.collection_Widget_5.setObjectName(u"collection_Widget_5")
        sizePolicy.setHeightForWidth(self.collection_Widget_5.sizePolicy().hasHeightForWidth())
        self.collection_Widget_5.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_11 = QVBoxLayout(self.collection_Widget_5)
        self.collection_VBoxLayout_11.setSpacing(6)
        self.collection_VBoxLayout_11.setObjectName(u"collection_VBoxLayout_11")
        self.collection_VBoxLayout_11.setContentsMargins(0, 0, 0, 0)
        self.collection_episode_state_panel = QFrame(self.collection_Widget_5)
        self.collection_episode_state_panel.setObjectName(u"collection_episode_state_panel")
        sizePolicy.setHeightForWidth(self.collection_episode_state_panel.sizePolicy().hasHeightForWidth())
        self.collection_episode_state_panel.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_12 = QVBoxLayout(self.collection_episode_state_panel)
        self.collection_VBoxLayout_12.setSpacing(5)
        self.collection_VBoxLayout_12.setObjectName(u"collection_VBoxLayout_12")
        self.collection_VBoxLayout_12.setContentsMargins(6, 6, 6, 6)
        self.collection_episode_identity_layout = QHBoxLayout()
        self.collection_episode_identity_layout.setSpacing(6)
        self.collection_episode_identity_layout.setObjectName(u"collection_episode_identity_layout")
        self.collection_episode_identity_layout.setContentsMargins(0, 0, 0, 0)
        self.collection_eyebrow_5 = QLabel(self.collection_episode_state_panel)
        self.collection_eyebrow_5.setObjectName(u"collection_eyebrow_5")
        self.collection_eyebrow_5.setProperty(u"role", u"eyebrow")
        sizePolicy.setHeightForWidth(self.collection_eyebrow_5.sizePolicy().hasHeightForWidth())
        self.collection_eyebrow_5.setSizePolicy(sizePolicy)
        self.collection_eyebrow_5.setWordWrap(True)
        self.collection_eyebrow_5.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_eyebrow_5.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_episode_identity_layout.addWidget(self.collection_eyebrow_5)

        self.collection_episode_id_label = QLabel(self.collection_episode_state_panel)
        self.collection_episode_id_label.setObjectName(u"collection_episode_id_label")
        self.collection_episode_id_label.setProperty(u"role", u"eyebrow")
        sizePolicy.setHeightForWidth(self.collection_episode_id_label.sizePolicy().hasHeightForWidth())
        self.collection_episode_id_label.setSizePolicy(sizePolicy)
        self.collection_episode_id_label.setWordWrap(False)
        self.collection_episode_id_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_episode_id_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_episode_identity_layout.addWidget(self.collection_episode_id_label)


        self.collection_VBoxLayout_12.addLayout(self.collection_episode_identity_layout)

        self.collection_episode_headline = QLabel(self.collection_episode_state_panel)
        self.collection_episode_headline.setObjectName(u"collection_episode_headline")
        self.collection_episode_headline.setProperty(u"role", u"stateHeadline")
        sizePolicy.setHeightForWidth(self.collection_episode_headline.sizePolicy().hasHeightForWidth())
        self.collection_episode_headline.setSizePolicy(sizePolicy)
        self.collection_episode_headline.setWordWrap(True)
        self.collection_episode_headline.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_episode_headline.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_12.addWidget(self.collection_episode_headline)

        self.collection_episode_hint = QLabel(self.collection_episode_state_panel)
        self.collection_episode_hint.setObjectName(u"collection_episode_hint")
        self.collection_episode_hint.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_episode_hint.sizePolicy().hasHeightForWidth())
        self.collection_episode_hint.setSizePolicy(sizePolicy)
        self.collection_episode_hint.setWordWrap(True)
        self.collection_episode_hint.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_episode_hint.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_12.addWidget(self.collection_episode_hint)


        self.collection_VBoxLayout_11.addWidget(self.collection_episode_state_panel)

        self.collection_episode_actions_layout = QHBoxLayout()
        self.collection_episode_actions_layout.setSpacing(6)
        self.collection_episode_actions_layout.setObjectName(u"collection_episode_actions_layout")
        self.collection_episode_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.collection_outcome_combo = QComboBox(self.collection_Widget_5)
        self.collection_outcome_combo.addItem("")
        self.collection_outcome_combo.addItem("")
        self.collection_outcome_combo.addItem("")
        self.collection_outcome_combo.setObjectName(u"collection_outcome_combo")
        sizePolicy1.setHeightForWidth(self.collection_outcome_combo.sizePolicy().hasHeightForWidth())
        self.collection_outcome_combo.setSizePolicy(sizePolicy1)
        self.collection_outcome_combo.setEditable(False)

        self.collection_episode_actions_layout.addWidget(self.collection_outcome_combo)

        self.collection_episode_start_button = QPushButton(self.collection_Widget_5)
        self.collection_episode_start_button.setObjectName(u"collection_episode_start_button")
        self.collection_episode_start_button.setProperty(u"role", u"primary")
        sizePolicy2.setHeightForWidth(self.collection_episode_start_button.sizePolicy().hasHeightForWidth())
        self.collection_episode_start_button.setSizePolicy(sizePolicy2)

        self.collection_episode_actions_layout.addWidget(self.collection_episode_start_button)

        self.collection_episode_stop_button = QPushButton(self.collection_Widget_5)
        self.collection_episode_stop_button.setObjectName(u"collection_episode_stop_button")
        self.collection_episode_stop_button.setProperty(u"role", u"primary")
        sizePolicy2.setHeightForWidth(self.collection_episode_stop_button.sizePolicy().hasHeightForWidth())
        self.collection_episode_stop_button.setSizePolicy(sizePolicy2)

        self.collection_episode_actions_layout.addWidget(self.collection_episode_stop_button)

        self.collection_HBoxLayout_9 = QHBoxLayout()
        self.collection_HBoxLayout_9.setSpacing(6)
        self.collection_HBoxLayout_9.setObjectName(u"collection_HBoxLayout_9")
        self.collection_HBoxLayout_9.setContentsMargins(0, 0, 0, 0)
        self.collection_save_success_button = QPushButton(self.collection_Widget_5)
        self.collection_save_success_button.setObjectName(u"collection_save_success_button")
        self.collection_save_success_button.setProperty(u"role", u"primary")
        sizePolicy2.setHeightForWidth(self.collection_save_success_button.sizePolicy().hasHeightForWidth())
        self.collection_save_success_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_9.addWidget(self.collection_save_success_button)

        self.collection_save_failure_button = QPushButton(self.collection_Widget_5)
        self.collection_save_failure_button.setObjectName(u"collection_save_failure_button")
        self.collection_save_failure_button.setProperty(u"role", u"primary")
        sizePolicy2.setHeightForWidth(self.collection_save_failure_button.sizePolicy().hasHeightForWidth())
        self.collection_save_failure_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_9.addWidget(self.collection_save_failure_button)


        self.collection_episode_actions_layout.addLayout(self.collection_HBoxLayout_9)

        self.collection_discard_button = QPushButton(self.collection_Widget_5)
        self.collection_discard_button.setObjectName(u"collection_discard_button")
        self.collection_discard_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_discard_button.sizePolicy().hasHeightForWidth())
        self.collection_discard_button.setSizePolicy(sizePolicy2)

        self.collection_episode_actions_layout.addWidget(self.collection_discard_button)


        self.collection_VBoxLayout_11.addLayout(self.collection_episode_actions_layout)

        self.collection_HBoxLayout_10 = QGridLayout()
        self.collection_HBoxLayout_10.setSpacing(6)
        self.collection_HBoxLayout_10.setObjectName(u"collection_HBoxLayout_10")
        self.collection_HBoxLayout_10.setContentsMargins(0, 0, 0, 0)
        self.collection_VBoxLayout_13 = QVBoxLayout()
        self.collection_VBoxLayout_13.setSpacing(1)
        self.collection_VBoxLayout_13.setObjectName(u"collection_VBoxLayout_13")
        self.collection_VBoxLayout_13.setContentsMargins(0, 0, 0, 0)
        self.collection_saved_metric = QLabel(self.collection_Widget_5)
        self.collection_saved_metric.setObjectName(u"collection_saved_metric")
        self.collection_saved_metric.setProperty(u"role", u"metricValue")
        sizePolicy.setHeightForWidth(self.collection_saved_metric.sizePolicy().hasHeightForWidth())
        self.collection_saved_metric.setSizePolicy(sizePolicy)
        self.collection_saved_metric.setWordWrap(True)
        self.collection_saved_metric.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_saved_metric.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_13.addWidget(self.collection_saved_metric)

        self.collection_metricLabel_1 = QLabel(self.collection_Widget_5)
        self.collection_metricLabel_1.setObjectName(u"collection_metricLabel_1")
        self.collection_metricLabel_1.setProperty(u"role", u"metricLabel")
        sizePolicy.setHeightForWidth(self.collection_metricLabel_1.sizePolicy().hasHeightForWidth())
        self.collection_metricLabel_1.setSizePolicy(sizePolicy)
        self.collection_metricLabel_1.setWordWrap(True)
        self.collection_metricLabel_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_metricLabel_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_13.addWidget(self.collection_metricLabel_1)


        self.collection_HBoxLayout_10.addLayout(self.collection_VBoxLayout_13, 0, 0, 1, 1)

        self.collection_VBoxLayout_14 = QVBoxLayout()
        self.collection_VBoxLayout_14.setSpacing(1)
        self.collection_VBoxLayout_14.setObjectName(u"collection_VBoxLayout_14")
        self.collection_VBoxLayout_14.setContentsMargins(0, 0, 0, 0)
        self.collection_frame_metric = QLabel(self.collection_Widget_5)
        self.collection_frame_metric.setObjectName(u"collection_frame_metric")
        self.collection_frame_metric.setProperty(u"role", u"metricValue")
        sizePolicy.setHeightForWidth(self.collection_frame_metric.sizePolicy().hasHeightForWidth())
        self.collection_frame_metric.setSizePolicy(sizePolicy)
        self.collection_frame_metric.setWordWrap(True)
        self.collection_frame_metric.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_frame_metric.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_14.addWidget(self.collection_frame_metric)

        self.collection_metricLabel_2 = QLabel(self.collection_Widget_5)
        self.collection_metricLabel_2.setObjectName(u"collection_metricLabel_2")
        self.collection_metricLabel_2.setProperty(u"role", u"metricLabel")
        sizePolicy.setHeightForWidth(self.collection_metricLabel_2.sizePolicy().hasHeightForWidth())
        self.collection_metricLabel_2.setSizePolicy(sizePolicy)
        self.collection_metricLabel_2.setWordWrap(True)
        self.collection_metricLabel_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_metricLabel_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_14.addWidget(self.collection_metricLabel_2)


        self.collection_HBoxLayout_10.addLayout(self.collection_VBoxLayout_14, 0, 1, 1, 1)

        self.collection_VBoxLayout_15 = QVBoxLayout()
        self.collection_VBoxLayout_15.setSpacing(1)
        self.collection_VBoxLayout_15.setObjectName(u"collection_VBoxLayout_15")
        self.collection_VBoxLayout_15.setContentsMargins(0, 0, 0, 0)
        self.collection_duration_metric = QLabel(self.collection_Widget_5)
        self.collection_duration_metric.setObjectName(u"collection_duration_metric")
        self.collection_duration_metric.setProperty(u"role", u"metricValue")
        sizePolicy.setHeightForWidth(self.collection_duration_metric.sizePolicy().hasHeightForWidth())
        self.collection_duration_metric.setSizePolicy(sizePolicy)
        self.collection_duration_metric.setWordWrap(True)
        self.collection_duration_metric.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_duration_metric.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_15.addWidget(self.collection_duration_metric)

        self.collection_metricLabel_3 = QLabel(self.collection_Widget_5)
        self.collection_metricLabel_3.setObjectName(u"collection_metricLabel_3")
        self.collection_metricLabel_3.setProperty(u"role", u"metricLabel")
        sizePolicy.setHeightForWidth(self.collection_metricLabel_3.sizePolicy().hasHeightForWidth())
        self.collection_metricLabel_3.setSizePolicy(sizePolicy)
        self.collection_metricLabel_3.setWordWrap(True)
        self.collection_metricLabel_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_metricLabel_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_15.addWidget(self.collection_metricLabel_3)


        self.collection_HBoxLayout_10.addLayout(self.collection_VBoxLayout_15, 0, 2, 1, 1)

        self.collection_VBoxLayout_16 = QVBoxLayout()
        self.collection_VBoxLayout_16.setSpacing(6)
        self.collection_VBoxLayout_16.setObjectName(u"collection_VBoxLayout_16")
        self.collection_VBoxLayout_16.setContentsMargins(0, 0, 0, 0)
        self.collection_fps_metric = QLabel(self.collection_Widget_5)
        self.collection_fps_metric.setObjectName(u"collection_fps_metric")
        self.collection_fps_metric.setProperty(u"role", u"metricSecondary")
        sizePolicy.setHeightForWidth(self.collection_fps_metric.sizePolicy().hasHeightForWidth())
        self.collection_fps_metric.setSizePolicy(sizePolicy)
        self.collection_fps_metric.setWordWrap(False)
        self.collection_fps_metric.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_fps_metric.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_16.addWidget(self.collection_fps_metric)

        self.collection_metricLabel_4 = QLabel(self.collection_Widget_5)
        self.collection_metricLabel_4.setObjectName(u"collection_metricLabel_4")
        self.collection_metricLabel_4.setProperty(u"role", u"metricLabel")
        sizePolicy.setHeightForWidth(self.collection_metricLabel_4.sizePolicy().hasHeightForWidth())
        self.collection_metricLabel_4.setSizePolicy(sizePolicy)
        self.collection_metricLabel_4.setWordWrap(False)
        self.collection_metricLabel_4.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_metricLabel_4.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_16.addWidget(self.collection_metricLabel_4)


        self.collection_HBoxLayout_10.addLayout(self.collection_VBoxLayout_16, 1, 0, 1, 1)

        self.collection_VBoxLayout_17 = QVBoxLayout()
        self.collection_VBoxLayout_17.setSpacing(6)
        self.collection_VBoxLayout_17.setObjectName(u"collection_VBoxLayout_17")
        self.collection_VBoxLayout_17.setContentsMargins(0, 0, 0, 0)
        self.collection_dropped_metric = QLabel(self.collection_Widget_5)
        self.collection_dropped_metric.setObjectName(u"collection_dropped_metric")
        self.collection_dropped_metric.setProperty(u"role", u"metricSecondary")
        sizePolicy.setHeightForWidth(self.collection_dropped_metric.sizePolicy().hasHeightForWidth())
        self.collection_dropped_metric.setSizePolicy(sizePolicy)
        self.collection_dropped_metric.setWordWrap(False)
        self.collection_dropped_metric.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_dropped_metric.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_17.addWidget(self.collection_dropped_metric)

        self.collection_metricLabel_5 = QLabel(self.collection_Widget_5)
        self.collection_metricLabel_5.setObjectName(u"collection_metricLabel_5")
        self.collection_metricLabel_5.setProperty(u"role", u"metricLabel")
        sizePolicy.setHeightForWidth(self.collection_metricLabel_5.sizePolicy().hasHeightForWidth())
        self.collection_metricLabel_5.setSizePolicy(sizePolicy)
        self.collection_metricLabel_5.setWordWrap(False)
        self.collection_metricLabel_5.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_metricLabel_5.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_17.addWidget(self.collection_metricLabel_5)


        self.collection_HBoxLayout_10.addLayout(self.collection_VBoxLayout_17, 1, 1, 1, 2)


        self.collection_VBoxLayout_11.addLayout(self.collection_HBoxLayout_10)

        self.collection_HBoxLayout_11 = QHBoxLayout()
        self.collection_HBoxLayout_11.setSpacing(6)
        self.collection_HBoxLayout_11.setObjectName(u"collection_HBoxLayout_11")
        self.collection_HBoxLayout_11.setContentsMargins(0, 0, 0, 0)
        self.collection_dataset_setup_toggle = QToolButton(self.collection_Widget_5)
        self.collection_dataset_setup_toggle.setObjectName(u"collection_dataset_setup_toggle")
        sizePolicy8 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy8.setHorizontalStretch(0)
        sizePolicy8.setVerticalStretch(0)
        sizePolicy8.setHeightForWidth(self.collection_dataset_setup_toggle.sizePolicy().hasHeightForWidth())
        self.collection_dataset_setup_toggle.setSizePolicy(sizePolicy8)
        self.collection_dataset_setup_toggle.setCheckable(True)
        self.collection_dataset_setup_toggle.setChecked(True)
        self.collection_dataset_setup_toggle.setArrowType(Qt.DownArrow)
        self.collection_dataset_setup_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.collection_HBoxLayout_11.addWidget(self.collection_dataset_setup_toggle)

        self.collection_episode_details_toggle = QToolButton(self.collection_Widget_5)
        self.collection_episode_details_toggle.setObjectName(u"collection_episode_details_toggle")
        sizePolicy8.setHeightForWidth(self.collection_episode_details_toggle.sizePolicy().hasHeightForWidth())
        self.collection_episode_details_toggle.setSizePolicy(sizePolicy8)
        self.collection_episode_details_toggle.setCheckable(True)
        self.collection_episode_details_toggle.setChecked(False)
        self.collection_episode_details_toggle.setArrowType(Qt.NoArrow)
        self.collection_episode_details_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.collection_HBoxLayout_11.addWidget(self.collection_episode_details_toggle)

        self.collection_dagger_expander = QToolButton(self.collection_Widget_5)
        self.collection_dagger_expander.setObjectName(u"collection_dagger_expander")
        sizePolicy8.setHeightForWidth(self.collection_dagger_expander.sizePolicy().hasHeightForWidth())
        self.collection_dagger_expander.setSizePolicy(sizePolicy8)
        self.collection_dagger_expander.setCheckable(True)
        self.collection_dagger_expander.setChecked(False)
        self.collection_dagger_expander.setArrowType(Qt.RightArrow)
        self.collection_dagger_expander.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.collection_HBoxLayout_11.addWidget(self.collection_dagger_expander, 0, Qt.AlignLeft)


        self.collection_VBoxLayout_11.addLayout(self.collection_HBoxLayout_11)

        self.collection_dataset_setup = QWidget(self.collection_Widget_5)
        self.collection_dataset_setup.setObjectName(u"collection_dataset_setup")
        self.collection_dataset_setup.setMinimumSize(QSize(170, 200))
        sizePolicy.setHeightForWidth(self.collection_dataset_setup.sizePolicy().hasHeightForWidth())
        self.collection_dataset_setup.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_18 = QVBoxLayout(self.collection_dataset_setup)
        self.collection_VBoxLayout_18.setSpacing(8)
        self.collection_VBoxLayout_18.setObjectName(u"collection_VBoxLayout_18")
        self.collection_VBoxLayout_18.setContentsMargins(0, 0, 0, 0)
        self.collection_sectionTitle_4 = QLabel(self.collection_dataset_setup)
        self.collection_sectionTitle_4.setObjectName(u"collection_sectionTitle_4")
        self.collection_sectionTitle_4.setProperty(u"role", u"sectionTitle")
        sizePolicy.setHeightForWidth(self.collection_sectionTitle_4.sizePolicy().hasHeightForWidth())
        self.collection_sectionTitle_4.setSizePolicy(sizePolicy)
        self.collection_sectionTitle_4.setWordWrap(True)
        self.collection_sectionTitle_4.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_sectionTitle_4.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_18.addWidget(self.collection_sectionTitle_4)

        self.collection_recording_source_combo = QComboBox(self.collection_dataset_setup)
        self.collection_recording_source_combo.addItem("")
        self.collection_recording_source_combo.addItem("")
        self.collection_recording_source_combo.addItem("")
        self.collection_recording_source_combo.setObjectName(u"collection_recording_source_combo")
        sizePolicy1.setHeightForWidth(self.collection_recording_source_combo.sizePolicy().hasHeightForWidth())
        self.collection_recording_source_combo.setSizePolicy(sizePolicy1)
        self.collection_recording_source_combo.setEditable(False)

        self.collection_VBoxLayout_18.addWidget(self.collection_recording_source_combo)

        self.collection_FormLayout_1 = QFormLayout()
        self.collection_FormLayout_1.setObjectName(u"collection_FormLayout_1")
        self.collection_FormLayout_1.setHorizontalSpacing(8)
        self.collection_FormLayout_1.setVerticalSpacing(7)
        self.collection_FormLayout_1.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.collection_FormLayout_1.setContentsMargins(0, 0, 0, 0)
        self.collection_Label_1 = QLabel(self.collection_dataset_setup)
        self.collection_Label_1.setObjectName(u"collection_Label_1")
        sizePolicy.setHeightForWidth(self.collection_Label_1.sizePolicy().hasHeightForWidth())
        self.collection_Label_1.setSizePolicy(sizePolicy)
        self.collection_Label_1.setWordWrap(False)
        self.collection_Label_1.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_1.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_FormLayout_1.setWidget(0, QFormLayout.ItemRole.LabelRole, self.collection_Label_1)

        self.collection_task_edit = QLineEdit(self.collection_dataset_setup)
        self.collection_task_edit.setObjectName(u"collection_task_edit")
        sizePolicy9 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy9.setHorizontalStretch(0)
        sizePolicy9.setVerticalStretch(0)
        sizePolicy9.setHeightForWidth(self.collection_task_edit.sizePolicy().hasHeightForWidth())
        self.collection_task_edit.setSizePolicy(sizePolicy9)

        self.collection_FormLayout_1.setWidget(0, QFormLayout.ItemRole.FieldRole, self.collection_task_edit)

        self.collection_Label_2 = QLabel(self.collection_dataset_setup)
        self.collection_Label_2.setObjectName(u"collection_Label_2")
        sizePolicy.setHeightForWidth(self.collection_Label_2.sizePolicy().hasHeightForWidth())
        self.collection_Label_2.setSizePolicy(sizePolicy)
        self.collection_Label_2.setWordWrap(False)
        self.collection_Label_2.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_2.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_FormLayout_1.setWidget(1, QFormLayout.ItemRole.LabelRole, self.collection_Label_2)

        self.collection_description_edit = QLineEdit(self.collection_dataset_setup)
        self.collection_description_edit.setObjectName(u"collection_description_edit")
        sizePolicy9.setHeightForWidth(self.collection_description_edit.sizePolicy().hasHeightForWidth())
        self.collection_description_edit.setSizePolicy(sizePolicy9)

        self.collection_FormLayout_1.setWidget(1, QFormLayout.ItemRole.FieldRole, self.collection_description_edit)


        self.collection_VBoxLayout_18.addLayout(self.collection_FormLayout_1)

        self.collection_FormLayout_2 = QFormLayout()
        self.collection_FormLayout_2.setObjectName(u"collection_FormLayout_2")
        self.collection_FormLayout_2.setHorizontalSpacing(8)
        self.collection_FormLayout_2.setVerticalSpacing(7)
        self.collection_FormLayout_2.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.collection_FormLayout_2.setContentsMargins(0, 0, 0, 0)
        self.collection_Label_3 = QLabel(self.collection_dataset_setup)
        self.collection_Label_3.setObjectName(u"collection_Label_3")
        sizePolicy.setHeightForWidth(self.collection_Label_3.sizePolicy().hasHeightForWidth())
        self.collection_Label_3.setSizePolicy(sizePolicy)
        self.collection_Label_3.setWordWrap(False)
        self.collection_Label_3.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_3.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_FormLayout_2.setWidget(0, QFormLayout.ItemRole.LabelRole, self.collection_Label_3)

        self.collection_dataset_format = QComboBox(self.collection_dataset_setup)
        self.collection_dataset_format.addItem("")
        self.collection_dataset_format.addItem("")
        self.collection_dataset_format.addItem("")
        self.collection_dataset_format.setObjectName(u"collection_dataset_format")
        sizePolicy1.setHeightForWidth(self.collection_dataset_format.sizePolicy().hasHeightForWidth())
        self.collection_dataset_format.setSizePolicy(sizePolicy1)
        self.collection_dataset_format.setEditable(False)

        self.collection_FormLayout_2.setWidget(0, QFormLayout.ItemRole.FieldRole, self.collection_dataset_format)

        self.collection_Label_4 = QLabel(self.collection_dataset_setup)
        self.collection_Label_4.setObjectName(u"collection_Label_4")
        sizePolicy.setHeightForWidth(self.collection_Label_4.sizePolicy().hasHeightForWidth())
        self.collection_Label_4.setSizePolicy(sizePolicy)
        self.collection_Label_4.setWordWrap(False)
        self.collection_Label_4.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_4.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_FormLayout_2.setWidget(1, QFormLayout.ItemRole.LabelRole, self.collection_Label_4)

        self.collection_Widget_6 = QWidget(self.collection_dataset_setup)
        self.collection_Widget_6.setObjectName(u"collection_Widget_6")
        sizePolicy.setHeightForWidth(self.collection_Widget_6.sizePolicy().hasHeightForWidth())
        self.collection_Widget_6.setSizePolicy(sizePolicy)
        self.collection_HBoxLayout_12 = QHBoxLayout(self.collection_Widget_6)
        self.collection_HBoxLayout_12.setSpacing(6)
        self.collection_HBoxLayout_12.setObjectName(u"collection_HBoxLayout_12")
        self.collection_HBoxLayout_12.setContentsMargins(0, 0, 0, 0)
        self.collection_root_edit = QLineEdit(self.collection_Widget_6)
        self.collection_root_edit.setObjectName(u"collection_root_edit")
        sizePolicy9.setHeightForWidth(self.collection_root_edit.sizePolicy().hasHeightForWidth())
        self.collection_root_edit.setSizePolicy(sizePolicy9)

        self.collection_HBoxLayout_12.addWidget(self.collection_root_edit)

        self.collection_root_browse_button = QPushButton(self.collection_Widget_6)
        self.collection_root_browse_button.setObjectName(u"collection_root_browse_button")
        self.collection_root_browse_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_root_browse_button.sizePolicy().hasHeightForWidth())
        self.collection_root_browse_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_12.addWidget(self.collection_root_browse_button)


        self.collection_FormLayout_2.setWidget(1, QFormLayout.ItemRole.FieldRole, self.collection_Widget_6)


        self.collection_VBoxLayout_18.addLayout(self.collection_FormLayout_2)

        self.collection_HBoxLayout_13 = QHBoxLayout()
        self.collection_HBoxLayout_13.setSpacing(8)
        self.collection_HBoxLayout_13.setObjectName(u"collection_HBoxLayout_13")
        self.collection_HBoxLayout_13.setContentsMargins(0, 0, 0, 0)
        self.collection_create_dataset_button = QPushButton(self.collection_dataset_setup)
        self.collection_create_dataset_button.setObjectName(u"collection_create_dataset_button")
        self.collection_create_dataset_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_create_dataset_button.sizePolicy().hasHeightForWidth())
        self.collection_create_dataset_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_13.addWidget(self.collection_create_dataset_button)

        self.collection_finalize_dataset_button = QPushButton(self.collection_dataset_setup)
        self.collection_finalize_dataset_button.setObjectName(u"collection_finalize_dataset_button")
        self.collection_finalize_dataset_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_finalize_dataset_button.sizePolicy().hasHeightForWidth())
        self.collection_finalize_dataset_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_13.addWidget(self.collection_finalize_dataset_button)


        self.collection_VBoxLayout_18.addLayout(self.collection_HBoxLayout_13)

        self.collection_name_preview = QLabel(self.collection_dataset_setup)
        self.collection_name_preview.setObjectName(u"collection_name_preview")
        self.collection_name_preview.setProperty(u"role", u"mutedText")
        sizePolicy.setHeightForWidth(self.collection_name_preview.sizePolicy().hasHeightForWidth())
        self.collection_name_preview.setSizePolicy(sizePolicy)
        self.collection_name_preview.setWordWrap(True)
        self.collection_name_preview.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_name_preview.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_18.addWidget(self.collection_name_preview)

        self.collection_resume_dataset_button = QPushButton(self.collection_dataset_setup)
        self.collection_resume_dataset_button.setObjectName(u"collection_resume_dataset_button")
        self.collection_resume_dataset_button.setProperty(u"role", u"quiet")
        sizePolicy2.setHeightForWidth(self.collection_resume_dataset_button.sizePolicy().hasHeightForWidth())
        self.collection_resume_dataset_button.setSizePolicy(sizePolicy2)

        self.collection_VBoxLayout_18.addWidget(self.collection_resume_dataset_button)


        self.collection_VBoxLayout_11.addWidget(self.collection_dataset_setup)

        self.collection_save_receipt = QLabel(self.collection_Widget_5)
        self.collection_save_receipt.setObjectName(u"collection_save_receipt")
        self.collection_save_receipt.setProperty(u"state", u"success")
        self.collection_save_receipt.setVisible(False)
        sizePolicy.setHeightForWidth(self.collection_save_receipt.sizePolicy().hasHeightForWidth())
        self.collection_save_receipt.setSizePolicy(sizePolicy)
        self.collection_save_receipt.setWordWrap(True)
        self.collection_save_receipt.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_save_receipt.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_11.addWidget(self.collection_save_receipt)

        self.collection_episode_status = QLabel(self.collection_Widget_5)
        self.collection_episode_status.setObjectName(u"collection_episode_status")
        self.collection_episode_status.setProperty(u"role", u"mutedText")
        self.collection_episode_status.setVisible(False)
        sizePolicy.setHeightForWidth(self.collection_episode_status.sizePolicy().hasHeightForWidth())
        self.collection_episode_status.setSizePolicy(sizePolicy)
        self.collection_episode_status.setWordWrap(True)
        self.collection_episode_status.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_episode_status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.collection_VBoxLayout_11.addWidget(self.collection_episode_status)


        self.collection_session_layout.addWidget(self.collection_Widget_5)

        self.collection_spacer_9 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.collection_session_layout.addItem(self.collection_spacer_9)

        self.collection_workspace_splitter.addWidget(self.collection_surfacePanel_6)

        self.collection_VBoxLayout_1.addWidget(self.collection_workspace_splitter)

        self.collection_dagger_panel = QWidget(CollectionPage)
        self.collection_dagger_panel.setObjectName(u"collection_dagger_panel")
        self.collection_dagger_panel.setVisible(False)
        sizePolicy.setHeightForWidth(self.collection_dagger_panel.sizePolicy().hasHeightForWidth())
        self.collection_dagger_panel.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_19 = QVBoxLayout(self.collection_dagger_panel)
        self.collection_VBoxLayout_19.setSpacing(6)
        self.collection_VBoxLayout_19.setObjectName(u"collection_VBoxLayout_19")
        self.collection_VBoxLayout_19.setContentsMargins(0, 0, 0, 0)
        self.collection_dagger_content = QGroupBox(self.collection_dagger_panel)
        self.collection_dagger_content.setObjectName(u"collection_dagger_content")
        self.collection_dagger_content.setVisible(False)
        sizePolicy.setHeightForWidth(self.collection_dagger_content.sizePolicy().hasHeightForWidth())
        self.collection_dagger_content.setSizePolicy(sizePolicy)
        self.collection_VBoxLayout_20 = QVBoxLayout(self.collection_dagger_content)
        self.collection_VBoxLayout_20.setSpacing(6)
        self.collection_VBoxLayout_20.setObjectName(u"collection_VBoxLayout_20")
        self.collection_VBoxLayout_20.setContentsMargins(9, 9, 9, 9)
        self.collection_HBoxLayout_14 = QHBoxLayout()
        self.collection_HBoxLayout_14.setSpacing(6)
        self.collection_HBoxLayout_14.setObjectName(u"collection_HBoxLayout_14")
        self.collection_HBoxLayout_14.setContentsMargins(0, 0, 0, 0)
        self.collection_Label_5 = QLabel(self.collection_dagger_content)
        self.collection_Label_5.setObjectName(u"collection_Label_5")
        sizePolicy.setHeightForWidth(self.collection_Label_5.sizePolicy().hasHeightForWidth())
        self.collection_Label_5.setSizePolicy(sizePolicy)
        self.collection_Label_5.setWordWrap(False)
        self.collection_Label_5.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_5.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_14.addWidget(self.collection_Label_5)

        self.collection_dagger_host = QLineEdit(self.collection_dagger_content)
        self.collection_dagger_host.setObjectName(u"collection_dagger_host")
        self.collection_dagger_host.setMaximumSize(QSize(180, 16777215))
        sizePolicy9.setHeightForWidth(self.collection_dagger_host.sizePolicy().hasHeightForWidth())
        self.collection_dagger_host.setSizePolicy(sizePolicy9)

        self.collection_HBoxLayout_14.addWidget(self.collection_dagger_host)

        self.collection_dagger_port = QSpinBox(self.collection_dagger_content)
        self.collection_dagger_port.setObjectName(u"collection_dagger_port")
        sizePolicy2.setHeightForWidth(self.collection_dagger_port.sizePolicy().hasHeightForWidth())
        self.collection_dagger_port.setSizePolicy(sizePolicy2)
        self.collection_dagger_port.setMinimum(1)
        self.collection_dagger_port.setMaximum(65535)
        self.collection_dagger_port.setSingleStep(1)
        self.collection_dagger_port.setValue(8000)

        self.collection_HBoxLayout_14.addWidget(self.collection_dagger_port)

        self.collection_Label_6 = QLabel(self.collection_dagger_content)
        self.collection_Label_6.setObjectName(u"collection_Label_6")
        sizePolicy.setHeightForWidth(self.collection_Label_6.sizePolicy().hasHeightForWidth())
        self.collection_Label_6.setSizePolicy(sizePolicy)
        self.collection_Label_6.setWordWrap(False)
        self.collection_Label_6.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_6.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_14.addWidget(self.collection_Label_6)

        self.collection_dagger_round = QLineEdit(self.collection_dagger_content)
        self.collection_dagger_round.setObjectName(u"collection_dagger_round")
        self.collection_dagger_round.setMaximumSize(QSize(100, 16777215))
        sizePolicy9.setHeightForWidth(self.collection_dagger_round.sizePolicy().hasHeightForWidth())
        self.collection_dagger_round.setSizePolicy(sizePolicy9)

        self.collection_HBoxLayout_14.addWidget(self.collection_dagger_round)

        self.collection_dagger_start_button = QPushButton(self.collection_dagger_content)
        self.collection_dagger_start_button.setObjectName(u"collection_dagger_start_button")
        sizePolicy2.setHeightForWidth(self.collection_dagger_start_button.sizePolicy().hasHeightForWidth())
        self.collection_dagger_start_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_14.addWidget(self.collection_dagger_start_button)

        self.collection_dagger_toggle_button = QPushButton(self.collection_dagger_content)
        self.collection_dagger_toggle_button.setObjectName(u"collection_dagger_toggle_button")
        sizePolicy2.setHeightForWidth(self.collection_dagger_toggle_button.sizePolicy().hasHeightForWidth())
        self.collection_dagger_toggle_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_14.addWidget(self.collection_dagger_toggle_button)

        self.collection_dagger_stop_button = QPushButton(self.collection_dagger_content)
        self.collection_dagger_stop_button.setObjectName(u"collection_dagger_stop_button")
        sizePolicy2.setHeightForWidth(self.collection_dagger_stop_button.sizePolicy().hasHeightForWidth())
        self.collection_dagger_stop_button.setSizePolicy(sizePolicy2)

        self.collection_HBoxLayout_14.addWidget(self.collection_dagger_stop_button)


        self.collection_VBoxLayout_20.addLayout(self.collection_HBoxLayout_14)

        self.collection_HBoxLayout_15 = QHBoxLayout()
        self.collection_HBoxLayout_15.setSpacing(6)
        self.collection_HBoxLayout_15.setObjectName(u"collection_HBoxLayout_15")
        self.collection_HBoxLayout_15.setContentsMargins(0, 0, 0, 0)
        self.collection_Label_7 = QLabel(self.collection_dagger_content)
        self.collection_Label_7.setObjectName(u"collection_Label_7")
        sizePolicy.setHeightForWidth(self.collection_Label_7.sizePolicy().hasHeightForWidth())
        self.collection_Label_7.setSizePolicy(sizePolicy)
        self.collection_Label_7.setWordWrap(False)
        self.collection_Label_7.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_Label_7.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_HBoxLayout_15.addWidget(self.collection_Label_7)

        self.collection_dagger_root = QLineEdit(self.collection_dagger_content)
        self.collection_dagger_root.setObjectName(u"collection_dagger_root")
        sizePolicy9.setHeightForWidth(self.collection_dagger_root.sizePolicy().hasHeightForWidth())
        self.collection_dagger_root.setSizePolicy(sizePolicy9)

        self.collection_HBoxLayout_15.addWidget(self.collection_dagger_root)


        self.collection_VBoxLayout_20.addLayout(self.collection_HBoxLayout_15)

        self.collection_dagger_status = QLabel(self.collection_dagger_content)
        self.collection_dagger_status.setObjectName(u"collection_dagger_status")
        sizePolicy.setHeightForWidth(self.collection_dagger_status.sizePolicy().hasHeightForWidth())
        self.collection_dagger_status.setSizePolicy(sizePolicy)
        self.collection_dagger_status.setWordWrap(True)
        self.collection_dagger_status.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.collection_dagger_status.setTextInteractionFlags(Qt.LinksAccessibleByMouse)

        self.collection_VBoxLayout_20.addWidget(self.collection_dagger_status)


        self.collection_VBoxLayout_19.addWidget(self.collection_dagger_content)


        self.collection_VBoxLayout_1.addWidget(self.collection_dagger_panel)

        self.collection_VBoxLayout_1.setStretch(1, 1)

        self.retranslateUi(CollectionPage)

        self.collection_robot_selector.setCurrentIndex(0)
        self.collection_control_source.setCurrentIndex(0)
        self.collection_outcome_combo.setCurrentIndex(0)
        self.collection_recording_source_combo.setCurrentIndex(0)
        self.collection_dataset_format.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(CollectionPage)
    # setupUi

    def retranslateUi(self, CollectionPage):
        CollectionPage.setProperty(u"density", QCoreApplication.translate("CollectionPage", u"compact", None))
        self.collection_sectionTitle_1.setText(QCoreApplication.translate("CollectionPage", u"\u64cd\u4f5c\u51c6\u5907", None))
        self.collection_preparation_hint.setText(QCoreApplication.translate("CollectionPage", u"\u4e0b\u4e00\u6b65\uff1a\u8fde\u63a5\u673a\u5668\u4eba", None))
        self.collection_robot_selector.setItemText(0, QCoreApplication.translate("CollectionPage", u"CR3A + O6", None))

        self.collection_eyebrow_1.setText(QCoreApplication.translate("CollectionPage", u"01  \u8fde\u63a5\u673a\u5668\u4eba", None))
        self.collection_stage_status_labels_0.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u51c6\u5907", None))
        self.collection_connect_button.setText(QCoreApplication.translate("CollectionPage", u"\u8fde\u63a5\u673a\u5668\u4eba", None))
        self.collection_disconnect_button.setText(QCoreApplication.translate("CollectionPage", u"\u65ad\u5f00\u673a\u5668\u4eba", None))
        self.collection_eyebrow_2.setText(QCoreApplication.translate("CollectionPage", u"03  \u8fde\u63a5\u9065\u64cd\u8bbe\u5907", None))
        self.collection_control_source.setItemText(0, QCoreApplication.translate("CollectionPage", u"GELLO", None))

#if QT_CONFIG(tooltip)
        self.collection_control_source.setToolTip(QCoreApplication.translate("CollectionPage", u"\u5f53\u524d\u9065\u64cd\u63a7\u5236\u6e90\uff0c\u5728\u8bbe\u7f6e\u4e2d\u914d\u7f6e", None))
#endif // QT_CONFIG(tooltip)
        self.collection_stage_status_labels_1.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u51c6\u5907", None))
        self.collection_prepare_devices_button.setText(QCoreApplication.translate("CollectionPage", u"\u8fde\u63a5\u4e3b\u81c2 / O6", None))
        self.collection_eyebrow_3.setText(QCoreApplication.translate("CollectionPage", u"02  Servo On", None))
        self.collection_stage_status_labels_2.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u51c6\u5907", None))
        self.collection_power_on_button.setText(QCoreApplication.translate("CollectionPage", u"\u4e0a\u4f7f\u80fd", None))
        self.collection_power_off_button.setText(QCoreApplication.translate("CollectionPage", u"\u4e0b\u4f7f\u80fd", None))
        self.collection_eyebrow_4.setText(QCoreApplication.translate("CollectionPage", u"04  \u5f00\u59cb\u9065\u64cd", None))
        self.collection_stage_status_labels_3.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u51c6\u5907", None))
        self.collection_start_teleop_button.setText(QCoreApplication.translate("CollectionPage", u"\u5f00\u59cb\u9065\u64cd", None))
        self.collection_stop_teleop_button.setText(QCoreApplication.translate("CollectionPage", u"\u505c\u6b62\u9065\u64cd", None))
        self.collection_sectionTitle_2.setText(QCoreApplication.translate("CollectionPage", u"\u76f8\u673a\u5de5\u4f5c\u533a", None))
        self.collection_start_cameras_button.setText(QCoreApplication.translate("CollectionPage", u"\u542f\u52a8\u76f8\u673a", None))
        self.collection_stop_cameras_button.setText(QCoreApplication.translate("CollectionPage", u"\u505c\u6b62\u76f8\u673a", None))
        self.collection_camera_hint.setText(QCoreApplication.translate("CollectionPage", u"\u76f8\u673a\u672a\u542f\u52a8 \u00b7 \u53ef\u72ec\u7acb\u4e8e\u9065\u64cd\u51c6\u5907", None))
        self.collection_preview_titles_0.setText(QCoreApplication.translate("CollectionPage", u"Base RGB", None))
        self.collection_base_preview.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u76f8\u673a", None))
        self.collection_camera_metrics_0.setText(QCoreApplication.translate("CollectionPage", u"OFFLINE \u00b7 FPS \u2014 \u00b7 Age \u2014", None))
        self.collection_preview_titles_1.setText(QCoreApplication.translate("CollectionPage", u"Wrist RGB", None))
        self.collection_wrist_preview.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u76f8\u673a", None))
        self.collection_camera_metrics_1.setText(QCoreApplication.translate("CollectionPage", u"OFFLINE \u00b7 FPS \u2014 \u00b7 Age \u2014", None))
        self.collection_preview_titles_2.setText(QCoreApplication.translate("CollectionPage", u"Base ROI", None))
        self.collection_roi_preview.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u76f8\u673a", None))
        self.collection_camera_metrics_2.setText(QCoreApplication.translate("CollectionPage", u"OFFLINE \u00b7 FPS \u2014 \u00b7 Age \u2014", None))
        self.collection_sectionTitle_3.setText(QCoreApplication.translate("CollectionPage", u"\u91c7\u96c6\u63a7\u5236", None))
        self.collection_session_summary.setText(QCoreApplication.translate("CollectionPage", u"\u5c1a\u672a\u8bbe\u7f6e\u4efb\u52a1 \u00b7 LeRobot V3", None))
        self.collection_eyebrow_5.setText(QCoreApplication.translate("CollectionPage", u"EPISODE \u00b7 \u5355\u6bb5\u91c7\u96c6", None))
        self.collection_episode_id_label.setText(QCoreApplication.translate("CollectionPage", u"Episode \u2014", None))
        self.collection_episode_headline.setText(QCoreApplication.translate("CollectionPage", u"\u7b49\u5f85\u91c7\u96c6\u51c6\u5907", None))
        self.collection_episode_hint.setText(QCoreApplication.translate("CollectionPage", u"\u8fde\u63a5\u5e76\u4f7f\u80fd\u673a\u5668\u4eba\uff0c\u76f8\u673a\u753b\u9762\u5c31\u7eea\u540e\u5f00\u59cb\u3002", None))
        self.collection_outcome_combo.setItemText(0, QCoreApplication.translate("CollectionPage", u"\u8bf7\u9009\u62e9\u7ed3\u679c", None))
        self.collection_outcome_combo.setItemText(1, QCoreApplication.translate("CollectionPage", u"\u6210\u529f", None))
        self.collection_outcome_combo.setItemText(2, QCoreApplication.translate("CollectionPage", u"\u5931\u8d25", None))

        self.collection_episode_start_button.setText(QCoreApplication.translate("CollectionPage", u"\u5f00\u59cb\u5f55\u5236", None))
        self.collection_episode_stop_button.setText(QCoreApplication.translate("CollectionPage", u"\u7ed3\u675f\u5f55\u5236", None))
        self.collection_save_success_button.setText(QCoreApplication.translate("CollectionPage", u"\u6210\u529f \u00b7 \u4fdd\u5b58", None))
        self.collection_save_failure_button.setText(QCoreApplication.translate("CollectionPage", u"\u5931\u8d25 \u00b7 \u4fdd\u5b58", None))
        self.collection_discard_button.setText(QCoreApplication.translate("CollectionPage", u"\u4e22\u5f03\u672c\u6bb5", None))
        self.collection_saved_metric.setText(QCoreApplication.translate("CollectionPage", u"0", None))
        self.collection_metricLabel_1.setText(QCoreApplication.translate("CollectionPage", u"\u5df2\u4fdd\u5b58\u6bb5\u6570", None))
        self.collection_frame_metric.setText(QCoreApplication.translate("CollectionPage", u"0", None))
        self.collection_metricLabel_2.setText(QCoreApplication.translate("CollectionPage", u"\u5f53\u524d\u5e27\u6570", None))
        self.collection_duration_metric.setText(QCoreApplication.translate("CollectionPage", u"0.0s", None))
        self.collection_metricLabel_3.setText(QCoreApplication.translate("CollectionPage", u"\u672c\u6bb5\u65f6\u957f", None))
        self.collection_fps_metric.setText(QCoreApplication.translate("CollectionPage", u"\u2014", None))
        self.collection_metricLabel_4.setText(QCoreApplication.translate("CollectionPage", u"\u91c7\u96c6 FPS", None))
        self.collection_dropped_metric.setText(QCoreApplication.translate("CollectionPage", u"\u672a\u7edf\u8ba1", None))
        self.collection_metricLabel_5.setText(QCoreApplication.translate("CollectionPage", u"\u4e22\u6837", None))
        self.collection_dataset_setup_toggle.setText(QCoreApplication.translate("CollectionPage", u"\u4efb\u52a1\u4e0e\u6570\u636e\u96c6\u8bbe\u7f6e", None))
        self.collection_episode_details_toggle.setText(QCoreApplication.translate("CollectionPage", u"\u91c7\u96c6\u8be6\u60c5", None))
        self.collection_dagger_expander.setText(QCoreApplication.translate("CollectionPage", u"DAgger", None))
#if QT_CONFIG(tooltip)
        self.collection_dagger_expander.setToolTip(QCoreApplication.translate("CollectionPage", u"\u9ad8\u7ea7\uff1aDAgger \u7b56\u7565\u63a5\u7ba1", None))
#endif // QT_CONFIG(tooltip)
        self.collection_sectionTitle_4.setText(QCoreApplication.translate("CollectionPage", u"\u4efb\u52a1\u4e0e\u6570\u636e\u96c6", None))
        self.collection_recording_source_combo.setItemText(0, QCoreApplication.translate("CollectionPage", u"\u9065\u64cd\u8ddf\u968f", None))
        self.collection_recording_source_combo.setItemText(1, QCoreApplication.translate("CollectionPage", u"\u8f68\u8ff9\u56de\u653e", None))
        self.collection_recording_source_combo.setItemText(2, QCoreApplication.translate("CollectionPage", u"\u7cbe\u786e\u8d70\u70b9", None))

        self.collection_Label_1.setText(QCoreApplication.translate("CollectionPage", u"\u4efb\u52a1\u540d\u79f0", None))
        self.collection_task_edit.setText("")
        self.collection_task_edit.setPlaceholderText(QCoreApplication.translate("CollectionPage", u"\u4f8b\u5982 motor_pick", None))
        self.collection_Label_2.setText(QCoreApplication.translate("CollectionPage", u"\u4efb\u52a1\u63cf\u8ff0", None))
        self.collection_description_edit.setText("")
        self.collection_description_edit.setPlaceholderText(QCoreApplication.translate("CollectionPage", u"\u63cf\u8ff0\u8981\u5b8c\u6210\u7684\u52a8\u4f5c", None))
        self.collection_Label_3.setText(QCoreApplication.translate("CollectionPage", u"\u4fdd\u5b58\u683c\u5f0f", None))
        self.collection_dataset_format.setItemText(0, QCoreApplication.translate("CollectionPage", u"LeRobot V3", None))
        self.collection_dataset_format.setItemText(1, QCoreApplication.translate("CollectionPage", u"LeRobot V2.1", None))
        self.collection_dataset_format.setItemText(2, QCoreApplication.translate("CollectionPage", u"HDF5", None))

        self.collection_Label_4.setText(QCoreApplication.translate("CollectionPage", u"\u4fdd\u5b58\u76ee\u5f55", None))
#if QT_CONFIG(tooltip)
        self.collection_root_edit.setToolTip(QCoreApplication.translate("CollectionPage", u"\u6570\u636e\u96c6\u4f1a\u8bdd\u5f00\u59cb\u540e\u9501\u5b9a\u76ee\u5f55\uff1b\u5b8c\u6210\u5f53\u524d\u6570\u636e\u96c6\u540e\u53ef\u66f4\u6362\u76ee\u5f55", None))
#endif // QT_CONFIG(tooltip)
        self.collection_root_edit.setText("")
        self.collection_root_edit.setPlaceholderText(QCoreApplication.translate("CollectionPage", u"\u9009\u62e9\u6570\u636e\u96c6\u7236\u76ee\u5f55", None))
        self.collection_root_browse_button.setText(QCoreApplication.translate("CollectionPage", u"\u9009\u62e9\u2026", None))
        self.collection_create_dataset_button.setText(QCoreApplication.translate("CollectionPage", u"\u521b\u5efa\u6570\u636e\u96c6", None))
        self.collection_finalize_dataset_button.setText(QCoreApplication.translate("CollectionPage", u"\u5b8c\u6210\u6570\u636e\u96c6", None))
        self.collection_name_preview.setText(QCoreApplication.translate("CollectionPage", u"\u586b\u5199\u4efb\u52a1\u540d\u79f0\u540e\u521b\u5efa\u6570\u636e\u96c6", None))
        self.collection_resume_dataset_button.setText(QCoreApplication.translate("CollectionPage", u"\u7ee7\u7eed\u672a\u5b8c\u6210\u6279\u6b21", None))
        self.collection_save_receipt.setText("")
        self.collection_episode_status.setText(QCoreApplication.translate("CollectionPage", u"\u672a\u542f\u52a8\u6570\u636e\u96c6", None))
        self.collection_dagger_content.setTitle(QCoreApplication.translate("CollectionPage", u"\u4e13\u5bb6\u7ea0\u6b63\u91c7\u96c6", None))
        self.collection_Label_5.setText(QCoreApplication.translate("CollectionPage", u"\u6a21\u578b\u670d\u52a1", None))
        self.collection_dagger_host.setText(QCoreApplication.translate("CollectionPage", u"127.0.0.1", None))
        self.collection_dagger_host.setPlaceholderText("")
        self.collection_dagger_port.setSuffix("")
        self.collection_Label_6.setText(QCoreApplication.translate("CollectionPage", u"\u8f6e\u6b21", None))
        self.collection_dagger_round.setText(QCoreApplication.translate("CollectionPage", u"round1", None))
        self.collection_dagger_round.setPlaceholderText("")
        self.collection_dagger_start_button.setText(QCoreApplication.translate("CollectionPage", u"\u542f\u52a8\u6a21\u578b\u63a7\u5236", None))
        self.collection_dagger_toggle_button.setText(QCoreApplication.translate("CollectionPage", u"\u7a7a\u683c\uff1a\u63a5\u7ba1\u5e76\u5f55\u5236", None))
        self.collection_dagger_stop_button.setText(QCoreApplication.translate("CollectionPage", u"\u505c\u6b62 DAgger", None))
        self.collection_Label_7.setText(QCoreApplication.translate("CollectionPage", u"\u7ea0\u6b63\u6570\u636e\u76ee\u5f55", None))
        self.collection_dagger_root.setText("")
        self.collection_dagger_root.setPlaceholderText("")
        self.collection_dagger_status.setText(QCoreApplication.translate("CollectionPage", u"\u7a7a\u683c\u6309\u4e00\u6b21\u63a5\u7ba1\u5e76\u8bb0\u5f55\uff0c\u518d\u6309\u4e00\u6b21\u7ed3\u675f\u7ea0\u6b63\u3001\u6062\u590d\u6a21\u578b\uff1bTask \u4f7f\u7528\u4e0a\u65b9\u4efb\u52a1\u6587\u672c", None))
    # retranslateUi
