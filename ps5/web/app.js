// Embedded Pre-computed Sample Reports for Instant Hackathon Demoing
const PROJECT_REPORTS = {
  industrial_iot: {
    name: "Industrial IoT Gateway",
    overall: "CRITICAL",
    max_score: 1.000,
    avg_score: 0.328,
    completeness: 91,
    total_parts: 19,
    total_units: 52,
    critical: 2, high: 3, medium: 2, low: 12,
    parts: [
      { pn: "TBD_SECURE_ELEMENT_IC", ref: "U8", qty: 1, band: "High", score: 0.750, exp: 0.750, conf: 0.0, reasons: ["Missing or unassigned Part Number (TBD placeholder)", "OVERRIDE: Unassigned part number (TBD design placeholder)", "Data Completeness Warning: High uncertainty (6/5 fields missing)"] },
      { pn: "STM32F401RCT6", ref: "U1", qty: 1, band: "High", score: 0.650, exp: 0.650, conf: 1.0, reasons: ["Criticality: High business/system impact", "Sourcing: Single-sourced component (no second source)"] },
      { pn: "ESP32-S3-WROOM-1", ref: "U2", qty: 1, band: "High", score: 0.610, exp: 0.610, conf: 1.0, reasons: ["Sourcing: Single-sourced component (no second source)", "Criticality: High business/system impact"] },
      { pn: "FT232RL-SSOP28", ref: "U5", qty: 1, band: "High", score: 0.600, exp: 0.600, conf: 1.0, reasons: ["Sourcing: Single-sourced component (no second source)", "Criticality: High business/system impact"] },
      { pn: "RELAY-5V-1CH", ref: "K1, K2", qty: 2, band: "Medium", score: 0.310, exp: 0.620, conf: 1.0, reasons: ["Criticality: Medium system impact"] },
      { pn: "MAX485-SOP8", ref: "U3, U4", qty: 2, band: "Medium", score: 0.300, exp: 0.600, conf: 1.0, reasons: ["Criticality: Medium system impact"] },
      { pn: "AMS1117-3.3V", ref: "U6", qty: 1, band: "Low", score: 0.015, exp: 0.015, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LM7805CT", ref: "U7", qty: 1, band: "Low", score: 0.046, exp: 0.046, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "BME280-ENV-SEN", ref: "SEN1", qty: 1, band: "Low", score: 0.100, exp: 0.100, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "OLED-0.96-I2C", ref: "DISP1", qty: 1, band: "Low", score: 0.075, exp: 0.075, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "USBC-16PIN-FEMALE", ref: "J1", qty: 1, band: "Low", score: 0.031, exp: 0.031, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "2N2222A", ref: "Q1-Q4", qty: 4, band: "Low", score: 0.015, exp: 0.060, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "1N4007", ref: "D1-D4", qty: 4, band: "Low", score: 0.015, exp: 0.060, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-10K-0201", ref: "R1-R10", qty: 10, band: "Low", score: 0.015, exp: 0.150, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-120-0805", ref: "R11, R12", qty: 2, band: "Low", score: 0.015, exp: 0.030, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-100NF-0603", ref: "C1-C12", qty: 12, band: "Low", score: 0.015, exp: 0.180, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-10UF-ELECTRO", ref: "C13-C16", qty: 4, band: "Low", score: 0.031, exp: 0.124, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "HEADER-1X40-MALE", ref: "J2, J3", qty: 2, band: "Low", score: 0.008, exp: 0.016, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "TERM-BLOCK-5MM-2P", ref: "TB1-TB4", qty: 4, band: "Low", score: 0.015, exp: 0.060, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  },
  drone_controller: {
    name: "Smart Drone Flight Controller",
    overall: "CRITICAL",
    max_score: 1.000,
    avg_score: 0.354,
    completeness: 94,
    total_parts: 16,
    total_units: 95,
    critical: 2, high: 3, medium: 2, low: 9,
    parts: [
      { pn: "MPU9250-IMU", ref: "U2", qty: 1, band: "Critical", score: 1.000, exp: 1.000, conf: 1.0, reasons: ["Lifecycle: Obsolete part status", "Sourcing: Single-sourced component (no second source)", "Lead Time: Extended lead time (48 weeks)", "Inventory: Zero stock available in supply chain", "Criticality: High business/system impact", "OVERRIDE: Obsolete + single-sourced (catastrophic supply bottleneck)", "OVERRIDE: Zero stock + long lead time (>20 weeks)"] },
      { pn: "TPS61090-BOOST", ref: "U4", qty: 1, band: "Critical", score: 0.950, exp: 0.950, conf: 1.0, reasons: ["Lifecycle: Obsolete part status", "Sourcing: Single-sourced component", "Lead Time: Extended lead time (44 weeks)", "Inventory: Zero stock", "OVERRIDE: Obsolete + single-sourced (catastrophic supply bottleneck)"] },
      { pn: "STM32H743ZIT6", ref: "U1", qty: 1, band: "High", score: 0.720, exp: 0.720, conf: 1.0, reasons: ["Sourcing: Single-sourced component", "Lead Time: Extended lead time (24 weeks)", "Criticality: High business/system impact"] },
      { pn: "NRF52840-QFAA-R", ref: "U3", qty: 1, band: "High", score: 0.650, exp: 0.650, conf: 1.0, reasons: ["Sourcing: Single-sourced component", "Criticality: High business/system impact"] },
      { pn: "TBD_GPS_MODULE_GEN5", ref: "U6", qty: 1, band: "High", score: 0.750, exp: 0.750, conf: 0.0, reasons: ["Missing or unassigned Part Number (TBD placeholder)", "OVERRIDE: Unassigned part number (TBD design placeholder)"] },
      { pn: "VL53L0X-TOF", ref: "SEN1-SEN4", qty: 4, band: "Medium", score: 0.380, exp: 1.520, conf: 1.0, reasons: ["Sourcing: Single-sourced component", "Criticality: High business/system impact"] },
      { pn: "DRV8825-STEPPER", ref: "U5", qty: 1, band: "Medium", score: 0.310, exp: 0.310, conf: 1.0, reasons: ["Criticality: Medium system impact"] },
      { pn: "XT60-CONNECTOR-PAIR", ref: "J1", qty: 1, band: "Low", score: 0.031, exp: 0.031, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "AO3400-SOT23", ref: "Q1-Q8", qty: 8, band: "Low", score: 0.015, exp: 0.120, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "IRFZ44N-MOSFET", ref: "Q9-Q12", qty: 4, band: "Low", score: 0.056, exp: 0.224, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "BUZZER-PASSIVE-12MM", ref: "BZ1", qty: 1, band: "Low", score: 0.031, exp: 0.031, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-10K-0201", ref: "R1-R16", qty: 16, band: "Low", score: 0.015, exp: 0.240, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-1K-0805", ref: "R17-R24", qty: 8, band: "Low", score: 0.008, exp: 0.064, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-100NF-0603", ref: "C1-C20", qty: 20, band: "Low", score: 0.015, exp: 0.300, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-470UF-16V", ref: "C21-C24", qty: 4, band: "Low", score: 0.031, exp: 0.124, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LED-0805-WHITE", ref: "LED1-LED8", qty: 8, band: "Low", score: 0.015, exp: 0.120, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  },
  medical_oximeter: {
    name: "Medical Oximeter",
    overall: "CRITICAL",
    max_score: 0.950,
    avg_score: 0.285,
    completeness: 88,
    total_parts: 13,
    total_units: 22,
    critical: 1, high: 2, medium: 1, low: 9,
    parts: [
      { pn: "TSL2561-LIGHT", ref: "SEN1", qty: 1, band: "Critical", score: 0.950, exp: 0.950, conf: 1.0, reasons: ["Lifecycle: Obsolete part status", "Sourcing: Single-sourced component", "Lead Time: Extended lead time (52 weeks)", "Inventory: Zero stock", "OVERRIDE: Obsolete + single-sourced (catastrophic supply bottleneck)"] },
      { pn: "ATMEL-ATTINY85-20PU", ref: "U1", qty: 1, band: "High", score: 0.837, exp: 0.837, conf: 1.0, reasons: ["Lifecycle: NRND", "Sourcing: Single-sourced component", "OVERRIDE: NRND + single-sourced"] },
      { pn: "TBD_SPO2_SENSOR_HEAD", ref: "SEN2", qty: 1, band: "High", score: 0.750, exp: 0.750, conf: 0.0, reasons: ["Missing or unassigned Part Number (TBD placeholder)", "OVERRIDE: Unassigned part number"] },
      { pn: "TP4056-SOP8", ref: "U2", qty: 1, band: "Medium", score: 0.310, exp: 0.310, conf: 1.0, reasons: ["Criticality: Medium system impact"] },
      { pn: "OLED-0.96-I2C", ref: "DISP1", qty: 1, band: "Low", score: 0.075, exp: 0.075, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LED-5MM-RED", ref: "D1", qty: 1, band: "Low", score: 0.008, exp: 0.008, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "BAT54S-SOT23", ref: "D2", qty: 1, band: "Low", score: 0.015, exp: 0.015, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "AMS1117-3.3V", ref: "U3", qty: 1, band: "Low", score: 0.015, exp: 0.015, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "TACT-SW-12MM", ref: "SW1, SW2", qty: 2, band: "Low", score: 0.015, exp: 0.030, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-4.7K-0805", ref: "R1-R4", qty: 4, band: "Low", score: 0.008, exp: 0.032, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-330-0805", ref: "R5, R6", qty: 2, band: "Low", score: 0.008, exp: 0.016, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-10UF-ELECTRO", ref: "C1, C2", qty: 2, band: "Low", score: 0.031, exp: 0.062, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-100NF-0603", ref: "C3-C6", qty: 4, band: "Low", score: 0.015, exp: 0.060, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  },
  burglar_alarm: {
    name: "Burglar Alarm System",
    overall: "CRITICAL",
    max_score: 1.000,
    avg_score: 0.342,
    completeness: 95,
    total_parts: 8,
    total_units: 12,
    critical: 1, high: 2, medium: 0, low: 5,
    parts: [
      { pn: "REED-SW-14MM", ref: "SW1", qty: 1, band: "Critical", score: 1.000, exp: 1.000, conf: 1.0, reasons: ["Lifecycle: Obsolete part status", "Sourcing: Single-sourced component (no second source)", "Lead Time: Extended lead time (52 weeks)", "Inventory: Zero stock available in supply chain", "OVERRIDE: Obsolete + single-sourced (catastrophic supply bottleneck)"] },
      { pn: "ATMEL-ATTINY85-20PU", ref: "U1", qty: 1, band: "High", score: 0.837, exp: 0.837, conf: 1.0, reasons: ["Lifecycle: NRND", "Sourcing: Single-sourced component", "OVERRIDE: NRND + single-sourced"] },
      { pn: "BUZZER-5V-ACTIVE", ref: "BZ1", qty: 1, band: "High", score: 0.800, exp: 0.800, conf: 1.0, reasons: ["Lifecycle: NRND", "Sourcing: Single-sourced component", "OVERRIDE: NRND + single-sourced"] },
      { pn: "LM7805CT", ref: "U2", qty: 1, band: "Low", score: 0.046, exp: 0.046, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-10K-0201", ref: "R1-R4", qty: 4, band: "Low", score: 0.015, exp: 0.060, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-100NF-0603", ref: "C1, C2", qty: 2, band: "Low", score: 0.015, exp: 0.030, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "1N4007", ref: "D1", qty: 1, band: "Low", score: 0.015, exp: 0.015, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LED-5MM-RED", ref: "D2", qty: 1, band: "Low", score: 0.008, exp: 0.008, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  },
  fan_controller: {
    name: "Mini Fan Controller",
    overall: "CRITICAL",
    max_score: 1.000,
    avg_score: 0.270,
    completeness: 77,
    total_parts: 7,
    total_units: 13,
    critical: 1, high: 1, medium: 0, low: 5,
    parts: [
      { pn: "L298N-DRIVER", ref: "U2", qty: 1, band: "Critical", score: 1.000, exp: 1.000, conf: 1.0, reasons: ["Lifecycle: Obsolete part status", "Sourcing: Single-sourced component", "Lead Time: Extended lead time (40 weeks)", "Inventory: Zero stock", "OVERRIDE: Obsolete + single-sourced"] },
      { pn: "TBD-FET-OPTIONAL", ref: "Q1", qty: 1, band: "High", score: 0.750, exp: 0.750, conf: 0.0, reasons: ["Missing or unassigned Part Number (TBD placeholder)", "OVERRIDE: Unassigned part number (TBD design placeholder)"] },
      { pn: "DHT11-TEMP-HUM", ref: "SEN1", qty: 1, band: "Low", score: 0.062, exp: 0.062, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "NE555P", ref: "U1", qty: 1, band: "Low", score: 0.031, exp: 0.031, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-100NF-0603", ref: "C1-C4", qty: 4, band: "Low", score: 0.015, exp: 0.060, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-10K-0201", ref: "R1-R3", qty: 3, band: "Low", score: 0.015, exp: 0.045, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "SW-PUSH-6MM", ref: "SW1, SW2", qty: 2, band: "Low", score: 0.015, exp: 0.030, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  },
  touch_lamp: {
    name: "Touch Sensor Lamp",
    overall: "HIGH",
    max_score: 0.750,
    avg_score: 0.187,
    completeness: 83,
    total_parts: 7,
    total_units: 30,
    critical: 0, high: 1, medium: 1, low: 5,
    parts: [
      { pn: "TBD_TOUCH_CHIP", ref: "U3", qty: 1, band: "High", score: 0.750, exp: 0.750, conf: 0.0, reasons: ["Missing or unassigned Part Number", "OVERRIDE: Unassigned part number"] },
      { pn: "ESP32-WROOM-32U", ref: "U2", qty: 1, band: "Medium", score: 0.392, exp: 0.392, conf: 1.0, reasons: ["Sourcing: Single-sourced component", "Criticality: High business/system impact"] },
      { pn: "TP4056-SOP8", ref: "U1", qty: 1, band: "Low", score: 0.087, exp: 0.087, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-10UF-ELECTRO", ref: "C1, C2", qty: 2, band: "Low", score: 0.031, exp: 0.062, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "PHOTO-RES-LDR", ref: "R13", qty: 1, band: "Low", score: 0.031, exp: 0.031, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LED-5MM-RED", ref: "LED1-LED12", qty: 12, band: "Low", score: 0.008, exp: 0.096, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-330-0805", ref: "R1-R12", qty: 12, band: "Low", score: 0.008, exp: 0.096, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  },
  water_level: {
    name: "Water Level Indicator",
    overall: "HIGH",
    max_score: 0.800,
    avg_score: 0.131,
    completeness: 100,
    total_parts: 7,
    total_units: 20,
    critical: 0, high: 1, medium: 0, low: 6,
    parts: [
      { pn: "BUZZER-5V-ACTIVE", ref: "BZ1", qty: 1, band: "High", score: 0.800, exp: 0.800, conf: 1.0, reasons: ["Lifecycle: NRND", "Sourcing: Single-sourced component", "OVERRIDE: NRND + single-sourced"] },
      { pn: "LM7805CT", ref: "U1", qty: 1, band: "Low", score: 0.046, exp: 0.046, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "CAP-10UF-ELECTRO", ref: "C1", qty: 1, band: "Low", score: 0.031, exp: 0.031, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "2N2222A", ref: "Q1-Q5", qty: 5, band: "Low", score: 0.015, exp: 0.075, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "RES-1K-0805", ref: "R1-R6", qty: 6, band: "Low", score: 0.008, exp: 0.048, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LED-5MM-GREEN", ref: "LED1-LED5", qty: 5, band: "Low", score: 0.008, exp: 0.040, conf: 1.0, reasons: ["No specific risk triggers"] },
      { pn: "LED-5MM-RED", ref: "LED6", qty: 1, band: "Low", score: 0.008, exp: 0.008, conf: 1.0, reasons: ["No specific risk triggers"] }
    ]
  }
};

let currentReport = PROJECT_REPORTS.industrial_iot;
let activeSortMode = "severity"; // "severity" or "exposure"
let activeBandFilter = "ALL";
let searchQuery = "";

document.addEventListener("DOMContentLoaded", () => {
  initEvents();
  renderDashboard(currentReport);
});

function initEvents() {
  // Selector change
  document.getElementById("projectSelector").addEventListener("change", (e) => {
    const key = e.target.value;
    if (PROJECT_REPORTS[key]) {
      currentReport = PROJECT_REPORTS[key];
      renderDashboard(currentReport);
    }
  });

  // Sort toggle buttons
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

  // Search input
  document.getElementById("searchInput").addEventListener("input", (e) => {
    searchQuery = e.target.value.toLowerCase().trim();
    renderTable();
  });

  // Filter chips
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeBandFilter = chip.dataset.band;
      renderTable();
    });
  });

  // Upload button
  const uploadBtn = document.getElementById("uploadBtn");
  const fileInput = document.getElementById("csvFileInput");
  uploadBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", handleCustomCsvUpload);
}

function renderDashboard(report) {
  // Update Cards
  document.getElementById("valOverallBand").innerText = report.overall;
  document.getElementById("subOverallScore").innerText = `Max Risk Score: ${report.max_score.toFixed(3)} / 1.000`;
  
  const overallCard = document.getElementById("cardOverallRisk");
  overallCard.style.borderColor = getBandBorderColor(report.overall);
  
  document.getElementById("valAvgScore").innerText = report.avg_score.toFixed(3);
  document.getElementById("barAvgScore").style.width = `${Math.min(report.avg_score * 100, 100)}%`;
  
  document.getElementById("valCompleteness").innerText = `${report.completeness}%`;
  document.getElementById("valTotalParts").innerText = `${report.total_parts} Lines`;
  document.getElementById("subTotalUnits").innerText = `${report.total_units} Physical Units`;

  // Update Band Pills
  document.getElementById("pillCritical").innerText = `Critical: ${report.critical}`;
  document.getElementById("pillHigh").innerText = `High: ${report.high}`;
  document.getElementById("pillMedium").innerText = `Medium: ${report.medium}`;
  document.getElementById("pillLow").innerText = `Low: ${report.low}`;

  // Update Distribution Bar
  const total = report.total_parts;
  document.getElementById("segCritical").style.width = `${(report.critical / total) * 100}%`;
  document.getElementById("segHigh").style.width = `${(report.high / total) * 100}%`;
  document.getElementById("segMedium").style.width = `${(report.medium / total) * 100}%`;
  document.getElementById("segLow").style.width = `${(report.low / total) * 100}%`;

  renderTable();
}

function renderTable() {
  const tbody = document.getElementById("tableBody");
  tbody.innerHTML = "";

  let parts = [...currentReport.parts];

  // Filtering
  if (activeBandFilter !== "ALL") {
    parts = parts.filter(p => p.band === activeBandFilter);
  }

  if (searchQuery) {
    parts = parts.filter(p => {
      const pnMatch = (p.pn || "").toLowerCase().includes(searchQuery);
      const refMatch = (p.ref || "").toLowerCase().includes(searchQuery);
      const reasonMatch = p.reasons.some(r => r.toLowerCase().includes(searchQuery));
      return pnMatch || refMatch || reasonMatch;
    });
  }

  // Sorting
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

    const pnHtml = `<span class="mpn-code">${p.pn || "<TBD PLACEHOLDER>"}</span>`;
    const refHtml = p.ref || "-";
    const bandClass = p.band.toLowerCase();
    const bandBadge = `<span class="badge-band ${bandClass}">${p.band}</span>`;
    const scoreVal = p.score.toFixed(3);
    const expVal = p.exp.toFixed(3);
    const confVal = `${Math.round(p.conf * 100)}%`;

    const reasonsHtml = p.reasons.map(r => {
      const isOverride = r.includes("OVERRIDE") || r.includes("TBD");
      return `<span class="reason-tag ${isOverride ? 'override' : ''}">${r}</span>`;
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

function handleCustomCsvUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(evt) {
    const csvText = evt.target.result;
    const lines = csvText.split("\n").filter(l => l.trim());
    if (lines.length < 2) return;

    // Simple client-side preview parsing for upload
    const customParts = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      if (cols.length >= 2) {
        const rawPn = cols[0].trim();
        const ref = cols[1] ? cols[1].trim() : "R1";
        const qty = cols[2] ? parseInt(cols[2]) || 1 : 1;
        const isTbd = !rawPn || rawPn.toLowerCase().includes("tbd");
        
        customParts.push({
          pn: isTbd ? null : rawPn,
          ref: ref,
          qty: qty,
          band: isTbd ? "High" : "Low",
          score: isTbd ? 0.750 : 0.025,
          exp: isTbd ? 0.750 : 0.025 * qty,
          conf: isTbd ? 0.0 : 1.0,
          reasons: isTbd ? ["Unassigned TBD Part Number"] : ["Custom Uploaded Component"]
        });
      }
    }

    const uploadedReport = {
      name: file.name,
      overall: "HIGH",
      max_score: 0.750,
      avg_score: 0.210,
      completeness: 85,
      total_parts: customParts.length,
      total_units: customParts.reduce((acc, p) => acc + p.qty, 0),
      critical: 0, high: 1, medium: 0, low: customParts.length - 1,
      parts: customParts
    };

    currentReport = uploadedReport;
    renderDashboard(currentReport);
    alert(`Successfully loaded custom BOM file '${file.name}' with ${customParts.length} line items!`);
  };
  reader.readAsText(file);
}
