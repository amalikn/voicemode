# VoiceMode Usage Guide

This guide maps the most common VoiceMode tasks to the correct command or MCP
tool. It is intended as the primary operator reference for day-to-day use.

## Overview

VoiceMode exposes two distinct surfaces:

| Surface | Use for | Primary commands |
| --- | --- | --- |
| `chat` | single-turn and continuous voice conversation | `voicemode chat`, `voicemode chat --continuous` |
| local runtime | push-to-talk, open-mic mode, read-aloud, and playback control | `voicemode voice run`, `voicemode read`, `voicemode mode`, `voicemode stop` |

Important runtime requirement:

- `voicemode chat` does not require the local runtime
- `voicemode read`, `voicemode mode`, and `voicemode stop` require `voicemode voice run` to be active

## Architecture At A Glance

The most common operational confusion is that VoiceMode has two different local
processes:

| Component | What it is | Default port | What it enables |
| --- | --- | --- | --- |
| HTTP MCP server | the MCP/API process exposed to clients such as Codex or Claude Code | `8765` | `chat`, `converse`, `service`, `connect_status`, and the shortcut MCP tools |
| local voice runtime | the desktop voice engine started with `voicemode voice run` | `8766` | `read`, `mode`, `stop`, push-to-talk, conversational mode, and read-aloud controls |

Practical consequence:

- `voicemode service status voicemode` can be healthy while `voicemode mode walk` still fails
- that happens when the HTTP MCP server is up but the local voice runtime is not running

## Named Runtime Modes

The local voice runtime supports exactly two named modes:

| Mode | Meaning | Start directly | Switch a running runtime |
| --- | --- | --- | --- |
| `walkie-talkie` | push-to-talk mode | `voicemode voice run --mode walkie-talkie` | `voicemode mode walk` |
| `conversational` | open-mic mode with VAD turn detection | `voicemode voice run --mode conversational` | `voicemode mode convo` |

Accepted shorthand values:

- `walk` maps to `walkie-talkie`
- `convo` maps to `conversational`

## Default Push-To-Talk Binding

The default push-to-talk hotkey is:

```text
Cmd+Shift+Space
```

This comes from `VOICEMODE_PTT_HOTKEY`. If the variable is unset, the runtime
uses `cmd+shift+space` by default.

## Quick Reference

### Common commands

```bash
voicemode chat
voicemode chat --continuous
voicemode read README.md
voicemode mode walk
voicemode mode convo
voicemode stop
```

### Short aliases

```bash
voicemode c
voicemode r README.md
voicemode m walk
voicemode x
```

### MCP shortcuts

```text
mcp__voicemode__chat
mcp__voicemode__read
mcp__voicemode__mode
mcp__voicemode__stop
```

### Original MCP tools

```text
mcp__voicemode__converse
mcp__voicemode__service
mcp__voicemode__connect_status
```

Use the shortcut tools for day-to-day operation. Use the original tool names
when you want the established API surface.

## Task Selection

| Goal | Recommended command | Notes |
| --- | --- | --- |
| Ask one question and exit | `voicemode chat -m "..." --wait` | one spoken reply cycle |
| Stay in an interactive CLI loop | `voicemode chat --continuous` | continues until exit phrase or `Ctrl+C` |
| Read a file aloud | `voicemode voice run` then `voicemode read <file>` | local runtime required |
| Use push-to-talk | `voicemode voice run --mode walkie-talkie` | explicit turn boundaries |
| Use open-mic conversation | `voicemode voice run --mode conversational` | VAD-controlled turn detection |
| Switch a running runtime to walkie-talkie | `voicemode mode walk` | does not start the runtime |
| Switch a running runtime to conversational | `voicemode mode convo` | does not start the runtime |
| Stop current speech immediately | `voicemode stop` | runtime shortcut for immediate stop |

## Common Workflows

### Single-turn conversation

Use a single-turn conversation when you want one prompt, one reply, and then
the command should exit.

```bash
voicemode chat -m "What changed in this repo today?" --wait
```

Behavior:

- VoiceMode speaks the prompt
- VoiceMode listens for one reply
- the reply is transcribed and returned
- the command exits after the response

If you want spoken output only, without a listening step:

```bash
voicemode chat -m "Build completed." --no-wait
```

MCP usage:

- call `mcp__voicemode__chat` or `mcp__voicemode__converse`
- set `message`
- set `wait_for_response="true"` for one response cycle

### Continuous conversation

Use continuous conversation for an ongoing CLI loop.

```bash
voicemode chat --continuous
```

