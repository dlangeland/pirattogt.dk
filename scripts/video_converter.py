import argparse
import logging
import os
from subprocess import CalledProcessError
import subprocess


logging.basicConfig(format='%(levelname)0.1s:%(message)s', level=logging.DEBUG)
log = logging.getLogger('')


# ffmpeg -async 1 -i 00001.h264 -i 00001.wav -vcodec copy -af "volume=30, highpass=f=200, lowpass=f=3000" out.mp4
parser = argparse.ArgumentParser(description='Mux .h264 video and .wav audio files Raspberry to .mp4 than can be processed or viewed elsewhere')
parser.add_argument('--path', '-p', dest='path', action='store', default='.', help='path containing files (default: current folder)')
parser.add_argument('--operation', '-o', dest='operation', action='store', default='1', help='1) Mux video and audio 2a) Concat timelapse videos 2b) Reencode concatenated video')


args = parser.parse_args()

if not os.path.exists(args.path):
    log.critical('Wrong path - such noobz: %s', args.path)
    exit(-1)

# TODO: Check for ffmpeg
abs_path = os.path.abspath(args.path)
log.debug('Path exists: %s', abs_path)
conv_count = 0

if args.operation == '1':
    for dirpath, dirnames, filenames in os.walk(abs_path):
        log.debug('Processing: %s, %s, %s', dirpath, dirnames, filenames)
        for file in filenames:
            if file.endswith('.h264'):
                #basefile = os.path.basename(file)
                basefile = dirpath + os.sep + file.replace('.h264', '')
                log.debug(basefile)
                
                if os.path.exists(basefile + '.wav'):
                    log.info('Muxing %s', dirpath + os.path.sep + file)
                    cmd = 'ffmpeg -y -async 25 -i ' + basefile + '.h264 -i ' + basefile + '.wav -vcodec copy -af "volume=5, highpass=f=200, lowpass=f=3000" -r 25 ' + basefile + '.mp4'
                    log.debug(cmd)
                    try:
                        out = subprocess.check_output(cmd)
                        conv_count += 1
                        log.info('Muxing complete!')
                    except CalledProcessError as err:
                        log.error('Conversion failed: %s', str(err))

if args.operation == '2a' or args.operation == '2b':
    for dirpath, dirnames, filenames in os.walk(abs_path):
        log.debug('Processing: %s, %s, %s', dirpath, dirnames, filenames)
        with open(dirpath + os.path.sep + 'out.h264', 'wb') as out_file:
            for file in filenames:
                if file.endswith('.h264'):
                    with open(dirpath + os.path.sep + file, 'rb') as in_file:
                        out_file.write(in_file.read())
                    #filelist.write('file \'' + dirpath + os.sep + file + '\'\n')
                    conv_count += 1

        if conv_count > 0 and args.operation == '2b':
            log.info('Converting file')
            cmd = 'ffmpeg -y -i ' + dirpath + os.path.sep + 'out.h264' + ' -vcodec copy ' + dirpath + os.sep + 'output.mp4' #libx264
            log.debug(cmd)
            try:
                out = subprocess.check_output(cmd)
                conv_count += 1
                log.info('Concat complete!')
            except CalledProcessError as err:
                log.error('Conversion failed: %s', str(err))
     
log.info('Processed %s file(s)!', conv_count)
