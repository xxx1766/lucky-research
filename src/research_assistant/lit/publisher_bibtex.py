"""Fetch canonical BibTeX from publishers given a DOI.

Three-tier strategy, cheapest first:

1. **CrossRef API** (``api.crossref.org``) — content-negotiation endpoint.
   Covers ~95% of registered DOIs (ACM, IEEE, Springer, Wiley, Elsevier, …).
   Plain HTTP via ``urllib`` — no extra deps.
2. **DOI content negotiation** (``doi.org`` with ``Accept: application/x-bibtex``).
   Some publishers honor this when CrossRef doesn't have a clean record.
   Plain HTTP via ``urllib``.
3. **CloakBrowser** — anti-bot stealth Chromium. Optional dep
   (``pip install -e ".[crawl]"``). Used for sites that block plain HTTP
   (Cloudflare / FingerprintJS / reCAPTCHA-protected publisher pages).

Top-level entry point is :func:`fetch_bibtex_from_publisher`. The lower-tier
functions are also exported so callers can opt into a specific path.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

__all__ = [
    "detect_publisher",
    "normalize_doi",
    "looks_like_bibtex",
    "fetch_bibtex_via_crossref",
    "fetch_bibtex_via_doi_content_negotiation",
    "fetch_bibtex_via_browser",
    "fetch_bibtex_from_publisher",
]

# ---------------------------------------------------------------------------
# Publisher detection (by DOI registrant prefix)
# ---------------------------------------------------------------------------

_PUBLISHER_BY_DOI_PREFIX: dict[str, str] = {
    "10.1145": "acm",
    "10.1109": "ieee",
    "10.1007": "springer",
    "10.1002": "wiley",
    "10.1016": "elsevier",
    "10.1126": "science",
    "10.1038": "nature",
    "10.18653": "acl",       # ACL Anthology
    "10.48550": "arxiv",     # arXiv-issued DOIs
}

_DOI_URL_PREFIXES: tuple[str, ...] = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi.org/",
    "doi:",
)
# `DOI:` (uppercase) is folded into `doi:` by the case-insensitive match in
# :func:`normalize_doi`, so it's not listed separately.

_BIBTEX_HEAD_RE = re.compile(r"^\s*@\w+\s*\{", re.MULTILINE)

_USER_AGENT = "lucky-research/0.0.1 (https://github.com/xxx1766/lucky-research)"

# Cap HTTP body reads so a misbehaving publisher serving multi-MB HTML can't
# eat memory. BibTeX entries top out at a few KiB even for papers with 30+
# authors; 64 KiB is generous.
_MAX_BIBTEX_BYTES = 64 * 1024


def normalize_doi(value: str) -> str:
    """Strip ``https://doi.org/`` / ``doi:`` wrappers; return the bare DOI.

    Raises ``ValueError`` if the input is empty or doesn't look like a DOI
    (must contain ``/`` and start with ``10.``).
    """
    if not value:
        raise ValueError("empty DOI")
    s = value.strip()
    for prefix in _DOI_URL_PREFIXES:
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):]
            break
    s = s.strip().strip("/")
    if not s.startswith("10.") or "/" not in s:
        raise ValueError(f"not a DOI: {value!r}")
    return s


def detect_publisher(doi: str) -> str | None:
    """Map a DOI registrant prefix to a publisher slug. ``None`` if unknown.

    Examples
    --------
    >>> detect_publisher("10.1145/3567955.3567958")
    'acm'
    >>> detect_publisher("10.99999/unknown") is None
    True
    """
    try:
        bare = normalize_doi(doi)
    except ValueError:
        return None
    prefix = bare.split("/", 1)[0]
    return _PUBLISHER_BY_DOI_PREFIX.get(prefix)


def looks_like_bibtex(text: str | bytes | None) -> bool:
    """Cheap sniff: does ``text`` start with ``@<entry-type>{`` somewhere near the top?"""
    if not text:
        return False
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            text = text.decode("utf-8", errors="replace")
    # Look only in the first ~1 KiB to avoid false positives in long HTML
    # bodies that happen to contain an @-symbol elsewhere.
    return bool(_BIBTEX_HEAD_RE.search(text[:1024]))


# ---------------------------------------------------------------------------
# Shared HTTP helper for tier 1 + tier 2 (CrossRef + doi.org)
# ---------------------------------------------------------------------------


def _fetch_bibtex_http(url: str, *, accept: str, timeout: float) -> str | None:
    """GET ``url`` with the given ``Accept`` header; return BibTeX or ``None``.

    Shared body for tier 1 (CrossRef) and tier 2 (doi.org). Caps the read at
    :data:`_MAX_BIBTEX_BYTES` so a misbehaving server can't memory-bomb us,
    sniffs the body with :func:`looks_like_bibtex`, and never raises for
    network-level errors.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(_MAX_BIBTEX_BYTES)
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None
    if not looks_like_bibtex(body):
        return None
    try:
        return body.decode("utf-8").strip() or None
    except UnicodeDecodeError:
        return body.decode("utf-8", errors="replace").strip() or None


# ---------------------------------------------------------------------------
# Tier 1 — CrossRef content-negotiation endpoint
# ---------------------------------------------------------------------------


def fetch_bibtex_via_crossref(doi: str, *, timeout: float = 15.0) -> str | None:
    """Fetch BibTeX from CrossRef's ``transform`` endpoint.

    URL shape::

        https://api.crossref.org/works/<DOI>/transform/application/x-bibtex

    Returns the BibTeX text, or ``None`` on any failure (HTTP error, timeout,
    non-BibTeX response). Never raises for network-level errors — the caller
    decides whether to fall through to another tier.
    """
    try:
        bare = normalize_doi(doi)
    except ValueError:
        return None
    url = f"https://api.crossref.org/works/{bare}/transform/application/x-bibtex"
    return _fetch_bibtex_http(url, accept="application/x-bibtex", timeout=timeout)


# ---------------------------------------------------------------------------
# Tier 2 — DOI content negotiation
# ---------------------------------------------------------------------------


def fetch_bibtex_via_doi_content_negotiation(doi: str, *, timeout: float = 15.0) -> str | None:
    """Fetch BibTeX by asking ``doi.org`` for ``Accept: application/x-bibtex``.

    Honored by most major publishers via the DOI Foundation content-negotiation
    spec. Returns ``None`` on any failure.
    """
    try:
        bare = normalize_doi(doi)
    except ValueError:
        return None
    url = f"https://doi.org/{bare}"
    return _fetch_bibtex_http(
        url,
        accept="application/x-bibtex; q=1.0, application/x-bibtex-thread-safe; q=0.5",
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Tier 3 — CloakBrowser stealth fallback
# ---------------------------------------------------------------------------


def fetch_bibtex_via_browser(doi: str, *, timeout: float = 60.0) -> str | None:
    """Fetch BibTeX via CloakBrowser (anti-bot Chromium).

    Lazy-imports ``cloakbrowser``. Raises :class:`ImportError` with an install
    hint when the optional dep is missing — caller catches and degrades if
    desired.

    The browser opens ``doi.org/<DOI>`` with
    ``Accept: application/x-bibtex``; publishers that block plain ``urllib``
    behind bot-detection (Cloudflare, FingerprintJS, …) still see a real
    Chromium fingerprint and serve the BibTeX response. Returns ``None`` if
    the response doesn't look like BibTeX.
    """
    try:
        bare = normalize_doi(doi)
    except ValueError:
        return None

    try:
        from cloakbrowser import launch  # type: ignore
    except ImportError as e:  # pragma: no cover - exercised by test_browser_missing
        raise ImportError(
            "fetching BibTeX via stealth browser requires the optional "
            "`crawl` extra. Install with:\n"
            "    pip install -e \".[crawl]\"\n"
            "or:\n"
            "    pip install cloakbrowser"
        ) from e

    timeout_ms = int(max(1.0, timeout) * 1000)
    url = f"https://doi.org/{bare}"

    body: str | None = None
    browser = None
    try:
        browser = launch(headless=True)
        context = browser.new_context(
            extra_http_headers={
                "Accept": "application/x-bibtex",
                "User-Agent": _USER_AGENT,
            }
        )
        page = context.new_page()
        response = page.goto(url, timeout=timeout_ms)
        if response is None:
            return None
        # Prefer the raw response body over rendered HTML — publishers serve
        # BibTeX as text/plain or application/x-bibtex.
        try:
            body = response.text()
        except Exception:  # noqa: BLE001 - cloakbrowser surfaces many shapes
            body = page.content()
    except ImportError:
        # Caller (this very function) raises ImportError when cloakbrowser
        # isn't installed — re-raise so the orchestrator can surface the
        # install hint on `prefer_browser=True`.
        raise
    except Exception:  # noqa: BLE001 - mirror tier 1/2 "never raise" contract
        # CloakBrowser / Playwright surface many exception types (TimeoutError,
        # Error, navigation errors, TLS, DNS). The orchestrator and `_main`
        # treat this tier as best-effort; swallow everything except ImportError
        # so the cite-as-you-write flow degrades gracefully on transient
        # browser/network issues.
        return None
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass

    if not looks_like_bibtex(body):
        return None
    return body.strip() or None


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def fetch_bibtex_from_publisher(
    doi: str,
    *,
    prefer_browser: bool = False,
    timeout: float = 60.0,
) -> str | None:
    """Fetch BibTeX for ``doi`` using the cheapest path that works.

    Strategy:

    1. **CrossRef** (``fetch_bibtex_via_crossref``) — fast, no deps.
    2. **doi.org content negotiation** (``fetch_bibtex_via_doi_content_negotiation``).
    3. **CloakBrowser** (``fetch_bibtex_via_browser``) — only if installed.

    Returns the BibTeX text on the first successful tier, or ``None`` if every
    tier fails. Passes through ``ImportError`` from tier 3 ONLY when
    ``prefer_browser=True``; otherwise a missing ``cloakbrowser`` install is
    treated as "tier 3 unavailable" and swallowed.

    Parameters
    ----------
    doi : str
        DOI in any common form (``10.1145/abc``, ``doi:10.1145/abc``,
        ``https://doi.org/10.1145/abc``).
    prefer_browser : bool
        Skip tiers 1 and 2 and go straight to the stealth browser. Useful when
        you know a publisher returns garbage via content negotiation.
    timeout : float
        Per-tier deadline in seconds. Tiers 1 and 2 cap at ``min(timeout, 15)``;
        tier 3 uses the full value.
    """
    if prefer_browser:
        return fetch_bibtex_via_browser(doi, timeout=timeout)

    http_timeout = min(timeout, 15.0)

    bib = fetch_bibtex_via_crossref(doi, timeout=http_timeout)
    if bib:
        return bib

    bib = fetch_bibtex_via_doi_content_negotiation(doi, timeout=http_timeout)
    if bib:
        return bib

    try:
        return fetch_bibtex_via_browser(doi, timeout=timeout)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Small CLI helper (debug-only — not wired through any skill)
# ---------------------------------------------------------------------------


def _main(argv: list[str]) -> int:
    """``python -m research_assistant.lit.publisher_bibtex <DOI>``."""
    if len(argv) != 1:
        print(json.dumps({"error": "usage: publisher_bibtex <DOI>"}))
        return 2
    bib = fetch_bibtex_from_publisher(argv[0])
    if bib is None:
        print(json.dumps({"doi": argv[0], "bibtex": None, "publisher": detect_publisher(argv[0])}))
        return 1
    print(bib)
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(_main(sys.argv[1:]))
