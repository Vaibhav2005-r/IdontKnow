(function () {
  "use strict";

  const form = document.getElementById("predict-form");
  const input = document.getElementById("url-input");
  const checkBtn = document.getElementById("check-btn");
  const resultEl = document.getElementById("result");

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
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
        <p class="gauge-label">${pct}% phishing probability · model v${escapeHtml(String(data.model_version))}</p>
      </div>
      <div class="result-actions">
        <button type="button" id="feedback-wrong-btn" class="btn-ghost" data-feedback-id="${data.feedback_id}">
          This is wrong
        </button>
        <p class="feedback-thanks" hidden>Thanks — logged for the next training run.</p>
      </div>
    `;
    // animate the gauge in on the next frame
    requestAnimationFrame(() => {
      const fill = resultEl.querySelector(".gauge-fill");
      if (fill) fill.style.width = pct + "%";
    });
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
  }

  function clearFormError() {
    const errEl = form.querySelector(".form-error");
    if (errEl) errEl.remove();
  }

  async function submitUrl(url) {
    checkBtn.classList.add("loading");
    checkBtn.disabled = true;
    clearFormError();
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

  // event delegation: the "This is wrong" button is re-rendered dynamically
  resultEl.addEventListener("click", async (e) => {
    const btn = e.target.closest("#feedback-wrong-btn");
    if (!btn) return;

    btn.disabled = true;
    btn.textContent = "Sending…";
    try {
      const res = await fetch("/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify({ feedback_id: btn.dataset.feedbackId }),
      });
      if (!res.ok) throw new Error("feedback failed");
      btn.hidden = true;
      const thanks = resultEl.querySelector(".feedback-thanks");
      if (thanks) thanks.hidden = false;
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "This is wrong";
    }
  });
})();
