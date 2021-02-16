#!/usr/bin/python
#-*- coding: utf-8 -*-

# audio-offset-finder
#
# Copyright (c) 2014 British Broadcasting Corporation
# Copyright (c) 2018 Abram Hindle
# Copyright (c) 2021 Haujet Zhao
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse, sys, os, shlex, subprocess
from .audio_offset_finder import find_offset

def main():
    not_exit_immediately = False
    if len(sys.argv) == 1:
        not_exit_immediately = True

        print(f'''
You haven't pass any audio or video files. 
So this short message shall guide you.

This program is used to replace the audio of a video to
another audio recordered in another device, such as:

  * Using a camera to record a video
  * Carry a audio recorder or phone to record a better quality audio
  * Replace the camera audio the the higher quality audio automaticlly

The audio is normally considered longer than the video.
So this process can be thought as:
    Find the offset of video sound (target) in another better quality
audio file (scope), and replace the video sound automaticlly. 
''')
        print(f'\nFirst input the audio（scope）')
        sys.argv.append(get_input_file())

        print(f'\nThen input the video（target）')
        sys.argv.append(get_input_file())


    parser = argparse.ArgumentParser(
        description='''Purpose：    Get the offset of a video sound to another audio, and replace the audio. 
                       Example:     Record vlog, use a recorder for better sound, then sync the audio. ''',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('Audio', type=str, help='Offset to find within')
    parser.add_argument('Video', nargs='+',  type=str, help='Video to find the offset of（Can be more than one）')

    parser.add_argument('--version', action='version', version='%(prog)s 1.0')
    parser.add_argument('--offset', metavar='Minutes', type=int, default=0, help='Neglect how many minutes of the audio (in case your audio is very long)')
    parser.add_argument('--trim', metavar='Minutes', type=int, default=15, help='Using how many minutes of audio as one clip to analyse with')
    parser.add_argument('--sr', metavar='SampleRate', type=int, default=16000, help='When resample audio, what the target sample rate should be')
    parser.add_argument('--format', metavar='Format', type=str, default='mp4', help='Output audio format such as: mp4, mkv')
    parser.add_argument('--not-generate',action='store_true', help='Do not use FFmpeg to generate new video')
    parser.add_argument('--plotit',action='store_true', help='Show the plot picture of the analyse')

    args = parser.parse_args()

    slice_seconds = args.trim * 60
    pre_offset_seconds = args.offset * 60
    for index, video in enumerate(args.Video):
        print(f'\nTotal task count: {len(args.Video)}, processing No.{index + 1} : {video}')
        sync(args.Audio, video, pre_offset_seconds, slice_seconds, args.sr, args.format, args.not_generate, args.plotit)

    if not_exit_immediately:
        input('\nMission complete, enter to finish')

def get_input_file():
    while True:
        user_input = input(f'Please input the file path or drag it in: ')
        if user_input == '':
            continue
        if os.path.exists(user_input.strip('\'"')):
            input_file = user_input.strip('\'"')
            break
        else:
            print('The file you input does not exitst, please retry. ')
    return input_file

def sync(within, find_offset_of, offset, trim, sr, format, not_generate, plotit):
    
    for file in [within, find_offset_of]:
        if not os.path.exists(file):
            print(f'File do not exist, skip: {file}')
            return False

    offset, score = find_offset(within, find_offset_of, offset, sr, trim, plotit=plotit)

    # ffmpeg command
    if offset >= 0:
        ffmpeg_cmd = f'''ffmpeg -y -hide_banner -i "{find_offset_of}" -ss {offset} -i "{within}" -map 0:v:0 -map 1:a:0  -c:v copy -shortest "{find_offset_of}.sync.{"{:.2f}".format(offset)}.{format}"'''
    else:
        delay = int(abs(offset) * 1000)
        ffmpeg_cmd = f'''ffmpeg -y -hide_banner -i "{find_offset_of}" -i "{within}" -map 0:v:0 -map 1:a:0 -c:v copy -af "adelay=delays={delay}:all=1" -shortest "{find_offset_of}.sync.{"{:.2f}".format(offset)}.{format}"'''
    print(f'FFmpeg command：\n    {ffmpeg_cmd}\n')

    # Generate new video
    if not not_generate:
        command_arg = shlex.split(ffmpeg_cmd)
        subprocess.run(command_arg)

if __name__ == '__main__':
    main()
