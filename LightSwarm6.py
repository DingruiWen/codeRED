'''
    LightSwarm Raspberry Pi Logger 
    SwitchDoc Labs 
    December 2020
'''
from __future__ import print_function
 
from builtins import chr
from builtins import str
from builtins import range
import sys  
import time
import random

from netifaces import interfaces, ifaddresses, AF_INET
import netifaces

from socket import *

VERSIONNUMBER = 7
# packet type definitions
LIGHT_UPDATE_PACKET = 0
RESET_SWARM_PACKET = 1
CHANGE_TEST_PACKET = 2   # Not Implemented
RESET_ME_PACKET = 3
DEFINE_SERVER_LOGGER_PACKET = 4
LOG_TO_SERVER_PACKET = 5
MASTER_CHANGE_PACKET = 6
BLINK_BRIGHT_LED = 7
LOG_DATA_PACKET = 8

MYPORT = 2910

SWARMSIZE = 5


logString = ""
# command from command Code

#!/usr/bin/env python3
#shebang line is used to make sure script use python3
#button's one end connect to GND, other end to GPIO 16

# GPIO setup
import RPi.GPIO as GPIO
import signal
button_pin = 7
led_pin = 11
red_pin = 40
green_pin = 38
blue_pin = 36
com_pins = [31, 33, 35, 37]
latch_pin = 16
clock_pin = 12
data_pin = 18

latchPin= 13
clockPin = 11
dataPin = 15

LSBFIRST = 1
MSBFIRST = 2

GPIO.setmode(GPIO.BOARD)
#bouncetime ensure callback is triggered once in 100ms
GPIO.setup(led_pin, GPIO.OUT)
GPIO.setup(red_pin, GPIO.OUT)
GPIO.setup(green_pin, GPIO.OUT)
GPIO.setup(blue_pin, GPIO.OUT)
# Turn off LED at the beginning
GPIO.output(led_pin, GPIO.LOW)
GPIO.output(red_pin, GPIO.LOW)
GPIO.output(green_pin, GPIO.LOW)
GPIO.output(blue_pin, GPIO.LOW)
#RGB value
HIGH = 400
MEDIUM = 200

GPIO.setup(latch_pin, GPIO.OUT)
GPIO.setup(clock_pin, GPIO.OUT)
GPIO.setup(data_pin, GPIO.OUT)
for pin in com_pins:
    GPIO.setup(pin, GPIO.OUT)

GPIO.setup(dataPin, GPIO.OUT)
GPIO.setup(latchPin, GPIO.OUT)
GPIO.setup(clockPin, GPIO.OUT)

#press button command
#import matplotlib.animation as animation
from matplotlib.animation import FuncAnimation
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import json

from tracemalloc import *

start_time = time.time()
history_time = []
log_data = []  # List to store log entries
current_master = 0
previous_master = 0
current_value = 0
history_value = []
history_master = []
sliding_window = [0]*30  # Initialize sliding window with zeros
log_entry = {}
ip_address = "192.168.1.5"
#below is how my RGB LEDs reflects on different voltage value

num = {
    '0': 0xc0,
    '1': 0xf9,
    '2': 0xa4,
    '3': 0xb0,
    '4': 0x99,
    '5': 0x92,
    '6': 0x82,
    '7': 0xf8,
    '8': 0x80,
    '9': 0x90,
    '.': 0xbf  # 添加小数点
}

y = [
    0x01, 0x03, 0x07, 0x0F, 0x1F, 0x3F, 0x7F, 0xFF
]


def map_value_to_range(value, start, end, target_range):
    # 线性映射
    return int((value - start) / (end - start) * (len(target_range) - 1))

def map_value_to_y(value):
    start_value = 1
    end_value = 1023
    return y[map_value_to_range(value, start_value, end_value, y)]

def elect_digital_display(com):
    for pin in com_pins:
        GPIO.output(pin, GPIO.LOW)
    GPIO.output(com_pins[com], GPIO.HIGH)

