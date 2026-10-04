import pytest


@pytest.fixture(autouse=True)
def no_user_presets(monkeypatch, tmp_path):
    """Keep a developer's own presets.toml out of every test."""
    monkeypatch.setenv("FLIGHT_TRACER_PRESETS", str(tmp_path / "absent.toml"))
