"""End-to-end UI tests against a running PhishGuard instance (app + browser).

Run with: pytest -m ui --base-url set via APP_BASE_URL env var (default
http://localhost:5000). Needs Chrome/Chromium installed; webdriver-manager
fetches a matching chromedriver automatically.
"""
import json
import urllib.request

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.ui


def _version_stats(base_url):
    with urllib.request.urlopen(f"{base_url}/version", timeout=5) as resp:
        return json.loads(resp.read())


def test_safe_url_shows_verdict(driver, base_url):
    driver.get(base_url)
    url_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "url-input")))
    url_input.clear()
    url_input.send_keys("https://www.wikipedia.org")
    driver.find_element(By.ID, "check-btn").click()

    result = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#result.result--visible"))
    )
    assert "wikipedia.org" in result.text.lower()


def test_phishing_url_shows_verdict_and_feedback_button(driver, base_url):
    driver.get(base_url)
    url_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "url-input")))
    url_input.clear()
    url_input.send_keys("http://192.168.4.20/sbi/kyc/update.php")
    driver.find_element(By.ID, "check-btn").click()

    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#result.result--visible"))
    )
    wrong_btn = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "feedback-wrong-btn"))
    )
    assert wrong_btn.is_displayed()


def test_feedback_submission_reaches_the_database(driver, base_url):
    before = _version_stats(base_url)["feedback_stats"]["corrections"]

    driver.get(base_url)
    url_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "url-input")))
    url_input.clear()
    url_input.send_keys("http://free-gift-card-claim-now.tk/winner")
    driver.find_element(By.ID, "check-btn").click()

    wrong_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "feedback-wrong-btn"))
    )
    wrong_btn.click()

    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "feedback-wrong-btn").get_attribute("hidden") is not None
    )

    after = _version_stats(base_url)["feedback_stats"]["corrections"]
    assert after == before + 1


def test_invalid_url_shows_error(driver, base_url):
    driver.get(base_url)
    url_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "url-input")))
    url_input.clear()
    url_input.send_keys("not a url")
    driver.find_element(By.ID, "check-btn").click()

    error = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".form-error"))
    )
    assert error.text
