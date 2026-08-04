/* Upload page (Phase 2B). Keeps the actual upload request alive across the
 * "redirect" to the Progress view by only changing the visible URL
 * (history.pushState) rather than performing a real navigation - a real
 * navigation would cancel the in-flight fetch. Progress shown here is real:
 * /api/v1/upload/web returns immediately with a job_id (the pipeline runs
 * in a backend BackgroundTask), and this page polls the real
 * /api/v1/progress/{job_id} endpoint until the job reaches a terminal
 * stage. (The plain /api/v1/upload endpoint is the synchronous Phase 2A
 * API contract and is not used by this page - it blocks until the whole
 * pipeline finishes.) */
(() => {
  const form = document.getElementById("upload-form");
  const fileInput = document.getElementById("file-input");
  const selectedFilename = document.getElementById("selected-filename");
  const validationMessage = document.getElementById("validation-message");
  const uploadBtn = document.getElementById("upload-btn");
  const resetBtn = document.getElementById("reset-btn");
  const uploadSection = document.getElementById("upload-section");
  const progressSection = document.getElementById("progress-section");

  const statusMessageEl = document.getElementById("progress-status-message");
  const barFillEl = document.getElementById("progress-bar-fill");
  const barTrackEl = document.getElementById("progress-bar-track");
  const percentValueEl = document.getElementById("progress-percent-value");
  const stageListEl = document.getElementById("stage-list");

  const POLL_INTERVAL_MS = 900;
  const POLL_TIMEOUT_MS = 180000;
  let pollTimer = null;

  function showValidationMessage(text) {
    validationMessage.textContent = text;
    validationMessage.hidden = !text;
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (file) {
      selectedFilename.textContent = "Selected: " + file.name;
      selectedFilename.hidden = false;
      showValidationMessage(TAP.validateFile(file) || "");
    } else {
      selectedFilename.hidden = true;
      showValidationMessage("");
    }
  });

  resetBtn.addEventListener("click", () => {
    form.reset();
    selectedFilename.hidden = true;
    showValidationMessage("");
  });

  function applyProgress(stageKey, percent, message) {
    const currentIndex = TAP.stageIndex(stageKey);
    const knownStage = TAP.STAGES.find((s) => s.key === stageKey);
    const displayPercent = typeof percent === "number" ? percent : (knownStage ? knownStage.percent : 0);

    statusMessageEl.textContent = message || TAP.STATUS_MESSAGES[stageKey] || "Processing\u2026";
    barFillEl.style.width = displayPercent + "%";
    barTrackEl.setAttribute("aria-valuenow", String(displayPercent));
    percentValueEl.textContent = String(displayPercent);

    Array.from(stageListEl.children).forEach((li) => {
      const liIndex = TAP.stageIndex(li.dataset.stage);
      li.classList.remove("stage-done", "stage-current");
      if (currentIndex < 0) return;
      if (liIndex < currentIndex) {
        li.classList.add("stage-done");
      } else if (liIndex === currentIndex) {
        li.classList.add("stage-current");
      }
    });
  }

  function goToError(status, body, context) {
    const info = TAP.describeError(status, body, context);
    TAP.setLastError(info);
    window.location.href = "/error";
  }

  function stopPolling() {
    if (pollTimer) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function pollProgress(jobId, startedAt) {
    if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
      stopPolling();
      goToError(0, null, "timeout");
      return;
    }

    fetch(`/api/v1/progress/${encodeURIComponent(jobId)}`)
      .then(async (response) => {
        if (!response.ok) {
          let body = null;
          try {
            body = await response.json();
          } catch (e) {
            body = null;
          }
          stopPolling();
          goToError(response.status, body, "http");
          return;
        }

        const job = await response.json();
        applyProgress(job.stage, job.progress, job.message);

        if (job.stage === "failed") {
          stopPolling();
          goToError(0, { detail: job.error, error: null }, "http");
          return;
        }

        if (job.stage === "completed") {
          stopPolling();
          const result = job.result || {};

          if (result.needs_clarification) {
            TAP.setLastError({
              title: "More Information Needed",
              message:
                job.message ||
                "We need a bit more information about this document before we can process it.",
              action: "Please try uploading again, or try a different document.",
            });
            window.location.href = "/error";
            return;
          }

          if (!result.document_id) {
            goToError(0, { detail: job.message }, "http");
            return;
          }

          TAP.setUploadResult(result.document_id, result);
          window.location.href = "/results/" + encodeURIComponent(result.document_id);
          return;
        }

        pollTimer = window.setTimeout(() => pollProgress(jobId, startedAt), POLL_INTERVAL_MS);
      })
      .catch(() => {
        stopPolling();
        goToError(0, null, "network");
      });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = fileInput.files && fileInput.files[0];
    const validationError = TAP.validateFile(file);
    if (validationError) {
      showValidationMessage(validationError);
      return;
    }
    showValidationMessage("");

    uploadBtn.disabled = true;
    uploadSection.hidden = true;
    progressSection.hidden = false;
    window.history.pushState({ view: "progress" }, "", "/progress");
    applyProgress("queued", 0, "Uploading\u2026");

    const formData = new FormData();
    formData.append("file", file);

    let response;
    try {
      response = await fetch("/api/v1/upload/web", { method: "POST", body: formData });
    } catch (err) {
      goToError(0, null, "network");
      return;
    }

    let body = null;
    try {
      body = await response.json();
    } catch (e) {
      body = null;
    }

    if (!response.ok) {
      goToError(response.status, body, "http");
      return;
    }

    if (!body || !body.job_id) {
      goToError(response.status, body, "http");
      return;
    }

    pollProgress(body.job_id, Date.now());
  });
})();
