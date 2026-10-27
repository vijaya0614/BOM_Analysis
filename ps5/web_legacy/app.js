let currentReport = null;
let activeSortMode = "severity";
let activeBandFilter = "ALL";
let searchQuery = "";
let selectedPart = null;
let activeSubstituteResponse = null;

const RISK_API_BASE = "http://127.0.0.1:8001";
const SUBSTITUTE_API_BASE = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
  createSubstitutePanel();
  initEvents();
  loadProjectsAndInitialReport();
});

function initEvents() {
  document.getElementById("projectSelector").addEventListener("change", (e) => {
    closeSubstitutePanel();
    loadRiskReportForProject(e.target.value);
  });

  document.getElementById("btnSortSeverity").addEventListener("click", () => {
    activeSortMode = "severity";
    document.getElementById("btnSortSeverity").classList.add("active");
    document.getElementById("btnSortExposure").classList.remove("active");
    renderTable();
  });

  document.getElementById("btnSortExposure").addEventListener("click", () => {
    activeSortMode = "exposure";
    document.getElementById("btnSortExposure").classList.add("active");
    document.getElementById("btnSortSeverity").classList.remove("active");
    renderTable();
  });

  document.getElementById("searchInput").addEventListener("input", (e) => {
    searchQuery = e.target.value.toLowerCase().trim();
    renderTable();
  });

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeBandFilter = chip.dataset.band;
      renderTable();
    });
  });

  const uploadBtn = document.getElementById("uploadBtn");
  const fileInput = document.getElementById("csvFileInput");
  uploadBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", handleCustomCsvUpload);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSubstitutePanel();
  });
}

async function loadProjectsAndInitialReport() {
  try {
    const response = await fetch(`${RISK_API_BASE}/risk/projects`);
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.message || "Unable to load projects.");
    }
    populateProjectSelector(data.projects || []);
    const selector = document.getElementById("projectSelector");
    await loadRiskReportForProject(selector.value || "industrial_iot");
  } catch (error) {
    renderDashboardError("Risk API is not reachable. Start it with: python -m src.risk_api");
  }
}

function populateProjectSelector(projects) {
  const selector = document.getElementById("projectSelector");
  selector.innerHTML = "";
  projects.forEach(project => {
    const option = document.createElement("option");
    option.value = project.id;
    option.innerText = project.name;
    selector.appendChild(option);
  });
}

async function loadRiskReportForProject(projectId) {
  renderDashboardLoading("Running Person 1 risk pipeline...");
  try {
    const response = await fetch(`${RISK_API_BASE}/risk/analyze?project=${encodeURIComponent(projectId)}`);
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.message || "Risk analysis failed.");
    }
    currentReport = data.dashboard;
    renderDashboard(currentReport);
  } catch (error) {
    renderDashboardError(error.message || "Risk analysis failed.");
  }
}

function renderDashboard(report) {
  document.getElementById("valOverallBand").innerText = report.overall;
  document.getElementById("subOverallScore").innerText = `Max Risk Score: ${report.max_score.toFixed(3)} / 1.000`;

  const overallCard = document.getElementById("cardOverallRisk");
  overallCard.style.borderColor = getBandBorderColor(report.overall);

  document.getElementById("valAvgScore").innerText = report.avg_score.toFixed(3);
  document.getElementById("barAvgScore").style.width = `${Math.min(report.avg_score * 100, 100)}%`;

  document.getElementById("valCompleteness").innerText = `${report.completeness}%`;
  document.getElementById("valTotalParts").innerText = `${report.total_parts} Lines`;
  document.getElementById("subTotalUnits").innerText = `${report.total_units} Physical Units`;

  document.getElementById("pillCritical").innerText = `Critical: ${report.critical}`;
  document.getElementById("pillHigh").innerText = `High: ${report.high}`;
  document.getElementById("pillMedium").innerText = `Medium: ${report.medium}`;
  document.getElementById("pillLow").innerText = `Low: ${report.low}`;

  const total = Math.max(report.total_parts, 1);
  document.getElementById("segCritical").style.width = `${(report.critical / total) * 100}%`;
  document.getElementById("segHigh").style.width = `${(report.high / total) * 100}%`;
  document.getElementById("segMedium").style.width = `${(report.medium / total) * 100}%`;
  document.getElementById("segLow").style.width = `${(report.low / total) * 100}%`;

  renderTable();
}

