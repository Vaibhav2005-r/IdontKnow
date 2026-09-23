import math

from ml.features import FEATURE_NAMES, extract_features, features_frame


def test_feature_names_count():
    assert len(FEATURE_NAMES) == 32
    assert len(set(FEATURE_NAMES)) == 32


def test_extract_features_length_matches_names():
    features = extract_features("https://example.com/path?a=1")
    assert len(features) == len(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in features)


def test_https_flag():
    idx = FEATURE_NAMES.index("is_https")
    assert extract_features("https://example.com")[idx] == 1.0
    assert extract_features("http://example.com")[idx] == 0.0


def test_ip_address_detected():
    idx = FEATURE_NAMES.index("has_ip_address")
    assert extract_features("http://192.168.1.1/login")[idx] == 1.0
    assert extract_features("http://example.com/login")[idx] == 0.0


def test_url_without_scheme_is_handled():
    features = extract_features("example.com/path")
    assert len(features) == len(FEATURE_NAMES)


def test_empty_url_does_not_crash():
    features = extract_features("")
    assert len(features) == len(FEATURE_NAMES)


def test_suspicious_words_counted():
    idx = FEATURE_NAMES.index("num_suspicious_words")
    phishy = extract_features("http://secure-login-verify-account.tk/update")[idx]
    clean = extract_features("http://example.com/about")[idx]
    assert phishy > clean


def test_entropy_is_nonnegative():
    idx = FEATURE_NAMES.index("url_entropy")
    assert extract_features("http://example.com")[idx] >= 0.0
    assert not math.isnan(extract_features("http://a.com")[idx])


def test_features_frame_shape():
    urls = ["http://example.com", "http://192.168.1.1/login", "https://safe.org/page"]
    df = features_frame(urls)
    assert df.shape == (3, len(FEATURE_NAMES))
    assert list(df.columns) == FEATURE_NAMES


def test_shortening_service_flag():
    idx = FEATURE_NAMES.index("has_shortening_service")
    assert extract_features("http://bit.ly/abc123")[idx] == 1.0
    assert extract_features("http://example.com/abc123")[idx] == 0.0
