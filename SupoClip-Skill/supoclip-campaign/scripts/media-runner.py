"""Run packaged media helpers in an existing SupoClip backend image."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--image', default='supoclip-backend')
    parser.add_argument('--python-in-image', default='/app/.venv/bin/python')
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == '--' else args.command
    if not command or command[0] not in {'render.py', 'benchmark-threads.py'}:
        parser.error('Choose render.py or benchmark-threads.py after --')
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir() or ',' in str(root):
        parser.error('Working root must be a directory without commas')
    scripts = Path(__file__).resolve().parent
    if shutil.which('ffmpeg') and shutil.which('ffprobe'):
        translated = [str(root / arg[6:]) if arg.startswith('/work/') else arg for arg in command[1:]]
        return subprocess.call([sys.executable, str(scripts / command[0]), *translated])
    if not shutil.which('docker'):
        parser.error('Use FFmpeg/FFprobe or the installed Docker runtime')
    docker = ['docker', 'run', '--rm', '--network', 'none']
    if args.gpu:
        docker += ['--gpus', 'all']
    docker += ['--mount', f'type=bind,source={scripts},target=/skill,readonly',
               '--mount', f'type=bind,source={root},target=/work',
               '--entrypoint', args.python_in_image, args.image,
               '-I', '/skill/' + command[0], *command[1:]]
    return subprocess.call(docker)


if __name__ == '__main__':
    raise SystemExit(main())
