"""
Ultra Fast Ingestion & Analytics Script for:
1. Excel Rekap Okupansi 2025 (Sheets: OKUPANSI STATIS and PENDAPATAN)
2. Train Departure Trends (Tripdate) from Daily Booking CSVs
3. Distance & Class Analysis (JAUH, SEDANG, DEKAT x EKS, EKO, BIS)
4. Occupancy vs Revenue Quadrants
5. Seasonality Analysis (Juli = Libur Sekolah, Oktober = Reguler, Desember = Nataru)
"""

import os
import sys
import csv
import time
import json
import datetime
import openpyxl
import duckdb

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = r"d:\Histori Booking"
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
DB_PATH = os.path.join(DATA_DIR, "booking_analytics.duckdb")
EXCEL_PATH = os.path.join(BASE_DIR, "XLSX Data Rekap Okupansi tahun 2025 (Juli, Oktober, Desember).xlsx")
JSON_PATH = os.path.join(DATA_DIR, "summary_insights.json")

os.makedirs(TMP_DIR, exist_ok=True)

MONTH_FOLDERS = [
    "1. Januari", "2. Februari", "3. Maret", "4. April",
    "5. Mei", "6. Juni", "7. Juli", "8. Agustus",
    "9. September", "10. Oktober", "11. November", "12. Desember"
]

