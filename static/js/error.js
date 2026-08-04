(() => {
  const titleEl = document.getElementById("error-title");
  const messageEl = document.getElementById("error-message");
  const actionEl = document.getElementById("error-action");
  const retryBtn = document.getElementById("retry-btn");

  const info = TAP.getLastError() || {
    title: "Something Went Wrong",
    message: "An unexpected error occurred while processing your document.",
    action: "Please try again.",
  };

  titleEl.textContent = info.title || "Something Went Wrong";
  messageEl.textContent = info.message || "";
  actionEl.textContent = info.action || "";

  retryBtn.addEventListener("click", () => {
    window.location.href = "/upload";
  });
})();