Optional opening message:

```bash
voicemode chat --continuous -m "Let's review today's tasks."
```

Behavior:

- VoiceMode records a turn
- VoiceMode responds
- VoiceMode listens again automatically
- the loop continues until you say `exit`, `quit`, `goodbye`, or `bye`, or you stop it with `Ctrl+C`

MCP usage:

- one MCP `chat` or `converse` call handles one response cycle
- a multi-turn conversation in an MCP client must be implemented as repeated tool calls

### Read a file aloud

Start the local runtime:

```bash
voicemode voice run
```

Then send the file to the runtime:

```bash
voicemode read README.md
```

Behavior:

- the runtime accepts the file path
- the content is read in chunks
- text remains the primary interface and speech is supplemental

Playback controls:

```bash
voicemode voice control READ_CONTINUE
voicemode voice control READ_REPEAT
voicemode voice control READ_SKIP
voicemode voice control READ_SUMMARIZE
voicemode voice control READ_STOP
```

Typical uses:

- reviewing README files
- listening to notes or markdown documents
- hands-free document playback while away from the keyboard

### Walkie-talkie mode

Start directly in walkie-talkie mode:

```bash
voicemode voice run --mode walkie-talkie
```

Or switch a running runtime:

```bash
voicemode mode walk
```

Typical flow:

- hold the push-to-talk hotkey
- speak while recording is active
- release the hotkey
- VoiceMode routes the turn and responds

Manual controls:

```bash
voicemode voice control PTT_DOWN
voicemode voice control PTT_UP
```

Recommended when:

- you do not want an always-listening microphone
- you want precise start and stop control
- you prefer explicit turn ownership

### Conversational mode

Start directly in conversational mode:

```bash
voicemode voice run --mode conversational
```

Or switch a running runtime:

```bash
voicemode mode convo
```

Behavior:

- the runtime remains in a listening state
- voice activity detection determines when a turn begins and ends
- a new user turn can interrupt current playback

Recommended when:

- you want natural back-and-forth interaction
- you do not want to hold a push-to-talk key
- you want interruption support while VoiceMode is speaking

### Interrupt or barge in

Barge-in means a new user turn takes ownership from current speech or read
playback.

In practice:

- in conversational mode, start speaking while VoiceMode is talking
- in walkie-talkie mode, begin a new push-to-talk turn
- to stop output immediately without starting a new turn, run:

```bash
voicemode stop
```

Typical pattern:

1. `voicemode read README.md`
2. VoiceMode begins reading
3. interrupt the playback
4. run `voicemode voice control READ_SUMMARIZE`

## MCP Reference

| Tool | Purpose | Notes |
| --- | --- | --- |
| `mcp__voicemode__chat` | short conversation entry point | preferred shortcut |
| `mcp__voicemode__converse` | original conversation tool | same conversation surface |
| `mcp__voicemode__read` | send a file to the local runtime for read-aloud | runtime must be active |
| `mcp__voicemode__mode` | switch runtime mode | accepts `walk`, `walkie-talkie`, `convo`, `conversational` |
| `mcp__voicemode__stop` | stop current speech or playback | runtime must be active |
| `mcp__voicemode__service` | inspect or manage VoiceMode services | HTTP MCP server, Whisper, Kokoro, Connect |
| `mcp__voicemode__connect_status` | inspect remote Connect presence | separate from local runtime |

## Desktop Integration

Export the Hammerspoon configuration:

```bash
voicemode voice export-hammerspoon
```

Desktop shortcuts:

- push-to-talk uses `VOICEMODE_PTT_HOTKEY`
- `cmd+shift+1` switches to walkie-talkie
- `cmd+shift+2` switches to conversational
- `cmd+shift+.` stops speech
- `cmd+shift+/` continues reading

Hammerspoon requirements:

- `~/.hammerspoon/init.lua` must contain `require("voicemode")`
- the generated configuration is written to `~/.hammerspoon/voicemode.lua`

## Troubleshooting

Check runtime status:

```bash
voicemode voice status
```

Check runtime readiness and dependency health:

```bash
voicemode voice diag
```

If `voicemode read ...` fails:

- confirm that `voicemode voice run` is active
- confirm that the file path exists
- run `voicemode voice status`
- run `voicemode voice diag`

If your MCP client still shows only `connect_status`, `converse`, and `service`:

- the HTTP MCP server may have restarted while the client kept an older session
- reconnect or refresh the `voicemode` MCP client
- after reconnect, the live server should advertise `chat`, `read`, `mode`, and `stop`
