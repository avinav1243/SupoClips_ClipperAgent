import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';

export function validate(c) {
  if (!c.campaign?.intake_complete || !c.campaign.name?.trim() || !Array.isArray(c.campaign.terms) || !c.campaign.terms.length) throw Error('Complete campaign terms and intake first.');
  if (!c.source?.verified || !c.source.evidence?.trim()) throw Error('Verify source content and window first.');
  if (!c.generation?.approved || !c.generation.external_processing_agreed) throw Error('Agree the generation plan and processing costs first.');
  if (!Number.isInteger(c.generation.max_clips) || c.generation.max_clips < 1 || c.generation.max_clips > 10) throw Error('Highlights count must be 1–10.');
  if (!['target', 'require_limit'].includes(c.generation.count_policy || 'target')) throw Error('Choose target or require_limit for candidate count.');
  for (const key of ['add_subtitles', 'include_broll', 'cut_long_pauses', 'remove_filler_words']) if (typeof c.generation[key] !== 'boolean') throw Error('Expected a boolean generation option: ' + key);
  if (!['fast', 'balanced', 'quality'].includes(c.generation.processing_mode)) throw Error('Invalid processing mode.');
  if (!['vertical', 'vertical_fit', 'vertical_split', 'original'].includes(c.generation.output_format)) throw Error('Invalid output format.');
  if (!['auto', 'short', 'medium', 'long'].includes(c.generation.clip_length)) throw Error('Invalid clip length.');
  if ((c.generation.instructions || '').length > 500) throw Error('Instructions exceed 500 characters.');
  if (!Number.isFinite(c.source.window_start_seconds) || !Number.isFinite(c.source.window_end_seconds) || c.source.window_start_seconds < 0 || c.source.window_end_seconds <= c.source.window_start_seconds) throw Error('Invalid source window.');
  if (!(c.campaign.min_clip_seconds > 0 && c.campaign.max_clip_seconds >= c.campaign.min_clip_seconds)) throw Error('Invalid duration bounds.');
  for (const key of ['required_caption_lines', 'hashtags', 'platforms', 'prohibited_content']) if (!Array.isArray(c.campaign[key]) || c.campaign[key].some(x => typeof x !== 'string')) throw Error('Expected string list: ' + key);
  if (!['frontend', 'backend'].includes(c.connection?.mode)) throw Error('Choose frontend session or backend API-key auth.');
  const url = new URL(c.connection.origin);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw Error('Use a plain API origin without credentials or path.');
  if (url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw Error('Use HTTPS for non-local credential transport.');
  return c;
}
export function taskBody(c, uploadedPath, explicitCount = true) {
  const g = c.generation;
  return { source: { url: uploadedPath, title: c.campaign.name + ': selected window' }, workflow: 'highlights', ...(explicitCount ? { workflow_options: { advanced: { max_clips: g.max_clips } } } : {}), processing_mode: g.processing_mode, output_format: g.output_format, clip_length: g.clip_length, add_subtitles: g.add_subtitles, caption_template: 'default', include_broll: g.include_broll, cut_long_pauses: g.cut_long_pauses, remove_filler_words: g.remove_filler_words, ...(g.instructions ? { instructions: g.instructions } : {}) };
}
export async function digest(file) {
  const hash = crypto.createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
function atomicJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = file + '.' + crypto.randomUUID() + '.tmp';
  fs.writeFileSync(temp, JSON.stringify(value, null, 2), { flag: 'wx', mode: 0o600 }); fs.renameSync(temp, file);
}
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
const terminal = new Set(['completed', 'error', 'failed', 'cancelled', 'canceled']);
function option(flags, key, fallback) { const i = flags.indexOf(key); return i < 0 ? fallback : flags[i + 1]; }

async function run(action, configFile, flags) {
  const root = path.dirname(path.resolve(configFile)), c = readJson(configFile);
  if (action === 'validate') { validate(c); console.log('Campaign configuration is valid.'); return; }
  if (!['inspect', 'submit', 'status', 'watch', 'collect'].includes(action)) throw Error('Unknown command.');
  validate({ ...c, campaign: { ...c.campaign, intake_complete: true, name: 'inspection', terms: ['inspection'] }, source: { ...c.source, verified: true, evidence: 'inspection' }, generation: { ...c.generation, approved: true, external_processing_agreed: true } });
  const origin = c.connection.origin.replace(/\/$/, ''), frontend = c.connection.mode === 'frontend';
  let auth, identity;
  if (frontend) {
    const account = readJson(path.resolve(root, c.connection.session_file));
    if (!account.cookies || !account.userId) throw Error('Session file needs cookies and userId.');
    auth = { Cookie: account.cookies, Origin: origin }; identity = account.userId;
  } else {
    const key = process.env[c.connection.api_key_env || 'SUPOCLIP_API_KEY'];
    if (!key) throw Error('Configured API-key environment variable is missing.');
    auth = { Authorization: 'Bearer ' + key }; identity = crypto.createHash('sha256').update(key).digest('hex');
  }
  const apiPath = suffix => (frontend ? '/api/tasks' : '/tasks') + suffix;
  async function request(route, method = 'GET', body, extra = {}, timeout = 60000) {
    const response = await fetch(origin + route, { method, headers: { ...auth, ...extra }, body, redirect: 'error', signal: AbortSignal.timeout(timeout), ...(body instanceof Readable ? { duplex: 'half' } : {}) });
    if (!response.ok) throw Error('SupoClip HTTP ' + response.status + '. Inspect the app before retrying.');
    return response;
  }
  if (frontend) {
    const session = await (await request('/api/auth/get-session')).json();
    if (session?.user?.id !== identity) throw Error('Session expired or account differs. Reauthenticate locally.');
  }
  if (action === 'inspect') {
    if (!frontend) await request('/health');
    const schema = await (await request(apiPath('/workflows'))).json();
    console.log(JSON.stringify({ authenticated: true, workflow_options: schema }, null, 2)); return;
  }
  const privateDir = path.join(root, 'private'); fs.mkdirSync(privateDir, { recursive: true });
  const lockFile = path.join(privateDir, 'job.lock'), lock = fs.openSync(lockFile, 'wx', 0o600);
  fs.writeFileSync(lock, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }));
  const jobFile = path.join(privateDir, 'job.json');
  let job;
  try {
    job = fs.existsSync(jobFile) ? readJson(jobFile) : null;
    const configHash = crypto.createHash('sha256').update(JSON.stringify(c)).digest('hex');
    const authHash = crypto.createHash('sha256').update(origin + ':' + identity).digest('hex');
    const save = () => atomicJson(jobFile, job);
    if (job && (job.configHash !== configHash || job.authHash !== authHash)) throw Error('Saved job has different configuration/authentication; use a new campaign directory.');
    async function snapshot() {
      if (!job?.taskId) throw Error('No saved task ID. Inspect interrupted submission; do not duplicate generation.');
      const data = await (await request(apiPath('/' + encodeURIComponent(job.taskId)))).json();
      atomicJson(path.join(privateDir, 'task-status.json'), data);
      const task = data.task || data, clips = data.clips || task.clips || [];
      job.lastStatus = task.status; job.availableClips = clips.length; job.lastCheckedAt = new Date().toISOString(); save();
      return { task, clips };
    }
    if (action === 'submit') {
      validate(c);
      const source = path.resolve(root, c.source.file), size = fs.statSync(source).size;
      if (size <= 0) throw Error('Source file is empty.');
      const sourceHash = await digest(source);
      if (job && job.sourceHash !== sourceHash) throw Error('Source changed after job initialization.');
      if (!job) { job = { configHash, authHash, sourceHash, uploadKey: crypto.randomUUID(), taskKey: crypto.randomUUID(), phase: 'ready', createdAt: new Date().toISOString() }; save(); }
      if (job.taskId) { console.log('Saved task exists; resuming status.'); await snapshot(); return; }
      if (['upload_pending', 'submit_pending'].includes(job.phase) && !flags.includes('--retry-ambiguous')) throw Error('Previous request outcome is ambiguous. Inspect app history, then use --retry-ambiguous with the existing key if appropriate.');
      const schema = await (await request(apiPath('/workflows'))).json();
      const workflow = schema.workflows?.find(w => w.id === 'highlights'), setting = workflow?.settings?.find(s => s.key === 'max_clips');
      if (!workflow?.available) throw Error('Highlights are unavailable on this account.');
      const explicitCount = Boolean(setting && c.generation.max_clips >= setting.min && c.generation.max_clips <= setting.max);
      if (!explicitCount && c.generation.count_policy === 'require_limit') throw Error('Requested clip-count limit is not advertised by this installation/account. No upload/task created.');
      if (c.generation.instructions && !schema.enabled) throw Error('Editorial instructions unavailable on this account.');
      if (!explicitCount) console.log('This account uses automatic candidate count; requested count remains an editorial target.');
      job.countControl = explicitCount ? 'explicit_limit' : 'automatic_target'; save();
      if (!job.uploadedPath) {
        const boundary = 'SupoCampaign' + crypto.randomBytes(12).toString('hex');
        const prefix = Buffer.from('--' + boundary + '\r\nContent-Disposition: form-data; name="video"; filename="campaign-window.mp4"\r\nContent-Type: video/mp4\r\n\r\n'), suffix = Buffer.from('\r\n--' + boundary + '--\r\n');
        async function* stream() { yield prefix; for await (const chunk of fs.createReadStream(source)) yield chunk; yield suffix; }
        job.phase = 'upload_pending'; save();
        const uploaded = await (await request(frontend ? '/api/upload' : '/upload', 'POST', Readable.from(stream()), { 'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Content-Length': String(size + prefix.length + suffix.length), 'Idempotency-Key': job.uploadKey }, 1800000)).json();
        if (!uploaded.video_path) throw Error('Upload response has no video_path; inspect accepted upload before retry.');
        job.uploadedPath = uploaded.video_path; job.phase = 'uploaded'; save();
      }
      job.request = taskBody(c, job.uploadedPath, explicitCount); job.phase = 'submit_pending'; save();
      const created = await (await request(frontend ? '/api/tasks/create' : '/tasks/', 'POST', JSON.stringify(job.request), { 'Content-Type': 'application/json', 'Idempotency-Key': job.taskKey }, 120000)).json();
      if (!created.task_id) throw Error('Task response has no ID; inspect app history before retry.');
      job.taskId = created.task_id; job.phase = 'queued'; job.queuedAt = new Date().toISOString(); save();
      console.log('One generation task queued; checkpoint saved privately.'); return;
    }
    if (!job) throw Error('No campaign checkpoint exists.');
    if (action === 'status') {
      const { task, clips } = await snapshot();
      console.log(JSON.stringify({ status: task.status, candidates: clips.length, progress: task.progress, stage_timings: task.stage_timings_json }, null, 2)); return;
    }
    if (action === 'watch') {
      const seconds = Number(option(flags, '--seconds', 45));
      if (!Number.isFinite(seconds) || seconds < 1 || seconds > 3600) throw Error('Watch seconds must be 1–3600.');
      const deadline = Date.now() + seconds * 1000; let failures = 0, previous = '';
      do {
        try {
          const { task, clips } = await snapshot(); failures = 0;
          const signature = task.status + ':' + clips.length;
          if (signature !== previous) { console.log('Status: ' + task.status + '; candidates: ' + clips.length); previous = signature; }
          if (terminal.has(task.status)) { if (task.status !== 'completed') process.exitCode = 2; return; }
        } catch { if (++failures >= 3) throw Error('Three status failures; inspect the app before continuing.'); }
        if (Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, Math.min(15000, deadline - Date.now())));
      } while (Date.now() < deadline);
      console.log('Watch deadline reached; continue watching the same saved task.'); return;
    }
    const concurrency = Number(option(flags, '--concurrency', 2));
    if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 4) throw Error('Download concurrency must be 1–4.');
    const { clips } = await snapshot(); job.downloads ||= {};
    for (const clip of clips) {
      if (!clip.id) throw Error('Candidate has no canonical ID.');
      job.downloads[clip.id] ||= { index: Math.max(0, ...Object.values(job.downloads).map(x => x.index)) + 1 };
    }
    save(); let cursor = 0;
    const workers = Array.from({ length: concurrency }, async () => {
      while (cursor < clips.length) {
        const clip = clips[cursor++], entry = job.downloads[clip.id];
        const dir = path.join(root, 'exports', 'raw', 'clip-' + String(entry.index).padStart(2, '0')); fs.mkdirSync(dir, { recursive: true });
        const target = path.join(dir, 'clip.mp4'), part = target + '.part';
        if (fs.existsSync(target)) {
          if (!entry.sha256 || fs.statSync(target).size !== entry.bytes || await digest(target) !== entry.sha256) throw Error('Candidate file differs from its completed-download fingerprint.');
          continue;
        }
        if (fs.existsSync(part)) { if (!flags.includes('--retry-partials')) throw Error('Incomplete download found; inspect before --retry-partials.'); fs.unlinkSync(part); }
        atomicJson(path.join(dir, 'metadata.json'), clip);
        const response = await request(apiPath('/' + encodeURIComponent(job.taskId) + '/clips/' + encodeURIComponent(clip.id) + '/file?download=true'), 'GET', undefined, {}, 300000);
        if (!response.body) throw Error('Candidate response has no media.');
        await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(part, { flags: 'wx' }));
        entry.bytes = fs.statSync(part).size;
        if (!entry.bytes) throw Error('Candidate download empty.');
        entry.sha256 = await digest(part); fs.renameSync(part, target); save();
        console.log('Candidate ' + entry.index + ' downloaded.');
      }
    });
    const results = await Promise.allSettled(workers), failed = results.find(r => r.status === 'rejected');
    if (failed) throw failed.reason;
    console.log('Collected ' + clips.length + ' candidates; editorial review remains.');
  } finally { fs.closeSync(lock); fs.unlinkSync(lockFile); }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [action, file, ...flags] = process.argv.slice(2);
  if (!action || !file) { console.error('Usage: campaign.mjs validate|inspect|submit|status|watch|collect campaign.json [options]'); process.exitCode = 1; }
  else run(action, path.resolve(file), flags).catch(error => { console.error(error.message); process.exitCode = 1; });
}
