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
'''
目前L10没有监听当前速度的can指令，暂时不支持实时获取速度
'''
class GetSpeed:
    def __init__(self,hand_joint="L10",hand_type="left",speed=[180,180,180,180,180]):
        self.speed = speed
        self.hand_joint = hand_joint
        self.hand_type = hand_type
        self.hand = LinkerHandApi(hand_joint=hand_joint,hand_type=hand_type)
        self.set_speed()
        self.get_speed()
    
    def set_speed(self):
        if self.hand_joint == "L7":
            if len(self.speed) == 5:
                s = self.speed+[100,100]
            else:
                s = self.speed
            self.hand.set_speed(speed=s)
        else:
            self.hand.set_speed(speed=self.speed)
        time.sleep(1)
        ColorMsg(msg=f"Set speed: {self.speed}", color='green')
    def get_speed(self):
        #while True:
        speed = self.hand.get_speed()
        ColorMsg(msg=f"Current speed: {speed}", color='yellow')
        time.sleep(0.01)

if __name__ == "__main__":
    # python3 get_set_speed.py --hand_joint L10 --hand_type right --speed 100 123 211 121 222
    parser = argparse.ArgumentParser(description='GetSpeed Example')
    parser.add_argument('--hand_joint', type=str, default='L10',required=True, help='手指关节类型，默认是L10')
    parser.add_argument('--hand_type', type=str, default='left',required=True, help='手的类型，默认是左手')
    parser.add_argument('--speed', 
                   nargs=5,  # 接收5个参数
                   type=int, 
                   default=[180]*5,
                   required=True,
                   help='手指速度（5个整数），默认是180 180 180 180 180')

    args = parser.parse_args()
    GetSpeed(hand_joint=args.hand_joint, hand_type=args.hand_type,speed=args.speed)