def get_connection():
    conn = duckdb.connect(DB_PATH)
    conn.execute(f"SET temp_directory = '{TMP_DIR.replace(chr(92), '/')}'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute("SET threads = 4")
    return conn

# -------------------------------------------------------------
# STEP 1: PARSE EXCEL SHEETS (OKUPANSI STATIS & PENDAPATAN)
# -------------------------------------------------------------
def parse_excel_data(conn):
    print("=" * 65, flush=True)
    print("STEP 1: PARSING EXCEL OKUPANSI STATIS & PENDAPATAN...", flush=True)
    print("=" * 65, flush=True)
    t0 = time.time()

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)

    # 1. Parse OKUPANSI STATIS directly to temp CSV
    print("Parsing sheet 'OKUPANSI STATIS' to temp CSV...", flush=True)
    ws_occ = wb['OKUPANSI STATIS']
    iter_occ = ws_occ.iter_rows(values_only=True)

    for _ in range(4): next(iter_occ)
    row5 = next(iter_occ)
    row6 = next(iter_occ)
    row7 = next(iter_occ)

    date_col_map = {}
    for c_idx, cell in enumerate(row7):
        if isinstance(cell, (datetime.datetime, datetime.date)):
            date_col_map[c_idx] = cell.strftime('%Y-%m-%d')

    occ_csv_path = os.path.join(TMP_DIR, "tmp_occupancy.csv")
    occ_count = 0
    with open(occ_csv_path, "w", newline="", encoding="utf-8") as f_occ:
        writer = csv.writer(f_occ)
        writer.writerow(["no_ka", "nama_ka", "relasi", "jarak_km", "kelas_jarak", "kelas", "wilayah", "log_date", "okupansi_statis"])

        for row in iter_occ:
            if row[0] is None or row[4] is None or str(row[4]).strip() == '':
                continue
            no_ka = str(row[0]).strip()
            nama_ka = str(row[4]).strip()
            relasi = str(row[5]).strip() if row[5] else ''
            try:
                jarak_km = float(row[6]) if row[6] is not None else 0.0
            except (ValueError, TypeError):
                jarak_km = 0.0
            kelas_jarak = str(row[7]).strip() if row[7] else 'LAINNYA'
            kelas = str(row[8]).strip() if row[8] else 'EKO'
            wilayah = str(row[10]).strip() if row[10] else 'JAWA'

            for col_idx, dt_str in date_col_map.items():
                if col_idx < len(row):
                    val = row[col_idx]
                    if val is not None and str(val).strip() != '':
                        try:
                            occ_val = float(val)
                            writer.writerow([no_ka, nama_ka, relasi, jarak_km, kelas_jarak, kelas, wilayah, dt_str, occ_val])
                            occ_count += 1
                        except (ValueError, TypeError):
                            pass

    print(f"Wrote {occ_count:,} occupancy records to CSV in {time.time()-t0:.2f}s.", flush=True)

    # 2. Parse PENDAPATAN directly to temp CSV
    print("Parsing sheet 'PENDAPATAN' to temp CSV...", flush=True)
    t1 = time.time()
    ws_rev = wb['PENDAPATAN']
    iter_rev = ws_rev.iter_rows(values_only=True)

    for _ in range(4): next(iter_rev)
    _ = next(iter_rev)
    _ = next(iter_rev)
    row7_rev = next(iter_rev)

    date_col_map_rev = {}
    for c_idx, cell in enumerate(row7_rev):
        if isinstance(cell, (datetime.datetime, datetime.date)):
            date_col_map_rev[c_idx] = cell.strftime('%Y-%m-%d')

    rev_csv_path = os.path.join(TMP_DIR, "tmp_revenue.csv")
    rev_count = 0
    with open(rev_csv_path, "w", newline="", encoding="utf-8") as f_rev:
        writer = csv.writer(f_rev)
        writer.writerow(["no_ka", "relasi", "kelas", "log_date", "revenue_excel"])

        for row in iter_rev:
            if row[0] is None or row[4] is None or str(row[4]).strip() == '':
                continue
            no_ka = str(row[0]).strip()
            relasi = str(row[5]).strip() if row[5] else ''
            kelas = str(row[8]).strip() if row[8] else 'EKO'

            for col_idx, dt_str in date_col_map_rev.items():
                if col_idx < len(row):
                    val = row[col_idx]
                    if val is not None and str(val).strip() != '':
                        try:
                            rev_val = float(val)
                            if rev_val > 0:
                                writer.writerow([no_ka, relasi, kelas, dt_str, rev_val])
                                rev_count += 1
                        except (ValueError, TypeError):
                            pass

    print(f"Wrote {rev_count:,} revenue records to CSV in {time.time()-t1:.2f}s.", flush=True)
    wb.close()

    # Lightning Fast Load into DuckDB using COPY FROM
    print("Loading temp CSVs into DuckDB via vectorized COPY...", flush=True)
    t2 = time.time()
    conn.execute("DROP TABLE IF EXISTS stage_excel_occupancy;")
    conn.execute(f"""
    CREATE TABLE stage_excel_occupancy AS 
    SELECT * FROM read_csv('{occ_csv_path.replace(chr(92), '/')}', header=True);
    """)

    conn.execute("DROP TABLE IF EXISTS stage_excel_revenue;")
    conn.execute(f"""
    CREATE TABLE stage_excel_revenue AS 
    SELECT * FROM read_csv('{rev_csv_path.replace(chr(92), '/')}', header=True);
    """)

    conn.execute("DROP TABLE IF EXISTS excel_daily_master;")
    conn.execute("""
    CREATE TABLE excel_daily_master AS
    SELECT 
        o.no_ka,
        o.nama_ka,
        o.relasi,
        o.jarak_km,
        o.kelas_jarak,
        o.kelas,
        o.wilayah,
        o.log_date,
        o.okupansi_statis,
        COALESCE(r.revenue_excel, 0) as revenue_excel
    FROM stage_excel_occupancy o
    LEFT JOIN stage_excel_revenue r
        ON o.no_ka = r.no_ka 
       AND o.relasi = r.relasi 
       AND o.kelas = r.kelas 
       AND o.log_date = r.log_date;
    """)

    conn.execute("DROP TABLE stage_excel_occupancy;")
    conn.execute("DROP TABLE stage_excel_revenue;")

    # Remove temp files
    try:
        os.remove(occ_csv_path)
        os.remove(rev_csv_path)
    except Exception:
        pass

    total_master = conn.execute("SELECT count(*) FROM excel_daily_master").fetchone()[0]
    print(f"Master Excel Table loaded in {time.time()-t2:.2f}s ({total_master:,} rows).", flush=True)

