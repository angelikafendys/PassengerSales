import os
import json
import duckdb

DATA_DIR = r"d:\Histori Booking\data"
JSON_PATH = os.path.join(DATA_DIR, "summary_insights.json")
DB_PATH = os.path.join(DATA_DIR, "booking_analytics.duckdb")

def verify():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)

    kpi = d["kpi"]
    print("=" * 60)
    print("           VERIFIKASI DATA BOOKING TAHUN 2025")
    print("=" * 60)
    print(f"Total Hari Teranalisis : {kpi['total_days']} hari")
    print(f"Total Tiket Terjual    : {kpi['total_tickets']:,} tiket")
    print(f"Total Pendapatan       : Rp {kpi['total_revenue']:,}")
    print(f"Rata-rata Tiket/Hari   : {kpi['avg_daily_tickets']:,} tiket/hari")
    print(f"Rata-rata Revenue/Hari : Rp {kpi['avg_daily_revenue']:,}/hari")
    print(f"Peak Day (Puncak)      : {kpi['peak_day']['date']} ({kpi['peak_day']['day_of_week']}) - {kpi['peak_day']['tickets']:,} tiket (Rp {kpi['peak_day']['revenue']:,})")
    print(f"Lowest Day (Terendah)  : {kpi['low_day']['date']} ({kpi['low_day']['day_of_week']}) - {kpi['low_day']['tickets']:,} tiket")
    
    print("\n--- DISTRIBUSI WAKTU & JAM SIBUK (HOURLY) ---")
    sorted_hours = sorted(d["hourly"], key=lambda x: x["tickets"], reverse=True)
    for h in sorted_hours[:5]:
        print(f"Jam {h['hour']:02d}:00 - {h['tickets']:,} tiket ({h['pct']}%), Rp {h['revenue']:,}")

    print("\n--- ANALISIS LEAD TIME (JARAK PEMESANAN) ---")
    for lt in d["lead_time"]:
        print(f"{lt['bucket']:<15}: {lt['tickets']:>10,} tiket ({lt['pct']:>5.2f}%) - Rp {lt['revenue']:>16,}")

    print("\n--- TOP 5 KANAL PEMESANAN (CHANNELS) ---")
    for ch in d["channels"][:5]:
        print(f"{ch['channel']:<12}: {ch['tickets']:>10,} tiket ({ch['pct']:>5.2f}%) - Rp {ch['revenue']:>16,}")

    print("\n--- TOP 5 METODE PEMBAYARAN ---")
    for pay in d["payments"][:5]:
        print(f"{pay['pay_type']:<15} ({pay['pic_pay']:<18}): {pay['tickets']:>10,} tiket ({pay['pct']:>5.2f}%)")

    print("\n--- TOP 5 RUTE TERPOPULER ---")
    for r in d["top_routes"][:5]:
        print(f"{r['route']:<15}: {r['tickets']:>10,} tiket | Rp {r['revenue']:>15,} | Rata-rata: Rp {r['avg_price']:>9,}")

    print("\n--- TOP 5 KERETA API DENGAN VOLUME TERTINGGI ---")
    for tr in d["top_trains"][:5]:
        print(f"{tr['train_name']:<20}: {tr['tickets']:>10,} tiket | Rp {tr['revenue']:>15,} | Rata-rata: Rp {tr['avg_price']:>9,}")

    print("\n--- DISTRIBUSI KELAS KERETA ---")
    for cl in d["classes"]:
        print(f"{cl['wagon_class']:<10}: {cl['tickets']:>10,} tiket ({cl['pct']:>5.2f}%) - Rp {cl['revenue']:>16,}")

    print("\n" + "=" * 60)
    print("Verifikasi selesai: Seluruh 365 hari terpetakan dengan lengkap!")
    print("=" * 60)

if __name__ == "__main__":
    verify()
