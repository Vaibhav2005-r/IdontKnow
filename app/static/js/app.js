(function () {
  "use strict";

  const form = document.getElementById("predict-form");
  const input = document.getElementById("url-input");
  const checkBtn = document.getElementById("check-btn");
  const resultEl = document.getElementById("result");
  const mascot = document.getElementById("mascot");
  const mascotCaption = document.getElementById("mascot-caption");

  const GAUGE_RADIUS = 42;
  const GAUGE_CIRCUMFERENCE = 2 * Math.PI * GAUGE_RADIUS;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function setMascot(state, caption) {
    if (mascot) mascot.setAttribute("class", "mascot mascot--" + state);
    if (mascotCaption && caption !== undefined) mascotCaption.textContent = caption;
  }

  // ---- count-up number animation ----
  function countUp(el, target, opts) {
    if (!el) return;
    opts = opts || {};
    const duration = opts.duration || 900;
    const decimals = opts.decimals || 0;
    const suffix = opts.suffix || "";
    const start = parseFloat(el.dataset.currentValue || "0") || 0;
    const t0 = performance.now();
    function tick(now) {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      const value = start + (target - start) * eased;
      el.textContent = value.toFixed(decimals) + suffix;
      if (p < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = target.toFixed(decimals) + suffix;
        el.dataset.currentValue = String(target);
      }
    }
    requestAnimationFrame(tick);
  }

  // ---- circular gauge draw-in + percent count-up ----
  function animateGauge(container) {
    if (!container) return;
    const fill = container.querySelector(".gauge-ring-fill");
    const percentEl = container.querySelector(".gauge-percent");
    if (fill) {
      const target = parseFloat(fill.dataset.targetOffset || GAUGE_CIRCUMFERENCE);
      fill.style.strokeDashoffset = String(GAUGE_CIRCUMFERENCE);
      // force reflow so the transition actually animates from the reset value
      // eslint-disable-next-line no-unused-expressions
      fill.getBoundingClientRect();
      requestAnimationFrame(() => {
        fill.style.strokeDashoffset = String(target);
      });
    }
    if (percentEl) {
      const target = parseFloat(percentEl.dataset.countTo || "0");
      percentEl.dataset.currentValue = "0";
      countUp(percentEl, target, { duration: 1100, decimals: 1, suffix: "%" });
    }
  }

  // ---- stats strip ----
  function refreshStats() {
    fetch("/version", { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        const predEl = document.getElementById("stat-predictions");
        const corrEl = document.getElementById("stat-corrections");
        const accEl = document.getElementById("stat-accuracy");
        const stats = data.feedback_stats || {};
        if (predEl) countUp(predEl, stats.total_predictions || 0, { duration: 800 });
        if (corrEl) countUp(corrEl, stats.corrections || 0, { duration: 800 });
        if (accEl && typeof data.accuracy === "number") {
          accEl.textContent = (data.accuracy * 100).toFixed(1) + "%";
        }
      })
      .catch(() => {});
  }

  // ---- cursor-follow spotlight ----
  (function initSpotlight() {
    const spot = document.getElementById("bg-spotlight");
    if (!spot) return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let active = false;
    window.addEventListener("mousemove", (e) => {
      const xPct = (e.clientX / window.innerWidth) * 100;
      const yPct = (e.clientY / window.innerHeight) * 100;
      spot.style.setProperty("--spot-x", xPct + "%");
      spot.style.setProperty("--spot-y", yPct + "%");
      if (!active) {
        spot.classList.add("is-active");
        active = true;
      }
    });
    window.addEventListener("mouseleave", () => {
      spot.classList.remove("is-active");
      active = false;
    });
  })();

  // ---- 3D tilt on [data-tilt] cards ----
  (function initTilt() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.matchMedia && window.matchMedia("(hover: none)").matches) return; // skip on touch
    document.querySelectorAll("[data-tilt]").forEach((card) => {
      let raf = null;
      card.addEventListener("mousemove", (e) => {
        const rect = card.getBoundingClientRect();
        const px = (e.clientX - rect.left) / rect.width - 0.5;
        const py = (e.clientY - rect.top) / rect.height - 0.5;
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          card.style.transform = `rotateX(${(-py * 5).toFixed(2)}deg) rotateY(${(px * 6).toFixed(2)}deg) translateZ(0)`;
        });
      });
      card.addEventListener("mouseleave", () => {
        if (raf) cancelAnimationFrame(raf);
        card.style.transform = "rotateX(0deg) rotateY(0deg)";
      });
    });
  })();

  function renderReasons(reasons) {
    if (!reasons || !reasons.length) return "";
    const items = reasons.map((r, i) => `<li style="--i: ${i}">${escapeHtml(r)}</li>`).join("");
    return `<ul class="reasons-list">${items}</ul>`;
  }

  function renderResult(data) {
    const isPhishing = data.label_id === 1;
    const pct = Math.round(data.phishing_probability * 1000) / 10;
    const offset = (GAUGE_CIRCUMFERENCE * (1 - data.phishing_probability)).toFixed(2);

    resultEl.className = "result result--visible " + (isPhishing ? "result--phishing" : "result--safe");
    resultEl.dataset.feedbackId = data.feedback_id;
    resultEl.innerHTML = `
      <div class="result-shimmer" aria-hidden="true"></div>
      <div class="result-top">
        <div class="gauge-ring">
          <svg viewBox="0 0 100 100">
            <circle class="gauge-track" cx="50" cy="50" r="${GAUGE_RADIUS}"></circle>
            <circle class="gauge-ring-fill" cx="50" cy="50" r="${GAUGE_RADIUS}"
                    stroke-dasharray="${GAUGE_CIRCUMFERENCE.toFixed(2)}"
                    stroke-dashoffset="${GAUGE_CIRCUMFERENCE.toFixed(2)}"
                    data-target-offset="${offset}"></circle>
          </svg>
          <div class="gauge-percent" data-count-to="${pct}">0%</div>
        </div>
        <div class="result-top-text">
          <p class="result-verdict">${isPhishing ? "Phishing" : "Safe"}</p>
          <p class="result-url">${escapeHtml(data.url)}</p>
          <p class="result-model">model v${escapeHtml(String(data.model_version))}</p>
        </div>
      </div>
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
    `;
    animateGauge(resultEl);
    refreshStats();

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
      refreshStats();
    } catch (err) {
      noBtn.disabled = false;
      noBtn.textContent = "No, report it";
    }
  });

  // initial page load: animate stats in, and the gauge if the server
  // rendered a result already (non-JS form-submit fallback path)
  refreshStats();
  if (resultEl.classList.contains("result--visible")) {
    animateGauge(resultEl);
  }
})();