def write_data(value):
    GPIO.output(latch_pin, GPIO.LOW)
    for _ in range(8):
        GPIO.output(data_pin, value & 0x01)
        GPIO.output(clock_pin, GPIO.HIGH)
        GPIO.output(clock_pin, GPIO.LOW)
        value >>= 1
    GPIO.output(latch_pin, GPIO.HIGH)

def shiftOut(dPin, cPin, order, val):
    for i in range(0, 8):
        GPIO.output(cPin, GPIO.LOW)
        if order == LSBFIRST:
            GPIO.output(dPin, (0x01 & (val >> i) == 0x01) and GPIO.HIGH or GPIO.LOW)
        elif order == MSBFIRST:
            GPIO.output(dPin, (0x80 & (val << i) == 0x80) and GPIO.HIGH or GPIO.LOW)
        GPIO.output(cPin, GPIO.HIGH)

def compress_window(sliding_window):
    compressed_window = []
    
    # 将前 28 个数据按照每四个数据平均一个进行压缩
    for i in range(0, 28, 4):
        average_value = sum(sliding_window[i:i+4]) // 4
        mapped_value = map_value_to_y(average_value)
        compressed_window.append(mapped_value)

    # 将最后两个数据平均到最后一个
    average_last_values = (sliding_window[28] + sliding_window[29]) // 2
    mapped_value = map_value_to_y(average_last_values)
    compressed_window.append(mapped_value)
    
    return compressed_window

def matrix(sliding_window):
    compressed_window = compress_window(sliding_window)
    print(compressed_window)
    for j in range(0,20):# times of repeated displaying LEDMatrix in every frame, the bigger the "j", the longer the display time.
            x=0x80# Set the column information to start from the first column
            for i in range(0,8):
                GPIO.output(latchPin, GPIO.LOW)
                shiftOut(dataPin,clockPin,MSBFIRST,compressed_window[i])
                shiftOut(dataPin, clockPin, MSBFIRST, ~x)  # Invert the values to match LED logic (common anode)
                GPIO.output(latchPin, GPIO.HIGH)
                time.sleep(0.001)  # Display the next column
                x >>= 1
def flash_led(times,blink_pin):
    for i in range(times):
        #print ("LED on")
        GPIO.output(blink_pin,GPIO.HIGH)
        time.sleep(1/times)
        #print ("LED off")
        GPIO.output(blink_pin,GPIO.LOW)
        time.sleep(1/times)

def change_rgb(average,masterSwarmNum,ledDict):
    global HIGH,MEDIUM
    for key,value in ledDict.items():
        if(int(masterSwarmNum) == value):
            blink_pin = key
    if average >= HIGH:
        times = 4
    elif average >= MEDIUM and average < HIGH:
        times = 2
    else:
        times = 1
    print("now ledDict : ")
    print(ledDict)
    return times, blink_pin ,ledDict

def clear_led():
    GPIO.output(red_pin, GPIO.LOW)
    GPIO.output(green_pin, GPIO.LOW)
    GPIO.output(blue_pin, GPIO.LOW)
    print ("clear LED on")
    GPIO.output(led_pin, GPIO.HIGH)
    time.sleep(3)
    print ("clear LED off")
    GPIO.output(led_pin, GPIO.LOW)

def save_n_create_log():
    global current_master, current_value, history_value, history_master,history_time,sliding_window,log_data,start_time,log_entry
    log_entry = {
        #"time": time.time(),
        #"current_master": current_master,
        #"current_value": current_value,
        "packet_type": "log_data_packet",
        "history_value": history_value,
        "history_master": history_master,
        "history_time": history_time
    }
    log_data.append(log_entry)
    #current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"log_{start_time}.txt"
    log_str = ', '.join(map(str, log_data))  # 将列表转换为逗号分隔的字符串
    
    # Implement code to save log data to the file
    with open(log_filename, 'w') as log_file:
        # Write your log data
        log_file.write("Log data here\n")
        log_file.write(log_str)
    
    #reset all the data
    start_time = time.time()
    history_time = []
    previous_master = 0
    current_master = 0
    current_value = 0
    history_value = []
    history_master = []
    sliding_window = [0]*30  # Initialize sliding window with zeros


