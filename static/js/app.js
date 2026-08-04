/* Shared helpers for the Teacher AI Platform frontend (Phase 2B). */

const TAP = (() => {
  const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt"];
  const MAX_UPLOAD_SIZE_MB = 50;

  // Mirrors the backend's JobStage values and the real per-stage progress
  // percentages from app.progress.tracker._STAGE_PROGRESS, so the numbers
  // shown here are the same ones the server is actually reporting.
  const STAGES = [
    { key: "queued", label: "Uploading", percent: 0 },
    { key: "routing", label: "Routing", percent: 10 },
    { key: "parsing", label: "Parsing", percent: 28 },
    { key: "structuring", label: "Structuring", percent: 40 },
    { key: "chunking", label: "Chunking", percent: 52 },
    { key: "embedding", label: "Embedding", percent: 64 },
    { key: "indexing", label: "Indexing", percent: 74 },
    { key: "classifying", label: "Classification", percent: 84 },
    { key: "extracting_knowledge", label: "Knowledge Extraction", percent: 94 },
    { key: "generating_package", label: "Teaching Package Generation", percent: 97 },
    { key: "completed", label: "Completed", percent: 100 },
  ];

  const STATUS_MESSAGES = {
    queued: "Uploading\u2026",
    routing: "Uploading\u2026",
    parsing: "Parsing document\u2026",
    structuring: "Structuring document\u2026",
    chunking: "Chunking document\u2026",
    embedding: "Preparing document embeddings\u2026",
    indexing: "Indexing document\u2026",
    classifying: "Classifying document\u2026",
    extracting_knowledge: "Extracting educational concepts\u2026",
    generating_package: "Generating lesson plan\u2026",
    completed: "Teaching package ready.",
  };

  function validateFile(file) {
    if (!file) {
      return "Please choose a file to upload.";
    }
    if (file.size === 0) {
      return "That file is empty. Please choose a different file.";
    }
    const name = file.name || "";
    const ext = name.includes(".") ? "." + name.split(".").pop().toLowerCase() : "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `"${ext || "unknown"}" files aren't supported. Please upload a PDF, DOCX, PPTX, or TXT file.`;
    }
    const maxBytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      return `That file is ${sizeMb}MB, which is over the ${MAX_UPLOAD_SIZE_MB}MB limit.`;
    }
    return null;
  }

  function stageIndex(key) {
    return STAGES.findIndex((s) => s.key === key);
  }

  // Maps a backend/HTTP error payload to a friendly {title, message, action}.
  function describeError(status, body, context) {
    const detail = (body && (body.detail || body.error)) || null;
    const errorType = body && body.error;

    const known = {
      UnsupportedFileTypeError: {
        title: "Unsupported File Type",
        message: detail || "That file type isn't supported.",
        action: "Please upload a PDF, DOCX, PPTX, or TXT file.",
      },
      FileTooLargeError: {
        title: "File Too Large",
        message: detail || "That file is too large to upload.",
        action: "Please upload a smaller file.",
      },
      ParsingError: {
        title: "Couldn't Read That Document",
        message: detail || "We couldn't parse the document you uploaded.",
        action: "Check that the file isn't corrupted or password-protected, then try again.",
      },
      EmbeddingError: {
        title: "AI Processing Failed",
        message: "We couldn't generate embeddings for this document.",
        action: "This is usually temporary. Please try again in a moment.",
      },
      VectorStoreError: {
        title: "Storage Error",
        message: "We couldn't index this document.",
        action: "Please try again in a moment.",
      },
      ClassificationError: {
        title: "Classification Failed",
        message: "We couldn't determine the subject and grade for this document.",
        action: "Please try again, or try a different document.",
      },
      KnowledgeExtractionError: {
        title: "Knowledge Extraction Failed",
        message: "We couldn't extract structured knowledge from this document.",
        action: "Please try again, or try a different document.",
      },
      TeachingPackageGenerationError: {
        title: "Teaching Package Generation Failed",
        message: "We couldn't generate the teaching package for this document.",
        action: "Please try again in a moment.",
      },
      LLMGenerationError: {
        title: "AI Service Unavailable",
        message: "The AI service didn't respond as expected. This can happen when an API quota or key is invalid.",
        action: "Please check your API configuration or try again shortly.",
      },
    };

    if (errorType && known[errorType]) {
      return known[errorType];
    }

    if (status === 422) {
      return {
        title: "Couldn't Process That File",
        message: detail || "That file couldn't be accepted.",
        action: "Please check the file and try again.",
      };
    }

    if (status === 404) {
      return {
        title: "Not Found",
        message: detail || "We couldn't find what you were looking for.",
        action: "It may still be processing, or the link may be out of date.",
      };
    }

    if (status >= 500) {
      return {
        title: "Something Went Wrong",
        message: detail || "An unexpected error occurred while processing your document.",
        action: "Please try again. If this keeps happening, try a different document.",
      };
    }

    if (context === "network") {
      return {
        title: "Connection Problem",
        message: "We couldn't reach the server. Your network connection may have been interrupted.",
        action: "Check your connection and try again.",
      };
    }

    if (context === "timeout") {
      return {
        title: "This Is Taking Too Long",
        message: "The document is taking longer than expected to process.",
        action: "Please try again, or try a smaller document.",
      };
    }

    return {
      title: "Something Went Wrong",
      message: detail || "An unexpected error occurred.",
      action: "Please try again.",
    };
  }

  function setLastError(info) {
    try {
      sessionStorage.setItem("tap_last_error", JSON.stringify(info));
    } catch (e) {
      /* sessionStorage unavailable - the error page falls back to a generic message */
    }
  }

  function getLastError() {
    try {
      const raw = sessionStorage.getItem("tap_last_error");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function setUploadResult(documentId, data) {
    try {
      sessionStorage.setItem("tap_upload_" + documentId, JSON.stringify(data));
    } catch (e) {
      /* non-fatal: results page will re-fetch what it can */
    }
  }

  function getUploadResult(documentId) {
    try {
      const raw = sessionStorage.getItem("tap_upload_" + documentId);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  return {
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE_MB,
    STAGES,
    STATUS_MESSAGES,
    validateFile,
    stageIndex,
    describeError,
    setLastError,
    getLastError,
    setUploadResult,
    getUploadResult,
  };
})();
