"""
Generates a standalone, self-contained interactive HTML report.
The data is embedded directly into window.EMBEDDED_DATA so it works completely offline
and on static Vercel hosting without any server dependency. All JavaScript functions and charts remain 100% intact.
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INSIGHTS_JSON = os.path.join(DATA_DIR, "summary_insights.json")
TEMPLATE_PATH = os.path.join(BASE_DIR, "dashboard", "templates", "index.html")
OUTPUT_HTML = os.path.join(BASE_DIR, "index.html")

def generate_report():
    print("Reading data and template...")
    with open(INSIGHTS_JSON, "r", encoding="utf-8") as f:
        data_json_str = f.read().strip()

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Replace window.EMBEDDED_DATA = null; with actual json data
    target_marker = "window.EMBEDDED_DATA = null;"
    if target_marker not in html_content:
        raise ValueError(f"Marker '{target_marker}' not found in {TEMPLATE_PATH}!")
        
    new_html = html_content.replace(target_marker, f"window.EMBEDDED_DATA = {data_json_str};", 1)

    # Ensure CSV download link points to static file for offline / Vercel
    new_html = new_html.replace(
        'href="/api/export-csv"',
        'href="data/daily_summary.csv" download="kai_daily_booking_summary_2025.csv"'
    )

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    file_size_kb = os.path.getsize(OUTPUT_HTML) / 1024
    print(f"Standalone report successfully generated: {OUTPUT_HTML}")
    print(f"File size: {file_size_kb:.1f} KB")
    print("Report is 100% self-contained and ready for Vercel and offline browser viewing!")

if __name__ == "__main__":
    generate_report()
