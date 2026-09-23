"""Synthetic URLs so tests and CI can run offline.

This data is generated, not real-world traffic. Its accuracy is
unrealistically high by construction (the generator bakes in the exact
patterns the features look for) -- never report it as a project result.
Real accuracy comes only from data/raw/phishing_urls.csv.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

_SAFE_DOMAINS = [
    "example.com", "wikipedia.org", "github.com", "python.org", "mozilla.org",
    "nytimes.com", "amazon.com", "microsoft.com", "apple.com", "stackoverflow.com",
]
_SAFE_PATHS = [
    "/", "/about", "/products", "/blog/2024/09/article", "/docs/api/v1",
    "/contact-us", "/search?q=weather", "/en/help", "/user/settings",
]
_PHISH_WORDS = ["login", "verify", "secure", "update", "account", "confirm", "billing", "signin"]
_PHISH_BRANDS = ["paypal", "amazon", "netflix", "apple", "chase", "microsoft", "bankofamerica"]
_PHISH_TLDS = ["tk", "ml", "ga", "cf", "xyz", "top", "gq"]


def _random_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def _make_safe_url(rng: random.Random) -> str:
    domain = rng.choice(_SAFE_DOMAINS)
    path = rng.choice(_SAFE_PATHS)
    scheme = "https"
    return f"{scheme}://{domain}{path}"


def _make_phishing_url(rng: random.Random) -> str:
    style = rng.randint(0, 3)
    brand = rng.choice(_PHISH_BRANDS)
    word = rng.choice(_PHISH_WORDS)
    if style == 0:
        return f"http://{_random_ip()}/{brand}/{word}.php"
    if style == 1:
        suffix = rng.choice(_PHISH_TLDS)
        return f"http://{brand}-{word}-secure.{suffix}/{word}?session={rng.randint(1000,9999)}"
    if style == 2:
        suffix = rng.choice(_PHISH_TLDS)
        return f"http://{word}.{brand}.account-{word}.{suffix}/webscr?cmd=login&id={rng.randint(10000,99999)}"
    suffix = rng.choice(_PHISH_TLDS)
    return f"http://{brand}{rng.randint(1,999)}.{suffix}/{word}/{word}/index.php?u={rng.randint(1,9999)}"


def generate_sample_dataset(n: int = 400, seed: int = 42) -> pd.DataFrame:
    """Generate a balanced synthetic dataset of n URLs -> DataFrame[url, label]."""
    rng = random.Random(seed)
    half = n // 2
    rows = []
    for _ in range(half):
        rows.append({"url": _make_safe_url(rng), "label": 0})
    for _ in range(n - half):
        rows.append({"url": _make_phishing_url(rng), "label": 1})
    df = pd.DataFrame(rows).drop_duplicates(subset="url").reset_index(drop=True)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    out_path = Path("data/sample/sample_urls.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_sample_dataset()
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} synthetic URLs to {out_path}")


if __name__ == "__main__":
    main()
