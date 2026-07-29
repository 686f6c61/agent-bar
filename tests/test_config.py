"""Config loading: defaults, user overrides, invalid values."""

from agent_bar.config import Config


def test_defaults_written_on_first_load(tmp_path):
    path = tmp_path / "config.toml"
    cfg = Config.load(path)
    assert cfg.style == "symbolic" and cfg.show_label and cfg.sound
    assert path.exists()  # default file created for discoverability
    assert "[panel]" in path.read_text()


def test_user_overrides(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[panel]\nstyle = "color"\nshow_label = false\n'
                    'pulse_ms = 300\n\n[alerts]\nsound = false\n')
    cfg = Config.load(path)
    assert cfg.style == "color"
    assert cfg.show_label is False
    assert cfg.pulse_ms == 300
    assert cfg.sound is False


def test_invalid_values_fall_back(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[panel]\nstyle = "neon"\npulse_ms = 5\n')
    cfg = Config.load(path)
    assert cfg.style == "symbolic"
    assert cfg.pulse_ms == 150  # clamped to minimum


def test_garbage_file_uses_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("this is = = not toml [[[")
    assert Config.load(path).style == "symbolic"
