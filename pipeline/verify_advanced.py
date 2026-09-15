import os
import json

DATA_DIR = r"d:\Histori Booking\data"
JSON_PATH = os.path.join(DATA_DIR, "summary_insights.json")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    d = json.load(f)

print("=" * 60)
print("     VERIFIKASI INTEGRASI ADVANCED EXCEL & TRIPDATE")
print("=" * 60)

print("\n--- 1. DEPARTURES VS BOOKINGS ---")
total_dep = sum(x["passengers"] for x in d.get("daily_departures", []))
total_dep_rev = sum(x["revenue"] for x in d.get("daily_departures", []))
print(f"Total Keberangkatan (Tripdate) : {total_dep:,} penumpang")
print(f"Total Revenue Keberangkatan    : Rp {total_dep_rev:,}")

print("\n--- 2. ANALISIS JARAK & KELAS (DISTANCE & CLASS) ---")
for dc in d.get("distance_class", []):
    print(f"Tier {dc['tier']:<6} | Kelas {dc['class']:<3} | Rute: {dc['routes_count']:>3} | Jarak: {dc['avg_km']:>5} km | Okupansi: {dc['avg_occupancy_pct']:>5}% | Rev: Rp {dc['revenue']:>15,}")

print("\n--- 3. ANALISIS MUSIMAN (SEASONALITY: JULI, OKTOBER, DESEMBER) ---")
for s in d.get("seasonality", []):
    print(f"{s['season']:<25} | Kelas {s['class']:<3} | Okupansi: {s['occupancy_pct']:>5.2f}% | Rev: Rp {s['revenue']:>15,} | Rata2 Harian: Rp {s['daily_revenue']:>12,}")

print("\n--- 4. TOP 5 RUTE PER MUSIM (SEASONALITY TOP ROUTES) ---")
for sr in d.get("seasonality_top_routes", []):
    print(f"{sr['season']:<25} | Relasi: {sr['relasi']:<12} | Okupansi: {sr['occupancy_pct']:>5.1f}% | Rev: Rp {sr['revenue']:>14,}")

print("\n--- 5. SAMPLE KUADRAN OKUPANSI VS REVENUE (TOP 8) ---")
for q in d.get("quadrant_trains", [])[:8]:
    print(f"{q['train_name']:<24} ({q['relasi']:<9} - {q['class']}): Okupansi: {q['occupancy_pct']:>5.1f}% | Rev: Rp {q['revenue']:>14,} | Jarak: {q['km']:>4} km")
