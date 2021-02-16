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

from subprocess import Popen, PIPE
from scipy.io import wavfile
# from scikits.talkbox.features.mfcc import mfcc
import matplotlib.pyplot as plt
import librosa
import os, tempfile, warnings, math
import numpy as np
import shlex

def mfcc(audio_file, nwin=256, n_fft=512, sr=16000, n_mfcc=20):
    return [np.transpose(librosa.feature.mfcc(y=audio_file, sr=sr, n_fft=n_fft, win_length=nwin, n_mfcc=n_mfcc))]

def add_feature(mfcc1, rmsa1):
    tmfcc1 = np.zeros((mfcc1.shape[0],mfcc1.shape[1]+rmsa1.shape[0]))
    n = mfcc1.shape[0]
    m = mfcc1.shape[1]
    w = rmsa1.shape[0]
    tmfcc1[0:n,0:m] = mfcc1[0:n,0:m]
    tmfcc1[0:n,m:m+w]   = np.transpose(rmsa1[0:w,0:n])
    return tmfcc1

def get_audio(file, sr=16000):

    # Removing warnings because of 18 bits block size
    # outputted by ffmpeg
    # https://trac.ffmpeg.org/ticket/1843
    warnings.simplefilter("ignore", wavfile.WavFileWarning)

    a = wavfile.read(file, mmap=False)[1] / (2.0 ** 15)
    # print(f"Find samples: {a.shape[0]}")

    # We truncate zeroes off the beginning of each signals
    # (only seems to happen in ffmpeg, not in sox)
    a = ensure_non_zero(a)

    mfcca = mfcc(a, nwin=256, n_fft=512, sr=sr, n_mfcc=26)[0]
    mfcca = std_mfcc(mfcca)
    rmsa = librosa.feature.rms(a)
    cent = librosa.feature.spectral_centroid(y=a, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=a, sr=sr, roll_percent=0.1)

    chroma_cq = librosa.feature.chroma_cqt(y=a, sr=sr, n_chroma=12)


    onset_env = librosa.onset.onset_strength(y=a, sr=sr, n_mels=int(sr / 800))
    pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)

    mfcca = add_feature(mfcca, rmsa)
    mfcca = add_feature(mfcca, rolloff / sr)
    mfcca = add_feature(mfcca, cent / sr)
    mfcca = add_feature(mfcca, chroma_cq)
    mfcca = add_feature(mfcca, onset_env.reshape(1, onset_env.shape[0]))
    mfcca = add_feature(mfcca, pulse.reshape(1, onset_env.shape[0]))

    return file, mfcca, a, rmsa

def find_offset(scope, target, pre_offset=0, sr=16000, trim=60 * 15, correl_nframes=1000, plotit=True):

    # 子音频在母音频中找偏移值
    # Here, we call the scope-audio as mother-audio,
    # and the target-audio as child-audio,
    # easier to understand the relationship of these two audios.

    mother = convert_and_trim(scope, sr, trim=None, offset=pre_offset)
    mother_data = wavfile.read(mother, mmap=True)[1]
    mother_data_length = len(mother_data)

    child = convert_and_trim(target, sr, trim, offset=0)
    child_data = wavfile.read(child, mmap=True)[1]
    child_data_length = len(child_data)
    child_duration = child_data_length / sr
    del child_data

    # 不能从子音频的第一帧开始取片段进行分析
    # 因为录制者有可能先按下了录像开关，然后过了几秒钟才按下录音笔开关
    # 所以要对采样的起始点添加一个偏移
    # We shouldn't analyse from the first audio frame of the audio 2
    # because the user may first pressed the Camera recording button
    # and after few seconds, the Audio Recorder button is pressed then.
    # So we make a pre-shift to the audio2, analysing a not-to-close-to-begining audio clip.
    # If the child audio is shorter than 9min, it's 1/3 point is where the first analysing-frame sets.
    # If the child audio is longer than 9 min, the 3min point is where the first analysing-frame sets.

    child_pre_offset = min(child_duration * 1 / 3, 3 * 60)
    child = convert_and_trim(target, sr, trim, offset=child_pre_offset)

    unit_clip_data_length = trim * sr
    unit_numbers = math.ceil(mother_data_length / unit_clip_data_length)

    clip_tmp = tempfile.NamedTemporaryFile(mode='r+b', prefix='offset_clip_', suffix='.wav')
    clip_tmp_name = clip_tmp.name
    clip_tmp.close()

    # 如果我们将要分析的片段长度设为15分钟，但是音频视频都比较长
    # 如果偏移时间过长，例如30分钟，我们就可能分析不到
    # 所以要将母音频分成15分钟一段（并再向前位移 1 分钟），依次分析
    # 直到得到合格的分数
    # Suppose we set the trim to 15min
    # The former BBC solution can only analyse the first 15min of the mother audio
    # But if the audio and video are very long,
    # the actual offset may be longer than 15min, say: 30min.
    # In this circumstance, we may not be able to get the correct offset.
    # So, it is needed to cut the mother audio into slices, whose length is 15min
    # with a pre-offset of 60s.
    # Then we compare the child frames to the mother-clips one by one, until we get
    # a qualified score.
    passing_score = 8
    hightst_score = 0
    total_offset = pre_offset
    new_clip_pre_offset = 0

    for i in range(unit_numbers):
        start = i * unit_clip_data_length

        # 新的一段和前的一段需要有60秒的重叠，以保证实际的偏移发生在切点时可以被检测到
        # The child frames is considered shorter than 60s.
        # If the actual offset is 14:45, and the trim is 15min
        # We the first and second clips may both won't get the offset
        # So we need a 60s overlay between the first and second clips.
        if i > 0:
            new_clip_pre_offset = 60
            start -= new_clip_pre_offset * sr

        end = min(i * unit_clip_data_length + unit_clip_data_length, mother_data_length - 1)

        wavfile.write(clip_tmp_name, sr, mother_data[start:end])

        audio1 = get_audio(clip_tmp_name, sr)
        audio2 = get_audio(child, sr)

        offset, score, c = find_clip_offset(audio1, audio2, sr)
        if score > hightst_score:
            hightst_score = score
            total_offset = i * trim + pre_offset + offset - child_pre_offset - new_clip_pre_offset
        if score > passing_score:
            break

    print(f'The offset calculated is: {total_offset}\nThe score is: {hightst_score}\n    (Score higher than {passing_score} is considered qualified.)')

    # 显示具体分数的图表
    # Show the plot
    if plotit:
        plt.figure(figsize=(8, 4))
        plt.plot(c)
        plt.show()

    return total_offset, hightst_score