# -------------------------------------------------------------
# STEP 2: EXTRACT DEPARTURE TRENDS (TRIPDATE) FROM RAW CSVS
# -------------------------------------------------------------
def extract_departure_trends(conn):
    print("\n" + "=" * 65, flush=True)
    print("STEP 2: AGGREGATING DEPARTURE TRENDS (TRIPDATE) FROM 365 CSVS...", flush=True)
    print("=" * 65, flush=True)
    t0 = time.time()

    conn.execute("DROP TABLE IF EXISTS mart_daily_departures;")
    conn.execute("""
    CREATE TABLE mart_daily_departures (
        departure_date DATE PRIMARY KEY,
        month_num INTEGER,
        month_name VARCHAR,
        day_of_week VARCHAR,
        day_of_week_num INTEGER,
        is_weekend BOOLEAN,
        total_passengers BIGINT,
        total_departure_revenue BIGINT
    );
    """)

    for idx, folder in enumerate(MONTH_FOLDERS):
        folder_path = os.path.join(BASE_DIR, folder)
        csv_pattern = os.path.join(folder_path, "*.csv").replace("\\", "/")
        t_m = time.time()
        print(f"  [{idx+1}/12] Extracting departures from {folder}...", flush=True)

        conn.execute(f"""
        INSERT INTO mart_daily_departures
        SELECT 
            departure_date,
            MONTH(departure_date) as month_num,
            STRFTIME(departure_date, '%B') as month_name,
            DAYNAME(departure_date) as day_of_week,
            DAYOFWEEK(departure_date) as day_of_week_num,
            CASE WHEN DAYOFWEEK(departure_date) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend,
            COUNT(*) as total_passengers,
            SUM(COALESCE(TRY_CAST("Revenue" AS BIGINT), 0)) as total_departure_revenue
        FROM (
            SELECT 
                CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE) as departure_date,
                "Revenue"
            FROM read_csv('{csv_pattern}', header=True, union_by_name=True, quote='"', null_padding=true)
            WHERE "Tripdate" IS NOT NULL
        )
        WHERE departure_date >= '2025-01-01' AND departure_date <= '2025-12-31'
        GROUP BY 1, 2, 3, 4, 5, 6
        ON CONFLICT (departure_date) DO UPDATE SET
            total_passengers = mart_daily_departures.total_passengers + EXCLUDED.total_passengers,
            total_departure_revenue = mart_daily_departures.total_departure_revenue + EXCLUDED.total_departure_revenue;
        """)
        print(f"    Done in {time.time()-t_m:.2f}s", flush=True)

    dep_count = conn.execute("SELECT count(*), sum(total_passengers) FROM mart_daily_departures").fetchone()
    print(f"Departures aggregated: {dep_count[0]} days, {dep_count[1]:,} passengers in {time.time()-t0:.2f}s.", flush=True)

