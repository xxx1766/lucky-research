"""Tests for :mod:`research_assistant.lit.publisher_bibtex`.

All network access is mocked. Browser tier is exercised via a fake
``cloakbrowser`` module installed into ``sys.modules``; we never launch a
real Chromium.
"""
from __future__ import annotations

import io
import sys
import types
import urllib.error

import pytest

from research_assistant.lit import publisher_bibtex as pb


# ---------------------------------------------------------------------------
# normalize_doi
# ---------------------------------------------------------------------------


def test_normalize_doi_bare():
    assert pb.normalize_doi("10.1145/3567955.3567958") == "10.1145/3567955.3567958"


@pytest.mark.parametrize(
    "wrapped",
    [
        "https://doi.org/10.1145/3567955.3567958",
        "http://doi.org/10.1145/3567955.3567958",
        "https://dx.doi.org/10.1145/3567955.3567958",
        "doi.org/10.1145/3567955.3567958",
        "doi:10.1145/3567955.3567958",
        "DOI:10.1145/3567955.3567958",
        "  10.1145/3567955.3567958  ",
    ],
)
def test_normalize_doi_strips_url_and_scheme(wrapped):
    assert pb.normalize_doi(wrapped) == "10.1145/3567955.3567958"


@pytest.mark.parametrize("bad", ["", " ", "not-a-doi", "10.1145", "foo/bar"])
def test_normalize_doi_rejects_garbage(bad):
    with pytest.raises(ValueError):
        pb.normalize_doi(bad)


# ---------------------------------------------------------------------------
# detect_publisher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "doi, publisher",
    [
        ("10.1145/3567955.3567958", "acm"),
        ("10.1109/SP.2024.00001", "ieee"),
        ("10.1007/s10994-024-99999-9", "springer"),
        ("10.1002/cpe.7234", "wiley"),
        ("10.1016/j.future.2024.01.001", "elsevier"),
        ("10.1126/science.adk0001", "science"),
        ("10.1038/s41586-024-99999-9", "nature"),
        ("10.18653/v1/2024.acl-long.123", "acl"),
        ("10.48550/arXiv.2401.12345", "arxiv"),
    ],
)
def test_detect_publisher_known_prefixes(doi, publisher):
    assert pb.detect_publisher(doi) == publisher


def test_detect_publisher_unknown_prefix_is_none():
    assert pb.detect_publisher("10.99999/foo.bar") is None


def test_detect_publisher_invalid_is_none():
    assert pb.detect_publisher("not-a-doi") is None
    assert pb.detect_publisher("") is None


def test_detect_publisher_accepts_url_form():
    assert pb.detect_publisher("https://doi.org/10.1145/abc") == "acm"


# ---------------------------------------------------------------------------
# looks_like_bibtex
# ---------------------------------------------------------------------------


def test_looks_like_bibtex_obvious():
    assert pb.looks_like_bibtex("@inproceedings{smith2024,\n  title={Foo},\n}")
    assert pb.looks_like_bibtex("\n\n  @article{x, year=2024}\n")


def test_looks_like_bibtex_accepts_bytes():
    assert pb.looks_like_bibtex(b"@misc{a, title={b}}")


def test_looks_like_bibtex_rejects_html():
    assert not pb.looks_like_bibtex("<!DOCTYPE html>\n<html>...")


def test_looks_like_bibtex_rejects_empty():
    assert not pb.looks_like_bibtex("")
    assert not pb.looks_like_bibtex(None)


def test_looks_like_bibtex_only_scans_first_1k():
    # @-symbol buried after 1 KiB shouldn't trigger a false positive.
    padding = "x" * 2048
    assert not pb.looks_like_bibtex(padding + "@article{trap}")


# ---------------------------------------------------------------------------
# Tier 1 — CrossRef
# ---------------------------------------------------------------------------


