#!/usr/bin/env python3
import sys,os,time
current_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(target_dir)

from LinkerHand.linker_hand_api import LinkerHandApi
from LinkerHand.utils.load_write_yaml import LoadWriteYaml
from LinkerHand.utils.init_linker_hand import InitLinkerHand
from LinkerHand.utils.color_msg import ColorMsg

class GetState:
    def __init__(self):
        # 验证当前LinkerHand配置
        init_hand = InitLinkerHand()
        # 获取当前LinkerHand信息
        left_hand ,left_hand_joint ,left_hand_type ,left_hand_force,left_hand_pose, left_hand_torque, left_hand_speed ,right_hand ,right_hand_joint ,right_hand_type ,right_hand_force,right_hand_pose, right_hand_torque, right_hand_speed,setting = init_hand.current_hand()
        if left_hand_joint != False and left_hand_type != False:
            # 初始化API
            self.hand = LinkerHandApi(hand_joint=left_hand_joint,hand_type=left_hand_type)
        if right_hand_joint != False and right_hand_type != False:
            # 初始化API
            self.hand = LinkerHandApi(hand_joint=right_hand_joint,hand_type=right_hand_type)
        self.get_state()
    # 获取当前状态
    def get_state(self):
        count = 0
        while True:
            l24_state = self.api.get_state()
            print(f"L24 Current state: {l24_state}")
            count += 1
            #time.sleep(0.05)

if __name__ == "__main__":
    GetState()
