"""Optional D2 scaffold tests — graceful fallback if `d2` binary is missing."""
from pathlib import Path


from research_assistant.figures import d2 as fd2


def test_d2_available_returns_bool():
    out = fd2.d2_available()
    assert isinstance(out, bool)


def test_scaffold_returns_none_when_binary_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(fd2, "_which_d2", lambda: None)
    out = fd2.scaffold_to_svg(d2_source="boxA -> boxB", out_path=tmp_path / "x.svg")
    assert out is None  # caller falls back to raw SVG


def test_scaffold_invokes_d2_when_present(monkeypatch, tmp_path: Path):
    """Mock subprocess.run so we don't depend on `d2` actually being installed."""
    monkeypatch.setattr(fd2, "_which_d2", lambda: "/usr/local/bin/d2")
    called = {}
    def fake_run(cmd, **kw):
        called["cmd"] = cmd
        # Simulate d2 writing the output file.
        Path(cmd[-1]).write_text("<svg/>")
        class R:
            returncode = 0
            stderr = ""
        return R()
    monkeypatch.setattr(fd2.subprocess, "run", fake_run)
    out_path = tmp_path / "x.svg"
    result = fd2.scaffold_to_svg(d2_source="boxA -> boxB", out_path=out_path)
    assert result == out_path
    assert out_path.exists()
    assert called["cmd"][0] == "/usr/local/bin/d2"


def test_scaffold_returns_none_on_d2_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(fd2, "_which_d2", lambda: "/usr/local/bin/d2")
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stderr = "syntax error"
        return R()
    monkeypatch.setattr(fd2.subprocess, "run", fake_run)
    out = fd2.scaffold_to_svg(d2_source="!!! bad !!!", out_path=tmp_path / "x.svg")
    assert out is None
