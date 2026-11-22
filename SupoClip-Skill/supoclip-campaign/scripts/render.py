"""Render one reviewed continuous campaign moment with one video encode."""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import textwrap
import time
from fractions import Fraction
from pathlib import Path


def load(file):
    return json.loads(Path(file).read_text(encoding='utf-8-sig'))


def run(command, cwd=None, timeout=None):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Media command failed: ' + result.stderr[-2400:])
    return result.stdout


def probe(file):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(file)]))


def ass_time(second):
    ticks = max(0, round(second * 100))
    return f'{ticks//360000}:{ticks//6000%60:02}:{ticks//100%60:02}.{ticks%100:02}'


def escape(text):
    return str(text).replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').replace('\n', '\\N')


def box(value, width, height):
    if not isinstance(value, list) or len(value) != 4 or any(type(v) is not int for v in value):
        raise ValueError('Layout boxes must have four integer coordinates')
    x, y, w, h = value
    if x < 0 or y < 0 or w < 2 or h < 2 or x+w > width or y+h > height or any(v % 2 for v in value):
        raise ValueError('Layout boxes must fit the canvas and use even coordinates')
    return x, y, w, h


def select_encoder(requested, threads):
    candidates = ['h264_nvenc', 'h264_qsv', 'h264_amf', 'libx264'] if requested == 'auto' else [requested]
    if any(c not in {'h264_nvenc', 'h264_qsv', 'h264_amf', 'libx264'} for c in candidates):
        raise ValueError('Unsupported encoder')
    checks = []
    for encoder in candidates:
        test = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=320x240:r=30:d=0.2', '-frames:v', '6', '-c:v', encoder, '-threads', str(threads), '-f', 'null', '-'], capture_output=True, timeout=20)
        checks.append({'encoder': encoder, 'available': test.returncode == 0})
        if test.returncode == 0:
            return encoder, checks
    raise ValueError('No requested encoder passed the actual encode check')


