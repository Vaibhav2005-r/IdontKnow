"""Lexical feature extraction for phishing URL detection.

Every feature comes from the URL string alone -- no DNS, WHOIS, or HTTP
calls are ever made here. That keeps prediction offline and safe: this
module must be able to score a URL without visiting it.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from urllib.parse import urlsplit

import pandas as pd

FEATURE_NAMES = [
    "url_length",
    "hostname_length",
    "path_length",
    "query_length",
    "fragment_length",
    "num_dots",
    "num_hyphens",
    "num_underscores",
    "num_slashes",
    "num_digits",
    "digit_ratio",
    "num_letters",
    "num_special_chars",
    "num_equal_signs",
    "num_question_marks",
    "num_ampersands",
    "num_at_symbols",
    "num_percent_signs",
    "num_www",
    "num_subdomains",
    "tld_length",
    "has_ip_address",
    "is_https",
    "has_port",
    "has_shortening_service",
    "num_redirects",
    "url_entropy",
    "num_suspicious_words",
    "num_digits_in_hostname",
    "hostname_digit_ratio",
    "longest_path_segment_length",
    "num_path_segments",
]

_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_IPV6_RE = re.compile(r"^\[?[0-9a-fA-F:]+\]?$")
_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "adf.ly", "shorte.st", "bl.ink", "rebrand.ly", "cutt.ly", "tiny.cc",
    "shorturl.at", "s.id", "v.gd",
}
_SUSPICIOUS_WORDS = (
    "login", "signin", "verify", "update", "secure", "account", "bank",
    "confirm", "webscr", "ebayisapi", "password", "billing", "suspend",
    "invoice", "wallet", "unlock", "urgent", "click", "reset", "limited",
)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _is_ip_host(hostname: str) -> bool:
    if not hostname:
        return False
    bare = hostname.strip("[]")
    if _IPV4_RE.match(bare):
        parts = bare.split(".")
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    return hostname.startswith("[") and _IPV6_RE.match(bare) is not None and ":" in bare


def extract_features(url: str) -> list[float]:
    """Extract the 32 lexical features for a single URL, in FEATURE_NAMES order."""
    url = (url or "").strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "http://" + url

    parts = urlsplit(url)
    hostname = parts.hostname or ""
    path = parts.path or ""
    query = parts.query or ""
    fragment = parts.fragment or ""

    digits = sum(c.isdigit() for c in url)
    letters = sum(c.isalpha() for c in url)
    special = sum(not c.isalnum() for c in url)

    labels = [lbl for lbl in hostname.split(".") if lbl]
    tld = labels[-1] if len(labels) >= 2 else ""
    num_subdomains = max(len(labels) - 2, 0) if len(labels) > 2 else 0

    path_segments = [seg for seg in path.split("/") if seg]
    longest_segment = max((len(seg) for seg in path_segments), default=0)

    host_digits = sum(c.isdigit() for c in hostname)

    lower_url = url.lower()
    registered_domain = ".".join(labels[-2:]) if len(labels) >= 2 else hostname

    values = {
        "url_length": len(url),
        "hostname_length": len(hostname),
        "path_length": len(path),
        "query_length": len(query),
        "fragment_length": len(fragment),
        "num_dots": url.count("."),
        "num_hyphens": url.count("-"),
        "num_underscores": url.count("_"),
        "num_slashes": url.count("/"),
        "num_digits": digits,
        "digit_ratio": digits / len(url) if url else 0.0,
        "num_letters": letters,
        "num_special_chars": special,
        "num_equal_signs": url.count("="),
        "num_question_marks": url.count("?"),
        "num_ampersands": url.count("&"),
        "num_at_symbols": url.count("@"),
        "num_percent_signs": url.count("%"),
        "num_www": lower_url.count("www."),
        "num_subdomains": num_subdomains,
        "tld_length": len(tld),
        "has_ip_address": 1.0 if _is_ip_host(hostname) else 0.0,
        "is_https": 1.0 if parts.scheme.lower() == "https" else 0.0,
        "has_port": 1.0 if parts.port is not None else 0.0,
        "has_shortening_service": 1.0 if registered_domain.lower() in _SHORTENERS else 0.0,
        "num_redirects": max(url.count("//") - 1, 0),
        "url_entropy": _shannon_entropy(url),
        "num_suspicious_words": sum(word in lower_url for word in _SUSPICIOUS_WORDS),
        "num_digits_in_hostname": host_digits,
        "hostname_digit_ratio": host_digits / len(hostname) if hostname else 0.0,
        "longest_path_segment_length": longest_segment,
        "num_path_segments": len(path_segments),
    }
    return [float(values[name]) for name in FEATURE_NAMES]


def features_frame(urls: list[str]) -> pd.DataFrame:
    """Vectorised feature extraction for a list of URLs -> DataFrame[FEATURE_NAMES]."""
    rows = [extract_features(u) for u in urls]
    return pd.DataFrame(rows, columns=FEATURE_NAMES)