def init_graph(initialized):
# 创建初始图形
    fig, axs = plt.subplots(2, 1, figsize=(10, 6))

    height = 0
    # 初始绘制
    line, = axs[0].plot(sliding_window, label='Sliding Window')
    bar = axs[1].bar(0.5, height, color='red',width = 0.5)  # 修改这里
    axs[1].set_ylim(0, 50)
    axs[1].set_xlim(0,1)
    axs[0].set_ylim(0, 1023)
    axs[0].set_xlim(0,30)

    # 设置图形属性
    axs[0].set_title('Sliding Window Curve')
    axs[0].set_xlabel('Index')
    axs[0].set_ylabel('Value')
    axs[0].legend()

    axs[1].set_title('Master Time Change')
    axs[1].set_xlabel('Master Time')
    axs[1].set_ylabel('Bar Height')
    i = 0
    initialized = True
    plt.ion()
    plt.show()
    return initialized,line,bar,i,axs

def update_graphs(line,bar,i,ledDict,axs):
    global previous_master,sliding_window,current_master
    keyword = 0
    color = "white"
    for key,value in ledDict.items():
        if(int(current_master) == value):
            keyword = key
    colors = {40:'red', 38:'green',36:'blue'}
    for key,value in colors.items():
        if(keyword == key):
            color = value
    # 更新曲线和柱状图
    title = f"192.169.1.{current_master} is master"
    axs[1].set_title(title)
    line.set_ydata(sliding_window)
    if (current_master == previous_master):
        bar[0].set_height(i)
        i += 1
        #print("i am in first if")
    else:
        i = 0
        bar[0].set_color(color)
        bar[0].set_height(i)
        i += 1
        #print("I am in else")
    plt.draw()
    plt.pause(0.05)
    print(i)
    return line, bar,i,axs

def parseLogPacket(message):
    global current_master, previous_master,current_value, history_value, history_master,sliding_window,start_time
    # Extract data from the LOG_TO_SERVER_PACKET
    previous_master = current_master
    current_master = message[2]
    current_value = 256*message[5]+message[6]
    if (previous_master != current_master):
        current_time = time.time()
        history_time.append(current_time - start_time)
        start_time = current_time
    # Update history_master with current_master
    history_master.append(current_master)
    # Update history_value with current_value
    history_value.append(current_value)
    sliding_window.append(current_value)
    sliding_window.pop(0)  # 移除最旧的数据
    print(history_value)
    ip_address = f"192.169.1.{current_master}"
    # Additional functionality based on parseLogPacket
    incomingSwarmID = setAndReturnSwarmID((message[2]))
    print("Log From SwarmID:",(message[2]))

    logString = ""
    for i in range(0,(message[3])):
        logString = logString + chr((message[i+7]))

    return logString

def signal_handler(sig, frame):
    GPIO.cleanup()
    sys.exit(0)

def button_pressed_callback(channel):
    print("Button pressed!")
    clear_led()
    SendLOG_DATA_PACKET(s)
    time.sleep(1)
    SendLOG_DATA_PACKET(s)
    time.sleep(1)
    save_n_create_log()
    time.sleep(3)
 

def assignPin(swarmNum,ledDict):
    for value in swarmNum:
        if int(value) in ledDict.values():
            print(".")
            #print(f"Value {value} already exists in the dictionary.")
        else:
            # find the first 0 and append value in it
            for key, dict_value in ledDict.items():
                if dict_value == 0:
                    ledDict[key] = int(value)
                    break
    return swarmNum[0],ledDict

def completeCommand():

        #f = open("/home/pi/SDL_Pi_LightSwarm/state/LSCommand.txt", "w")
        f = open("./state/LSCommand.txt", "w")
        f.write("DONE")
        f.close()

