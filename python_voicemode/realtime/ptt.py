"""Hammerspoon integration helpers for push-to-talk control."""

from __future__ import annotations

from pathlib import Path

from .config import RealtimeVoiceConfig


def _lua_string_list(values: list[str]) -> str:
    return "{" + ", ".join(f'"{value}"' for value in values) + "}"


def render_hammerspoon_config(config: RealtimeVoiceConfig) -> str:
    """Render a Hammerspoon config for push-to-talk and status."""

    url = config.control_base_url
    modifiers = []
    key = "space"
    for part in config.ptt_hotkey.split("+"):
        clean = part.strip().lower()
        if clean in {"cmd", "shift", "ctrl", "alt", "option"}:
            modifiers.append(clean)
        elif clean:
            key = clean
    return f"""local json = hs.json
local http = hs.http
local timer = hs.timer

local base = "{url}"
local statusItem = hs.menubar.new()

local function titleForStatus(payload)
  local state = payload.state or "?"
  if state == "LISTENING" then
    return "VM LISTEN"
  elseif state == "RECORDING" then
    return "VM REC"
  elseif state == "WAITING_LOCAL" or state == "WAITING_CODEX" then
    return "VM THINK"
  elseif state == "PLAYING_TTS" then
    return "VM SPEAK"
  elseif state == "READING_CHUNK" then
    return "VM READ"
  elseif state == "ERROR" then
    return "VM ERR"
  end
  return "VM " .. state
end

local function setTransientStatus(title, tooltip)
  statusItem:setTitle(title)
  if tooltip then
    statusItem:setTooltip(tooltip)
  end
end

local function post(path, body)
  return http.asyncPost(base .. path, json.encode(body or {{}}), {{["Content-Type"] = "application/json"}}, function() end)
end

local function refreshStatus()
  http.asyncGet(base .. "/status", nil, function(code, body)
    if code ~= 200 then
      statusItem:setTitle("VM ERR")
      statusItem:setTooltip("VoiceMode runtime unreachable")
      return
    end
    local payload = json.decode(body)
    statusItem:setTitle(titleForStatus(payload))
    statusItem:setTooltip(string.format(
      "mode=%s\\nstate=%s\\nmuted=%s\\nreading=%s",
      payload.mode or "?",
      payload.state or "?",
      tostring(payload.muted),
      payload.reading_document or "-"
    ))
  end)
end

hs.hotkey.bind({_lua_string_list(modifiers)}, "{key}", function()
  setTransientStatus("VM REC", "Push-to-talk recording")
  post("/control", {{event = "PTT_DOWN"}})
end, function()
  setTransientStatus("VM THINK", "Processing the recorded turn")
  post("/control", {{event = "PTT_UP"}})
end)

hs.hotkey.bind({{"cmd", "shift"}}, "1", function()
  setTransientStatus("VM IDLE", "Switched to walkie-talkie mode")
  post("/control", {{event = "MODE_SWITCH", mode = "walkie-talkie"}})
end)

hs.hotkey.bind({{"cmd", "shift"}}, "2", function()
  setTransientStatus("VM LISTEN", "Switched to conversational mode")
  post("/control", {{event = "MODE_SWITCH", mode = "conversational"}})
end)

hs.hotkey.bind({{"cmd", "shift"}}, ".", function()
  setTransientStatus("VM IDLE", "Speech stopped")
  post("/control", {{event = "TTS_STOP"}})
end)

hs.hotkey.bind({{"cmd", "shift"}}, "/", function()
  setTransientStatus("VM READ", "Continuing read-aloud playback")
  post("/control", {{event = "READ_CONTINUE"}})
end)

refreshStatus()
timer.doEvery(2, refreshStatus)
"""


def write_hammerspoon_config(config: RealtimeVoiceConfig, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_hammerspoon_config(config), encoding="utf-8")
    return output_path