class _FakeResp:
    """Minimal stand-in for the object returned by urlopen()."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_crossref_returns_bibtex(monkeypatch):
    sample = b"@inproceedings{smith2024,\n  title = {Hello},\n}\n"
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["accept"] = req.get_header("Accept")
        return _FakeResp(sample)

    monkeypatch.setattr(pb.urllib.request, "urlopen", fake_urlopen)

    bib = pb.fetch_bibtex_via_crossref("10.1145/3567955.3567958")
    assert bib is not None
    assert "@inproceedings{smith2024" in bib
    assert captured["url"] == "https://api.crossref.org/works/10.1145/3567955.3567958/transform/application/x-bibtex"
    assert "bibtex" in (captured["accept"] or "").lower()


def test_crossref_404_returns_none(monkeypatch):
    def raise_404(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(pb.urllib.request, "urlopen", raise_404)
    assert pb.fetch_bibtex_via_crossref("10.1145/missing") is None


def test_crossref_timeout_returns_none(monkeypatch):
    def raise_timeout(req, timeout):
        raise TimeoutError("slow")

    monkeypatch.setattr(pb.urllib.request, "urlopen", raise_timeout)
    assert pb.fetch_bibtex_via_crossref("10.1145/whatever") is None


def test_crossref_non_bibtex_body_returns_none(monkeypatch):
    monkeypatch.setattr(
        pb.urllib.request,
        "urlopen",
        lambda req, timeout: _FakeResp(b"<!DOCTYPE html>\n<html>oops</html>"),
    )
    assert pb.fetch_bibtex_via_crossref("10.1145/abc") is None


def test_crossref_rejects_invalid_doi(monkeypatch):
    # Should never even reach urlopen.
    monkeypatch.setattr(
        pb.urllib.request,
        "urlopen",
        lambda *_a, **_k: pytest.fail("urlopen should not be called"),
    )
    assert pb.fetch_bibtex_via_crossref("not-a-doi") is None


# ---------------------------------------------------------------------------
# Tier 2 — doi.org content negotiation
# ---------------------------------------------------------------------------


def test_doi_content_negotiation_hits_doi_org(monkeypatch):
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return _FakeResp(b"@article{x, year=2024}")

    monkeypatch.setattr(pb.urllib.request, "urlopen", fake_urlopen)
    bib = pb.fetch_bibtex_via_doi_content_negotiation("10.1145/abc.def")
    assert bib == "@article{x, year=2024}"
    assert captured["url"] == "https://doi.org/10.1145/abc.def"


# ---------------------------------------------------------------------------
# Tier 3 — CloakBrowser
# ---------------------------------------------------------------------------


def _install_fake_cloakbrowser(monkeypatch, body: str):
    """Install a fake `cloakbrowser` module that returns ``body`` from page.goto()."""

    class _Response:
        def __init__(self, text: str):
            self._text = text

        def text(self) -> str:
            return self._text

    class _Page:
        def __init__(self, body: str):
            self._body = body

        def goto(self, url, timeout=None):
            self._last_url = url
            return _Response(self._body)

        def content(self) -> str:
            return self._body

    class _Context:
        def __init__(self, body: str):
            self._body = body

        def new_page(self) -> _Page:
            return _Page(self._body)

    class _Browser:
        def __init__(self, body: str):
            self._body = body
            self.closed = False

        def new_context(self, extra_http_headers=None) -> _Context:
            self.headers = extra_http_headers
            return _Context(self._body)

        def close(self) -> None:
            self.closed = True

    fake = types.ModuleType("cloakbrowser")
    fake.launch = lambda headless=True: _Browser(body)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cloakbrowser", fake)


def test_browser_returns_bibtex(monkeypatch):
    _install_fake_cloakbrowser(monkeypatch, "@inproceedings{foo, title={Bar}}")
    bib = pb.fetch_bibtex_via_browser("10.1145/abc")
    assert bib == "@inproceedings{foo, title={Bar}}"


def test_browser_rejects_html(monkeypatch):
    _install_fake_cloakbrowser(monkeypatch, "<!DOCTYPE html><html>...</html>")
    assert pb.fetch_bibtex_via_browser("10.1145/abc") is None


def test_browser_raises_on_missing_install(monkeypatch):
    # Ensure no cached cloakbrowser is present and force ImportError on import.
    monkeypatch.setitem(sys.modules, "cloakbrowser", None)
    with pytest.raises(ImportError, match="crawl"):
        pb.fetch_bibtex_via_browser("10.1145/abc")


def test_browser_invalid_doi_returns_none(monkeypatch):
    # Should bail before any cloakbrowser import.
    monkeypatch.setitem(sys.modules, "cloakbrowser", None)
    assert pb.fetch_bibtex_via_browser("not-a-doi") is None


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def test_orchestrator_returns_first_tier_hit(monkeypatch):
    monkeypatch.setattr(pb, "fetch_bibtex_via_crossref", lambda d, *, timeout: "@a{t1}")
    monkeypatch.setattr(
        pb, "fetch_bibtex_via_doi_content_negotiation", lambda *_a, **_k: pytest.fail("tier 2 should not run")
    )
    monkeypatch.setattr(
        pb, "fetch_bibtex_via_browser", lambda *_a, **_k: pytest.fail("tier 3 should not run")
    )
    assert pb.fetch_bibtex_from_publisher("10.1145/abc") == "@a{t1}"


def test_orchestrator_falls_to_tier_2(monkeypatch):
    monkeypatch.setattr(pb, "fetch_bibtex_via_crossref", lambda *_a, **_k: None)
    monkeypatch.setattr(pb, "fetch_bibtex_via_doi_content_negotiation", lambda *_a, **_k: "@a{t2}")
    monkeypatch.setattr(
        pb, "fetch_bibtex_via_browser", lambda *_a, **_k: pytest.fail("tier 3 should not run")
    )
    assert pb.fetch_bibtex_from_publisher("10.1145/abc") == "@a{t2}"


def test_orchestrator_falls_to_tier_3(monkeypatch):
    monkeypatch.setattr(pb, "fetch_bibtex_via_crossref", lambda *_a, **_k: None)
    monkeypatch.setattr(pb, "fetch_bibtex_via_doi_content_negotiation", lambda *_a, **_k: None)
    monkeypatch.setattr(pb, "fetch_bibtex_via_browser", lambda *_a, **_k: "@a{t3}")
    assert pb.fetch_bibtex_from_publisher("10.1145/abc") == "@a{t3}"


def test_orchestrator_swallows_missing_cloakbrowser(monkeypatch):
    monkeypatch.setattr(pb, "fetch_bibtex_via_crossref", lambda *_a, **_k: None)
    monkeypatch.setattr(pb, "fetch_bibtex_via_doi_content_negotiation", lambda *_a, **_k: None)

    def raise_missing(*_a, **_k):
        raise ImportError("crawl extra not installed")

    monkeypatch.setattr(pb, "fetch_bibtex_via_browser", raise_missing)
    assert pb.fetch_bibtex_from_publisher("10.1145/abc") is None


def test_orchestrator_all_tiers_fail(monkeypatch):
    monkeypatch.setattr(pb, "fetch_bibtex_via_crossref", lambda *_a, **_k: None)
    monkeypatch.setattr(pb, "fetch_bibtex_via_doi_content_negotiation", lambda *_a, **_k: None)
    monkeypatch.setattr(pb, "fetch_bibtex_via_browser", lambda *_a, **_k: None)
    assert pb.fetch_bibtex_from_publisher("10.1145/abc") is None


def test_orchestrator_prefer_browser_skips_tiers_1_and_2(monkeypatch):
    monkeypatch.setattr(
        pb, "fetch_bibtex_via_crossref", lambda *_a, **_k: pytest.fail("tier 1 should be skipped")
    )
    monkeypatch.setattr(
        pb,
        "fetch_bibtex_via_doi_content_negotiation",
        lambda *_a, **_k: pytest.fail("tier 2 should be skipped"),
    )
    monkeypatch.setattr(pb, "fetch_bibtex_via_browser", lambda *_a, **_k: "@a{browser}")
    assert pb.fetch_bibtex_from_publisher("10.1145/abc", prefer_browser=True) == "@a{browser}"


def test_orchestrator_prefer_browser_surfaces_import_error(monkeypatch):
    """When the user explicitly asks for browser, the ImportError must propagate
    so they see the install hint."""
    def raise_missing(*_a, **_k):
        raise ImportError("install cloakbrowser")

    monkeypatch.setattr(pb, "fetch_bibtex_via_browser", raise_missing)
    with pytest.raises(ImportError, match="install cloakbrowser"):
        pb.fetch_bibtex_from_publisher("10.1145/abc", prefer_browser=True)