def completeCommandWithValue(value):

        #f = open("/home/pi/SDL_Pi_LightSwarm/state/LSResponse.txt", "w")
        f = open(".state/LSResponse.txt", "w")
        f.write(value)
        print("in completeCommandWithValue=", value)
        f.close()

        completeCommand()


def processCommand(s):
        #f = open("//home/pi/SDL_Pi_LightSwarm/state/LSCommand.txt", "r")
        f = open("./state/LSCommand.txt", "r")
        command = f.read()
        f.close()

        command = command.rstrip()        
        if (command == "") or (command == "DONE"):
            # Nothing to do
            return False

        # Check for our commands
        #pclogging.log(pclogging.INFO, __name__, "Command %s Recieved" % command)

        print("Processing Command: ", command)
        if (command == "STATUS"):

            completeCommandWithValue(logString)

            return True

        if (command == "RESETSWARM"):

            SendRESET_SWARM_PACKET(s)
		
            completeCommand()

            return True

        # check for , commands

        print("command=%s" % command)
        myCommandList = command.split(',')
        print("myCommandList=", myCommandList)

        if (len(myCommandList) > 1):   
            # we have a list command
		
            if (myCommandList[0]== "BLINKLIGHT"):
                SendBLINK_BRIGHT_LED(s, int(myCommandList[1]), 1)

            if (myCommandList[0]== "RESETSELECTED"):
                SendRESET_ME_PACKET(s, int(myCommandList[1]))

            if (myCommandList[0]== "SENDSERVER"):
                SendDEFINE_SERVER_LOGGER_PACKET(s)

            completeCommand()

            return True
		

			
        completeCommand()
			


        return False


def SendLOG_DATA_PACKET(s):
    global history_master,history_time,history_value,current_time,start_time
    print("LOG_DATA_PACKET")
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    current_time = time.time()
    history_time.append(current_time - start_time)
    # 将 log_entry 转换为 JSON 字符串
    whole_len = len(history_value)+len(history_time)+len(history_master)
    data= ["" for i in range(2*whole_len+5)]
    data[0] = int("F0", 16).to_bytes(1,'little') 
    data[1] = int(LOG_DATA_PACKET).to_bytes(1,'little')
    data[2] = int(len(history_master)).to_bytes(1,'little')
    data[3] = int(len(history_time)).to_bytes(1,'little')
    data[4] = int(len(history_value)).to_bytes(1,'little')
    i = 5
    for obj in history_master:
        byte_array = int(obj).to_bytes(2, 'little')  # 转换为两个字节的小端表示
        data[i] = byte_array[0].to_bytes(1,'little')
        data[i+1] = byte_array[1].to_bytes(1,'little')
        i+=2
    #data[i] = ord('|').to_bytes(1,'little')
    #i+=1
    for obj in history_time:
        byte_array = int(obj).to_bytes(2, 'little')  # 转换为两个字节的小端表示
        data[i] = byte_array[0].to_bytes(1,'little')
        data[i+1] = byte_array[1].to_bytes(1,'little')
        i+=2
    #data[i] = ord('|').to_bytes(1,'little')
    #i+=1
    for obj in history_value:
        byte_array = int(obj).to_bytes(2, 'little')  # 转换为两个字节的小端表示
        data[i] = byte_array[0].to_bytes(1,'little')
        data[i+1] = byte_array[1].to_bytes(1,'little')
        i+=2
    #for obj in data:
        #print("data type is ",type(obj))
        #print("data is ",obj)
    mymessage = ''.encode()
    #print("data len is ",len(data)) 
    print("send data is ",mymessage.join(data))
    s.sendto(mymessage.join(data), ('<broadcast>'.encode(), MYPORT))


