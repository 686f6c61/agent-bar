"""Hook installer tests: idempotent, reversible, no clobbering."""

import json

from agent_bar import hooks_install as hi


def test_kimi_install_and_uninstall(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "kimi"
    cfg_dir.mkdir()
    cfg = cfg_dir / "config.toml"
    cfg.write_text('model = "k2"\n')
    monkeypatch.setattr(hi.paths, "kimi_home", lambda: cfg_dir)

    hi.install_kimi("/usr/bin/agent-bar")
    text = cfg.read_text()
    assert 'model = "k2"' in text  # original content preserved
    assert text.count("[[hooks]]") == len(hi.KIMI_EVENTS)
    assert 'event = "PermissionRequest"' in text

    hi.install_kimi("/usr/bin/agent-bar")  # idempotent
    assert cfg.read_text().count("[[hooks]]") == len(hi.KIMI_EVENTS)

    hi.uninstall_kimi()
    text = cfg.read_text()
    assert "[[hooks]]" not in text and 'model = "k2"' in text


def test_claude_install_merges_and_uninstalls(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "claude"
    cfg_dir.mkdir()
    cfg = cfg_dir / "settings.json"
    cfg.write_text(json.dumps({"model": "opus"}))
    monkeypatch.setattr(hi.paths, "claude_home", lambda: cfg_dir)

    hi.install_claude("/usr/bin/agent-bar")
    data = json.loads(cfg.read_text())
    assert data["model"] == "opus"
    assert "PermissionRequest" in data["hooks"]

    hi.install_claude("/usr/bin/agent-bar")  # idempotent
    data = json.loads(cfg.read_text())
    assert len(data["hooks"]["Stop"]) == 1

    hi.uninstall_claude()
    data = json.loads(cfg.read_text())
    assert "hooks" not in data and data["model"] == "opus"


def test_codex_install_refuses_existing_notify(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "codex"
    cfg_dir.mkdir()
    cfg = cfg_dir / "config.toml"
    cfg.write_text('notify = ["other-tool"]\n')
    monkeypatch.setattr(hi.paths, "codex_home", lambda: cfg_dir)

    import pytest
    with pytest.raises(RuntimeError):
        hi.install_codex("/usr/bin/agent-bar")
    assert 'notify = ["other-tool"]' in cfg.read_text()  # untouched


def test_codex_install_and_uninstall(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "codex"
    cfg_dir.mkdir()
    cfg = cfg_dir / "config.toml"
    cfg.write_text('model = "gpt-5"\n')
    monkeypatch.setattr(hi.paths, "codex_home", lambda: cfg_dir)

    hi.install_codex("/usr/bin/agent-bar")
    text = cfg.read_text()
    assert '"hook", "--cli", "codex"' in text and 'model = "gpt-5"' in text
    hi.uninstall_codex()
    assert "notify" not in cfg.read_text()


def test_backup_created_once(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "kimi"
    cfg_dir.mkdir()
    cfg = cfg_dir / "config.toml"
    cfg.write_text('model = "k2"\n')
    monkeypatch.setattr(hi.paths, "kimi_home", lambda: cfg_dir)
    hi.install_kimi("/usr/bin/agent-bar")
    bak = cfg_dir / "config.toml.agent-bar.bak"
    assert bak.read_text() == 'model = "k2"\n'
