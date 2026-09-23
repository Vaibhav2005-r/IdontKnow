(function () {
  "use strict";

  const form = document.getElementById("predict-form");
  const input = document.getElementById("url-input");
  const checkBtn = document.getElementById("check-btn");
  const resultEl = document.getElementById("result");
  const mascot = document.getElementById("mascot");
  const mascotCaption = document.getElementById("mascot-caption");

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function setMascot(state, caption) {
    if (mascot) mascot.setAttribute("class", "mascot mascot--" + state);
    if (mascotCaption && caption !== undefined) mascotCaption.textContent = caption;
  }

  function renderReasons(reasons) {
    if (!reasons || !reasons.length) return "";
    const items = reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("");
    return `<ul class="reasons-list">${items}</ul>`;
  }

  function renderResult(data) {
    const isPhishing = data.label_id === 1;
    const pct = Math.round(data.phishing_probability * 1000) / 10;

    resultEl.className = "result result--visible " + (isPhishing ? "result--phishing" : "result--safe");
    resultEl.dataset.feedbackId = data.feedback_id;
    resultEl.innerHTML = `
      <div class="result-icon">${isPhishing ? "⚠️" : "✅"}</div>
      <div class="result-body">
        <p class="result-verdict">${isPhishing ? "Phishing" : "Safe"}</p>
        <p class="result-url">${escapeHtml(data.url)}</p>
        <div class="gauge"><div class="gauge-fill" style="width: 0%"></div></div>
        <p class="gauge-label">Confidence ${pct}% · model v${escapeHtml(String(data.model_version))}</p>
        ${renderReasons(data.reasons)}
        <div class="feedback-ask">
          <span class="feedback-ask-label">Was this prediction correct?</span>
          <div class="feedback-buttons">
            <button type="button" id="feedback-yes-btn" class="btn-ghost btn-ghost--yes">Yes</button>
            <button type="button" id="feedback-wrong-btn" class="btn-ghost btn-ghost--no" data-feedback-id="${data.feedback_id}">
              No, report it
            </button>
          </div>
          <p class="feedback-thanks" hidden></p>
        </div>
      </div>
    `;
    requestAnimationFrame(() => {
      const fill = resultEl.querySelector(".gauge-fill");
      if (fill) fill.style.width = pct + "%";
    });

    setMascot(
      isPhishing ? "phishing" : "safe",
      isPhishing
        ? "That one's phishing — steer clear."
        : "Looks safe to me!"
    );
  }

  function renderError(message) {
    resultEl.className = "result";
    resultEl.innerHTML = "";
    let errEl = form.querySelector(".form-error");
    if (!errEl) {
      errEl = document.createElement("p");
      errEl.className = "form-error";
      errEl.setAttribute("role", "alert");
      form.appendChild(errEl);
    }
    errEl.textContent = message;
    setMascot("idle", "Hmm, that didn't look like a URL.");
  }

  function clearFormError() {
    const errEl = form.querySelector(".form-error");
    if (errEl) errEl.remove();
  }

  async function submitUrl(url) {
    checkBtn.classList.add("loading");
    checkBtn.disabled = true;
    clearFormError();
    setMascot("scanning", "Scanning the link…");
    try {
      const res = await fetch("/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) {
        renderError(data.error || "Something went wrong.");
        return;
      }
      renderResult(data);
    } catch (err) {
      renderError("Could not reach the server. Is the app running?");
    } finally {
      checkBtn.classList.remove("loading");
      checkBtn.disabled = false;
    }
  }

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const url = input.value.trim();
      if (url) submitUrl(url);
    });
  }

  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      input.value = chip.dataset.url;
      submitUrl(chip.dataset.url);
    });
  });

  function lockFeedbackButtons(selectedBtn) {
    const ask = resultEl.querySelector(".feedback-ask");
    if (!ask) return;
    ask.querySelectorAll(".btn-ghost").forEach((b) => {
      b.disabled = true;
      b.classList.remove("is-selected");
    });
    selectedBtn.classList.add("is-selected");
    const thanks = ask.querySelector(".feedback-thanks");
    if (thanks) thanks.hidden = false;
  }

  // event delegation: feedback buttons are re-rendered dynamically
  resultEl.addEventListener("click", async (e) => {
    const yesBtn = e.target.closest("#feedback-yes-btn");
    if (yesBtn) {
      const thanks = resultEl.querySelector(".feedback-thanks");
      if (thanks) thanks.textContent = "Thanks for confirming!";
      lockFeedbackButtons(yesBtn);
      return;
    }

    const noBtn = e.target.closest("#feedback-wrong-btn");
    if (!noBtn) return;

    noBtn.disabled = true;
    noBtn.textContent = "Sending…";
    try {
      const res = await fetch("/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({ feedback_id: noBtn.dataset.feedbackId }),
      });
      if (!res.ok) throw new Error("feedback failed");
      noBtn.textContent = "No, report it";
      const thanks = resultEl.querySelector(".feedback-thanks");
      if (thanks) thanks.textContent = "Thanks — logged for the next training run.";
      lockFeedbackButtons(noBtn);
    } catch (err) {
      noBtn.disabled = false;
      noBtn.textContent = "No, report it";
    }
  });
})();