def SendDEFINE_SERVER_LOGGER_PACKET(s):
    print("DEFINE_SERVER_LOGGER_PACKET Sent") 
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

	# get IP address
    #for ifaceName in interfaces():
            #addresses = [i['addr'] for i in ifaddresses(ifaceName).setdefault(AF_INET, [{'addr':'0.0.0.0'}] )]
            #print('%s: %s' % (ifaceName, ', '.join(addresses)))
  
    # last interface (wlan0) grabbed 
    diction = netifaces.ifaddresses('wlan0')
    #print(diction)
    for i in diction:
        addresses = diction.get(2)[0]['addr']
    print(addresses) 
    myIP = addresses.split('.')
    data= ["" for i in range(14)]

    
    data[0] = int("F0", 16).to_bytes(1,'little') 
    data[1] = int(DEFINE_SERVER_LOGGER_PACKET).to_bytes(1,'little')
    data[2] = int("FF", 16).to_bytes(1,'little') # swarm id (FF means not part of swarm)
    data[3] = int(VERSIONNUMBER).to_bytes(1,'little')
    data[4] = int(myIP[0]).to_bytes(1,'little') # 1 octet of ip
    data[5] = int(myIP[1]).to_bytes(1,'little') # 2 octet of ip
    data[6] = int(myIP[2]).to_bytes(1,'little') # 3 octet of ip
    data[7] = int(myIP[3]).to_bytes(1,'little') # 4 octet of ip
    data[8] = int(0x00).to_bytes(1,'little')
    data[9] = int(0x00).to_bytes(1,'little')
    data[10] = int(0x00).to_bytes(1,'little')
    data[11] = int(0x00).to_bytes(1,'little')
    data[12] = int(0x00).to_bytes(1,'little')
    data[13] = int(0x0F).to_bytes(1,'little')
    mymessage = ''.encode()  	
    s.sendto(mymessage.join(data), ('<broadcast>'.encode(), MYPORT))
	
def SendRESET_SWARM_PACKET(s):
    print("RESET_SWARM_PACKET Sent") 
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    data= ["" for i in range(14)]

    data[0] = int("F0", 16).to_bytes(1,'little')
    
    data[1] = int(RESET_SWARM_PACKET).to_bytes(1,'little')
    data[2] = int("FF", 16).to_bytes(1,'little') # swarm id (FF means not part of swarm)
    data[3] = int(VERSIONNUMBER).to_bytes(1,'little')
    data[4] = int(0x00).to_bytes(1,'little')
    data[5] = int(0x00).to_bytes(1,'little')
    data[6] = int(0x00).to_bytes(1,'little')
    data[7] = int(0x00).to_bytes(1,'little')
    data[8] = int(0x00).to_bytes(1,'little')
    data[9] = int(0x00).to_bytes(1,'little')
    data[10] = int(0x00).to_bytes(1,'little')
    data[11] = int(0x00).to_bytes(1,'little')
    data[12] = int(0x00).to_bytes(1,'little')
    data[13] = int(0x0F).to_bytes(1,'little')
      	
    mymessage = ''.encode()  	
    s.sendto(mymessage.join(data), ('<broadcast>'.encode(), MYPORT))
	
def SendRESET_ME_PACKET(s, swarmID):
    print("RESET_ME_PACKET Sent") 
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    data= ["" for i in range(14)]

    data[0] = int("F0", 16).to_bytes(1,'little')
    
    data[1] = int(RESET_ME_PACKET).to_bytes(1,'little')
    data[2] = int(swarmStatus[swarmID][5]).to_bytes(1,'little')
    data[3] = int(VERSIONNUMBER).to_bytes(1,'little')
    data[4] = int(0x00).to_bytes(1,'little')
    data[5] = int(0x00).to_bytes(1,'little')
    data[6] = int(0x00).to_bytes(1,'little')
    data[7] = int(0x00).to_bytes(1,'little')
    data[8] = int(0x00).to_bytes(1,'little')
    data[9] = int(0x00).to_bytes(1,'little')
    data[10] = int(0x00).to_bytes(1,'little')
    data[11] = int(0x00).to_bytes(1,'little')
    data[12] = int(0x00).to_bytes(1,'little')
    data[13] = int(0x0F).to_bytes(1,'little')
      	
    mymessage = ''.encode()  	
    s.sendto(mymessage.join(data), ('<broadcast>'.encode(), MYPORT))