# -------------------------------------------------------------
# STEP 3: ANALYTICS & MARTS GENERATION
# -------------------------------------------------------------
def build_advanced_marts(conn):
    print("\n" + "=" * 65, flush=True)
    print("STEP 3: COMPUTING ADVANCED MARTS & JOIN ANALYTICS...", flush=True)
    print("=" * 65, flush=True)

    # 1. Distance & Class Analysis
    print("Computing Distance & Class Revenue/Occupancy Mart...", flush=True)
    conn.execute("DROP TABLE IF EXISTS mart_distance_class;")
    conn.execute("""
    CREATE TABLE mart_distance_class AS
    SELECT 
        kelas_jarak,
        kelas,
        COUNT(DISTINCT no_ka || '-' || relasi) as total_routes,
        ROUND(AVG(jarak_km), 1) as avg_distance_km,
        ROUND(AVG(okupansi_statis) * 100, 1) as avg_occupancy_pct,
        SUM(revenue_excel) as total_revenue_excel
    FROM excel_daily_master
    WHERE kelas_jarak IN ('JAUH', 'SEDANG', 'DEKAT')
    GROUP BY 1, 2
    ORDER BY 
        CASE kelas_jarak WHEN 'JAUH' THEN 1 WHEN 'SEDANG' THEN 2 WHEN 'DEKAT' THEN 3 ELSE 4 END,
        CASE kelas WHEN 'EKS' THEN 1 WHEN 'BIS' THEN 2 WHEN 'EKO' THEN 3 ELSE 4 END;
    """)

    # 2. Occupancy vs Revenue Per Train & Route (for Quadrant / Scatter Plot)
    print("Computing Train Performance Quadrant Mart...", flush=True)
    conn.execute("DROP TABLE IF EXISTS mart_train_performance_quadrant;")
    conn.execute("""
    CREATE TABLE mart_train_performance_quadrant AS
    SELECT 
        nama_ka,
        relasi,
        kelas,
        kelas_jarak,
        ROUND(AVG(jarak_km), 0) as jarak_km,
        ROUND(AVG(okupansi_statis) * 100, 1) as avg_occupancy_pct,
        SUM(revenue_excel) as total_revenue_excel,
        ROUND(AVG(revenue_excel), 0) as avg_daily_revenue
    FROM excel_daily_master
    WHERE okupansi_statis > 0
    GROUP BY 1, 2, 3, 4
    HAVING SUM(revenue_excel) > 0
    ORDER BY total_revenue_excel DESC;
    """)

    # 3. Seasonality Analysis: Juli (Libur Sekolah) vs Oktober (Reguler) vs Desember (Nataru)
    print("Computing Seasonality Benchmark Mart (Juli vs Oktober vs Desember)...", flush=True)
    conn.execute("DROP TABLE IF EXISTS mart_seasonality_benchmark;")
    conn.execute("""
    CREATE TABLE mart_seasonality_benchmark AS
    SELECT 
        CASE 
            WHEN MONTH(log_date) = 7 THEN 'Juli (Libur Sekolah)'
            WHEN MONTH(log_date) = 10 THEN 'Oktober (Musim Reguler)'
            WHEN MONTH(log_date) = 12 THEN 'Desember (Nataru)'
        END as season_name,
        MONTH(log_date) as month_num,
        kelas,
        ROUND(AVG(okupansi_statis) * 100, 2) as avg_occupancy_pct,
        SUM(revenue_excel) as total_revenue_excel,
        ROUND(SUM(revenue_excel) / COUNT(DISTINCT log_date), 0) as avg_daily_revenue
    FROM excel_daily_master
    WHERE MONTH(log_date) IN (7, 10, 12)
    GROUP BY 1, 2, 3
    ORDER BY month_num, CASE kelas WHEN 'EKS' THEN 1 WHEN 'BIS' THEN 2 WHEN 'EKO' THEN 3 ELSE 4 END;
    """)

    # 4. Top Routes comparison in Seasonality
    conn.execute("DROP TABLE IF EXISTS mart_seasonality_top_routes;")
    conn.execute("""
    CREATE TABLE mart_seasonality_top_routes AS
    SELECT 
        CASE 
            WHEN MONTH(log_date) = 7 THEN 'Juli (Libur Sekolah)'
            WHEN MONTH(log_date) = 10 THEN 'Oktober (Musim Reguler)'
            WHEN MONTH(log_date) = 12 THEN 'Desember (Nataru)'
        END as season_name,
        relasi,
        ROUND(AVG(okupansi_statis) * 100, 1) as avg_occupancy_pct,
        SUM(revenue_excel) as total_revenue_excel
    FROM excel_daily_master
    WHERE MONTH(log_date) IN (7, 10, 12)
    GROUP BY 1, 2
    ORDER BY season_name, total_revenue_excel DESC;
    """)

