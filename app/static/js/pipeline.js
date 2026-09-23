(function () {
  "use strict";

  const svg = document.getElementById("pipeline-svg");
  if (!svg) return;

  const caption = document.getElementById("pipeline-caption");
  const playBtn = document.getElementById("pipeline-play-btn");
  const nodes = Array.from(svg.querySelectorAll(".node"));
  const edges = Array.from(svg.querySelectorAll(".edge"));
  const pills = Array.from(svg.querySelectorAll(".stage-pill"));

  let playToken = 0; // bumped to cancel an in-flight walkthrough

  function clearActive() {
    nodes.forEach((n) => n.classList.remove("is-active"));
    edges.forEach((e) => e.classList.remove("is-active"));
    pills.forEach((p) => p.classList.remove("is-active"));
  }

  function setCaption(text) {
    if (caption) caption.textContent = text;
  }

  function activateNode(id, text) {
    clearActive();
    const el = document.getElementById(id);
    if (el) el.classList.add("is-active");
    if (text) setCaption(text);
  }

  function activateEdge(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("is-active");
  }

  function activatePill(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("is-active");
  }

  nodes.forEach((node) => {
    node.addEventListener("click", () => {
      playToken++; // cancel any running walkthrough
      clearActive();
      node.classList.add("is-active");
      setCaption(node.dataset.caption || "");
    });
  });

  const STEPS = [
    { node: "node-user", caption: "1. A user pastes a URL and clicks Check URL." },
    { edge: "edge-user-app" },
    { node: "node-app", caption: "2. Flask scores it with the live model and logs the prediction." },
    { edge: "edge-app-db" },
    { node: "node-db", caption: "3. A “No, report it” click saves the correction here as new labelled data." },
    { edge: "edge-db-jenkins" },
    { node: "node-github", caption: "4. A GitHub push -- or the nightly cron -- triggers Jenkins." },
    { edge: "edge-gh-jenkins" },
    { node: "node-jenkins", pill: "stage-train", caption: "5. Jenkins merges the feedback and retrains a candidate model." },
    { pill: "stage-gate", caption: "6. The accuracy gate compares the candidate to the live model on the same held-out split." },
    { pill: "stage-test", caption: "7. pytest and Selenium run against the freshly built container." },
    { pill: "stage-scan", caption: "8. Trivy scans the image for known vulnerabilities." },
    { edge: "edge-jenkins-docker" },
    { node: "node-docker", caption: "9. A passing build is tagged phishguard:vX.Y." },
    { edge: "edge-docker-app" },
    { node: "node-app", caption: "10. Docker Compose redeploys -- the new version goes live." },
    { edge: "edge-jenkins-dash" },
    { node: "node-dash", caption: "11. The dashboard picks up the new version, accuracy, and feedback stats." },
  ];

  function sleep(ms, token) {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (token !== playToken) reject(new Error("cancelled"));
        else resolve();
      }, ms);
    });
  }

  async function play() {
    const token = ++playToken;
    if (playBtn) playBtn.disabled = true;
    try {
      for (const step of STEPS) {
        if (token !== playToken) return;
        if (step.node) {
          activateNode(step.node, step.caption);
        } else {
          clearActive();
          if (step.caption) setCaption(step.caption);
        }
        if (step.edge) activateEdge(step.edge);
        if (step.pill) activatePill(step.pill);
        await sleep(1150, token);
      }
      if (token === playToken) {
        clearActive();
        setCaption("That's the whole loop -- click any box to explore it yourself.");
      }
    } catch (err) {
      // cancelled by a node click or a new play; nothing to do
    } finally {
      if (playBtn) playBtn.disabled = false;
    }
  }

  if (playBtn) {
    playBtn.addEventListener("click", play);
  }
})();