def SendCHANGE_TEST_PACKET(s, swarmID):
    print("RESET_ME_PACKET Sent") 
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    data= ["" for i in range(14)]

    data[0] = int("F0", 16).to_bytes(1,'little')
    
    data[1] = int(RESET_ME_PACKET).to_bytes(1,'little')
    data[2] = int(swarmStatus[swarmID][5]).to_bytes(1,'little')
    
    data[3] = int(VERSIONNUMBER).to_bytes(1,'little')
    data[4] = int(0x00).to_bytes(1,'little')
    data[5] = int(0x00).to_bytes(1,'little')
    data[6] = int(0x00).to_bytes(1,'little')
    data[7] = int(0x00).to_bytes(1,'little')
    data[8] = int(0x00).to_bytes(1,'little')
    data[9] = int(0x00).to_bytes(1,'little')
    data[10] = int(0x00).to_bytes(1,'little')
    data[11] = int(0x00).to_bytes(1,'little')
    data[12] = int(0x00).to_bytes(1,'little')
    data[13] = int(0x0F).to_bytes(1,'little')
      	
    mymessage = ''.encode()  	
    s.sendto(mymessage.join(data), ('<broadcast>'.encode(), MYPORT))
	

def SendBLINK_BRIGHT_LED(s, swarmID, seconds):
    print("BLINK_BRIGHT_LED Sent") 
    print("swarmStatus=", swarmStatus);
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    data= ["" for i in range(0,14)]

    data[0] = int("F0", 16).to_bytes(1,'little')
    
    data[1] = int(BLINK_BRIGHT_LED).to_bytes(1,'little')
    print("swarmStatus[swarmID][5]", swarmStatus[swarmID][5]) 
    
    data[2] = int(swarmStatus[swarmID][5]).to_bytes(1,'little')
    data[3] = int(VERSIONNUMBER).to_bytes(1,'little')
    if (seconds > 12.6):
        seconds = 12.6
    data[4] = int(seconds*10).to_bytes(1,'little')
    data[5] = int(0x00).to_bytes(1,'little')
    data[6] = int(0x00).to_bytes(1,'little')
    data[7] = int(0x00).to_bytes(1,'little')
    data[8] = int(0x00).to_bytes(1,'little')
    data[9] = int(0x00).to_bytes(1,'little')
    data[10] = int(0x00).to_bytes(1,'little')
    data[11] = int(0x00).to_bytes(1,'little')
    data[12] = int(0x00).to_bytes(1,'little')
    data[13] = int(0x0F).to_bytes(1,'little')
      	
    mymessage = ''.encode()  	
    s.sendto(mymessage.join(data), ('<broadcast>'.encode(), MYPORT))
    
	

def parseLogPacket2(message):

	incomingSwarmID = setAndReturnSwarmID((message[2]))
	print("Log From SwarmID:",(message[2]))
	print("Swarm Software Version:", (message[4]))
	print("StringLength:",(message[3]))
	logString = ""
	for i in range(0,(message[3])):
		logString = logString + chr((message[i+7]))

	#print("logString:", logString)	and return swarm ID
	return logString



# build Webmap

def buildWebMapToFile(logString,swarmSize):
    swarmNum = []
    swarmList = logString.split("|")
    for i in range(0,swarmSize):
        swarmElement = swarmList[i].split(",")
        if(swarmElement[5] != 0):
            swarmNum.append(swarmElement[5])    
        print("swarmElement=", swarmElement)
    return swarmNum

