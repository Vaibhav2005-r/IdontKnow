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

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#result.result--visible"))
    )
    url_line = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#result .result-url"))
    )
    assert "wikipedia.org" in url_line.get_attribute("textContent").lower()


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
        lambda d: d.find_element(By.ID, "feedback-wrong-btn").get_attribute("disabled") is not None
    )

    after = _version_stats(base_url)["feedback_stats"]["corrections"]
    assert after == before + 1


def test_reasons_list_and_yes_button(driver, base_url):
    driver.get(base_url)
    url_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "url-input")))
    url_input.clear()
    url_input.send_keys("http://paypal-secure-login.tk/verify?id=88231")
    driver.find_element(By.ID, "check-btn").click()

    reasons = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#result .reasons-list"))
    )
    assert len(reasons.find_elements(By.TAG_NAME, "li")) > 0

    yes_btn = driver.find_element(By.ID, "feedback-yes-btn")
    yes_btn.click()
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "feedback-yes-btn").get_attribute("disabled") is not None
    )
    thanks = driver.find_element(By.CSS_SELECTOR, "#result .feedback-thanks")
    assert thanks.get_attribute("hidden") is None


def test_mascot_reacts_to_verdict(driver, base_url):
    driver.get(base_url)
    mascot = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "mascot")))
    assert "mascot--idle" in mascot.get_attribute("class")

    url_input = driver.find_element(By.ID, "url-input")
    url_input.send_keys("http://192.168.4.20/sbi/kyc/update.php")
    driver.find_element(By.ID, "check-btn").click()

    WebDriverWait(driver, 10).until(
        lambda d: "mascot--phishing" in d.find_element(By.ID, "mascot").get_attribute("class")
    )


def test_pipeline_diagram_node_click_updates_caption(driver, base_url):
    driver.get(base_url)
    jenkins_node = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "node-jenkins"))
    )
    caption = driver.find_element(By.ID, "pipeline-caption")
    before = caption.text
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", jenkins_node)
    jenkins_node.click()
    WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, "pipeline-caption").text != before)
    assert "trivy" in caption.text.lower()


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
