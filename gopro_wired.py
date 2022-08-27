import requests
import re
import time
import os
from urllib.request import urlretrieve
import subprocess

def cmd(command):
    response = (
            subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)  # type: ignore
            .stdout.read()
            .decode(errors="ignore")
    )
    return response


class GoProWiredClient:

    resolution_options_reversed = {1:"4K",4:"2.7K",6:"2.7K4:3",7:"1440",9:"1080p",18:"4K4:3",24:"5K",25:"5K4:3",100:"5.3K"}
    resolution_options = {value: key for key, value in resolution_options_reversed.items()}
    
    fps_options_reversed = {0:"240",1:"120",5:"60",8:"30",10:"24",13:"200"}
    fps_options = {value: key for key, value in fps_options_reversed.items()}

    def __init__(self) -> None:
        self.gopro_url = ""
        self.media_list = []
        self.connect()

    def connect(self):
        while True:
            response = cmd("ifconfig | grep 172.")
            gopro_found = re.search('172\.2[0-9]\.1[0-9][0-9].5[0-9]', response)
            if  gopro_found:
                pattern_start = gopro_found.start()
                pattern_end = gopro_found.end()
                gopro_ip = response[pattern_start:pattern_end]
                x = gopro_ip[5]
                yz = gopro_ip[8:10]
    
                self.gopro_url = f"http://172.2{x}.1{yz}.51/"
                    
                #Turning on wired control
                self.make_request("gopro/camera/control/wired_usb?p=0")
                self.make_request("gopro/camera/control/wired_usb?p=1")
                self.make_request("gopro/camera/shutter/stop")
                self.media_list, _ = self.pull_media_list()
                self.connected = True
                print("GoPro connected")
                break
            time.sleep(1)
            print("Gopro is not connected, trying again")


    def make_request(self,command):
        try:
            result = requests.get(self.gopro_url+command, timeout=5)
            #print(self.gopro_url+command)
            return True, result
        except Exception as e:
            print(e)
            return False, None

    def set_resolution(self,resolution):
        resolution_option = self.resolution_options[resolution]
        self.make_request(f"gopro/camera/setting?setting=2&option={resolution_option}")

    def set_fps(self,fps):
        fps_option = self.fps_options[fps]
        self.make_request(f"gopro/camera/setting?setting=3&option={fps_option}")
    
    def get_settings(self):
        settings = {}

        while True:
            ret, response = self.make_request("gopro/camera/state")
            response_json = response.json()
            if "settings" in response_json:
                break

        resolution_option = response_json['settings']['2']
        if resolution_option in self.resolution_options_reversed:
            settings['resolution'] = self.resolution_options_reversed[resolution_option]
        else:
            settings['resolution'] = 'unknown'
        fps_option = response_json['settings']['3']
        if fps_option in self.fps_options_reversed:
            settings['fps'] = self.fps_options_reversed[fps_option]
        else:
            settings['fps'] = 'unknown'
        settings['system_hot'] = int(response_json['status']['6']) # if gopro is overheated
        settings['encoding'] = int(response_json['status']['10']) # if gopro is recording at the moment
        settings['busy'] = int(response_json['status']['8']) # if gopro is not ready to record
        # to parse more settings, look here: https://gopro.github.io/OpenGoPro/http_2_0#settings
        return settings

    def pull_media_list(self):
        """
        Returns:
        - current list of medias on the gopro
        - new medias since last method call
        """

        #try to get media list, untril response looks correct. (reponse can be 'camera busy',
        # because we usually call this method right after the recording and gopro may be not ready yet)
        while True:
            ret, response = self.make_request("gopro/media/list")
            raw_media_list = response.json()
            if "media" in raw_media_list:
                break
        new_media_list = [(x["n"], x["cre"]) for x in raw_media_list["media"][0]["fs"]]
        
        new_medias = []
        for media in new_media_list:
            filename, _ = media
            if filename not in self.media_list:
                new_medias.append(media)

        new_filenames = []
        #if more than one chapter was recorded, then sort them by creation date
        if len(new_medias)>1:
            new_medias = sorted(new_medias, key=lambda x: x[1])
        for media in new_medias:
            new_filenames.append(media[0])
       
        media_list  = [x[0] for x in new_media_list]

        return media_list, new_filenames

    def record_clip(self, duration):
        """
        Input:
        - duration in seconds
        Return:
        - path to the recorded file(s) on the Gopro
        """
        self.make_request("gopro/camera/shutter/start")
        time.sleep(duration)
        self.make_request("gopro/camera/shutter/stop")
        self.media_list, new_filenames = self.pull_media_list()
        return new_filenames
    
    def download_file(self, filename, out_dir="."):
        out_file = os.path.join(out_dir,filename)
        src = self.gopro_url+"videos/DCIM/100GOPRO/" + filename
        try:
            urlretrieve(src, out_file)
            return True
        except Exception as e:
            return False

if __name__=="__main__":
    
    gopro_client = GoProWiredClient()
    gopro_client.set_resolution("4K")
    gopro_client.set_fps("120")
    print(gopro_client.get_settings())

    print("Recording a 5 sec clip")
    clips = gopro_client.record_clip(5)
    print("Downloading recorded clip")
    for clip in clips:
        gopro_client.download_file(clip)
        print("{} downloaded".format(clip))

    
