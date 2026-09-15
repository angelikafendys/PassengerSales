"""
Generates a standalone, self-contained interactive HTML report.
The data is embedded directly into the HTML so it works completely offline without a server.
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INSIGHTS_JSON = os.path.join(DATA_DIR, "summary_insights.json")
TEMPLATE_PATH = os.path.join(BASE_DIR, "dashboard", "templates", "index.html")
OUTPUT_HTML = os.path.join(BASE_DIR, "laporan_tren_booking_2025.html")

def generate_report():
    print("Reading data and template...")
    with open(INSIGHTS_JSON, "r", encoding="utf-8") as f:
        data_json_str = f.read()

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    # In standalone mode, replace fetch('/api/summary') with direct inline variable assignment
    replacement_script = f"""
    async function loadData() {{
      try {{
        globalData = {data_json_str};
        initKPIs();
        initDailyTrendChart();
        initHourlyChart();
        initMonthlyChart();
        initHeatmapChart();
        initLeadTimeCharts();
        initRouteCharts();
        initChannelCharts();
        initClassCharts();
        lucide.createIcons();
      }} catch (err) {{
        console.error('Failed to load embedded data:', err);
      }}
    }}
    """

    # Replace fetch function
    start_marker = "async function loadData() {"
    end_marker = "window.addEventListener('DOMContentLoaded', loadData);"

    start_idx = html_content.find(start_marker)
    end_idx = html_content.find(end_marker)

    if start_idx != -1 and end_idx != -1:
        new_html = html_content[:start_idx] + replacement_script + "\n    " + html_content[end_idx:]
    else:
        # Fallback if marker not found
        new_html = html_content.replace(
            "const res = await fetch('/api/summary');\n        globalData = await res.json();",
            f"globalData = {data_json_str};"
        )

    # Disable backend download link in offline mode, make it export client-side CSV
    new_html = new_html.replace(
        'href="/api/export-csv"',
        'href="data/daily_summary.csv" download="kai_daily_booking_summary_2025.csv"'
    )

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    file_size_mb = os.path.getsize(OUTPUT_HTML) / (1024 * 1024)
    print(f"Standalone report successfully generated: {OUTPUT_HTML}")
    print(f"File size: {file_size_mb:.2f} MB")
    print("You can open this file directly in any web browser!")

if __name__ == "__main__":
    generate_report()
