"""Tests for webapi_cli.config."""

from __future__ import annotations

import json
import stat
import tempfile
from pathlib import Path

from webapi_cli.config import Config, Profile


def _make_config(profiles=None, current=None):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    payload: dict = {"current_profile": current, "profiles": profiles or {}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return Config.load(path), path


def test_load_empty():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    path.write_text("{}", encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.current_profile is None
    assert cfg.profiles == {}


def test_load_missing_file():
    cfg = Config.load(Path("/no/such/config.json"))
    assert cfg.current_profile is None
    assert cfg.profiles == {}


def test_add_profile():
    cfg, path = _make_config()
    cfg.add(Profile("prod", "https://example.com", "tok"))
    assert cfg.profiles["prod"].server_url == "https://example.com"
    assert cfg.current_profile == "prod"  # first profile becomes current


def test_set_current():
    cfg, path = _make_config()
    cfg.add(Profile("dev", "https://dev.example.com"))
    cfg.add(Profile("prod", "https://example.com"))
    cfg.set_current("prod")
    assert cfg.current_profile == "prod"


def test_set_current_missing():
    cfg, path = _make_config()
    cfg.add(Profile("dev", "https://dev.example.com"))
    try:
        cfg.set_current("missing")
    except KeyError:
        pass
    else:
        assert False, "Should have raised KeyError"


def test_remove_profile():
    cfg, path = _make_config()
    cfg.add(Profile("dev", "https://dev.example.com"))
    cfg.add(Profile("prod", "https://example.com"))
    cfg.set_current("prod")
    cfg.remove("prod")
    assert "prod" not in cfg.profiles
    assert cfg.current_profile == "dev"


def test_remove_last_profile():
    cfg, path = _make_config()
    cfg.add(Profile("dev", "https://dev.example.com"))
    cfg.remove("dev")
    assert cfg.current_profile is None
    assert cfg.profiles == {}


def test_save_and_reload():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"
        # Override path
        cfg = Config(path=path)
        cfg.add(Profile("staging", "https://staging.example.com", "secret"))
        cfg.save()

        # Check permissions
        mode = path.stat().st_mode
        assert mode & stat.S_IRWXG == 0  # no group access
        assert mode & stat.S_IRWXO == 0  # no other access

        # Reload
        cfg2 = Config.load(path)
        assert cfg2.current_profile == "staging"
        assert cfg2.profiles["staging"].bearer_token == "secret"
        assert cfg2.profiles["staging"].server_url == "https://staging.example.com"


def test_get_profile():
    cfg, path = _make_config()
    cfg.add(Profile("dev", "https://dev.example.com"))
    p = cfg.get("dev")
    assert p is not None
    assert p.server_url == "https://dev.example.com"

    p2 = cfg.get()  # current profile
    assert p2 is p


def test_get_nonexistent():
    cfg, path = _make_config()
    assert cfg.get("nope") is None
    assert cfg.get() is None


def test_token_not_serialized_when_none():
    cfg, path = _make_config()
    cfg.add(Profile("dev", "https://dev.example.com", None))
    assert cfg.profiles["dev"].bearer_token is None

    # save + reload preserves None
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "cfg.json"
        cfg = Config(path=p)
        cfg.add(Profile("dev", "https://dev.example.com", None))
        cfg.save()
        cfg2 = Config.load(p)
        assert cfg2.profiles["dev"].bearer_token is None
