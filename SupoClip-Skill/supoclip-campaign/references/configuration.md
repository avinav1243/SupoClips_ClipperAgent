# Campaign configuration

Paths in `campaign.json` are relative to that file's directory, so a working campaign can be moved without rewriting machine paths. Keep credentials and jobs under `private/`, source under `sources/`, and exports under `exports/`. The template contains no prior campaign branding, URLs, or credentials.

`terms` holds the actual campaign requirements. `required_caption_lines`, `hashtags`, allowed `platforms`, prohibited content and duration bounds must come from intake. Empty caption/hashtag lists are valid when the campaign does not require them; intake must still be complete. Unavailable guides are recorded explicitly. `source.evidence` records the creator/content/window checks. The URL and time window document provenance; the submitted file must already contain exactly that window, within the installation's source-duration/upload limits.

Connection modes:

- `backend`: direct REST API at the discovered backend origin, using the variable named by `api_key_env` as a Bearer token. API keys require a verified email on this installation; use an existing key instead of bypassing verification.
- `frontend`: local web origin, using cookies from the private `session_file`. Claude's existing session file shape is supported: `cookies` and `userId`. The script verifies that session's user before accessing or creating tasks. It does not create accounts or save passwords.

`generation.max_clips` requests distinct highlight candidates, not guaranteed usable final clips. The helper checks the live `/tasks/workflows` schema for `max_clips` and sends `workflow_options.advanced.max_clips` when supported. `count_policy: target` permits the installation's automatic candidate count when advanced controls are gated; explicitly explain that more native candidates may render than the final editorial target. `count_policy: require_limit` stops before upload/generation if the requested limit cannot be enforced. Choose that policy when count controls spending or rendering time. Basic self-host highlights can work without advanced-workflow access. Other workflow types can use native MCP/editor tools; this helper submits highlights. Custom instructions may be gated even when basic highlights are available; never silently drop them.

For `source_fit`, review start/end are seconds into the source file. If the file is an excerpt, add `source.window_start_seconds` to get original-stream times. Use cached word timestamps in milliseconds in the same source timebase. For `native_fit`, review start/end are seconds into the native clip and `word_timebase_start_seconds` gives that native clip's start in the cached source transcript. Never mix native-output time with original-source time. Use the source-map sidecar for precise offsets and discontinuous mappings.

Review file (created after examining the moment):

```json
{
  "approved_for_draft": true,
  "headline": "An accurate short headline",
  "post_caption": "A caption grounded in this moment.",
  "start_seconds": 100.0,
  "end_seconds": 128.0,
  "word_timebase_start_seconds": 0,
  "words_file": "private/source-cache.json",
  "review_notes": "Source context and audio reviewed; trim ends on a complete thought."
}
```

The renderer handles one continuous full-frame segment. It preserves the source frame inside `foreground_box`, preserves logo aspect ratio within `logo_box`, and positions header/captions/CTA outside the footage. All geometry is measured in the output canvas's pixels. For `native_fit`, foreground must be the known unmasked full-fit region; the script masks only above/below it. Other crop/split layouts must use SupoClip's editor or a separately reviewed graph.

Captions are built from actual words. If no timestamped cache is available, obtain/review an ASS subtitle file and use existing editor/export tools, or explicitly agree a caption-free draft; do not fabricate speech. The bundled renderer requires a word cache whenever generation's `add_subtitles` is true. Coarse-language corrections require source review; don't rewrite meaning.

Use a smaller working concurrency on CPU systems; increase after observing throughput/RAM. `encoder: auto` checks NVENC/QSV/AMF with actual encoding and falls back to libx264. `cpu_threads` limits each render. Native GPU access can differ from container access; expose an NVIDIA GPU to Docker only when it exists and access was authorized. No model, GPU runtime, or paid provider is installed by this package.
