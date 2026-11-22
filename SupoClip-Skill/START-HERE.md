# Portable SupoClip campaign skill

Clone this repository on the other PC, or extract `SupoClip-Skill.zip` so its `SupoClip-Skill/` folder sits inside your working repository. SupoClip is expected to be installed directly at `<repo>/supoclip/`. This package contains no videos, logos, account records, API keys, or campaign data.

Expected layout:

```text
repo/
  .gitignore
  supoclip/                  External SupoClip installation; ignored by Git
    docker-compose.yml
    .env
  SupoClip-Skill/            Reusable skill source and installer
  campaigns/                Private campaign inputs and outputs; ignored by Git
```

Run the agent from this repository so it can locate `supoclip/` and its local configuration. The installed skill itself can live in your agent's home-directory skill folder.

On Windows, open PowerShell in `<repo>/SupoClip-Skill/` and install for both agents:

```powershell
& .\Install-Skill.ps1 -Agent Both
```

Use `-Agent Codex` or `-Agent Claude` if you use only one. The installer refuses to overwrite an existing skill. On Linux/macOS, copy `supoclip-campaign/` into `~/.codex/skills/` for Codex or `~/.claude/skills/` for Claude. Start a new agent session after installation, then invoke `$supoclip-campaign` in Codex or `/supoclip-campaign` in Claude.

Example request:

> Use the SupoClip campaign skill. Ask me for this campaign's clipping terms and video configuration, inspect this PC's existing SupoClip installation, and create original branded clip drafts efficiently.

The skill asks for campaign terms, source/window, framing, captions, branding, clip count/length, output quality and processing budget before generation. It reads local URLs and services from `<repo>/supoclip/`, inspects hardware and uses your current PC's own account. Node 20+ and Python 3.10+ are needed for the helpers; FFmpeg can run natively or through that installation's backend Docker image. A GPU is optional.

The helpers support stable keyed submissions, explicit candidate counts, bounded downloads, fingerprinted restart checkpoints, and a single-pass renderer for reviewed continuous full-frame clips. The renderer checks actual GPU availability and falls back to CPU. Full-frame logo validation remains enabled. Editorial review and campaign eligibility checks remain necessary; the package does not publish or submit clips automatically.

CPU rendering automatically uses the available cores for encoding, decoding, filters and logo validation. It respects Docker CPU limits, reserves one logical CPU by default, and divides the thread budget when you configure simultaneous renders. Manual overrides and a repeatable synthetic benchmark are included.

For the machine-independent commands and config schema, see `supoclip-campaign/references/`. Tests exercise retry/resume and clip collection against a local synthetic server; they incur no provider usage:

```text
node --test tests/campaign.test.mjs
python tests/test_render_threads.py
```

The measured local benchmark and cleanup outcome are in the workspace's separate completion report. Speedups depend on the source, filter graph and encoder actually available on the destination machine; no fixed speed multiplier is promised.