# -------------------------------------------------------------
# STEP 4: UPDATE SUMMARY_INSIGHTS.JSON & EXPORT CSV
# -------------------------------------------------------------
def update_insights_payload(conn):
    print("\n" + "=" * 65, flush=True)
    print("STEP 4: UPDATING DASHBOARD PAYLOAD WITH ADVANCED INSIGHTS...", flush=True)
    print("=" * 65, flush=True)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # 1. Departures daily time series
    dep_rows = conn.execute("""
    SELECT 
        strftime(departure_date, '%Y-%m-%d') as date,
        month_num,
        month_name,
        day_of_week,
        day_of_week_num,
        is_weekend,
        total_passengers,
        total_departure_revenue,
        ROUND(total_departure_revenue / total_passengers, 0) as avg_price
    FROM mart_daily_departures
    ORDER BY departure_date;
    """).fetchall()

    payload["daily_departures"] = [
        {
            "date": r[0], "month_num": r[1], "month_name": r[2],
            "day_of_week": r[3], "day_of_week_num": r[4], "is_weekend": bool(r[5]),
            "passengers": r[6], "revenue": r[7], "avg_price": r[8]
        }
        for r in dep_rows
    ]

    # 2. Distance & Class Analysis
    dist_rows = conn.execute("""
    SELECT kelas_jarak, kelas, total_routes, avg_distance_km, avg_occupancy_pct, total_revenue_excel
    FROM mart_distance_class;
    """).fetchall()

    payload["distance_class"] = [
        {
            "tier": r[0], "class": r[1], "routes_count": r[2],
            "avg_km": r[3], "avg_occupancy_pct": r[4], "revenue": r[5]
        }
        for r in dist_rows
    ]

    # 3. Train Performance Quadrant (Top 60 trains for rich interactive scatter plot)
    quad_rows = conn.execute("""
    SELECT nama_ka, relasi, kelas, kelas_jarak, jarak_km, avg_occupancy_pct, total_revenue_excel, avg_daily_revenue
    FROM mart_train_performance_quadrant
    LIMIT 60;
    """).fetchall()

    payload["quadrant_trains"] = [
        {
            "train_name": r[0], "relasi": r[1], "class": r[2], "tier": r[3],
            "km": r[4], "occupancy_pct": r[5], "revenue": r[6], "daily_rev": r[7]
        }
        for r in quad_rows
    ]

    # 4. Seasonality Benchmark (Juli, Oktober, Desember)
    seas_rows = conn.execute("""
    SELECT season_name, month_num, kelas, avg_occupancy_pct, total_revenue_excel, avg_daily_revenue
    FROM mart_seasonality_benchmark;
    """).fetchall()

    payload["seasonality"] = [
        {
            "season": r[0], "month": r[1], "class": r[2],
            "occupancy_pct": r[3], "revenue": r[4], "daily_revenue": r[5]
        }
        for r in seas_rows
    ]

    # 5. Seasonality Top Routes (Top 5 per season)
    seas_routes = conn.execute("""
    WITH ranked AS (
        SELECT season_name, relasi, avg_occupancy_pct, total_revenue_excel,
               ROW_NUMBER() OVER (PARTITION BY season_name ORDER BY total_revenue_excel DESC) as rn
        FROM mart_seasonality_top_routes
    )
    SELECT season_name, relasi, avg_occupancy_pct, total_revenue_excel
    FROM ranked
    WHERE rn <= 5;
    """).fetchall()

    payload["seasonality_top_routes"] = [
        {"season": r[0], "relasi": r[1], "occupancy_pct": r[2], "revenue": r[3]}
        for r in seas_routes
    ]

    # Write updated JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Updated summary_insights.json successfully ({round(os.path.getsize(JSON_PATH)/1024, 1)} KB).", flush=True)

    # Export Departure Summary CSV
    dep_csv = os.path.join(DATA_DIR, "departure_daily_summary.csv").replace("\\", "/")
    conn.execute(f"""
    COPY (
        SELECT 
            departure_date,
            month_num,
            month_name,
            day_of_week,
            total_passengers,
            total_departure_revenue,
            ROUND(total_departure_revenue / total_passengers, 0) as avg_price
        FROM mart_daily_departures
        ORDER BY departure_date
    ) TO '{dep_csv}' (HEADER, DELIMITER ',');
    """)
    print(f"Exported departure_daily_summary.csv successfully ({round(os.path.getsize(dep_csv)/1024, 1)} KB).", flush=True)

def run():
    t_start = time.time()
    conn = get_connection()

    parse_excel_data(conn)
    extract_departure_trends(conn)
    build_advanced_marts(conn)
    update_insights_payload(conn)

    conn.close()
    print("\n" + "=" * 65, flush=True)
    print(f"ADVANCED INTEGRATION PIPELINE FINISHED IN {time.time()-t_start:.2f}s!", flush=True)
    print("=" * 65, flush=True)

if __name__ == "__main__":
    run()