def find_clip_offset(audio1, audio2, fs=16000, correl_nframes=1000):

    file1, mfcc1, a1, rmsa1 = audio1
    file2, mfcc2, a2, rmsa2 = audio2

    c = cross_correlation(mfcc1, mfcc2, nframes=correl_nframes)
    max_k_index = np.argmax(c)

    # # The MFCC window overlap is hardcoded in scikits.talkbox
    # # offset = max_k_index * 160.0 / float(fs) # * over / sample rate
    offset = max_k_index * (a1.shape[0]/rmsa1.shape[1]) / float(fs) # * over / sample rate
    score = (c[max_k_index] - np.mean(c)) / np.std(c) # standard score of peak

    return offset, score, c

def ensure_non_zero(signal):
    # We add a little bit of static to avoid
    # 'divide by zero encountered in log'
    # during MFCC computation
    signal += np.random.random(len(signal)) * 10**-10
    return signal

def make_similar_shape(mfcc1,mfcc2):
    n1, mdim1 = mfcc1.shape
    n2, mdim2 = mfcc2.shape
    # print((nframes,(n1,mdim1),(n2,mdim2)))
    if (n2 < n1):
        t = np.zeros((n1,mdim2))
        t[0:n2,0:mdim2] = mfcc2[0:n2,0:mdim2]
        mfcc2 = t
    elif (n2 > n1):
        return make_similar_shape(mfcc2,mfcc1)
    return (mfcc1,mfcc2)

def cross_correlation(mfcc1, mfcc2, nframes):
    n1, mdim1 = mfcc1.shape
    n2, mdim2 = mfcc2.shape
    # print((nframes,(n1,mdim1),(n2,mdim2)))
    if (n2 < nframes):
        t = np.zeros((nframes,mdim2))
        t[0:n2,0:mdim2] = mfcc2[0:n2,0:mdim2]
        mfcc2 = t
    n = n1 - nframes + 1
    #c = np.zeros(min(n2,n))
    c = np.zeros(n)
    #for k in range(min(n2,n)):
    for k in range(n):
        cc = np.sum(np.multiply(mfcc1[k:k+nframes], mfcc2[:nframes]), axis=0)
        c[k] = np.linalg.norm(cc,1)
    return c

def std_mfcc(mfcc):
    return (mfcc - np.mean(mfcc, axis=0)) / np.std(mfcc, axis=0)

def convert_and_trim(afile, sr, trim, offset=0):
    tmp = tempfile.NamedTemporaryFile(mode='r+b', prefix='offset_', suffix='.wav')
    tmp_name = tmp.name
    tmp.close()

    if not trim:
        command = f'ffmpeg -loglevel panic -i "{afile}" -ac 1 -ar {sr} -ss {offset} -vn -c:a pcm_s16le "{tmp_name}"'
    else:
        command = f'ffmpeg -loglevel panic -i "{afile}" -ac 1 -ar {sr} -ss {offset} -t {trim} -vn -c:a pcm_s16le "{tmp_name}"'
    command = shlex.split(command)

    psox = Popen(command, stderr=PIPE)
    psox.communicate()

    if not psox.returncode == 0:
        raise Exception("FFMpeg failed")

    return tmp_name
