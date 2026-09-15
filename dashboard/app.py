import os
import json
from flask import Flask, render_template, jsonify, send_file, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
INSIGHTS_JSON = os.path.join(DATA_DIR, "summary_insights.json")
CSV_SUMMARY = os.path.join(DATA_DIR, "daily_summary.csv")

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/summary")
def get_summary():
    if not os.path.exists(INSIGHTS_JSON):
        return jsonify({"error": "Summary insights data not found. Please run the ETL pipeline first."}), 404
    with open(INSIGHTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/api/export-csv")
def export_csv():
    if not os.path.exists(CSV_SUMMARY):
        return jsonify({"error": "CSV summary not found."}), 404
    return send_file(CSV_SUMMARY, as_attachment=True, download_name="kai_daily_booking_summary_2025.csv")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=======================================================")
    print(f"  KAI BOOKING TRENDS DASHBOARD 2025 RUNNING")
    print(f"  Open in your browser: http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