def buildWebMapToFile2(logString, swarmSize ):



    webresponse = ""
    swarmNum = []
    swarmList = logString.split("|")
    for i in range(0,swarmSize):
        swarmElement = swarmList[i].split(",")
        if(swarmElement[5] != 0):
            swarmNum.append(swarmElement[5])	
        print("swarmElement=", swarmElement)
        webresponse += "<figure>"
        webresponse += "<figcaption"
        webresponse += " style='position: absolute; top: "
        webresponse +=  str(100-20)
        webresponse +=  "px; left: " +str(20+120*i)+  "px;'/>\n"
        if (int(swarmElement[5]) == 0):
            webresponse += "&nbsp;&nbsp;&nbsp&nbsp;&nbsp;---"
        else:
            webresponse += "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;%s" % swarmElement[5]
				
        webresponse += "</figcaption>"
        #webresponse += "<img src='" + "http://192.168.1.40:9750"
        webresponse += "<img src='" 
			
			
        if (swarmElement[4] == "PR"):
            if (swarmElement[1] == "1"):
                webresponse += "On-Master.png' style='position: absolute; top: "
            else:
                webresponse += "On-Slave.png' style='position: absolute; top: "
        else:
            if (swarmElement[4] == "TO"):
                webresponse += "Off-TimeOut.png' style='position: absolute; top: "
            else:
                webresponse += "Off-NotPresent.png' style='position: absolute; top: "

        webresponse +=  str(100)
        webresponse +=  "px; left: " +str(20+120*i)+  "px;'/>\n"

        webresponse += "<figcaption"
        webresponse += " style='position: absolute; top: "
        webresponse +=  str(100+100)
        webresponse +=  "px; left: " +str(20+120*i)+  "px;'/>\n"
        if (swarmElement[4] == "PR"):
            if (swarmElement[1] == "1"):
                webresponse += "&nbsp;&nbsp;&nbsp;&nbsp;Master"
            else:
                webresponse += "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Slave"
        else:
            if (swarmElement[4] == "TO"):
                webresponse += "TimeOut" 
            else:
                webresponse += "Not Present" 

				
        webresponse += "</figcaption>"
			
        webresponse += "</figure>"




    #f = open("/home/pi/SDL_Pi_LightSwarm/state/figure.html", "w")
    f = open("./state/figure.html", "w")
    f.write(webresponse)

    f.close()

    #f = open("/home/pi/SDL_Pi_LightSwarm/state/swarm.html", "w")
    f = open("./state/swarm.html", "w")
    #fh = open("/home/pi/SDL_Pi_LightSwarm/state/swarmheader.txt", "r")
    #ff = open("/home/pi/SDL_Pi_LightSwarm/state/swarmfooter.txt", "r")
    fh = open("./state/swarmheader.txt", "r")
    ff = open("./state/swarmfooter.txt", "r")

    webheader = fh.read()
    webfooter = ff.read()

    f.write(webheader)
    f.write(webresponse)
    f.write(webfooter)

    f.close
    fh.close
    ff.close

    return swarmNum


def setAndReturnSwarmID(incomingID):
 
  
    for i in range(0,SWARMSIZE):
        if (swarmStatus[i][5] == incomingID):
            return i
        else:
            if (swarmStatus[i][5] == 0):  # not in the system, so put it in
    
                swarmStatus[i][5] = incomingID;
                print("incomingID %d " % incomingID)
                print("assigned #%d" % i)
                return i
    
  
    # if we get here, then we have a new swarm member.   
    # Delete the oldest swarm member and add the new one in 
    # (this will probably be the one that dropped out)
  
    oldTime = time.time();
    oldSwarmID = 0
    for i in range(0,SWARMSIZE):
        if (oldTime > swarmStatus[i][1]):
            ldTime = swarmStatus[i][1]
            oldSwarmID = i
  		
 
 

    # remove the old one and put this one in....
    swarmStatus[oldSwarmID][5] = incomingID;
    # the rest will be filled in by Light Packet Receive
    print("oldSwarmID %i" % oldSwarmID)
 
    return oldSwarmID 
  

# set up sockets for UDP

s=socket(AF_INET, SOCK_DGRAM)
host = 'localhost';
s.bind(('',MYPORT))

