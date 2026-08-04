(() => {
  const documentId = window.TAP_DOCUMENT_ID;

  const loadingEl = document.getElementById("results-loading");
  const emptyEl = document.getElementById("results-empty");
  const emptyMessageEl = document.getElementById("results-empty-message");
  const contentEl = document.getElementById("results-content");

  const filenameEl = document.getElementById("results-filename");
  const metadataGridEl = document.getElementById("metadata-grid");
  const knowledgeGridEl = document.getElementById("knowledge-summary-grid");
  const packageSummaryEl = document.getElementById("package-summary-text");
  const moduleCardsEl = document.getElementById("module-cards");
  const downloadUnavailableEl = document.getElementById("download-unavailable");

  const MODULE_TITLES = {
    lesson_plan: "Lesson Plan",
    entry_ticket: "Entry Ticket",
    teacher_script: "Teacher Script",
    blackboard_notes: "Blackboard Notes",
    classroom_activity: "Activities",
    assessment: "Assessment",
    exit_ticket: "Exit Ticket",
    homework: "Homework",
    teacher_guidance: "Teacher Guidance",
  };
  const MODULE_ORDER = Object.keys(MODULE_TITLES);

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([key, value]) => {
        if (key === "text") {
          node.textContent = value;
        } else if (key === "class") {
          node.className = value;
        } else {
          node.setAttribute(key, value);
        }
      });
    }
    (children || []).forEach((child) => child && node.appendChild(child));
    return node;
  }

  function ul(items) {
    return el(
      "ul",
      null,
      (items || []).map((text) => el("li", { text }))
    );
  }

  function heading(text) {
    return el("h4", { text });
  }

  function paragraph(text) {
    return el("p", { text });
  }

  function renderLessonPlan(data) {
    const nodes = [
      paragraph(`Total periods: ${data.total_periods ?? "N/A"}`),
    ];
    if (data.pacing_rationale) nodes.push(paragraph(data.pacing_rationale));
    (data.periods || []).forEach((period) => {
      nodes.push(heading(`Period ${period.period_number} \u2014 ${period.title || ""} (${period.duration_minutes} min)`));
      if (period.summary) nodes.push(paragraph(period.summary));
      if (period.learning_objectives && period.learning_objectives.length) {
        nodes.push(ul(period.learning_objectives));
      }
    });
    return nodes;
  }

  function renderEntryTicket(data) {
    return (data.items || []).map((item) =>
      el("div", null, [
        heading(`Period ${item.period_number}`),
        paragraph(item.question),
        item.expected_answer ? paragraph("Expected answer: " + item.expected_answer) : null,
      ])
    ).flat();
  }

  function renderTeacherScript(data) {
    const nodes = [];
    (data.items || []).forEach((item) => {
      nodes.push(heading(`Period ${item.period_number}`));
      if (item.introduction) nodes.push(paragraph("Introduction: " + item.introduction));
      if (item.explanation) nodes.push(paragraph("Explanation: " + item.explanation));
      if (item.closure) nodes.push(paragraph("Closure: " + item.closure));
      if (item.mentor_moment) nodes.push(paragraph("Mentor Moment: " + item.mentor_moment));
    });
    return nodes;
  }

  function renderBlackboardNotes(data) {
    const nodes = [];
    (data.items || []).forEach((item) => {
      nodes.push(heading(`Period ${item.period_number}`));
      if (item.bullet_points && item.bullet_points.length) nodes.push(ul(item.bullet_points));
    });
    return nodes;
  }

  function renderClassroomActivity(data) {
    const nodes = [];
    (data.items || []).forEach((item) => {
      nodes.push(heading(`Period ${item.period_number} \u2014 ${item.title || ""}`));
      nodes.push(paragraph(`${item.activity_type || ""} \u00b7 ${item.duration_minutes} min`));
      if (item.instructions) nodes.push(paragraph("Instructions: " + item.instructions));
      if (item.materials_needed && item.materials_needed.length) {
        nodes.push(paragraph("Materials: " + item.materials_needed.join(", ")));
      }
      if (item.success_criteria) nodes.push(paragraph("Success criteria: " + item.success_criteria));
    });
    return nodes;
  }

  function renderAssessment(data) {
    const nodes = [];
    if (data.mcqs && data.mcqs.length) {
      nodes.push(heading("Multiple Choice Questions"));
      data.mcqs.forEach((mcq, i) => {
        nodes.push(paragraph(`${i + 1}. ${mcq.question}`));
        if (mcq.options && mcq.options.length) nodes.push(ul(mcq.options));
      });
    }
    if (data.short_answer && data.short_answer.length) {
      nodes.push(heading("Short Answer"));
      nodes.push(ul(data.short_answer.map((q) => q.question)));
    }
    if (data.long_answer && data.long_answer.length) {
      nodes.push(heading("Long Answer"));
      nodes.push(ul(data.long_answer.map((q) => q.question)));
    }
    if (data.numerical && data.numerical.length) {
      nodes.push(heading("Numerical"));
      nodes.push(ul(data.numerical.map((q) => q.question)));
    }
    if (data.rubric) {
      nodes.push(heading("Rubric"));
      nodes.push(paragraph(data.rubric));
    }
    return nodes;
  }

  function renderExitTicket(data) {
    return (data.items || []).map((item) =>
      paragraph(`Period ${item.period_number}: ${item.question}`)
    );
  }

  function renderHomework(data) {
    const nodes = [];
    (data.items || []).forEach((item) => {
      nodes.push(heading(`Period ${item.period_number}`));
      if (item.tasks && item.tasks.length) nodes.push(ul(item.tasks));
    });
    return nodes;
  }

  function renderTeacherGuidance(data) {
    const nodes = [];
    if (data.motivation_of_the_day) nodes.push(paragraph("Motivation of the day: " + data.motivation_of_the_day));
    if (data.key_takeaway) nodes.push(paragraph("Key takeaway: " + data.key_takeaway));
    if (data.teaching_tips && data.teaching_tips.length) {
      nodes.push(heading("Teaching Tips"));
      nodes.push(ul(data.teaching_tips));
    }
    if (data.misconception_guidance && data.misconception_guidance.length) {
      nodes.push(heading("Misconceptions"));
      data.misconception_guidance.forEach((m) => {
        nodes.push(paragraph(`(${m.severity}) ${m.misconception}`));
        if (m.remedial_action) nodes.push(paragraph("Remedial action: " + m.remedial_action));
      });
    }
    return nodes;
  }

  const RENDERERS = {
    lesson_plan: renderLessonPlan,
    entry_ticket: renderEntryTicket,
    teacher_script: renderTeacherScript,
    blackboard_notes: renderBlackboardNotes,
    classroom_activity: renderClassroomActivity,
    assessment: renderAssessment,
    exit_ticket: renderExitTicket,
    homework: renderHomework,
    teacher_guidance: renderTeacherGuidance,
  };

  function addMetadataRow(gridEl, label, value) {
    gridEl.appendChild(el("dt", { text: label }));
    gridEl.appendChild(el("dd", { text: value === null || value === undefined || value === "" ? "\u2014" : String(value) }));
  }

  function renderModuleCards(teachingPackage) {
    moduleCardsEl.innerHTML = "";
    const errors = teachingPackage.generation_errors || {};

    MODULE_ORDER.forEach((name) => {
      const data = teachingPackage[name];
      const details = document.createElement("details");
      details.className = "module-card";
      const summary = el("summary", { text: MODULE_TITLES[name] });
      const body = el("div", { class: "module-body" });

      if (data) {
        (RENDERERS[name](data) || []).forEach((node) => body.appendChild(node));
      } else {
        body.appendChild(
          el("p", {
            class: "module-unavailable",
            text: errors[name]
              ? "This module couldn't be generated: " + errors[name]
              : "This module wasn't generated for this document.",
          })
        );
      }

      details.appendChild(summary);
      details.appendChild(body);
      moduleCardsEl.appendChild(details);
    });
  }

  function showEmpty(message) {
    loadingEl.hidden = true;
    contentEl.hidden = true;
    emptyEl.hidden = false;
    emptyMessageEl.textContent = message;
  }

  function showContent() {
    loadingEl.hidden = true;
    emptyEl.hidden = true;
    contentEl.hidden = false;
  }

  async function load() {
    if (!documentId) {
      showEmpty("No document was specified.");
      return;
    }

    let response;
    try {
      response = await fetch(`/api/v1/export/${encodeURIComponent(documentId)}/json`);
    } catch (e) {
      showEmpty("We couldn't reach the server to load this Teaching Package. Please check your connection and try again.");
      return;
    }

    if (response.status === 404) {
      showEmpty("This document hasn't finished generating a Teaching Package yet, or the link is out of date.");
      return;
    }
    if (!response.ok) {
      showEmpty("We couldn't load this Teaching Package right now. Please try again.");
      return;
    }

    const bundle = await response.json();
    const metadata = bundle.document_metadata || {};
    const knowledge = bundle.knowledge_json || {};
    const teachingPackage = bundle.teaching_package || {};

    const cached = TAP.getUploadResult(documentId);
    filenameEl.textContent = (cached && cached.filename) || "Document";

    metadataGridEl.innerHTML = "";
    addMetadataRow(metadataGridEl, "Subject", metadata.subject);
    addMetadataRow(metadataGridEl, "Grade", metadata.grade);
    addMetadataRow(metadataGridEl, "Topic", metadata.topic);
    addMetadataRow(metadataGridEl, "Chapter", metadata.chapter);
    addMetadataRow(metadataGridEl, "Difficulty", metadata.difficulty);

    knowledgeGridEl.innerHTML = "";
    addMetadataRow(knowledgeGridEl, "Learning Objectives", (knowledge.learning_objectives || []).length);
    addMetadataRow(knowledgeGridEl, "Concepts", (knowledge.concepts || []).length);
    addMetadataRow(knowledgeGridEl, "Definitions", (knowledge.definitions || []).length);
    addMetadataRow(knowledgeGridEl, "Formulae", (knowledge.formulae || []).length);
    addMetadataRow(knowledgeGridEl, "Examples", (knowledge.examples || []).length);
    addMetadataRow(knowledgeGridEl, "Applications", (knowledge.applications || []).length);
    addMetadataRow(knowledgeGridEl, "Misconceptions", (knowledge.misconceptions || []).length);

    const generated = MODULE_ORDER.filter((name) => teachingPackage[name]);
    const failed = Object.keys(teachingPackage.generation_errors || {});
    let summaryText = `${generated.length} of ${MODULE_ORDER.length} modules generated.`;
    if (failed.length) {
      summaryText += ` ${failed.length} module(s) could not be generated.`;
    }
    packageSummaryEl.textContent = summaryText;

    renderModuleCards(teachingPackage);

    document.getElementById("download-json").href = `/api/v1/export/${encodeURIComponent(documentId)}/json`;
    document.getElementById("download-pdf").href = `/api/v1/export/${encodeURIComponent(documentId)}/pdf`;
    document.getElementById("download-docx").href = `/api/v1/export/${encodeURIComponent(documentId)}/docx`;
    downloadUnavailableEl.hidden = generated.length > 0;

    showContent();
  }

  load();
})();