function renderDashboardLoading(message) {
  currentReport = null;
  document.getElementById("valOverallBand").innerText = "LOADING";
  document.getElementById("subOverallScore").innerText = message;
  document.getElementById("valAvgScore").innerText = "0.000";
  document.getElementById("barAvgScore").style.width = "0%";
  document.getElementById("valCompleteness").innerText = "0%";
  document.getElementById("valTotalParts").innerText = "0 Lines";
  document.getElementById("subTotalUnits").innerText = "0 Physical Units";
  document.getElementById("pillCritical").innerText = "Critical: 0";
  document.getElementById("pillHigh").innerText = "High: 0";
  document.getElementById("pillMedium").innerText = "Medium: 0";
  document.getElementById("pillLow").innerText = "Low: 0";
  document.getElementById("tableBody").innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">${escapeHtml(message)}</td></tr>`;
}

function renderDashboardError(message) {
  currentReport = null;
  document.getElementById("valOverallBand").innerText = "OFFLINE";
  document.getElementById("subOverallScore").innerText = message;
  document.getElementById("tableBody").innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">${escapeHtml(message)}</td></tr>`;
}

function renderTable() {
  const tbody = document.getElementById("tableBody");
  tbody.innerHTML = "";

  if (!currentReport) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">No risk report loaded.</td></tr>`;
    return;
  }

  let parts = [...currentReport.parts];

  if (activeBandFilter !== "ALL") {
    parts = parts.filter(p => p.band === activeBandFilter);
  }

  if (searchQuery) {
    parts = parts.filter(p => {
      const pnMatch = (p.pn || "").toLowerCase().includes(searchQuery);
      const refMatch = (p.ref || "").toLowerCase().includes(searchQuery);
      const reasonMatch = (p.reasons || []).some(r => r.toLowerCase().includes(searchQuery));
      return pnMatch || refMatch || reasonMatch;
    });
  }

  if (activeSortMode === "severity") {
    parts.sort((a, b) => b.score - a.score);
  } else {
    parts.sort((a, b) => b.exp - a.exp);
  }

  if (parts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">No matching components found for the selected filter.</td></tr>`;
    return;
  }

  parts.forEach(p => {
    const tr = document.createElement("tr");
    tr.className = "risk-row";
    tr.tabIndex = 0;
    tr.setAttribute("role", "button");
    tr.setAttribute("aria-label", `Open substitute intelligence for ${p.pn || p.ref || "component"}`);

    const pnHtml = `<span class="mpn-code">${escapeHtml(p.pn || "<TBD PLACEHOLDER>")}</span>`;
    const refHtml = escapeHtml(p.ref || "-");
    const bandClass = p.band.toLowerCase();
    const bandBadge = `<span class="badge-band ${bandClass}">${escapeHtml(p.band)}</span>`;
    const scoreVal = Number(p.score || 0).toFixed(3);
    const expVal = Number(p.exp || 0).toFixed(3);
    const confVal = `${Math.round((p.conf || 0) * 100)}%`;

    const reasonsHtml = (p.reasons || []).map(r => {
      const isOverride = r.includes("OVERRIDE") || r.includes("TBD");
      return `<span class="reason-tag ${isOverride ? "override" : ""}">${escapeHtml(r)}</span>`;
    }).join("");

    tr.innerHTML = `
      <td>${pnHtml}</td>
      <td>${refHtml}</td>
      <td>${p.qty}</td>
      <td>${bandBadge}</td>
      <td><strong>${scoreVal}</strong></td>
      <td>${expVal}</td>
      <td>${confVal}</td>
      <td>${reasonsHtml}</td>
    `;
    tr.addEventListener("click", () => openSubstitutePanel(p));
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openSubstitutePanel(p);
      }
    });
    tbody.appendChild(tr);
  });
}

function getBandBorderColor(band) {
  switch (band.toUpperCase()) {
    case "CRITICAL": return "rgba(239, 68, 68, 0.5)";
    case "HIGH": return "rgba(249, 115, 22, 0.5)";
    case "MEDIUM": return "rgba(234, 179, 8, 0.5)";
    default: return "rgba(16, 185, 129, 0.5)";
  }
}

