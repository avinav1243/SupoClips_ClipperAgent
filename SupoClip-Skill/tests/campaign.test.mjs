import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { validate } from '../supoclip-campaign/scripts/campaign.mjs';

const templateFile = fileURLToPath(new URL('../supoclip-campaign/assets/campaign.template.json', import.meta.url));
const script = fileURLToPath(new URL('../supoclip-campaign/scripts/campaign.mjs', import.meta.url));
const template = () => JSON.parse(fs.readFileSync(templateFile, 'utf8'));

test('unfinished intake and unagreed processing are rejected', () => {
  assert.throws(() => validate(template()), /intake|terms/);
  const c = template(); c.campaign = { ...c.campaign, intake_complete: true, name: 'Synthetic test', terms: ['Use original edits'] }; c.source.verified = true; c.source.evidence = 'Synthetic footage';
  assert.throws(() => validate(c), /Agree/);
});

test('successful resume, count support, ambiguous retry and partial collection', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'supoclip-skill-test-'));
  let uploads = 0, creates = 0, ambiguous = true, advertise = true;
  const keys = [], bodies = [];
  const server = http.createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/tasks/workflows') return res.end(JSON.stringify({ enabled: true, workflows: [{ id: 'highlights', available: true, settings: advertise ? [{ key: 'max_clips', min: 1, max: 10 }] : [] }] }));
    if (req.url === '/upload') { uploads++; return res.end(JSON.stringify({ video_path: 'upload://synthetic.mp4' })); }
    if (req.url === '/tasks/' && req.method === 'POST') {
      creates++; keys.push(req.headers['idempotency-key']); bodies.push(JSON.parse(body));
      if (ambiguous) { ambiguous = false; res.statusCode = 500; return res.end('{}'); }
      return res.end(JSON.stringify({ task_id: 'synthetic-task' }));
    }
    if (req.url === '/tasks/synthetic-task') return res.end(JSON.stringify({ status: 'completed', progress: 100, clips: [{ id: 'first' }, { id: 'second' }] }));
    if (req.url.includes('/file?')) { res.setHeader('Content-Type', 'video/mp4'); return res.end(Buffer.from('synthetic media bytes')); }
    res.statusCode = 404; res.end('{}');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.close(); fs.rmSync(root, { recursive: true, force: true }); });
  const c = template();
  c.campaign = { ...c.campaign, intake_complete: true, name: 'Synthetic test', terms: ['Use original edits'] }; c.source.verified = true; c.source.evidence = 'Synthetic test fixture';
  c.generation.approved = c.generation.external_processing_agreed = true; c.generation.max_clips = 7; c.generation.count_policy = 'require_limit';
  c.connection.origin = 'http://127.0.0.1:' + server.address().port;
  let file = path.join(root, 'campaign.json'); fs.writeFileSync(file, JSON.stringify(c)); fs.writeFileSync(path.join(root, 'source.mp4'), 'synthetic fixture');
  async function cli(action, ...flags) {
    return new Promise((resolve, reject) => {
      const child = spawn(process.execPath, [script, action, file, ...flags], { env: { ...process.env, SUPOCLIP_API_KEY: 'synthetic-key' } });
      let output = ''; child.stdout.on('data', data => output += data); child.stderr.on('data', data => output += data);
      child.on('error', reject); child.on('close', code => resolve({ code, output }));
    });
  }
  advertise = false;
  assert.equal((await cli('submit')).code, 1); assert.equal(uploads, 0); assert.equal(creates, 0);
  advertise = true;
  const firstSubmission = await cli('submit');
  assert.equal(firstSubmission.code, 1, firstSubmission.output); assert.equal(uploads, 1, firstSubmission.output); assert.equal(creates, 1, firstSubmission.output);
  assert.equal((await cli('submit')).code, 1); assert.equal(creates, 1);
  assert.equal((await cli('submit', '--retry-ambiguous')).code, 0); assert.equal(uploads, 1); assert.equal(keys[0], keys[1]);
  assert.equal(bodies[1].workflow_options.advanced.max_clips, 7);
  assert.equal((await cli('submit')).code, 0); assert.equal(creates, 2); assert.equal(uploads, 1);
  assert.equal((await cli('collect', '--concurrency', '2')).code, 0);
  assert.equal((await cli('collect', '--concurrency', '2')).code, 0);
  const first = path.join(root, 'exports/raw/clip-01/clip.mp4');
  fs.renameSync(first, first+'.part');
  assert.equal((await cli('collect')).code, 1); assert.ok(fs.existsSync(first+'.part'));
  assert.equal((await cli('collect', '--retry-partials')).code, 0);
  fs.writeFileSync(first, 'corruption');
  assert.equal((await cli('collect')).code, 1);
  c.generation.max_clips = 8; fs.writeFileSync(file, JSON.stringify(c));
  assert.equal((await cli('submit')).code, 1); assert.equal(creates, 2);
  assert.ok(!fs.existsSync(path.join(root, 'private/job.lock')));
  const autoRoot = path.join(root, 'automatic-count'); fs.mkdirSync(autoRoot);
  file = path.join(autoRoot, 'campaign.json'); c.generation.count_policy = 'target'; advertise = false;
  fs.writeFileSync(file, JSON.stringify(c)); fs.writeFileSync(path.join(autoRoot, 'source.mp4'), 'synthetic fixture');
  assert.equal((await cli('submit')).code, 0); assert.equal(creates, 3); assert.equal(uploads, 2);
  assert.ok(!Object.hasOwn(bodies.at(-1), 'workflow_options'));
});
