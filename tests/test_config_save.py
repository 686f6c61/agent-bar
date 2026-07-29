"""Config.save roundtrip: what the Settings menu writes must load back."""

from agent_bar.config import Config


def test_save_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    cfg = Config(style="color", show_label=False, pulse_ms=900,
                 spinner=False, notifications=False, sound=False)
    cfg.save(path)
    back = Config.load(path)
    assert back.style == "color"
    assert back.show_label is False
    assert back.pulse_ms == 900
    assert back.spinner is False
    assert back.notifications is False
    assert back.sound is False


def test_saved_file_keeps_comments(tmp_path):
    path = tmp_path / "config.toml"
    Config().save(path)
    text = path.read_text()
    assert "Icon theme" in text and "[alerts]" in text


def test_load_missing_creates_documented_default(tmp_path):
    path = tmp_path / "sub" / "config.toml"
    cfg = Config.load(path)
    assert cfg.style == "symbolic"
    assert path.exists() and 'style = "symbolic"' in path.read_text()
