#!/usr/bin/env python3
import sys,os,time
current_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(target_dir)
from LinkerHand.linker_hand_api import LinkerHandApi
'''
手指快速移动
'''
def main():
    hand = LinkerHandApi(hand_joint="L24",hand_type="right")
    # 设置L24为使能状态
    hand.set_enable()
    # 设置L24为失能状态
    #hand.set_disable()
    time.sleep(0.1)
    hand.set_speed(speed=180)
    count = 0
    while True:
        if count % 2 == 0:
            pose = [232, 254, 255, 254, 252, 250, 61, 0.0, 10, 40, 189, 0.0, 0.0, 0.0, 0.0, 255, 252, 243, 240, 252, 229, 232, 247, 252, 247]
        else:
            #pose = [255, 203, 173, 44, 79, 126, 234, 0.0, 81, 61, 150, 0.0, 0.0, 0.0, 0.0, 8, 77, 0, 85, 26, 117, 0, 22, 91, 10]
            pose = [248, 127, 107, 180, 214, 42, 137, 0.0, 30, 20, 189, 0.0, 0.0, 0.0, 0.0, 59, 47, 32, 11, 17, 170, 43, 84, 76, 81]
        print(pose)
        hand.finger_move(pose=pose)
        count = count+1
        time.sleep(4)

if __name__ == "__main__":
    main()