"""Profile and credential management for the WebAPI CLI.

Stores server profiles and Bearer tokens in
``~/.config/webapi-cli/config.json`` with ``0600`` permissions.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    """Return the config directory, respecting ``XDG_CONFIG_HOME``."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "webapi-cli"


def _config_path() -> Path:
    return _config_dir() / "config.json"


@dataclass
class Profile:
    """A named server profile with an optional Bearer token."""

    name: str
    server_url: str
    bearer_token: str | None = None
    default: bool = False


@dataclass
class Config:
    """Manages the config file on disk."""

    path: Path = field(default_factory=_config_path)
    current_profile: str | None = None
    profiles: dict[str, Profile] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or _config_path()
        if not path.exists():
            return cls(path=path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(path=path)

        profiles: dict[str, Profile] = {}
        for name, pdata in raw.get("profiles", {}).items():
            profiles[name] = Profile(
                name=name,
                server_url=pdata.get("server_url", ""),
                bearer_token=pdata.get("bearer_token"),
                default=pdata.get("default", False),
            )

        return cls(
            path=path,
            current_profile=raw.get("current_profile"),
            profiles=profiles,
        )

    def save(self) -> None:
        _config_dir().mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"current_profile": self.current_profile, "profiles": {}}
        for name, profile in self.profiles.items():
            payload["profiles"][name] = {
                "server_url": profile.server_url,
                "bearer_token": profile.bearer_token,
                "default": profile.default,
            }

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
        tmp.replace(self.path)

    # ------------------------------------------------------------------
    # Profile operations
    # ------------------------------------------------------------------

    def get(self, name: str | None = None) -> Profile | None:
        """Return a profile by name, or the current profile when name is None."""
        key = name or self.current_profile
        if key is None:
            return None
        return self.profiles.get(key)

    def set_current(self, name: str) -> None:
        if name not in self.profiles:
            raise KeyError(f"Profile '{name}' not found")
        self.current_profile = name

    def add(self, profile: Profile) -> None:
        self.profiles[profile.name] = profile
        if len(self.profiles) == 1:
            profile.default = True
            self.current_profile = profile.name

    def remove(self, name: str) -> None:
        del self.profiles[name]
        if self.current_profile == name:
            self.current_profile = next(iter(self.profiles), None) if self.profiles else None
            if self.current_profile and self.profiles:
                self.profiles[self.current_profile].default = True