def captions(config, review, review_root, duration):
    r = config['render']
    width, height = r['width'], r['height']
    font = str(r.get('font', 'Noto Sans')).replace(',', '').replace('\n', '')
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Header,{font},50,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,5,70,70,0,1
Style: Words,{font},52,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,5,80,80,0,1
Style: CTA,{font},31,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,5,70,70,0,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    events = []

    def event(style, start, end, y, text):
        events.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{{\\pos({width//2},{y})}}{text}')

    headline = str(review['headline']).strip()
    if not headline or len(headline) > 100:
        raise ValueError('Provide a concise reviewed headline of at most 100 characters')
    event('Header', 0, min(4.2, duration), r['headline_y'], escape('\n'.join(textwrap.wrap(headline, 34))))
    if r.get('cta'):
        event('CTA', 0, duration, r['cta_y'], escape(r['cta']))
    if config['generation'].get('add_subtitles', True):
        if not review.get('words_file'):
            raise ValueError('Reviewed timestamped word cache is required for captions')
        data = load(review_root / review['words_file'])
        start = float(review.get('word_timebase_start_seconds', 0)) + float(review['start_seconds'])
        words = []
        for word in data.get('words', []):
            a, b = float(word['start']) / 1000 - start, float(word['end']) / 1000 - start
            if b > 0 and a < duration:
                words.append({'text': str(word['text']).strip(), 'start': max(0, a), 'end': min(duration, b)})
        if not words:
            raise ValueError('No source words overlap this reviewed trim')
        groups, group = [], []
        for word in words:
            if group and (len(group) == 4 or len(' '.join(w['text'] for w in group + [word])) > 31):
                groups.append(group); group = []
            group.append(word)
        if group:
            groups.append(group)
        for group in groups:
            for active, word in enumerate(group):
                end = group[active+1]['start'] if active+1 < len(group) else min(duration, word['end']+0.08)
                if end <= word['start']:
                    continue
                line = ' '.join(('{\\c&H00FFFF&}' if i == active else '{\\c&HFFFFFF&}') + escape(w['text'].upper()) for i, w in enumerate(group))
                event('Words', word['start'], end, r['caption_y'], line)
    return header + '\n'.join(events) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    config_file, review_file, source, destination = [Path(v).resolve() for v in (args.config, args.review, args.source, args.out)]
    config, review = load(config_file), load(review_file)
    if not config['campaign'].get('intake_complete') or not review.get('approved_for_draft') or not review.get('review_notes'):
        raise ValueError('Campaign intake and this source moment must be reviewed before rendering')
    if destination.suffix.lower() != '.mp4' or destination.exists():
        raise ValueError('Choose a new MP4 output path; existing deliverables are never overwritten')
    partial = destination.with_name(destination.stem + '.partial.mp4')
    if partial.exists():
        raise ValueError('Partial render exists; inspect it before retrying')
    r = config['render']; width, height = r['width'], r['height']
    if type(width) is not int or type(height) is not int or not (320 <= width <= 3840 and 320 <= height <= 3840) or width % 2 or height % 2:
        raise ValueError('Use even canvas dimensions between 320 and 3840')
    gx, gy, gw, gh = box(r['foreground_box'], width, height)
    bx, by, bw, bh = box(r['logo_box'], width, height)
    if not (by+bh <= gy or by >= gy+gh):
        raise ValueError('Place the logo outside the full-frame footage')
    for key in ('headline_y', 'caption_y', 'cta_y'):
        value = r[key]
        if type(value) is not int or value < 40 or value > height-40 or gy-35 <= value <= gy+gh+35:
            raise ValueError('Text must stay outside the footage with readable canvas margins')
    logo = (config_file.parent / r['logo_file']).resolve(strict=True)
    info = probe(source); video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    start, end = float(review['start_seconds']), float(review['end_seconds'])
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= float(info['format']['duration']) + 0.05):
        raise ValueError('Reviewed trim must stay inside this source file')
    duration = end-start
    if not config['campaign']['min_clip_seconds'] <= duration <= config['campaign']['max_clip_seconds']:
        raise ValueError('Reviewed duration violates this campaign configuration')
    mode = r.get('input_mode', 'source_fit')
    if mode not in {'source_fit', 'native_fit'}:
        raise ValueError('Use source_fit or a reviewed native_fit input')
    if mode == 'native_fit' and (int(video['width']), int(video['height'])) != (width, height):
        raise ValueError('native_fit input must match the configured canvas')
    logo_video = next(s for s in probe(logo)['streams'] if s['codec_type'] == 'video')
    ratio = min(bw/int(logo_video['width']), bh/int(logo_video['height']))
    lw, lh = max(2, int(int(logo_video['width'])*ratio)//2*2), max(2, int(int(logo_video['height'])*ratio)//2*2)
    lx, ly = (bx+(bw-lw)//2)//2*2, (by+(bh-lh)//2)//2*2
    threads = r.get('cpu_threads', 4)
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError('CPU thread budget must be 1–64')
    encoder, checks = select_encoder(r.get('encoder', 'auto'), threads)
    fps = str(Fraction(video.get('avg_frame_rate') or '30'))
    if fps == '0':
        fps = '30'
    destination.parent.mkdir(parents=True, exist_ok=True)
    support = destination.parent / (destination.stem + '-support')
    support.mkdir(exist_ok=True)
    began = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='campaign-render-', dir=destination.parent) as scratch:
        scratch = Path(scratch)
        (scratch / 'captions.ass').write_text(captions(config, review, review_file.parent, duration), encoding='utf-8')
        if mode == 'source_fit':
            base = f'[0:v]scale={gw}:{gh}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:{gx}+({gw}-iw)/2:{gy}+({gh}-ih)/2:color=0x0c0c14,setsar=1,format=yuv420p[base];'
        else:
            base = f'[0:v]format=yuv420p,drawbox=x=0:y=0:w={width}:h={gy}:color=0x0c0c14:t=fill,drawbox=x=0:y={gy+gh}:w={width}:h={height-gy-gh}:color=0x0c0c14:t=fill[base];'
        logo_filter = f'scale={lw}:{lh}:flags=lanczos:out_color_matrix=bt709,format=yuv420p,setsar=1'
        graph = base + f'[1:v]{logo_filter}[logo];[base][logo]overlay=x={lx}:y={ly}:eof_action=repeat:shortest=0,ass=captions.ass[v]'
        encode_options = ['-c:v', encoder]
        if encoder == 'libx264':
            preset, crf = r.get('preset', 'veryfast'), r.get('crf', 18)
            if preset not in {'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow'} or type(crf) is not int or not 14 <= crf <= 28:
                raise ValueError('Invalid CPU quality settings')
            encode_options += ['-preset', preset, '-crf', str(crf)]
        elif encoder == 'h264_nvenc':
            encode_options += ['-preset', 'p4', '-rc', 'vbr', '-cq', '19', '-b:v', '0']
        elif encoder == 'h264_qsv':
            encode_options += ['-global_quality', '19']
        else:
            encode_options += ['-quality', 'balanced', '-rc', 'cqp', '-qp_i', '19', '-qp_p', '19']
        render_start = time.monotonic()
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(start), '-i', str(source), '-framerate', fps, '-loop', '1', '-i', str(logo), '-filter_complex_threads', str(min(threads, 4)), '-filter_complex', graph, '-map', '[v]', '-map', '0:a?', *encode_options, '-threads', str(threads), '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', str(duration), '-movflags', '+faststart', '-n', str(partial)], cwd=scratch)
        render_seconds = time.monotonic()-render_start
        final = probe(partial); fv = next(s for s in final['streams'] if s['codec_type'] == 'video')
        if (int(fv['width']), int(fv['height'])) != (width, height) or abs(float(final['format']['duration'])-duration) > 0.2:
            raise ValueError('Output dimensions/duration verification failed')
        if any(s['codec_type'] == 'audio' for s in info['streams']) and not any(s['codec_type'] == 'audio' for s in final['streams']):
            raise ValueError('Source audio disappeared from the output')
        verify_start = time.monotonic()
        proof = f'[0:v]crop={lw}:{lh}:{lx}:{ly},setsar=1[actual];[1:v]{logo_filter}[expected];[actual][expected]ssim=stats_file=logo-ssim.txt:shortest=1[checked]'
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(partial), '-framerate', fps, '-loop', '1', '-i', str(logo), '-filter_complex_threads', '2', '-filter_complex', proof, '-map', '[checked]', '-an', '-t', str(duration), '-f', 'null', '-'], cwd=scratch)
        values = [float(v) for v in re.findall(r'All:([0-9.]+)', (scratch / 'logo-ssim.txt').read_text())]
        frames = int(fv['nb_frames']) if str(fv.get('nb_frames', '')).isdigit() else None
        if frames is None:
            counted = json.loads(run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'json', str(partial)]))
            frames = int(counted['streams'][0]['nb_read_frames'])
        if not values or len(values) != frames or min(values) < 0.95:
            raise ValueError('Logo failed the check over every encoded frame')
        validation_seconds = time.monotonic()-verify_start
        for name, second in [('first', 0), ('middle', duration/2), ('last', max(0, duration-0.12))]:
            poster = support / (name+'.jpg')
            run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(second), '-i', str(partial), '-frames:v', '1', '-vf', 'scale=540:-2', '-y', str(poster)])
        (support / 'captions.ass').write_text((scratch / 'captions.ass').read_text(), encoding='utf-8')
        report = {'width': width, 'height': height, 'duration_seconds': float(final['format']['duration']), 'continuous_logo_checked_frames': len(values), 'expected_video_frames': frames, 'minimum_logo_ssim': min(values), 'encoder': encoder, 'encoder_checks': checks, 'input_mode': mode, 'render_seconds': round(render_seconds, 3), 'validation_seconds': round(validation_seconds, 3), 'total_seconds': round(time.monotonic()-began, 3), 'audio': 'AAC re-encoded at 192 kbps for precise trimming', 'publication_status': 'draft_only_not_posted', 'full_audio_video_review': 'pending', 'review': review, 'source_file': str(source), 'original_stream_start_seconds': config['source']['window_start_seconds']+review.get('word_timebase_start_seconds', 0)+start, 'original_stream_end_seconds': config['source']['window_start_seconds']+review.get('word_timebase_start_seconds', 0)+end}
        hasher = hashlib.sha256()
        with partial.open('rb') as media:
            for chunk in iter(lambda: media.read(1024*1024), b''):
                hasher.update(chunk)
        report['output_sha256'] = hasher.hexdigest()
        (support / 'validation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        text = [str(review.get('post_caption', '')).strip(), *config['campaign']['required_caption_lines']]
        if config['campaign']['hashtags']:
            text.append(' '.join('#'+tag.lstrip('#') for tag in config['campaign']['hashtags']))
        destination.with_name(destination.stem+'-caption.txt').write_text('\n\n'.join(t for t in text if t)+'\n', encoding='utf-8')
        os.rename(partial, destination)
        print(json.dumps({key: report[key] for key in ('encoder', 'render_seconds', 'validation_seconds', 'total_seconds', 'continuous_logo_checked_frames', 'minimum_logo_ssim')}, indent=2))


if __name__ == '__main__':
    main()
