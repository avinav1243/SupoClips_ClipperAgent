---
name: supoclip-campaign
description: Create original campaign clip drafts with an existing SupoClip installation, collecting campaign terms and video configuration first, resuming jobs, and exporting reviewed branded clips efficiently.
---

# SupoClip campaign clips

Use the existing SupoClip installation at **`REPO/supoclip/`**, where `REPO` is the current repository root. Determine that root from the working repository, independently of the skill's global installation folder. Check `supoclip/docker-compose.yml` and its local configuration there; if missing, report the expected repository layout. Keep campaign work under `REPO/campaigns/`. The external `supoclip/` checkout is excluded from Git.

This skill works with Codex and Claude on Windows or Linux. Helper scripts need Node.js 20+ and Python 3.10+; media work also needs FFmpeg/FFprobe, natively or in this installation's backend image. Discover actual URLs, container images, authentication, and encoder access from this repository's installation and the current PC. Never carry credentials, account IDs, provider keys, or machine paths from another PC.

## Campaign intake comes before generation

Ask for the campaign's terms and video configuration at the start of each new campaign. Reuse information already supplied in the conversation; ask only for missing decisions. Bundle questions so the user can answer once:

- Campaign name, complete terms, approval/warmup/audience guides, permitted creators and footage, logo/brand assets, required caption lines and hashtags, prohibited content, eligible platforms, and any clip length or submission deadlines.
- Source URL/file and desired timestamps; target number of distinct strong clips; minimum/maximum duration; language and caption style; crop versus full gameplay versus facecam/gameplay layout; logo position, headline/CTA preferences, and platform safe areas.
- SupoClip account; external AI processing/provider budget; available CPU/RAM/GPU, output quality, simultaneous jobs, and final output location. Inspect the repository's installation and PC to determine URLs and hardware. Ask about quality/cost priorities and limits.

Confirm footage and window suitability with small previews before downloading/transcribing an hour. A stream title or channel link alone does not prove actual game content or eligibility. Resolve contradictory terms or unavailable assets before dependent work. Missing publishing guides need not block private draft generation when the user authorizes it, but mark that condition in the manifest.

Read [references/configuration.md](references/configuration.md), copy `assets/campaign.template.json` into a new private working directory, and fill it from the agreed requirements. Summarize the concrete plan. Record `campaign.intake_complete`, `source.verified`, and `generation.approved` only when supported by the conversation; a default, timeout, or unanswered question is not approval. The `validate` command catches incomplete intake and invalid options.

## Efficient processing and restart safety

Prefer connected SupoClip MCP/API capabilities when available. The bundled `scripts/campaign.mjs` is a fallback for reliable local operations; it accepts backend API-key auth or frontend session auth. Read [references/operations.md](references/operations.md) for exact commands, auth, checkpoint recovery, and Docker media execution.

1. Validate the configuration and inspect health/workflow limits. Existing accounts are preferred; create an isolated drafts account only when authorized. API keys go to a local environment variable; session files stay in the campaign's `private/` directory. Do not print secrets or include them in the portable skill.
2. Obtain only the approved source window. Inspect the download process and partial-file growth before restarting a disconnected download. Reuse completed source files and cached transcripts. Stop unused downloads when authorized.
3. Submit once, saving the source fingerprint, upload path, stable idempotency keys, requested settings, and task ID atomically. Highlights clip count belongs in `workflow_options.advanced.max_clips`, subject to the installation's advertised limits. If gated, explain that target policy uses automatic native counts and may render more candidates than the final target. Use require_limit when candidate count is a hard cost/time constraint. Do not guess unsupported options or change global clip limits for one campaign.
4. Monitor the existing task and collect candidates with bounded concurrency. Resume from saved files after an interruption. Timeouts and 5xx responses can leave a request accepted: inspect history before retrying; reuse the same key. Do not recreate a paid generation task to fix a caption or logo.
5. Review source context and word timings while later candidates render. Reject weak, duplicate, misleading, or campaign-prohibited moments. Finalize trim, headline, layout, and subtitles before encoding. Candidate count is not completed-export count.
6. For a reviewed continuous full-frame moment, render directly from its source with `scripts/render.py`, so trim, layout, logo, title, CTA and subtitles are applied in one pass. Alternatively use `native_fit` for existing 1080x1920 SupoClip full-fit drafts. For portrait/split layouts or discontinuous edits, use SupoClip's existing editor and review its source-range mapping; do not apply the full-fit masks or continuous timing assumptions to those layouts.
7. Choose hardware encoding only after the script's real encode check succeeds. CPU fallback uses `libx264`, `veryfast`, CRF 18, with automatically sized encoder, decoder, filter and validation thread pools. Detection respects process affinity and Docker CPU quotas. Reserve one CPU by default; set `concurrent_renders` to the actual simultaneous render count to divide the per-render budget. Explicit thread overrides are supported. On a larger PC, benchmark the actual filter graph and allow a small number of concurrent final exports within available RAM/encoder capacity. More threads do not always improve throughput; use measured overrides when appropriate. GPU support is not guaranteed by an FFmpeg encoder listing.

Avoid development-frontend memory pressure for repeated production-like work: recommend the existing production build target after inspecting the installation. Make/restart that change only within the user's authorized scope and with no active generation affected. Do not rebuild an entire app for a clip edit. Report download, AI/planning, native rendering, final rendering and review times separately; do not promise a speedup without measurement.

## Review and delivery

The renderer verifies dimensions/duration/audio and compares the configured logo area against every encoded frame. It writes frames, caption text, and validation/timing reports. For mandatory continuous logos, keep the full-frame check. Logo similarity is evidence of the overlay, not a substitute for watching the clip and hearing its audio.

Inspect opening, middle and ending frames; watch/listen to the entire final clip using available media tools. Check an honest hook in the first 1–2 seconds, preserved context, caption synchronization/legibility, safe areas, continuous branding, and required posting text. Keep the result a draft if any required review or campaign guide remains incomplete. Never claim audience geography, engagement rate, warmup, rights, or platform approval from editing alone.

Maintain a manifest with source/time mapping, edit decisions, export paths, validation results, completed/rejected/pending counts, guide status, and measured timings. No automatic publishing, social connection, submission, or cleanup is included in this skill. When those actions are explicitly requested, preserve required deliverables, scope the operation, and follow the existing service's supported API. Stop paid retries after an unresolved ambiguous submission or three consecutive status failures; request the missing intervention instead of duplicating jobs.