print("--------------")
print("LightSwarm Logger")
print("Version ", VERSIONNUMBER)
print("--------------")

 
# first send out DEFINE_SERVER_LOGGER_PACKET to tell swarm where to send logging information 

SendDEFINE_SERVER_LOGGER_PACKET(s)
time.sleep(3)
SendDEFINE_SERVER_LOGGER_PACKET(s)



# swarmStatus
swarmStatus = [[0 for x  in range(6)] for x in range(SWARMSIZE)]

# 6 items per swarm item

# 0 - NP  Not present, P = present, TO = time out
# 1 - timestamp of last LIGHT_UPDATE_PACKET received
# 2 - Master or slave status   M S
# 3 - Current Test Item - 0 - CC 1 - Lux 2 - Red 3 - Green  4 - Blue
# 4 - Current Test Direction  0 >=   1 <=
# 5 - IP Address of Swarm


for i in range(0,SWARMSIZE):
	swarmStatus[i][0] = "NP"
	swarmStatus[i][5] = 0


#300 seconds round
seconds_300_round = time.time() + 300.0

#120 seconds round
seconds_120_round = time.time() + 120.0

last_light_update_time = time.time()
completeCommand() 

flash_state = False
times = 0
blink_pin = 0
ledDict = {40: 0, 38 : 0, 36 : 0}
GPIO.setmode(GPIO.BOARD)
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setwarnings(False)
GPIO.add_event_detect(button_pin, GPIO.FALLING, callback=button_pressed_callback, bouncetime=100)
#bouncetime ensure callback is triggered once in 100ms
signal.signal(signal.SIGINT, signal_handler)
initialized = False
while(1) :
    d = s.recvfrom(1024)
    message = d[0]
    addr = d[1]
    if (len(message) == 14):
        if (message[1] == LIGHT_UPDATE_PACKET):
            incomingSwarmID = setAndReturnSwarmID((message[2]))
            swarmStatus[incomingSwarmID][0] = "P"
            swarmStatus[incomingSwarmID][1] = time.time()  
            print("in LIGHT_UPDATE_PACKET")
            print("received from addr:",addr)
            if message[2] not in list(ledDict.values()):
                print(message[2])
                print(list(ledDict.values()))
                SendDEFINE_SERVER_LOGGER_PACKET(s)    	
        if ((message[1]) == RESET_SWARM_PACKET):
            print("Swarm RESET_SWARM_PACKET Received")
            print("received from addr:",addr)	
    else:
        if ((message[1]) == LOG_TO_SERVER_PACKET):
            print("Swarm LOG_TO_SERVER_PACKET Received")
            # process the Log Packet
            logString= parseLogPacket(message)
            swarmNum = buildWebMapToFile(logString, SWARMSIZE )
            masterSwarmNum,ledDict = assignPin(swarmNum,ledDict)
            times, blink_pin,ledDict = change_rgb(current_value,masterSwarmNum,ledDict)
            flash_led(times,blink_pin)
            line,bar,i,axs = update_graphs(line,bar,i,ledDict,axs)
        elif((message[1])== LOG_DATA_PACKET):
            print("My LOG_DATA_PACKET Received")
        else:
            print("error message length = ",len(message))
            print(message)
    matrix(sliding_window)
    for i, digit in enumerate(ip_address):
        elect_digital_display((i+1)%4-1)
        write_data(num[digit])
        time.sleep(0.1)
        write_data(0xff)

    if not initialized:
        initialized,line,bar,i,axs = init_graph(initialized)
    if (time.time() >  seconds_120_round):
        # do our 2 minute round
        print(">>>>doing 120 second task")
        sendTo = random.randint(0,SWARMSIZE-1)
        SendBLINK_BRIGHT_LED(s, sendTo, 1)
        seconds_120_round = time.time() + 120.0	

    if (time.time() >  seconds_300_round):
        # do our 2 minute round
        print(">>>>doing 300 second task")
        SendDEFINE_SERVER_LOGGER_PACKET(s)
        seconds_300_round = time.time() + 300.0	
signal.pause()
