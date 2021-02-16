audio-offset-finder
===================

A simple tool for finding the offset of an audio file within another
file. 

Uses cross-correlation of standardized Mel-Frequency Cepstral Coefficients,
so should be relatively robust to noise (encoding, compression, etc).

It uses ffmpeg for transcoding, so should work on all file formats
supported by ffmpeg.

It was updated from the BBC code because the MFCC's performed poorly. We use
`librosa` now and whole raft of MIR features to do the correlation.

The program will remix to generate a synced new video by default, you can
disable it with the `--not-generate` flag

You may shoot multiple videos during one audio recording, so you can sync 
multiple videos to one audio in one command. 

Installation
------------

    $ pip3 install --user git+https://github.com/abramhindle/audio-offset-finder.git

Usage
-----

There are two kinds of usage

#### Command line usage

```
$ audio-offset-finder audio.wav video1.mp4 video2.mkv video3.avi
```

    $ audio-offset-finder --help
    usage: audio-offset-finder [-h] [--version] [--offset Minutes]
                               [--trim Minutes] [--sr SampleRate]
                               [--format Format] [--not-generate]
                               [--plotit]
                               Audio Video [Video ...]
    
    Purpose： Get the offset of a video sound to another audio, and
    replace the audio. Example: Record vlog, use a recorder for better
    sound, then sync the audio.
    
    positional arguments:
      Audio             Offset to find within
      Video             Video to find the offset of（Can be more than
                        one）
    
    optional arguments:
      -h, --help        show this help message and exit
      --version         show program's version number and exit
      --offset Minutes  Neglect how many minutes of the audio (in case
                        your audio is very long) (default: 0)
      --trim Minutes    Using how many minutes of audio as one clip to
                        analyse with (default: 15)
      --sr SampleRate   When resample audio, what the target sample rate
                        should be (default: 16000)
      --format Format   Output audio format such as: mp4, mkv (default:
                        mp4)
      --not-generate    Do not use FFmpeg to generate new video
                        (default: False)
      --plotit          Show the plot picture of the analyse (default:
                        False)

#### Text guide usage

```
$ audio-offset-finder

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


First input the audio（scope）
Please input the file path or drag it in: audio.aac

Then input the video（target）
Please input the file path or drag it in: child.mp4

Total task count: 1, processing No.1 : child.mp4

The offset calculated is: 5.9889154800422
The score is: 33.88101201927532
    (Score higher than 8 is considered qualified.)
FFmpeg command：
    ffmpeg -y -hide_banner -i "child.mp4" -ss 599.9889154800422 -i "audio.aac" -map 0:v:0 -map 1:a:0  -c:v copy -shortest "child.mp4.sync.5.99.mp4"

......

Mission complete, enter to finish
```




Testing
-------

    $ nosetests

Currently broken 

Licensing terms and authorship
------------------------------

See 'COPYING' and 'AUTHORS' files.

The audio file used in the tests was downloaded from
[Wikimedia Commons](http://en.wikipedia.org/wiki/File:Tim_Berners-Lee_-_Today_-_9_July_2008.flac),
and was originally extracted from the 9 July 2008 
episode of the BBC [Today programme](http://www.bbc.co.uk/programmes/b00cddwc).
