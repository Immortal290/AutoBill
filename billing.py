#!/usr/bin/env python

#!/usr/bin/env python

import cv2
import os
import sys
import getopt
import signal
import time
from edge_impulse_linux.image import ImageImpulseRunner

import RPi.GPIO as GPIO 
from hx711 import HX711

import requests
import json
from requests.structures import CaseInsensitiveDict

runner = None
show_camera = True

c_value = 0
flag = 0
ratio = -1363.992

global id_product
id_product = 1
list_label = []
list_weight = []
count = 0
final_weight = 0
taken = 0

# Product names (constants)
a = 'Apple'
b = 'Banana'
l = 'Lays'
c = 'Coke'

def now():
    return round(time.time() * 1000)

def get_webcams():
    port_ids = []
    for port in range(5):
        print(f"Looking for a camera in port {port}:")
        camera = cv2.VideoCapture(port)
        if camera.isOpened():
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = int(camera.get(3))
                h = int(camera.get(4))
                print(f"Camera {backendName} ({h} x {w}) found in port {port}")
                port_ids.append(port)
            camera.release()
    return port_ids

def sigint_handler(sig, frame):
    print('Interrupted')
    global runner
    if runner:
        runner.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

def help():
    print('Usage: python classify.py <path_to_model.eim> [Camera port ID if multiple cameras]')

def find_weight():
    global c_value
    global hx
    if c_value == 0:
        print('Calibration starts')
        try:
            GPIO.setmode(GPIO.BCM)
            hx = HX711(dout_pin=20, pd_sck_pin=21)
            err = hx.zero()
            if err:
                raise ValueError('Tare is unsuccessful.')
            hx.set_scale_ratio(ratio)
            c_value = 1
            print('Calibration done')
        except (KeyboardInterrupt, SystemExit):
            print('Bye :)')
            sys.exit(0)
    else:
        try:
            weight = int(hx.get_weight_mean(20))
            print(weight, 'g')
            return weight
        except (KeyboardInterrupt, SystemExit):
            print('Bye :)')
            sys.exit(0)
        except Exception as e:
            print(f"Error reading weight: {e}")
            return 0

def post(label, price, final_rate, taken):
    global id_product
    url = "https://autobill-4.onrender.com"  # Changed to Render URL
    headers = CaseInsensitiveDict()
    headers["Content-Type"] = "application/json"
    data_dict = {
        "id": id_product,
        "name": label,
        "price": price,
        "units": "units",
        "taken": taken,
        "payable": final_rate
    }
    data = json.dumps(data_dict)
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=5)
        print(f"POST response code: {resp.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to post data: {e}")
    id_product += 1  # increment after post

def list_com(label, final_weight):
    global count, taken, list_weight, list_label
    if final_weight > 2:
        list_weight.append(final_weight)
        if count > 1 and list_weight[-1] > list_weight[-2]:
            taken += 1
    list_label.append(label)
    count += 1
    print('count is', count)
    time.sleep(1)
    if count > 1:
        if list_label[-1] != list_label[-2]:
            print("New Item detected")
            print("Final weight is", list_weight[-1])
            rate(list_weight[-2], list_label[-2], taken)

def rate(final_weight, label, taken):
    print("Calculating rate")
    if label == a:
        print(f"Calculating rate of {label}")
        final_rate_a = final_weight * 0.01
        price = 10
        post(label, price, final_rate_a, taken)
    elif label == b:
        print(f"Calculating rate of {label}")
        final_rate_b = final_weight * 0.02
        price = 20
        post(label, price, final_rate_b, taken)
    elif label == l:
        print(f"Calculating rate of {label}")
        final_rate_l = 1
        price = 1
        post(label, price, final_rate_l, taken)
    else:
        print(f"Calculating rate of {label}")
        final_rate_c = 2
        price = 2
        post(label, price, final_rate_c, taken)

def main(argv):
    global flag, final_weight
    if flag == 0:
        find_weight()
        flag = 1

    try:
        opts, args = getopt.getopt(argv, "h", ["--help"])
    except getopt.GetoptError:
        help()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help()
            sys.exit()

    if len(args) == 0:
        help()
        sys.exit(2)

    model = args[0]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    print('MODEL: ' + modelfile)

    global runner
    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print(f'Loaded runner for "{model_info["project"]["owner"]} / {model_info["project"]["name"]}"')
            labels = model_info['model_parameters']['labels']
            if len(args) >= 2:
                videoCaptureDeviceId = int(args[1])
            else:
                port_ids = get_webcams()
                if len(port_ids) == 0:
                    raise Exception('Cannot find any webcams')
                if len(args) <= 1 and len(port_ids) > 1:
                    raise Exception("Multiple cameras found. Add the camera port ID as a second argument.")
                videoCaptureDeviceId = int(port_ids[0])

            camera = cv2.VideoCapture(videoCaptureDeviceId)
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print(f"Camera {backendName} ({h} x {w}) in port {videoCaptureDeviceId} selected.")
                camera.release()
            else:
                raise Exception("Couldn't initialize selected camera.")

            next_frame = 0  # limit to ~10 fps

            for res, img in runner.classifier(videoCaptureDeviceId):
                if next_frame > now():
                    time.sleep((next_frame - now()) / 1000)

                if "classification" in res["result"]:
                    print(f'Result ({res["timing"]["dsp"] + res["timing"]["classification"]} ms.) ', end='')
                    for label in labels:
                        score = res['result']['classification'][label]
                        if score > 0.9:
                            final_weight = find_weight()
                            list_com(label, final_weight)
                            if label == a:
                                print('Apple detected')
                            elif label == b:
                                print('Banana detected')
                            elif label == l:
                                print('Lays detected')
                            else:
                                print('Coke detected')
                    print('', flush=True)
                next_frame = now() + 100

        finally:
            if runner:
                runner.stop()

if __name__ == "__main__":
    main(sys.argv[1:])
