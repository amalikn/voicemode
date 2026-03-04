# VoiceMode

> Natural voice conversations with Claude Code (and other MCP capable agents)

[![PyPI Downloads](https://static.pepy.tech/badge/voice-mode)](https://pepy.tech/project/voice-mode)
[![PyPI Downloads](https://static.pepy.tech/badge/voice-mode/month)](https://pepy.tech/project/voice-mode)
[![PyPI Downloads](https://static.pepy.tech/badge/voice-mode/week)](https://pepy.tech/project/voice-mode)

VoiceMode enables natural voice conversations with Claude Code. Voice isn't about replacing typing - it's about being available when typing isn't.

**Perfect for:**

- Walking to your next meeting
- Cooking while debugging
- Giving your eyes a break after hours of screen time
- Holding a coffee (or a dog)
- Any moment when your hands or eyes are busy

## See It In Action

[![VoiceMode Demo](https://img.youtube.com/vi/cYdwOD_-dQc/maxresdefault.jpg)](https://www.youtube.com/watch?v=cYdwOD_-dQc)

## Quick Start

**Requirements:** Computer with microphone and speakers

### Option 1: Claude Code Plugin (Recommended)

The fastest way for Claude Code users to get started:

```bash
# Add the VoiceMode marketplace
claude plugin marketplace add mbailey/voicemode

# Install VoiceMode plugin
claude plugin install voicemode@voicemode

## Install dependencies (CLI, Local Voice Services)

/voicemode:install

# Start talking!
/voicemode:converse
```

### Option 2: Python installer package

Installs dependencies and the VoiceMode Python package.

```bash
# Install UV package manager (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the installer (sets up dependencies and local voice services)
uvx voice-mode-install

# Add to Claude Code
claude mcp add --scope user voicemode -- uvx --refresh voice-mode

# Optional: Add OpenAI API key as fallback for local services
export OPENAI_API_KEY=your-openai-key

# Start a conversation
claude converse
```

### Option 3: Codex (Repo-pinned MCP, Recommended)

Use this when you want VoiceMode tools directly in Codex without the Claude plugin.

```bash
# 1) Install system dependencies (macOS)
brew install ffmpeg node portaudio

# 2) Install UV package manager (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3) Install VoiceMode + local voice service dependencies
uvx voice-mode-install
```

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.voicemode]
command = "bash"
args = ["-lc", "mkdir -p /Volumes/Data/_ai/mcp-data/voicemode && cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode && exec uv run voicemode"]
startup_timeout_sec = 120

[mcp_servers.voicemode.env]
VOICEMODE_DATA_DIR = "/Volumes/Data/_ai/mcp-data/voicemode"
VOICEMODE_LOG_DIR = "/Volumes/Data/_ai/mcp-data/voicemode/logs"
VOICEMODE_CACHE_DIR = "/Volumes/Data/_ai/mcp-data/voicemode/cache"
VOICEMODE_PREFER_LOCAL = "true"
# OPENAI_API_KEY = "your-openai-key"
```

Then:

```bash
# 4) Restart Codex and verify MCP registration
codex mcp list

# 5) Install/start local services (one-time install, then start)
cd /Volumes/Data/_ai/_mcp/mcp_stuff/voicemode
uv run voicemode service install whisper
uv run voicemode service install kokoro
uv run voicemode service start whisper
uv run voicemode service start kokoro
```

In Codex, test tool calls:

- `mcp__voicemode__service` with `service_name="whisper"` and `action="status"`
- `mcp__voicemode__service` with `service_name="kokoro"` and `action="status"`
- `mcp__voicemode__converse` with `message="VoiceMode test"` and `wait_for_response="true"`

If STT/TTS fails on macOS, check microphone permissions for your terminal app in:
`System Settings -> Privacy & Security -> Microphone`

`uvx` MCP variant (instead of repo-pinned):

```toml
[mcp_servers.voicemode]
command = "bash"
args = ["-lc", "mkdir -p /Volumes/Data/_ai/mcp-data/voicemode && exec uvx --refresh voice-mode"]
startup_timeout_sec = 120
```

Known issue (first run):

- Kokoro may stay in `starting up` for a few minutes on first boot while model assets are prepared.
- During this window, `mcp__voicemode__converse` may fail TTS unless `OPENAI_API_KEY` is set for fallback.
- Workarounds:
  - Wait for `mcp__voicemode__service` (`service_name="kokoro"`, `action="status"`) to report running.
  - Or call `mcp__voicemode__converse` with `skip_tts="true"` to test STT-only flow immediately.

For manual setup, see the [Getting Started Guide](docs/tutorials/getting-started.md).

## Features

- **Natural conversations** - speak naturally, hear responses immediately
- **Works offline** - optional local voice services (Whisper STT, Kokoro TTS)
- **Low latency** - fast enough to feel like a real conversation
- **Smart silence detection** - stops recording when you stop speaking
- **Privacy options** - run entirely locally or use cloud services

## MCP Capabilities

VoiceMode exposes the following MCP tool capabilities:

- Conversation: `mcp__voicemode__converse`
- Service management: `mcp__voicemode__service`
- Connect presence/status: `mcp__voicemode__connect_status`
- Diagnostics: `mcp__voicemode__voice_mode_info`, `mcp__voicemode__check_audio_dependencies`
- Devices/voices: `mcp__voicemode__voice_status`, `mcp__voicemode__check_audio_devices`, `mcp__voicemode__list_tts_voices`
- Provider registry: `mcp__voicemode__refresh_provider_registry`, `mcp__voicemode__get_provider_details`, `mcp__voicemode__voice_registry`
- Statistics: `mcp__voicemode__voice_statistics`, `mcp__voicemode__voice_statistics_summary`, `mcp__voicemode__voice_statistics_recent`, `mcp__voicemode__voice_statistics_export`, `mcp__voicemode__voice_statistics_reset`
- Configuration management: `mcp__voicemode__show_config_files`, `mcp__voicemode__list_config_keys`, `mcp__voicemode__config_reload`, `mcp__voicemode__update_config`
- Local service installers: `mcp__voicemode__whisper_install`, `mcp__voicemode__whisper_uninstall`, `mcp__voicemode__whisper_model_install`, `mcp__voicemode__kokoro_install`, `mcp__voicemode__kokoro_uninstall`

Operational behavior:

- Uses local Whisper/Kokoro when available (default preference).
- Falls back to OpenAI-compatible cloud providers when local services are unavailable and credentials exist.
- Supports STT-only verification with `skip_tts=true` during TTS warmup/troubleshooting.

## Compatibility

**Platforms:** Linux, macOS, Windows (WSL), NixOS
**Python:** 3.10-3.14

## Configuration

VoiceMode works out of the box. For customization:

```bash
# Set OpenAI API key (if using cloud services)
export OPENAI_API_KEY="your-key"

# Or configure via file
voicemode config edit
```

See the [Configuration Guide](docs/guides/configuration.md) for all options.

## Permissions Setup (Optional)

To use VoiceMode without permission prompts, add to `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__voicemode__converse",
      "mcp__voicemode__service"
    ]
  }
}
```

See the [Permissions Guide](docs/guides/permissions.md) for more options.

## Local Voice Services

For privacy or offline use, install local speech services:

- **[Whisper.cpp](docs/guides/whisper-setup.md)** - Local speech-to-text
- **[Kokoro](docs/guides/kokoro-setup.md)** - Local text-to-speech with multiple voices

These provide the same API as OpenAI, so VoiceMode switches seamlessly between them.

## Installation Details

<details>
<summary><strong>System Dependencies by Platform</strong></summary>

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y ffmpeg gcc libasound2-dev libasound2-plugins libportaudio2 portaudio19-dev pulseaudio pulseaudio-utils python3-dev
```

**WSL2 users**: The pulseaudio packages above are required for microphone access.

#### Fedora/RHEL

```bash
sudo dnf install alsa-lib-devel ffmpeg gcc portaudio portaudio-devel python3-devel
```

#### macOS

```bash
brew install ffmpeg node portaudio
```

#### NixOS

```bash
# Use development shell
nix develop github:mbailey/voicemode

# Or install system-wide
nix profile install github:mbailey/voicemode
```

</details>

<details>
<summary><strong>Alternative Installation Methods</strong></summary>

#### From source

```bash
git clone https://github.com/mbailey/voicemode.git
cd voicemode
uv tool install -e .
```

#### NixOS system-wide

```nix
# In /etc/nixos/configuration.nix
environment.systemPackages = [
  (builtins.getFlake "github:mbailey/voicemode").packages.${pkgs.system}.default
];
```

</details>

## Troubleshooting


| Problem | Solution |
|---------|----------|
| No microphone access | Check terminal/app permissions. WSL2 needs pulseaudio packages. |
| UV not found | Run `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| OpenAI API error | Verify `OPENAI_API_KEY` is set correctly |
| No audio output | Check system audio settings and available devices |


### Save Audio for Debugging

```bash
export VOICEMODE_SAVE_AUDIO=true
# Files saved to /Volumes/Data/_ai/mcp-data/voicemode/audio/YYYY/MM/
```

## Documentation

- [Getting Started](docs/tutorials/getting-started.md) - Full setup guide
- [Configuration](docs/guides/configuration.md) - All environment variables
- [Whisper Setup](docs/guides/whisper-setup.md) - Local speech-to-text
- [Kokoro Setup](docs/guides/kokoro-setup.md) - Local text-to-speech
- [Codex Voice Prefill Spec](docs/architecture/codex-voice-prefill-draft-spec.md) - Draft-prefill UX implementation plan for voice-to-compose flow
- [Development Setup](docs/tutorials/development-setup.md) - Contributing guide

Full documentation: [voice-mode.readthedocs.io](https://voice-mode.readthedocs.io)

## Links

- **Website**: [getvoicemode.com](https://getvoicemode.com)
- **GitHub**: [github.com/mbailey/voicemode](https://github.com/mbailey/voicemode)
- **PyPI**: [pypi.org/project/voice-mode](https://pypi.org/project/voice-mode/)
- **YouTube**: [@getvoicemode](https://youtube.com/@getvoicemode)
- **Twitter/X**: [@getvoicemode](https://twitter.com/getvoicemode)
- **Newsletter**: [![Subscribe](https://img.shields.io/badge/Subscribe-Newsletter-orange?style=flat-square)](https://buttondown.com/voicemode)

## License

MIT - A [Failmode](https://failmode.com) Project

---
mcp-name: com.failmode/voicemode
