import sys
import threading
import numpy as np
import mujoco, time
import mujoco.viewer
from PyQt5.QtWidgets import QApplication, QWidget, QSlider, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

XML_PATH = "urdf/linker_hand_l10_left/linker_hand_l10_left.xml"

# --- 加载模型 ---
model = mujoco.MjModel.from_xml_path(XML_PATH)
data = mujoco.MjData(model)
data.qpos[:] = 0
data.qvel[:] = 0
model.opt.disableflags = 1
mujoco.mj_forward(model, data)

joint_count = model.nu
ctrl_values = np.zeros(joint_count)

# 获取 actuator 控制范围（注意：actuator 不是 joint 本体）
ctrl_ranges = model.actuator_ctrlrange.copy()

# 关节名称映射（根据你的模型调整）
joint_names = [
    "thumb_joint0", "thumb_joint1", "thumb_joint2", "thumb_joint3", "thumb_joint4",
    "index_joint0", "index_joint1", "index_joint2", "index_joint3",
    "middle_joint0", "middle_joint1", "middle_joint2",
    "ring_joint0", "ring_joint1", "ring_joint2", "ring_joint3",
    "little_joint0", "little_joint1", "little_joint2", "little_joint3"
]

# --- MuJoCo 模拟线程 ---
def mujoco_thread():
    with mujoco.viewer.launch_passive(model, data) as viewer:
        print("MuJoCo viewer running...")
        last_print_time = time.time()
        
        while viewer.is_running():
            # 设置控制信号并执行仿真步
            data.ctrl[:] = ctrl_values
            mujoco.mj_step(model, data)
            viewer.sync()
            
            # 每秒打印一次关节数据（避免刷屏）
            current_time = time.time()
            if current_time - last_print_time >= 0.01:
                print_joint_data()
                last_print_time = current_time

def print_joint_data():
    """打印所有关节的实时状态"""
    print("\n" + "=" * 80)
    print(f"Time: {data.time:.2f}s")
    print("=" * 80)
    
    for i in range(model.njnt):
        jnt_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        if jnt_name not in joint_names:  # 只打印手指关节
            continue
            
        qpos_adr = model.jnt_qposadr[i]
        qvel_adr = model.jnt_dofadr[i]
        
        # 获取关节数据
        pos = data.qpos[qpos_adr]
        vel = data.qvel[qvel_adr] if qvel_adr != -1 else 0
        torque = data.qfrc_actuator[qvel_adr] if qvel_adr != -1 else 0
        
        print(f"{jnt_name}:")
        print(f"  Position: {pos:.4f} rad")
        print(f"  Velocity: {vel:.4f} rad/s")
        print(f"  Torque: {torque:.4f} N·m")
        print("-" * 40)

# --- GUI 控制窗口 ---
class ControlWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Joint Controller")
        self.setGeometry(100, 100, 400, 80 + 50 * joint_count)

        layout = QVBoxLayout()
        self.sliders = []
        
        for i in range(joint_count):
            min_val, max_val = ctrl_ranges[i]
            label = QLabel(f"{joint_names[i]} [{min_val:.2f}, {max_val:.2f}]")
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(int(min_val * 100))
            slider.setMaximum(int(max_val * 100))
            slider.setValue(0)

            slider.valueChanged.connect(self.make_slider_callback(i, min_val, max_val))
            layout.addWidget(label)
            layout.addWidget(slider)
            self.sliders.append(slider)

        self.setLayout(layout)

    def make_slider_callback(self, index, min_val, max_val):
        def callback(value):
            ctrl_values[index] = value / 100.0
        return callback

# --- 主函数 ---
if __name__ == "__main__":
    # 启动 MuJoCo 模拟线程
    sim_thread = threading.Thread(target=mujoco_thread)
    sim_thread.daemon = True  # 主线程退出时自动结束
    sim_thread.start()

    # 启动 GUI（主线程）
    app = QApplication(sys.argv)
    window = ControlWindow()
    window.show()
    sys.exit(app.exec_())
