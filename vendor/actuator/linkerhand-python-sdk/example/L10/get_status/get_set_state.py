#!/usr/bin/env python3
import sys,os,time
import argparse
current_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(target_dir)

from LinkerHand.linker_hand_api import LinkerHandApi
from LinkerHand.utils.load_write_yaml import LoadWriteYaml
from LinkerHand.utils.init_linker_hand import InitLinkerHand
from LinkerHand.utils.color_msg import ColorMsg

class GetState:
    def __init__(self,hand_joint="L10",hand_type="left",position=[180,180,180,180,180]):
        self.position = position
        self.hand_joint = hand_joint
        self.hand_type = hand_type
        self.hand = LinkerHandApi(hand_joint=self.hand_joint,hand_type=self.hand_type)
        self.set_position()
        self.get_state()

    def set_position(self):
        #for i in range(15):
        if self.hand_joint == "L7":
            if len(self.position) == 5:
                p = self.position + [100, 100]
            else:
                p = self.position
            self.hand.finger_move(pose=p)
        else:
            self.hand.finger_move(pose=self.position)
        time.sleep(0.01)
        ColorMsg(msg=f"Set position: {self.position}", color='green')
            
    # 获取当前状态
    def get_state(self):
        state = self.hand.get_state()
        print(f"Current state: {state}")
        time.sleep(0.01)

if __name__ == "__main__":
    # python3 get_set_state.py --hand_joint L10 --hand_type right --position 100 123 211 121 222 255 255 255 255 255
    parser = argparse.ArgumentParser(description='GetSpeed Example')
    parser.add_argument('--hand_joint', type=str, default='L10',required=True, help='手指关节类型，默认是L10')
    parser.add_argument('--hand_type', type=str, default='left',required=True, help='手的类型，默认是左手')
    parser.add_argument('--position', 
                   nargs='+',  # 接收5个参数
                   type=int, 
                   default=[180]*10,
                   required=True,
                   help='不同灵巧手的手指位置参数个数不同，L7是5个，L10是10个，L20是20个，L25是25个')

    args = parser.parse_args()
    GetState(hand_joint=args.hand_joint,hand_type=args.hand_type,position=args.position)
