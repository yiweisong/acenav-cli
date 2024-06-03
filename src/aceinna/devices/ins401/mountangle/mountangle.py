import os
import sys
import time
import json
import datetime
import platform
import threading
import math
import logging
#import matplotlib.pyplot as plt
import numpy as np
from numpy.core.defchararray import count
from ...ins401.mountangle.drivestatus import DriveStatus
import copy
from ctypes import *

#if os.name == 'nt':
#    from win32api import FreeLibrary

class MountAngle:
    def __init__(self, executor_path, data_path, process_file):

        self.executor_path = executor_path
        self.data_path = data_path
        self.process_file = process_file

        self.ins_postconfig_filename = None

        self.mountangle_logger = None

        self.drivestatus = DriveStatus()
        self.last_drive_res = None
        self.runstatus_mountangle = 0
        self.mountangle_result = []
        self.mountangle_estimate_result = []
        self.out_result_flag = 0

        self.stop = 0
        self.mountangle_thread_handle = None

        local_time = time.localtime()
        formatted_dir_time = time.strftime("%Y%m%d_%H%M%S", local_time)
        formatted_file_time = time.strftime("%Y_%m_%d_%H_%M_%S", local_time)

        # create file logging and console logging for this module
        self.mountangle_logger = logging.getLogger(__file__)
        self.mountangle_logger.setLevel(logging.DEBUG)
        self.mountangle_logger.propagate = False
        if not self.mountangle_logger.handlers:
            logfile = os.path.join(self.data_path, 'mountangle_logger_{0}.txt'.format(formatted_file_time))
            fh = logging.FileHandler(logfile, mode='w')
            fh.setLevel(logging.DEBUG)

            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            self.mountangle_logger.addHandler(fh)
            self.mountangle_logger.addHandler(ch)
        
        self.mountangle_logger.info("[mountangle] module enable!")
        
    def close(self):
        self.stop = 1

    def mountangle_set_parameters(self, rvb = []):
        # postprocess config file in /mountangle/, user need to set configuration in this file
        # set process file in post config file
        if os.name == 'nt':
            file_path = os.path.join(self.executor_path, 'src\\aceinna\\devices\\ins401\\mountangle')
        else:
            file_path = os.path.join(self.executor_path, 'src/aceinna/devices/ins401/mountangle')

        self.ins_postconfig_filename = os.path.join(file_path, 'content_aceinna_config.txt')
        with open(self.ins_postconfig_filename, 'r') as postconfigfile:
            postconfig = json.load(postconfigfile)
        
            setting_folder_path = os.path.join(self.executor_path, 'setting')
            # Load the openimu.json based on its app
            product_name = 'INS401'
            app_name = 'RTK_INS'  # self.app_info['app_name']
            app_file_path = os.path.join(setting_folder_path, product_name,
                                            app_name, 'ins401.json')
            with open(app_file_path, 'r') as json_data:
                properties = json.load(json_data)
                # search paramId in device json file, search key is parameter name, don't change the parameter name in json file
                gnssLeverArm_paramId = next(
                    (x['paramId'] for x in properties['userConfiguration'] if x['name'] == 'gnss lever arm x'), None)
                vrpLeverArm_paramId = next(
                    (x['paramId'] for x in properties['userConfiguration'] if x['name'] == 'vrp lever arm x'), None)
                userLeverArm_paramId = next(
                    (x['paramId'] for x in properties['userConfiguration'] if x['name'] == 'user lever arm x'), None)
                #print('gnssLeverArm_paramId:', gnssLeverArm_paramId, 'vrpLeverArm_paramId:', vrpLeverArm_paramId, 'userLeverArm_paramId:', userLeverArm_paramId)
   
                # use parameter value in post config file
                for i in range(3):
                    postconfig['priLeverArm'][i] = properties["initial"]["userParameters"][gnssLeverArm_paramId - 1 + i]["value"]
                    postconfig['odoLeverarm'][i] = properties["initial"]["userParameters"][vrpLeverArm_paramId - 1 + i]["value"]
                    postconfig['userLeverArm'][i] = properties["initial"]["userParameters"][userLeverArm_paramId - 1 + i]["value"]

            postconfig['rotationRBV'] = rvb
            postconfig['procfileNme'] = self.process_file

        with open(self.ins_postconfig_filename, 'w') as postconfigfile:
            postconfigfile.seek(0)
            postconfigfile.truncate()
            json.dump(postconfig, postconfigfile, indent=4, ensure_ascii=False)
        self.mountangle_logger.debug("set postconfig filename {0} in {1}".format(self.process_file, self.ins_postconfig_filename))
        

    def mountangle_run(self):
        if self.mountangle_thread_handle is None:
            self.mountangle_logger.info('[mountangle] initial ok and can drive the car')
            self.mountangle_thread_handle = threading.Thread(target=self.mountangle_thread)
            self.mountangle_thread_handle.start()
        

    def mountangle_calc(self, starttime, endtime):
        starttime = format(starttime, '.0f')
        endtime = format(endtime, '.0f')

        # copy contents of libs file under executor path
        lib_folder_path = os.path.join(os.getcwd(),'libs')
        # self.mountangle_logger.info('[mountangle] calc {0} {1}'.format(starttime, endtime))

        # # call INS.exe to post process and out ima data file
        # if platform.system().lower() == 'windows':
        #     execmd = "INS.exe " + self.ins_postconfig_filename + " 0"
        # elif platform.system().lower() == 'linux':
        #     execmd = "INS " + self.ins_postconfig_filename + " 0"
        # self.mountangle_logger.debug('[mountangle] {0}'.format(execmd))
        # r_v = os.system(execmd)

        # # call DR_MountAngle.exe process ima data 
        # imainputfile = self.process_file + '_ins.txt'    # mountangle input file
        # if platform.system().lower() == 'windows':
        #     execmd = "DR_MountAngle.exe " + imainputfile + " " + starttime + " " + endtime
        # if platform.system().lower() == 'linux':
        #     execmd = "DR_MountAngle " + imainputfile + " " + starttime + " " + endtime
        # self.mountangle_logger.debug('[mountangle] {0}'.format(execmd))
        # r_v = os.system(execmd)

        INS_DLL = os.path.join(lib_folder_path,'INS.dll')
        CINSDLL = CDLL(INS_DLL)
        CINSDLL.ins_start(self.ins_postconfig_filename.encode('utf-8'), 0)
        r_v = execmd = "INS " + self.ins_postconfig_filename + " 0"
        self.mountangle_logger.debug('[mountangle] {0}'.format(execmd))
        FreeLibrary(CINSDLL._handle)

        imainputfile = self.process_file + '_ins.txt'    # mountangle input file
        Dr_MountAngle_DLL = os.path.join(lib_folder_path,'DR_MountAngle.dll')
        DRMADLL = CDLL(Dr_MountAngle_DLL)
        r_v = DRMADLL.dr_mountangle_start(imainputfile.encode('utf-8'), starttime.encode('utf-8'), endtime.encode('utf-8'))
        execmd = "DR_MountAngle " + imainputfile + " " + starttime + " " + endtime
        self.mountangle_logger.debug('[mountangle] {0}'.format(execmd))
        FreeLibrary(DRMADLL._handle)

        if r_v == 0:
            index = imainputfile.rfind('.')
            if index != -1:
                imainputfile = imainputfile[:index]
            # imaoutputfile = imainputfile + '_ima_' + format(line_starttime,'.0f') + '-' + format(line_endtime,'.0f') + '.txt'
            imaoutputfile = imainputfile + '_ima_{0}-{1}.txt'.format(starttime, endtime)
            f_ima = open(imaoutputfile, 'r')
            data = f_ima.readlines()
            for i in range(0, len(data)):
                data[i] = data[i].replace(',', '')
            ima_dataarray = np.loadtxt(data)    # ima_dataarray is the result data
            result = {
                "starttime" : starttime,
                "endtime" : endtime,
                "roll" : ima_dataarray[-1,5],
                "pitch" : ima_dataarray[-1,6],
                "heading" : ima_dataarray[-1,7]
            }
            self.mountangle_result.append(copy.deepcopy(result))

            self.mountangle_logger.info('[mountangle] temp result {0}'.format(result))

    def mountangle_thread(self):

        while True:
            time.sleep(0.01)
            if self.stop:
                return
            if self.runstatus_mountangle == 1:
                drive_res = self.drive_res
                self.runstatus_mountangle = 0

                if drive_res['type'] == 14: # 500m, about 20m/s
                    starttime = drive_res['starttime'] + 3
                    endtime = drive_res['curtime']
                    self.mountangle_calc(starttime, endtime)

                elif drive_res['type'] == 15: # 700m, about 20m/s
                    starttime = drive_res['starttime'] + 5
                    endtime = drive_res['curtime'] - 5
                    self.mountangle_calc(starttime, endtime)

                    starttime = drive_res['starttime'] + 3
                    endtime = drive_res['curtime']
                    self.mountangle_calc(starttime, endtime)
                
                res_num = len(self.mountangle_result)
                if len(self.mountangle_result) >= 3:
                    threshold = [0.3, 0.2, 0.2]
                    roll_ref = 0.0
                    pitch_ref = 0.0
                    heading_ref = 0.0
                    res_valid = []
                    for res in self.mountangle_result:
                        roll_ref = roll_ref + res['roll']
                        pitch_ref = pitch_ref + res['pitch']
                        heading_ref = heading_ref + res['heading']
                    roll_ref = roll_ref / res_num
                    pitch_ref = pitch_ref / res_num
                    heading_ref = heading_ref / res_num
                    for res in self.mountangle_result:
                        if ((abs(res['roll'] - roll_ref) < threshold[0]) and
                            (abs(res['pitch'] - pitch_ref) < threshold[1]) and
                            (abs(res['heading'] - heading_ref) < threshold[2])):
                            res_valid.append(copy.deepcopy(res))

                    if len(res_valid) >= 3:
                        roll = 0.0
                        pitch = 0.0
                        heading = 0.0
                        for res in res_valid:
                            roll = roll + res['roll']
                            pitch = pitch + res['pitch']
                            heading = heading + res['heading']
                        roll = roll / len(res_valid)
                        pitch = pitch / len(res_valid)
                        heading = heading / len(res_valid)

                        estimate_result = []
                        
                        estimate_result.append(roll) 
                        estimate_result.append(pitch) 
                        estimate_result.append(heading) 

                        self.mountangle_estimate_result = estimate_result 
                        self.out_result_flag = 1

                        self.mountangle_logger.info('[mountangle] calc result [roll:{0} pitch:{1} heading:{2}]'.format(roll, pitch, heading))
                        break

        pattern_result = self.drivestatus.getpatterns()
        self.mountangle_logger.debug("[mountangle] patterns:{0}".format(pattern_result))

        self.mountangle_logger.debug("[mountangle] result:{0}".format(self.mountangle_result))

        while True:
            time.sleep(5)
            if self.stop:
                return

    def process_live_data(self, data, type):
        self.drivestatus.addrawdata(data, type)
        drive_res = self.drivestatus.getresult()
        if drive_res != None:
            self.mountangle_logger.debug('{0} {1}'.format(data[1]/1000, drive_res))
            if self.runstatus_mountangle == 0:
                if (self.last_drive_res != None):
                    if ((self.last_drive_res['type'] == 13 and drive_res['type'] == 14) or 
                        (self.last_drive_res['type'] == 14 and drive_res['type'] == 15)):
                        self.drive_res = drive_res
                        self.runstatus_mountangle = 1
                        print('runstatus_mountangle:\n', self.runstatus_mountangle)
                        
                self.last_drive_res = copy.deepcopy(drive_res)
    
 