"""Compare CPU rendering settings on synthetic footage, without AI calls."""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


def execute(command):
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:] or result.stdout[-3000:])
    return time.monotonic()-start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--baseline', help='Optional previous renderer script')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--seconds', type=int, default=12)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if list(root.iterdir()):
        parser.error('Use a new empty output directory')
    skill = Path(__file__).resolve().parents[1]
    renderer = skill / 'scripts/render.py'
    template = skill / 'assets/campaign.template.json'
    if not 1 <= args.repeat <= 5 or not 2 <= args.seconds <= 60:
        parser.error('Use 1–5 repeats and a 2–60 second sample')
    execute(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', f'testsrc2=s=1920x1080:r=30:d={args.seconds}', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', str(args.seconds), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-threads', '4', '-c:a', 'aac', '-n', str(root/'source.mp4')])
    execute(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=440x80:r=1:d=1', '-frames:v', '1', '-threads', '1', '-n', str(root/'logo.png')])
    words = [{'text': word, 'start': int(i*args.seconds/4*1000), 'end': int((i+1)*args.seconds/4*1000)} for i, word in enumerate(['MULTITHREADED', 'CPU', 'RENDER', 'TEST'])]
    (root/'words.json').write_text(json.dumps({'words': words}))
    review = {'approved_for_draft': True, 'headline': 'CPU rendering benchmark', 'post_caption': 'Synthetic renderer check', 'start_seconds': 0, 'end_seconds': args.seconds, 'word_timebase_start_seconds': 0, 'words_file': 'words.json', 'review_notes': 'Synthetic moving test pattern for technical verification'}
    (root/'review.json').write_text(json.dumps(review))
    results = {key: [] for key in ('previous_4_threads', '8_threads', 'auto_threads')}
    for repeat in range(args.repeat):
        # Rotate execution order to reduce warmup/order bias.
        order = list(results)
        order = order[repeat % len(order):] + order[:repeat % len(order)]
        for name in order:
            config = json.loads(template.read_text())
            config['campaign'].update(name='Synthetic CPU benchmark', intake_complete=True, terms=['Synthetic test pattern'], min_clip_seconds=2, max_clip_seconds=60)
            config['render'].update(encoder='libx264', cpu_threads=4 if name=='previous_4_threads' else 8 if name=='8_threads' else 'auto', cta='Synthetic CPU benchmark')
            if name=='previous_4_threads':
                config['render'].update(filter_threads=4, decode_threads=4)
            config_file = root/(name+'-'+str(repeat)+'.json')
            config_file.write_text(json.dumps(config))
            output = root/(name+'-'+str(repeat)+'.mp4')
            program = args.baseline if name=='previous_4_threads' and args.baseline else str(renderer)
            elapsed = execute([sys.executable, '-I', program, '--config', str(config_file), '--review', str(root/'review.json'), '--source', str(root/'source.mp4'), '--out', str(output)])
            report = json.loads((root/(output.stem+'-support')/'validation.json').read_text())
            results[name].append({'wall_seconds': round(elapsed, 3), 'render_seconds': report['render_seconds'], 'validation_seconds': report['validation_seconds'], 'frames': report['continuous_logo_checked_frames'], 'minimum_logo_ssim': report['minimum_logo_ssim'], 'threading': report.get('threading', {'encode_threads':4,'filter_threads':4,'validation_threads':2,'decode_threads':'FFmpeg default'})})
            print(f'{name}, run {repeat+1}: {elapsed:.3f}s; {report["continuous_logo_checked_frames"]} logo frames checked', flush=True)
    medians = {name: round(statistics.median(r['wall_seconds'] for r in runs), 3) for name, runs in results.items()}
    summary = {'sample_seconds': args.seconds, 'repeats': args.repeat, 'synthetic_footage': True, 'median_wall_seconds': medians, 'auto_speed_ratio': round(medians['previous_4_threads']/medians['auto_threads'],3), 'runs': results}
    (root/'thread-benchmark.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps({key: summary[key] for key in ('median_wall_seconds','auto_speed_ratio')}, indent=2))


if __name__ == '__main__':
    main()
