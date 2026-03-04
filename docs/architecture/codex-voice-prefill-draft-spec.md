# Codex Voice Prefill Draft Input Spec

## Objective

Enable a voice-first workflow in Codex where speech transcription is inserted into the compose input as an editable draft, and only sent when the user presses Enter.

This removes copy/paste friction between `mcp__voicemode__converse` output and normal text submission.

## Scope

- In scope:
  - Codex client behavior after a successful voice turn
  - Prefill/edit/submit UX
  - Stop-phrase handling in voice loop mode
  - Failure and fallback behavior
- Out of scope:
  - Core VoiceMode STT/TTS algorithms
  - Model quality tuning
  - New remote transport protocols

## Users

- Primary: Codex users running VoiceMode locally (`whisper` + `kokoro`)
- Secondary: Codex users on cloud fallback (`OPENAI_API_KEY`)

## Current Behavior (Problem)

- `converse` returns transcript text in tool output.
- User must manually copy transcript into compose input.
- Flow is slow and error-prone for iterative voice interaction.

## Target UX

1. User invokes voice mode (single turn or loop).
2. Voice turn completes and transcript is returned.
3. Codex client inserts transcript into compose input draft.
4. User can:
   - press Enter to submit as-is, or
   - edit text and press Enter.
5. Nothing auto-sends without user Enter.

## Functional Requirements

### FR1: Draft Prefill

- On successful `converse` return with transcript text, client sets compose draft to transcript.
- Existing unsent draft must not be silently lost:
  - If draft is non-empty, append transcript below a separator:
    - `\n\n---\nVoice draft:\n<transcript>`

### FR2: Manual Send Only

- Prefill never triggers auto-send.
- Enter behavior remains standard Codex submit behavior.

### FR3: Editable Before Send

- Cursor is placed at end of inserted text.
- User can edit before submission.

### FR4: Confidence/Quality Hint

- If transcript is short or likely partial, show non-blocking hint:
  - `Voice draft added. Review before sending.`
- No hard-blocking modal.

### FR5: Loop Mode Stop Phrase

- In hands-free loop mode, detect stop intent with case-insensitive match set:
  - `stop voice mode`
  - `stop voicemail`
  - `stop voice`
- On stop intent:
  - Exit loop
  - Do not prefill stop phrase as draft

### FR6: Error Handling

- If `converse` call fails:
  - Show inline error toast/banner
  - Keep current draft unchanged
- If TTS fails but STT succeeds:
  - Still prefill transcript

## Non-Functional Requirements

- Draft insertion must complete in <50ms after tool result render.
- No new blocking network calls in compose path.
- Compatible with existing keyboard shortcuts and multiline behavior.

## Client Integration Design

## Event Contract

Add client-side handler for voice tool results:

- Trigger condition:
  - Tool name matches `mcp__voicemode__converse`
  - Result includes recognizable transcript payload

## Transcript Extraction Rules

Attempt in order:

1. `Voice response: <text> (...)` parsing from current result format
2. Structured field if future format provides explicit `transcript`
3. Fallback: no prefill if transcript cannot be safely parsed

## State Model

- New UI state:
  - `voiceDraftPending: boolean`
  - `voiceLastTranscript: string | null`
- Compose store mutation:
  - `setDraftFromVoice(transcript, mode: replace|append)`

## Config Flags

- Add user setting:
  - `voice.prefill_mode = "off" | "on"` (default: `on`)
- Add loop stop phrase override (optional advanced):
  - `voice.stop_phrase = "stop voice mode"` (default)

## Compatibility Notes

- No MCP protocol change is required for initial version.
- Backward compatible with current tool output format.
- Future enhancement: add explicit structured transcript field from VoiceMode tool to remove string parsing dependency.

## Implementation Task List

1. Add voice-result parser utility in Codex client.
2. Add compose-store API: `setDraftFromVoice`.
3. Add UI state flags for voice draft tracking.
4. Add client setting `voice.prefill_mode` (default `on`).
5. Wire `converse` result handler to prefill logic.
6. Implement non-destructive append behavior when draft exists.
7. Implement stop intent matcher for loop mode.
8. Add inline hint/toast for partial transcript review.
9. Add analytics counters:
   - `voice_prefill_applied`
   - `voice_prefill_appended`
   - `voice_prefill_parse_failed`
   - `voice_loop_stop_detected`
10. Add unit tests for parser + store updates.
11. Add integration tests for end-to-end loop/prefill flow.
12. Update user docs/changelog.

## Test Plan

### Unit Tests

- Parse canonical transcript output string.
- Parse stop phrase variants.
- Reject malformed tool outputs safely.
- Replace vs append logic in compose store.

### Integration Tests

- Single-turn voice result prefills draft.
- Existing draft + voice result appends with separator.
- Enter submits prefilled draft unchanged.
- Edit then Enter submits edited text.
- Loop exits on stop phrase variant and does not prefill stop text.
- Tool failure leaves draft untouched.

### Manual QA Scenarios

- Long dictation paragraph
- Very short utterance
- Interrupted speech
- STT-only path (`skip_tts=true`)
- TTS fallback path with `OPENAI_API_KEY`

## Rollout Plan

1. Ship behind `voice.prefill_mode` setting (`on` by default for voice-enabled sessions).
2. Validate telemetry for parse failures.
3. If parse-failure rate is high, prioritize structured transcript output enhancement.

## Acceptance Criteria

- User can speak, see text prefilled, edit, and submit with Enter without copy/paste.
- No regression in normal typed compose flow.
- Stop phrase reliably exits loop mode.
- Draft safety preserved (no silent overwrite of existing text).

