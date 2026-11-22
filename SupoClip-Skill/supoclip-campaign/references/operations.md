# Operating commands

Resolve `SKILL` to this skill's folder and `WORK` to the private campaign directory. Copy the template to `WORK/campaign.json` and complete intake. Commands below use normal local Node/Python and work on Windows or Linux with appropriate path quoting.

```text
node SKILL/scripts/campaign.mjs validate WORK/campaign.json
node SKILL/scripts/campaign.mjs inspect WORK/campaign.json
node SKILL/scripts/campaign.mjs submit WORK/campaign.json
node SKILL/scripts/campaign.mjs status WORK/campaign.json
node SKILL/scripts/campaign.mjs watch WORK/campaign.json --seconds 45
node SKILL/scripts/campaign.mjs collect WORK/campaign.json --concurrency 2
python SKILL/scripts/render.py --config WORK/campaign.json --review WORK/review.json --source WORK/source.mp4 --out WORK/exports/clip-01.mp4
```

`inspect` is read-only and prints health/workflow availability without credentials. `submit` verifies intake and live count support/policy before streaming the existing local file once. Advanced counts are sent only when supported; target policy permits automatic native count, whereas require_limit stops if the limit is unavailable. It fingerprints the source and config, checkpoints every mutation, and retains both idempotency keys across retries. `status`, `watch`, and `collect` require `private/job.json` from submit or an explicitly adopted existing job with matching fingerprints. A saved task ID resumes; no new task is created.

An interrupted upload/create leaves its phase `upload_pending` or `submit_pending`. An error/timeout can still mean success. The next `submit` stops by default. First inspect existing uploads/tasks through the app/API; then, if a keyed retry is appropriate within server retention, use `--retry-ambiguous`. The same idempotency key is reused. Changed source/config/auth origin requires a separate campaign directory; don't edit an in-flight job to bypass the guard. Do not delete another live process's job lock. After a process is known dead, rename its stale lock and inspect its pending phase.

`collect` uses canonical clip IDs from the task and safe local numbered folders. It streams to `.part`, atomically commits each download, records SHA-256 and byte size, and verifies completed files before skipping them. Failed partial files are retained for diagnosis; `--retry-partials` discards only that campaign's known incomplete downloads after you inspect them. Parallel downloads are bounded (1–4). `watch` returns at its deadline, a terminal state, or three consecutive failures, so an agent can communicate and continue watching without a duplicate generation.

For YouTube windows, use the installation's existing yt-dlp with `--download-sections '*START-END'`, 1080p-or-lower source matching the chosen quality, audio, and merge to MP4. Obtain small preview sections before the large download; never infer that an existing partial is dead just from chat disconnection. Use `ffprobe` to verify the final file and correct length before submit. Don't request a whole multi-hour recording when the user agreed only an hour. Existing media/transcript caches are reused for edits.

If FFmpeg isn't installed on the host, reuse the installed backend image. The media runner mounts only the skill and selected working directory and disables networking:

```text
python SKILL/scripts/media-runner.py --root WORK --image supoclip-backend -- render.py --config /work/campaign.json --review /work/review.json --source /work/source.mp4 --out /work/exports/clip-01.mp4
```

Use `--gpu` only for a confirmed NVIDIA-equipped machine with working Docker GPU access. Otherwise CPU rendering works without it. Image name and Python executable inside the image are configurable with `--image` and `--python-in-image`. Move review inputs into `WORK`; `/work` paths are the container's view, and JSON references remain relative. A directory bind mount preserves Windows paths containing spaces without shell reconstruction.

After each final export inspect `clip-01-support/first.jpg`, `middle.jpg`, `last.jpg`, and `validation.json`, then watch/listen to the full MP4. Hardware-test success, render completion, and logo checks alone do not constitute editorial approval. The renderer refuses existing outputs and writes partial files until verification completes; failures stay available for inspection.
