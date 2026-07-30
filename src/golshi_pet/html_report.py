"""Self-contained Pet Derby evidence report."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any


def write_derby_html(report: dict[str, Any], atlas_path: Path, output: Path) -> None:
    image_type = "image/webp" if atlas_path.suffix.lower() == ".webp" else "image/png"
    image_data = base64.b64encode(atlas_path.read_bytes()).decode("ascii")
    metrics = report.get("metrics", {})
    worst = metrics.get("worst_transitions", [])
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item['state']))}</td>"
        f"<td>{item['from']} to {item['to']}</td>"
        f"<td>{item['centroid_jump']:.4f}</td>"
        f"<td>{item['area_ratio']:.4f}</td>"
        f"<td>{item['bbox_size_jump']:.4f}</td>"
        "</tr>"
        for item in worst
    )
    payload = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    status = "PASS" if report.get("ok") else "FAIL"
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pet Derby QA - {status}</title>
<style>
:root {{ color-scheme: dark; font-family: ui-monospace, Consolas, monospace; }}
body {{ margin: 0; background: #151316; color: #f7f2ea; }}
main {{ max-width: 1100px; margin: auto; padding: 32px 20px 64px; }}
.hero {{ display: grid; grid-template-columns: minmax(220px,360px) 1fr; gap: 24px; }}
.card {{ background: #211d24; border: 1px solid #4c3f54; padding: 18px; }}
.atlas {{ width: 100%; image-rendering: pixelated; background: #28232b; }}
h1 {{ margin-top: 0; font-size: clamp(2rem, 6vw, 4.5rem); line-height: .9; }}
.pass {{ color: #82e6a0; }} .fail {{ color: #ff8e88; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; border-bottom: 1px solid #433949; padding: 8px; }}
code {{ color: #ffda76; }}
@media (max-width: 760px) {{ .hero {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<main>
<div class="hero">
  <div class="card">
    <img class="atlas" alt="Validated Codex pet atlas"
      src="data:{image_type};base64,{image_data}">
  </div>
  <section>
    <p>SEEDED CODEX PET TRANSITION STRESS TEST</p>
    <h1 class="{status.lower()}">{status}</h1>
    <div class="card">
      <p>Seed <code>{metrics.get("seed")}</code>;
        steps <code>{metrics.get("steps")}</code></p>
      <p>Sequence SHA-256
        <code>{html.escape(str(metrics.get("sequence_sha256", "")))}</code></p>
      <p>Atlas SHA-256
        <code>{html.escape(str(metrics.get("atlas_sha256", "")))}</code></p>
    </div>
  </section>
</div>
<section class="card" style="margin-top:24px">
  <h2>Worst adjacent transitions</h2>
  <table>
    <thead>
      <tr><th>State</th><th>Frames</th><th>Centroid</th>
        <th>Area ratio</th><th>BBox</th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</section>
<script type="application/json" id="pet-derby-report">{payload}</script>
</main>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8", newline="\n")
