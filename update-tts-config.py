#!/usr/bin/env python3
"""Update TTS configuration to use local server."""
import sys
import json
from pathlib import Path

# Settings file location (Windows)
import os
app_data = os.environ.get('APPDATA')
if app_data:
    config_dir = Path(app_data) / "Rogius"
else:
    config_dir = Path.home() / "AppData" / "Roaming" / "Rogius"

settings_path = config_dir / "settings.json"

# Ensure directory exists
config_dir.mkdir(parents=True, exist_ok=True)

# Load or create settings
if settings_path.exists():
    with open(settings_path, 'r') as f:
        settings = json.load(f)
else:
    settings = {}

# Update TTS endpoint to local
old_endpoint = settings.get('tts_endpoint', 'not set')
settings['tts_endpoint'] = 'http://localhost:8880/v1/audio/speech'
settings['tts_voice'] = settings.get('tts_voice', 'af_bella')
settings['auto_play_audio'] = settings.get('auto_play_audio', False)

# Save settings
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print(f"Updated TTS endpoint:")
print(f"  Old: {old_endpoint}")
print(f"  New: {settings['tts_endpoint']}")
print(f"Settings saved to: {settings_path}")
