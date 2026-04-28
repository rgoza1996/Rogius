"""
Settings persistence for Rogius TUI

Save/load configuration to disk, matching webapp's localStorage behavior.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class TUISettings:
    """Settings for the TUI application."""
    # API Settings
    chat_endpoint: str = "http://localhost:1234/v1/chat/completions"
    chat_api_key: str = ""
    chat_model: str = "llama-3.1-8b"
    chat_context_length: int = 4096
    tts_endpoint: str = "http://100.71.89.62:8880/v1/audio/speech"
    tts_api_key: str = ""
    tts_voice: str = "af_bella"
    auto_play_audio: bool = False
    
    # UI Settings
    theme: str = "dark"
    sidebar_width: int = 25  # percentage
    show_terminal_panel: bool = True
    
    # Behavior Settings
    auto_execute_multistep: bool = True
    max_retries: int = 999
    confirm_destructive: bool = True
    
    # RAG Settings (LlamaIndex + Local Embeddings)
    rag_enabled: bool = True
    rag_embedding_model: str = "nomic-embed-text"  # LM Studio default embedding model
    rag_embedding_endpoint: str = "http://localhost:1234"  # LM Studio default (use :11434 for Ollama)
    rag_api_type: str = "openai"  # "openai" for LM Studio, "ollama" for Ollama
    rag_auto_index: bool = True  # Auto-index project on startup
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TUISettings":
        # Only use known fields, ignore extras
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


def get_config_dir() -> Path:
    """Get the configuration directory for the current platform."""
    if os.name == 'nt':  # Windows
        app_data = os.environ.get('APPDATA')
        if app_data:
            config_dir = Path(app_data) / "Rogius"
        else:
            config_dir = Path.home() / "AppData" / "Roaming" / "Rogius"
    else:  # Linux/macOS
        xdg_config = os.environ.get('XDG_CONFIG_HOME')
        if xdg_config:
            config_dir = Path(xdg_config) / "rogius"
        else:
            config_dir = Path.home() / ".config" / "rogius"
    
    return config_dir


def get_settings_path() -> Path:
    """Get the full path to the settings file."""
    return get_config_dir() / "settings.json"


def get_plans_dir() -> Path:
    """Get the directory for saved plans."""
    plans_dir = get_config_dir() / "plans"
    return plans_dir


def ensure_config_dir() -> Path:
    """Ensure the config directory exists."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Also create plans subdirectory
    plans_dir = config_dir / "plans"
    plans_dir.mkdir(exist_ok=True)
    
    return config_dir


def save_settings(settings: TUISettings) -> None:
    """Save settings to disk."""
    ensure_config_dir()
    settings_path = get_settings_path()
    
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings.to_dict(), f, indent=2)


def load_settings() -> TUISettings:
    """Load settings from disk, or return defaults."""
    settings_path = get_settings_path()
    
    if not settings_path.exists():
        return TUISettings()
    
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return TUISettings.from_dict(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Return defaults if file is corrupted
        return TUISettings()


def update_settings(**kwargs) -> TUISettings:
    """Update specific settings and save."""
    settings = load_settings()
    
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    save_settings(settings)
    return settings


def reset_settings() -> TUISettings:
    """Reset all settings to defaults."""
    settings = TUISettings()
    save_settings(settings)
    return settings


def export_settings(path: Path) -> None:
    """Export settings to a specific path."""
    settings = load_settings()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings.to_dict(), f, indent=2)


def import_settings(path: Path) -> TUISettings:
    """Import settings from a specific path."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    settings = TUISettings.from_dict(data)
    save_settings(settings)
    return settings


def get_api_config_from_settings(settings: Optional[TUISettings] = None) -> dict:
    """Convert TUI settings to AI client API config."""
    if settings is None:
        settings = load_settings()
    
    from ai_client import APIConfig
    
    return APIConfig(
        chat_endpoint=settings.chat_endpoint,
        chat_api_key=settings.chat_api_key,
        chat_model=settings.chat_model,
        chat_context_length=settings.chat_context_length,
        tts_endpoint=settings.tts_endpoint,
        tts_api_key=settings.tts_api_key,
        tts_voice=settings.tts_voice,
        auto_play_audio=settings.auto_play_audio
    )


def save_plan_to_history(plan_data: dict) -> None:
    """Save a completed plan to history."""
    ensure_config_dir()
    plans_dir = get_plans_dir()
    
    # Use plan ID as filename
    plan_id = plan_data.get('id', 'unknown')
    plan_path = plans_dir / f"{plan_id}.json"
    
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump(plan_data, f, indent=2)


def load_saved_plans() -> list[dict]:
    """Load all saved plans."""
    plans_dir = get_plans_dir()
    
    if not plans_dir.exists():
        return []
    
    plans = []
    for plan_file in plans_dir.glob("*.json"):
        try:
            with open(plan_file, 'r', encoding='utf-8') as f:
                plans.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue
    
    return plans


if __name__ == "__main__":
    # Test settings functionality
    print("Testing Settings Module")
    print("=" * 50)
    
    # Show config directory
    config_dir = get_config_dir()
    print(f"\nConfig directory: {config_dir}")
    
    # Test saving/loading
    print("\nTest 1: Save and load settings")
    settings = TUISettings(
        chat_model="test-model",
        chat_endpoint="http://test:1234",
        tts_voice="test_voice"
    )
    save_settings(settings)
    print("  Settings saved")
    
    loaded = load_settings()
    print(f"  Loaded chat_model: {loaded.chat_model}")
    print(f"  Loaded chat_endpoint: {loaded.chat_endpoint}")
    print(f"  Loaded tts_voice: {loaded.tts_voice}")
    
    # Test update
    print("\nTest 2: Update settings")
    update_settings(chat_model="updated-model")
    updated = load_settings()
    print(f"  Updated chat_model: {updated.chat_model}")
    
    # Test reset
    print("\nTest 3: Reset settings")
    reset_settings()
    reset = load_settings()
    print(f"  Reset chat_model: {reset.chat_model}")
    print(f"  Reset to default: {reset.chat_model == TUISettings().chat_model}")

    print("\n" + "=" * 50)
    print("All tests complete!")
