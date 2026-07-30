const reportOutput = document.querySelector("#report-output");
const reportButtons = document.querySelectorAll("[data-report]");
const cache = new Map();

function metricList(items) {
  const list = document.createElement("dl");
  items.forEach(([label, value]) => {
    const group = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = String(value);
    group.append(term, detail);
    list.append(group);
  });
  return list;
}

function renderDerby(report) {
  const metrics = report.metrics;
  return metricList([
    ["Status", report.ok ? "PASS" : "FAIL"],
    ["Seed", metrics.seed],
    ["Steps", metrics.steps],
    ["State coverage", `${Math.round(metrics.coverage.state_ratio * 100)}%`],
    ["Look coverage", `${Math.round(metrics.coverage.direction_ratio * 100)}%`],
    ["Sequence SHA-256", metrics.sequence_sha256],
  ]);
}

function renderBackdrop(report) {
  const metrics = report.metrics;
  const weakest = [...metrics.background_summary].sort(
    (first, second) =>
      first.worst_edge_contrast_p10 - second.worst_edge_contrast_p10,
  )[0];
  return metricList([
    ["Status", report.ok ? "PASS" : "FAIL"],
    ["Cells", metrics.cells_measured],
    ["Measurements", metrics.measurement_count],
    ["Backgrounds", metrics.background_summary.length],
    ["Weakest background", weakest.name],
    ["Worst edge p10", weakest.worst_edge_contrast_p10.toFixed(3)],
  ]);
}

async function loadReport(name) {
  reportOutput.replaceChildren();
  const loading = document.createElement("p");
  loading.className = "report-state";
  loading.textContent = "Loading verified evidence...";
  reportOutput.append(loading);
  try {
    const report = cache.has(name)
      ? cache.get(name)
      : await fetch(`assets/${name}-report.json`, { cache: "no-store" }).then(
          (response) => {
            if (!response.ok) {
              throw new Error(`Report request returned ${response.status}`);
            }
            return response.json();
          },
        );
    cache.set(name, report);
    reportOutput.replaceChildren(
      name === "derby" ? renderDerby(report) : renderBackdrop(report),
    );
  } catch (error) {
    const message = document.createElement("p");
    message.className = "report-state error";
    message.textContent =
      "Evidence could not be loaded. Download the release and run the acceptance commands.";
    reportOutput.replaceChildren(message);
  }
}

reportButtons.forEach((button) => {
  button.addEventListener("click", () => {
    reportButtons.forEach((candidate) => {
      candidate.setAttribute(
        "aria-pressed",
        candidate === button ? "true" : "false",
      );
    });
    loadReport(button.dataset.report);
  });
});

const copyButton = document.querySelector("#copy-command");
const command = document.querySelector("#install-command");
const copyStatus = document.querySelector("#copy-status");

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(command.textContent);
    copyStatus.textContent = "Command copied.";
  } catch (error) {
    copyStatus.textContent = "Copy failed. Select the command manually.";
  }
});

loadReport("derby");
