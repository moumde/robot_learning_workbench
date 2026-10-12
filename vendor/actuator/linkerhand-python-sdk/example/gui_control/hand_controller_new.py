#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵巧手控制界面（配置文件驱动 + 批量输入 + 实时回读）

功能：
  1. 从 setting.yaml 读取 左右手 / JOINT / TOUCH / CAN / MODBUS
  2. 支持单个关节 spinbox/slider 调节，也支持批量粘贴输入
  3. 点击“下发控制”调用 finger_move(positions)
  4. 定时轮询 get_state()，实时显示手指当前位置
"""

import os
import sys
import re
import time

from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSpinBox, QSlider, QLineEdit,
    QTextEdit, QMessageBox
)
from PyQt5.QtGui import QFont

# ----------------------------------------------------------------------
# 加入 SDK 根目录（从 example/ 上一级回到 linkerhand-python-sdk/）
# ----------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
sdk_root = os.path.abspath(os.path.join(current_dir, "../.."))
if sdk_root not in sys.path:
    sys.path.insert(0, sdk_root)

from LinkerHand.linker_hand_api import LinkerHandApi
from LinkerHand.utils.load_write_yaml import LoadWriteYaml
from LinkerHand.utils.color_msg import ColorMsg


# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------
JOINT_NUM = 6
JOINT_NAMES = [
    "0 大拇指弯曲",
    "1 大拇指横摆",
    "2 食指弯曲",
    "3 中指弯曲",
    "4 无名指弯曲",
    "5 小拇指弯曲",
]
POS_MIN = 0
POS_MAX = 255
INIT_POS = [255] * JOINT_NUM
STATE_INTERVAL_MS = 200   # 实时位置刷新周期


# ======================================================================
# API 管理器
# ======================================================================
class HandApiManager(QObject):
    """负责与 LinkerHandApi 通信，并周期性读取手部位置"""

    status_updated = pyqtSignal(str, str)   # (级别, 消息)
    state_updated = pyqtSignal(list)        # 实时位置列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = None
        self._busy = False

        # 这些成员由配置文件填充
        self.hand_exists = False
        self.left_hand = False
        self.right_hand = False
        self.hand_joint = None
        self.hand_type = None
        self.is_touch = False
        self.can = "can0"
        self.modbus = "None"

        # 1) 读配置
        self._load_config()

        # 2) 用配置初始化 API
        self._init_api()

        # 3) 定时刷新实时位置
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.read_state)
        self.state_timer.start(STATE_INTERVAL_MS)

    # ------------------------------------------------------------
    def _load_config(self):
        """从 setting.yaml 读取 左右手 / JOINT / TOUCH / CAN / MODBUS"""
        try:
            self.yaml = LoadWriteYaml()
            self.setting = self.yaml.load_setting_yaml()
            time.sleep(1)

            self.left_hand = bool(
                self.setting['LINKER_HAND']['LEFT_HAND']['EXISTS'])
            self.right_hand = bool(
                self.setting['LINKER_HAND']['RIGHT_HAND']['EXISTS'])

            # GUI 只控制单手，左右手互斥，优先左手（与 SDK 例程一致）
            if self.left_hand and self.right_hand:
                self.left_hand = True
                self.right_hand = False

            if self.left_hand:
                cfg = self.setting['LINKER_HAND']['LEFT_HAND']
                self.hand_type = "left"
            elif self.right_hand:
                cfg = self.setting['LINKER_HAND']['RIGHT_HAND']
                self.hand_type = "right"
            else:
                raise RuntimeError(
                    "配置文件中未启用任何手部（LEFT_HAND / RIGHT_HAND 都为 False）")

            self.hand_exists = True
            self.hand_joint = cfg['JOINT']
            self.is_touch = cfg['TOUCH']
            self.can = cfg['CAN']
            self.modbus = cfg['MODBUS']

            ColorMsg(
                msg=(f"当前配置为:Linker Hand {self.hand_type} {self.hand_joint} "
                     f"压感:{self.is_touch} modbus:{self.modbus} CAN:{self.can}"),
                color="green")

            self.status_updated.emit(
                "info",
                f"读取配置成功: {self.hand_type} {self.hand_joint} "
                f"modbus={self.modbus} can={self.can}")

        except Exception as e:
            ColorMsg(msg=f"Error 配置文件读取失败: {str(e)}", color="red")
            self.status_updated.emit("error", f"配置文件读取失败: {str(e)}")
            raise

    # ------------------------------------------------------------
    def _init_api(self):
        """用从配置读到的 can / modbus 初始化 LinkerHandApi"""
        try:
            self.api = LinkerHandApi(
                hand_joint=self.hand_joint,
                hand_type=self.hand_type,
                modbus=self.modbus,
                can=self.can,
            )
            modbus_str = str(self.modbus).strip().upper()
            if modbus_str in ("NONE", "", "0"):
                proto = f"CAN({self.can})"
            else:
                proto = f"RS485/Modbus({self.modbus})"
            self.status_updated.emit(
                "info",
                f"手部API初始化成功: {self.hand_type} {self.hand_joint} via {proto}")
        except Exception as e:
            self.api = None
            self.status_updated.emit("error", f"API初始化失败：{e}")

    # ------------------------------------------------------------
    def publish_joint_state(self, positions):
        """下发手指位置 finger_move(positions)"""
        if self.api is None:
            self.status_updated.emit("error", "手部API未初始化，无法下发")
            return False

        try:
            positions = [int(p) for p in positions]
        except Exception:
            self.status_updated.emit("error", "位置值必须是整数")
            return False

        if len(positions) != JOINT_NUM:
            self.status_updated.emit(
                "error", f"关节数量不匹配：需要 {JOINT_NUM} 个，实际 {len(positions)} 个")
            return False

        for p in positions:
            if p < POS_MIN or p > POS_MAX:
                self.status_updated.emit(
                    "error", f"值越界（应 0~255）：{p}")
                return False

        try:
            self._busy = True
            self.api.finger_move(positions)
            self.status_updated.emit("info", f"已下发位置：{positions}")
            return True
        except Exception as e:
            self.status_updated.emit("error", f"下发失败：{e}")
            return False
        finally:
            self._busy = False

    # ------------------------------------------------------------
    def read_state(self):
        """读取手部当前位置"""
        if self.api is None or self._busy:
            return
        try:
            state = self.api.get_state()
            if state is None:
                return
            if hasattr(state, "tolist"):
                state = state.tolist()
            state = list(state)
            # 处理 [[...]] 这种嵌套结构
            if state and isinstance(state[0], (list, tuple)):
                state = list(state[0])
            self.state_updated.emit([int(v) for v in state])
        except Exception:
            # 读取失败静默处理，避免刷屏
            pass

    # ------------------------------------------------------------
    def shutdown(self):
        if self.state_timer.isActive():
            self.state_timer.stop()
        if self.api is not None:
            try:
                self.api.close_can()
                self.status_updated.emit("info", "API 连接已关闭")
            except Exception as e:
                self.status_updated.emit("error", f"API 关闭失败：{e}")


# ======================================================================
# 主界面
# ======================================================================
class HandControlGUI(QWidget):

    def __init__(self, api_manager: HandApiManager):
        super().__init__()
        self.api_manager = api_manager

        self.api_manager.status_updated.connect(self.on_status)
        self.api_manager.state_updated.connect(self.on_state)

        self.spinboxes = []
        self.sliders = []
        self.real_labels = []

        self.init_ui()

    # ------------------------------------------------------------
    def init_ui(self):
        jt = self.api_manager.hand_joint or "?"
        ht = self.api_manager.hand_type or "?"
        self.setWindowTitle(f"灵巧手控制面板 - {jt} {ht}")
        self.resize(900, 720)

        self.setStyleSheet("""
            QWidget {
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                margin-top: 8px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #165DFF;
                font-weight: bold;
            }
            QSpinBox, QLineEdit {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 4px 6px;
                background: #FFFFFF;
            }
            QLineEdit#BatchInput {
                font-family: Consolas, monospace;
                font-size: 14px;
                background: #FFFDF0;
                border: 1px solid #F0C000;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                border-radius: 4px;
                background: #CCCCCC;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #165DFF, stop:1 #0E42D2);
                border: 1px solid #5C8AFF;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QPushButton {
                background-color: #E0E0E0;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 6px 14px;
                min-width: 90px;
            }
            QPushButton:hover  { background-color: #F0F0F0; }
            QPushButton:pressed{ background-color: #D0D0D0; }
            QPushButton#SendBtn {
                background-color: #165DFF;
                color: white;
                border: 1px solid #0E42D2;
                font-weight: bold;
            }
            QPushButton#SendBtn:hover { background-color: #3C7BFF; }
            QPushButton#ApplyBtn {
                background-color: #FFF7E6;
                color: #FA8C16;
                border: 1px solid #FFD591;
            }
            QPushButton#ApplyBtn:hover { background-color: #FFE6B3; }
            QTextEdit#LogEdit {
                background-color: #F8F8F8;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ---------------- 标题 ----------------
        title = QLabel(f"灵巧手关节控制  ({jt} / {ht})")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Bold))
        root.addWidget(title)

        tip = QLabel("控制量范围 0 ~ 255：255 = 完全伸直，0 = 完全弯曲")
        tip.setStyleSheet("color: #666666;")
        root.addWidget(tip)

        # ---------------- 批量输入区 ----------------
        batch_group = QGroupBox("批量输入（可从日志直接粘贴）")
        batch_layout = QHBoxLayout(batch_group)
        batch_layout.setSpacing(8)

        batch_layout.addWidget(QLabel("粘贴："))

        self.batch_input = QLineEdit()
        self.batch_input.setObjectName("BatchInput")
        self.batch_input.setPlaceholderText(
            "例如：[255, 255, 255, 255, 255, 255]  或  255,255,255,255,255,255")
        self.batch_input.returnPressed.connect(self.on_apply_and_send)
        batch_layout.addWidget(self.batch_input, stretch=1)

        self.apply_btn = QPushButton("应用")
        self.apply_btn.setObjectName("ApplyBtn")
        self.apply_btn.clicked.connect(self.on_apply_batch)
        batch_layout.addWidget(self.apply_btn)

        self.apply_send_btn = QPushButton("应用并下发")
        self.apply_send_btn.setObjectName("SendBtn")
        self.apply_send_btn.clicked.connect(self.on_apply_and_send)
        batch_layout.addWidget(self.apply_send_btn)

        self.fill_from_state_btn = QPushButton("用当前值填充")
        self.fill_from_state_btn.clicked.connect(self.on_fill_from_state)
        batch_layout.addWidget(self.fill_from_state_btn)

        root.addWidget(batch_group)

        # ---------------- 关节控制区 ----------------
        ctrl_group = QGroupBox("关节位置控制")
        grid = QGridLayout(ctrl_group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(2, 1)

        headers = ["关节", "目标值", "滑杆", "当前位置"]
        for c, h in enumerate(headers):
            lb = QLabel(h)
            lb.setStyleSheet("font-weight: bold; color: #165DFF;")
            lb.setAlignment(Qt.AlignCenter)
            grid.addWidget(lb, 0, c)

        for i, name in enumerate(JOINT_NAMES):
            row = i + 1

            name_lb = QLabel(name)
            name_lb.setMinimumWidth(120)
            grid.addWidget(name_lb, row, 0)

            spin = QSpinBox()
            spin.setRange(POS_MIN, POS_MAX)
            spin.setValue(INIT_POS[i])
            spin.setFixedWidth(80)
            spin.setAlignment(Qt.AlignCenter)
            grid.addWidget(spin, row, 1)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(POS_MIN, POS_MAX)
            slider.setValue(INIT_POS[i])
            slider.setMinimumWidth(260)
            grid.addWidget(slider, row, 2)

            real_lb = QLabel("--")
            real_lb.setMinimumWidth(70)
            real_lb.setAlignment(Qt.AlignCenter)
            real_lb.setStyleSheet(
                "background:#F0F7FF; color:#0066CC; "
                "border:1px solid #B3D8FF; border-radius:4px; padding:3px;")
            grid.addWidget(real_lb, row, 3)

            # 输入框 <-> 滑杆 双向同步
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(spin.setValue)

            self.spinboxes.append(spin)
            self.sliders.append(slider)
            self.real_labels.append(real_lb)

        root.addWidget(ctrl_group)

        # ---------------- 按钮区 ----------------
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.send_btn = QPushButton("下发控制")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.clicked.connect(self.on_send_clicked)
        btn_layout.addWidget(self.send_btn)

        btn_all_open = QPushButton("全部伸直 (255)")
        btn_all_open.clicked.connect(lambda: self.set_all(POS_MAX))
        btn_layout.addWidget(btn_all_open)

        btn_all_close = QPushButton("全部弯曲 (0)")
        btn_all_close.clicked.connect(lambda: self.set_all(POS_MIN))
        btn_layout.addWidget(btn_all_close)

        btn_reset = QPushButton("回到初始位置")
        btn_reset.clicked.connect(self.on_reset_clicked)
        btn_layout.addWidget(btn_reset)

        btn_clear = QPushButton("清空日志")
        btn_clear.clicked.connect(lambda: self.log_edit.clear())
        btn_layout.addWidget(btn_clear)

        btn_layout.addStretch()
        root.addLayout(btn_layout)

        # ---------------- 日志区 ----------------
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setObjectName("LogEdit")
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(140)
        log_layout.addWidget(self.log_edit)
        root.addWidget(log_group)

    # ------------------------------------------------------------
    # 批量输入相关
    # ------------------------------------------------------------
    @staticmethod
    def parse_positions(text):
        """从任意字符串中提取 6 个 0~255 的整数"""
        if not text:
            return None
        nums = re.findall(r"-?\d+", text)
        try:
            nums = [int(n) for n in nums]
        except ValueError:
            return None
        if len(nums) != JOINT_NUM:
            return None
        for n in nums:
            if n < POS_MIN or n > POS_MAX:
                return None
        return nums

    def on_apply_batch(self):
        """解析批量输入框并填充到 spinbox/slider"""
        text = self.batch_input.text().strip()
        positions = self.parse_positions(text)
        if positions is None:
            self.api_manager.status_updated.emit(
                "error",
                f"批量输入解析失败，需要 {JOINT_NUM} 个 0~255 的整数：{text}")
            return
        for sb, v in zip(self.spinboxes, positions):
            sb.setValue(v)
        self.api_manager.status_updated.emit("info", f"已应用批量输入：{positions}")

    def on_apply_and_send(self):
        """解析 + 填充 + 立即下发"""
        text = self.batch_input.text().strip()
        positions = self.parse_positions(text)
        if positions is None:
            self.api_manager.status_updated.emit(
                "error",
                f"批量输入解析失败，需要 {JOINT_NUM} 个 0~255 的整数：{text}")
            return
        for sb, v in zip(self.spinboxes, positions):
            sb.setValue(v)
        self.api_manager.status_updated.emit("info", f"已应用批量输入：{positions}")
        self.on_send_clicked()

    def on_fill_from_state(self):
        """把当前实时位置填进批量输入框，便于复制"""
        values = []
        for lb in self.real_labels:
            t = lb.text()
            try:
                values.append(int(t))
            except ValueError:
                values.append(0)
        self.batch_input.setText(str(values))

    # ------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------
    def on_send_clicked(self):
        positions = [sb.value() for sb in self.spinboxes]
        self.api_manager.publish_joint_state(positions)

    def on_reset_clicked(self):
        for i, sb in enumerate(self.spinboxes):
            sb.setValue(INIT_POS[i])
        self.on_send_clicked()

    def set_all(self, value):
        for sb in self.spinboxes:
            sb.setValue(value)

    def on_state(self, positions):
        """实时位置刷新"""
        for i, lb in enumerate(self.real_labels):
            if i < len(positions):
                lb.setText(str(positions[i]))
            else:
                lb.setText("--")

    def on_status(self, level, message):
        """日志输出"""
        ts = time.strftime("%H:%M:%S")
        color = {"error": "#CC0000", "warning": "#FA8C16"}.get(level, "#333333")
        self.log_edit.append(
            f'<span style="color:{color};">[{ts}] {message}</span>')

    def closeEvent(self, event):
        self.api_manager.shutdown()
        super().closeEvent(event)


# ======================================================================
# main
# ======================================================================
def main():
    app = QApplication(sys.argv)

    try:
        api_manager = HandApiManager()      # ← 协议从 YAML 自动读取
    except Exception as e:
        QMessageBox.critical(
            None, "启动失败",
            f"配置文件读取或 API 初始化失败：\n{e}")
        sys.exit(1)

    window = HandControlGUI(api_manager)
    window.show()

    exit_code = app.exec_()
    api_manager.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()