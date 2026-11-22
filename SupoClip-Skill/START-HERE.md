# Portable SupoClip campaign skill

Copy this whole folder or extract `SupoClip-Skill.zip` on the other PC. SupoClip itself must already be installed there. This package contains no videos, logos, account records, API keys, or campaign data.

On Windows, install for both agents from PowerShell:

```powershell
& .\Install-Skill.ps1 -Agent Both
```

Use `-Agent Codex` or `-Agent Claude` if you use only one. The installer refuses to overwrite an existing skill. On Linux/macOS, copy `supoclip-campaign/` into `~/.codex/skills/` for Codex or `~/.claude/skills/` for Claude. Start a new agent session after installation, then invoke `$supoclip-campaign` in Codex or `/supoclip-campaign` in Claude.

Example request:

> Use the SupoClip campaign skill. Ask me for this campaign's clipping terms and video configuration, inspect this PC's existing SupoClip installation, and create original branded clip drafts efficiently.

The skill asks for campaign terms, source/window, framing, captions, branding, clip count/length, output quality and processing budget before generation. It discovers local URLs and hardware and uses your current PC's own account. Node 20+ and Python 3.10+ are needed for the helpers; FFmpeg can run natively or through the already installed backend Docker image. A GPU is optional.

The helpers support stable keyed submissions, explicit candidate counts, bounded downloads, fingerprinted restart checkpoints, and a single-pass renderer for reviewed continuous full-frame clips. The renderer checks actual GPU availability and falls back to CPU. Full-frame logo validation remains enabled. Editorial review and campaign eligibility checks remain necessary; the package does not publish or submit clips automatically.

For the machine-independent commands and config schema, see `supoclip-campaign/references/`. Tests exercise retry/resume and clip collection against a local synthetic server; they incur no provider usage:

```text
node --test tests/campaign.test.mjs
```

The measured local benchmark and cleanup outcome are in the workspace's separate completion report. Speedups depend on the source, filter graph and encoder actually available on the destination machine; no fixed speed multiplier is promised.