async function handleCustomCsvUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  renderDashboardLoading(`Uploading and analyzing ${file.name}...`);
  try {
    const csvText = await file.text();
    const response = await fetch(`${RISK_API_BASE}/risk/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, csv_text: csvText })
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.message || "Uploaded BOM analysis failed.");
    }
    currentReport = data.dashboard;
    closeSubstitutePanel();
    renderDashboard(currentReport);
  } catch (error) {
    renderDashboardError(error.message || "Uploaded BOM analysis failed.");
  } finally {
    e.target.value = "";
  }
}

function createSubstitutePanel() {
  if (document.getElementById("substituteOverlay")) return;

  const overlay = document.createElement("aside");
  overlay.id = "substituteOverlay";
  overlay.className = "substitute-overlay";
  overlay.innerHTML = `
    <div class="substitute-panel" role="dialog" aria-modal="true" aria-labelledby="subPanelTitle">
      <button class="panel-close" id="subPanelClose" aria-label="Close substitute panel">x</button>
      <div id="subPanelContent"></div>
    </div>
  `;
  document.body.appendChild(overlay);
  document.getElementById("subPanelClose").addEventListener("click", closeSubstitutePanel);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeSubstitutePanel();
  });
}

function openSubstitutePanel(part) {
  selectedPart = part;
  activeSubstituteResponse = null;
  const overlay = document.getElementById("substituteOverlay");
  overlay.classList.add("open");
  renderSubstitutePanelIntro(part);
}

function closeSubstitutePanel() {
  const overlay = document.getElementById("substituteOverlay");
  if (overlay) overlay.classList.remove("open");
  selectedPart = null;
  activeSubstituteResponse = null;
}

function renderSubstitutePanelIntro(part) {
  const content = document.getElementById("subPanelContent");
  const riskReasons = (part.reasons || []).map(reason => `<li>${escapeHtml(reason)}</li>`).join("");
  const identifier = getComponentLookupId(part);
  content.innerHTML = `
    <div class="panel-eyebrow">Component Risk</div>
    <h2 id="subPanelTitle">${escapeHtml(part.pn || "Unassigned component")}</h2>
    <div class="panel-meta">
      <span>Reference ${escapeHtml(part.ref || "-")}</span>
      <span>Qty ${part.qty}</span>
      <span>Catalog ${escapeHtml(part.catalog_status || "UNKNOWN")}</span>
    </div>
    <div class="risk-summary-grid">
      <div>
        <span class="summary-label">Risk</span>
        <strong class="summary-value ${part.band.toLowerCase()}">${escapeHtml(part.band)}</strong>
      </div>
      <div>
        <span class="summary-label">Score</span>
        <strong>${Number(part.score || 0).toFixed(3)}</strong>
      </div>
      <div>
        <span class="summary-label">Confidence</span>
        <strong>${Math.round((part.conf || 0) * 100)}%</strong>
      </div>
    </div>
    <div class="panel-section">
      <h3>Why Risky</h3>
      <ul class="risk-reason-list">${riskReasons || "<li>No specific risk triggers reported.</li>"}</ul>
    </div>
    <div class="panel-section substitute-start">
      <div>
        <h3>Substitute Intelligence</h3>
        <p>Uses verified catalog fields, deterministic compatibility rules, and Person 1 supply-chain scoring.</p>
      </div>
      <button class="btn btn-primary" id="findSubstitutesBtn" ${identifier ? "" : "disabled"}>Find Substitutes</button>
    </div>
    <div id="substituteResults"></div>
  `;

  const button = document.getElementById("findSubstitutesBtn");
  if (button) button.addEventListener("click", () => fetchSubstitutesForPart(part));
  if (!identifier) {
    renderPanelMessage("No verified substitute candidates are available for this component.", "warning");
  }
}

async function fetchSubstitutesForPart(part) {
  const identifier = getComponentLookupId(part);
  if (!identifier) return;

  const results = document.getElementById("substituteResults");
  results.innerHTML = `<div class="panel-state">Loading deterministic substitute recommendations...</div>`;

  try {
    const response = await fetch(`${SUBSTITUTE_API_BASE}/components/${encodeURIComponent(identifier)}/substitutes?include_incompatible=true`);
    const data = await response.json();
    if (!response.ok || data.error) {
      renderPanelMessage(data.message || "No substitute data could be found for this component.", "warning");
      return;
    }
    activeSubstituteResponse = data;
    renderSubstituteRecommendations(data);
  } catch (error) {
    renderPanelMessage(
      "Substitute API is not reachable. Start it with: python -m src.substitute_api",
      "error"
    );
  }
}

function renderSubstituteRecommendations(data) {
  const results = document.getElementById("substituteResults");
  const candidates = data.candidates || [];

  if (!candidates.length) {
    renderPanelMessage("No candidate components are available in the current catalog.", "warning");
    return;
  }

  const original = data.original || {};
  const best = candidates[0];
  const cards = candidates.slice(0, 5).map(candidate => renderCandidateCard(candidate)).join("");
  results.innerHTML = `
    <div class="panel-section original-hardware">
      <h3>Hardware Mapping</h3>
      <div class="hardware-map">
        <span>${escapeHtml(original.component_id || "-")}</span>
        <span>${escapeHtml(original.refdes || "-")}</span>
        <span>${escapeHtml(original.physical_location || "No physical location mapped")}</span>
      </div>
    </div>
    <div class="best-match">
      <span class="panel-eyebrow">Best Match</span>
      <h3>${escapeHtml(best.part_number)}</h3>
      <p>${escapeHtml(best.explanation || "")}</p>
    </div>
    <div class="candidate-list">${cards}</div>
    <div id="comparisonView"></div>
    <p class="engineering-warning">${escapeHtml(data.advisory_warning || "Engineering validation required before production approval.")}</p>
  `;
  document.querySelectorAll(".candidate-card").forEach(card => {
    card.addEventListener("click", () => {
      const id = card.dataset.componentId;
      const selected = candidates.find(candidate => candidate.component.component_id === id);
      if (selected) renderComparisonView(original, selected);
    });
  });
  renderComparisonView(original, best);
}

function renderCandidateCard(candidate) {
  const cls = classificationClass(candidate.classification);
  return `
    <button class="candidate-card ${cls}" data-component-id="${escapeHtml(candidate.component.component_id)}">
      <div>
        <span class="rank-chip">#${candidate.rank}</span>
        <strong>${escapeHtml(candidate.part_number)}</strong>
        <small>${escapeHtml(candidate.classification.replaceAll("_", " "))}</small>
      </div>
      <div class="candidate-scores">
        <span>${candidate.compatibility_score}% compat</span>
        <span>${candidate.confidence_score}% evidence</span>
        <span>${candidate.supply_chain_score}% supply</span>
      </div>
    </button>
  `;
}

function renderComparisonView(original, candidate) {
  const target = document.getElementById("comparisonView");
  const evidence = candidate.evidence_summary || {};
  const checks = (candidate.checks || []).map(check => {
    const statusClass = check.status.toLowerCase();
    return `
      <tr>
        <td>${escapeHtml(formatParam(check.parameter))}</td>
        <td>${escapeHtml(formatValue(check.original))}</td>
        <td>${escapeHtml(formatValue(check.candidate))}</td>
        <td><span class="check-status ${statusClass}">${escapeHtml(check.status)}</span></td>
      </tr>
    `;
  }).join("");

  target.innerHTML = `
    <div class="comparison-card">
      <div class="comparison-head">
        <div>
          <span class="panel-eyebrow">Original vs Candidate</span>
          <h3>${escapeHtml(original.part_number || "-")} vs ${escapeHtml(candidate.part_number)}</h3>
        </div>
        <span class="classification-pill ${classificationClass(candidate.classification)}">${escapeHtml(candidate.classification.replaceAll("_", " "))}</span>
      </div>
      <table class="comparison-table">
        <thead>
          <tr><th>Parameter</th><th>Original</th><th>Candidate</th><th>Evidence</th></tr>
        </thead>
        <tbody>${checks}</tbody>
      </table>
      <div class="comparison-foot">
        <span>Lifecycle: ${escapeHtml(candidate.lifecycle || "unknown")}</span>
        <span>Lead time: ${formatValue(candidate.lead_time_weeks)} weeks</span>
        <span>Stock: ${formatValue(candidate.stock)}</span>
        <span>Second source: ${formatValue(candidate.has_second_source)}</span>
        <span>Evidence confidence: ${formatValue(candidate.confidence_score)}%</span>
      </div>
      <div class="comparison-foot">
        <span>Matched: ${escapeHtml(formatList(evidence.matched_parameters))}</span>
        <span>Mismatched: ${escapeHtml(formatList(evidence.mismatched_parameters))}</span>
        <span>Unknown: ${escapeHtml(formatList(evidence.unknown_parameters))}</span>
      </div>
    </div>
  `;
}

function renderPanelMessage(message, type) {
  const results = document.getElementById("substituteResults");
  if (!results) return;
  results.innerHTML = `<div class="panel-state ${type}">${escapeHtml(message)}</div>`;
}

function getComponentLookupId(part) {
  if (part.substitute_lookup_id) return part.substitute_lookup_id;
  if (part.component_id) return part.component_id;
  return "";
}

function formatList(values) {
  if (!values || !values.length) return "none";
  return values.map(formatParam).join(", ");
}

function classificationClass(classification) {
  if (classification === "DROP_IN_CANDIDATE") return "drop-in";
  if (classification === "REQUIRES_REDESIGN") return "redesign";
  return "incompatible";
}

function formatParam(value) {
  return String(value || "").replaceAll("_", " ");
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "unknown";
  return String(value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
