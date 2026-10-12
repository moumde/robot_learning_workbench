import sapien.core as sapien

import numpy as np

class LinkerHandController:
    def __init__(self, engine, scene, urdf_path,camera):
        self.engine = engine
        self.scene = scene
        self.urdf_path = urdf_path
        self.camera = camera
        self.robot = None  # Articulation 对象
        self.joint_names = []  # 关节名称列表
        self.joint_indices = {}  # 关节名称到索引的映射

        # 加载 URDF 文件并初始化驱动
        self.load_urdf()

    def load_urdf(self):
        """加载 URDF 文件并初始化机器人"""
        #loader = URDFLoader(self.engine, self.scene)
        scene = self.engine.create_scene()
        loader = scene.create_urdf_loader()
        self.robot = loader.load(self.urdf_path)
        self.robot.set_root_pose(sapien.Pose([0, 0, 0], [1, 0, 0, 0]))
        # 在仿真循环中渲染
        scene.update_render()
        self.camera.take_picture()
        rgb = self.camera.get_color_rgba()  # 获取图像数据
        # 获取所有活动关节的名称和索引
        active_joints = self.robot.get_active_joints()
        self.joint_names = [joint.get_name() for joint in active_joints]
        self.joint_indices = {name: idx for idx, name in enumerate(self.joint_names)}

        # 初始化关节驱动参数（PD 控制）
        for joint in active_joints:
            joint.set_drive_property(stiffness=100.0, damping=10.0)

    def set_joint_position(self, joint_name, target_position):
        """设置指定关节的目标位置（通过 PD 控制）"""
        if joint_name in self.joint_indices:
            idx = self.joint_indices[joint_name]
            #self.robot.set_q_target(target_position, idx)
        else:
            print(f"Joint {joint_name} not found!")

    def get_joint_positions(self):
        """获取所有关节的当前位置"""
        return self.robot.get_qpos()

    def step(self):
        """推进仿真"""
        self.scene.step()


# 示例使用
def main():
    # 初始化 Sapien 引擎和场景
    engine = sapien.Engine()
    renderer = sapien.SapienRenderer()
    engine.set_renderer(renderer)
    scene = engine.create_scene()
    scene.set_timestep(1 / 240.0)  # 设置仿真时间步长
    camera = scene.add_camera("camera", width=1280, height=720, fovy=1.0, near=0.1, far=100.0)
    camera.set_local_pose(sapien.Pose([-0.5, 0, 0.5], [0.707, 0, 0.707, 0]))
    # 添加地面
    scene.add_ground(altitude=0.0)

    # 创建 LinkerHandController 实例
    urdf_path = "urdf/linker_hand_l20_8_right.urdf"  # 替换为你的 URDF 文件路径
    hand_controller = LinkerHandController(engine, scene, urdf_path,camera)

    # 设置关节目标位置
    hand_controller.set_joint_position("thumb_joint0", 0.5)  # 设置拇指关节的位置
    hand_controller.set_joint_position("index_joint0", 0.3)  # 设置食指关节的位置

    # 仿真循环
    for _ in range(1000):
        hand_controller.step()  # 推进仿真
        positions = hand_controller.get_joint_positions()  # 获取所有关节位置
        print(positions)  # 打印关节位置（数组形式）


if __name__ == "__main__":
    main()