#!/usr/bin/env python3
import sys,os,time,argparse
# 设置当前目录和目标目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 设置目标目录为当前目录的上两级
target_dir = os.path.abspath(os.path.join(current_dir, "../.."))
# 将目标目录添加到系统路径中，以便导入自定义模块
sys.path.append(target_dir)
# 导入API模块
from LinkerHand.linker_hand_api import LinkerHandApi
# 导入工具模块
from LinkerHand.utils.color_msg import ColorMsg
'''
Linker Hand O6 API示例
'''
# O6 手指运动坐标 ["张开","壹","贰","叁","肆","伍","OK","点赞","握拳"]
POSE = [[250, 250, 250, 250, 250, 250],[125, 18, 255, 0, 0, 0],[92, 87, 255, 255, 0, 0],[92, 87, 255, 255, 255, 0],[92, 87, 255, 255, 255, 255],[255, 255, 255, 255, 255, 255],[139, 91, 103, 250, 250, 250],[250, 79, 0, 0, 0, 0],[102, 18, 0, 0, 0, 0],]
# O6 最大扭矩阈值
TORQUE = [255, 255, 255, 255, 255, 255]
# O6 最大速度阈值
SPEED = [255, 255, 255, 255, 255, 255]
def main():
    parser = argparse.ArgumentParser(description='处理手势参数')
    parser.add_argument('--hand_type', choices=['left', 'right'], required=True, help='指定左手或右手')
    parser.add_argument('--hand_joint', required=True, help='指定LinkerHand型号')
    parser.add_argument('--can', default="can0", help='指定CAN编号')
    args = parser.parse_args()
    print(f"手类型: {args.hand_type}, 关节: {args.hand_joint}")
    matrix_dic={}
    hand_joint = args.hand_joint
    hand_type = args.hand_type
    can = args.can
    # 初始化API
    hand = LinkerHandApi(hand_joint=hand_joint,hand_type=hand_type, can=can)
    # 设置速度
    hand.set_speed(speed=SPEED)
    time.sleep(0.1)
    ColorMsg(msg=f"当前设置速度为:{SPEED}", color="green")
    # 设置扭矩
    hand.set_torque(torque=TORQUE)
    time.sleep(0.1)
    ColorMsg(msg=f"当前设置扭矩为:{TORQUE}", color="green")
    while True:
        for i in range(6):
            ColorMsg(msg=f"当前为手指运动坐标:{POSE[i]}", color="green")
            hand.finger_move(pose=POSE[i])
            time.sleep(0.1)
            state = hand.get_state()
            ColorMsg(msg=f"当前手指状态为:{state}", color="green")
            time.sleep(1)
            matrix_dic["thumb_matrix"] = hand.get_thumb_matrix_touch(sleep_time=0.002).tolist()
            time.sleep(0.002)
            matrix_dic["index_matrix"] = hand.get_index_matrix_touch(sleep_time=0.002).tolist()
            time.sleep(0.002)
            matrix_dic["middle_matrix"] = hand.get_middle_matrix_touch(sleep_time=0.002).tolist()
            time.sleep(0.002)
            matrix_dic["ring_matrix"] = hand.get_ring_matrix_touch(sleep_time=0.002).tolist()
            time.sleep(0.002)
            matrix_dic["little_matrix"] = hand.get_little_matrix_touch(sleep_time=0.002).tolist()
            time.sleep(0.002)
            print("\n")
            ColorMsg(msg=f"当前手指触摸矩阵为:{matrix_dic}", color="green")
            print("\n")
            time.sleep(3)


if __name__ == "__main__":
    # Ubuntu python3 linker_hand_o6.py --hand_joint O6 --hand_type left --can can0
    
    # WIN 
    # pip install pyyaml numpy
    # python linker_hand_o6.py --hand_joint O6 --hand_type left --can PCAN_USBBUS1
    main()
