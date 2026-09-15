"""
Optimized High-Performance ETL Pipeline for Processing 365 Daily Booking Files
Reads each month's CSVs ONCE into a compact temp table, then executes all 10 analytical mart aggregations in milliseconds.
"""

import os
import sys
import glob
import time
import json
import duckdb

# Force immediate unbuffered stdout output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = r"d:\Histori Booking"
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(DATA_DIR, "tmp")
DB_PATH = os.path.join(DATA_DIR, "booking_analytics.duckdb")

os.makedirs(TMP_DIR, exist_ok=True)

MONTH_FOLDERS = [
    "1. Januari",
    "2. Februari",
    "3. Maret",
    "4. April",
    "5. Mei",
    "6. Juni",
    "7. Juli",
    "8. Agustus",
    "9. September",
    "10. Oktober",
    "11. November",
    "12. Desember"
]

def get_connection():
    conn = duckdb.connect(DB_PATH)
    conn.execute(f"SET temp_directory = '{TMP_DIR.replace(chr(92), '/')}'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute("SET threads = 4")
    return conn

def init_tables(conn):
    print("Initializing analytical mart tables...", flush=True)
    conn.execute("DROP TABLE IF EXISTS mart_daily_trends;")
    conn.execute("""
    CREATE TABLE mart_daily_trends (
        booking_date DATE PRIMARY KEY,
        month_num INTEGER,
        month_name VARCHAR,
        day_of_week VARCHAR,
        day_of_week_num INTEGER,
        is_weekend BOOLEAN,
        total_tickets BIGINT,
        total_revenue BIGINT,
        sales_tickets BIGINT,
        cancelled_tickets BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_hourly_distribution;")
    conn.execute("""
    CREATE TABLE mart_hourly_distribution (
        day_of_week VARCHAR,
        day_of_week_num INTEGER,
        booking_hour INTEGER,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_lead_time;")
    conn.execute("""
    CREATE TABLE mart_lead_time (
        lead_time_bucket VARCHAR,
        bucket_order INTEGER,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_routes;")
    conn.execute("""
    CREATE TABLE mart_routes (
        origin VARCHAR,
        destination VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_trains;")
    conn.execute("""
    CREATE TABLE mart_trains (
        train_name VARCHAR,
        train_number VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_channels;")
    conn.execute("""
    CREATE TABLE mart_channels (
        channel VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_payments;")
    conn.execute("""
    CREATE TABLE mart_payments (
        pay_type VARCHAR,
        pic_pay VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_classes;")
    conn.execute("""
    CREATE TABLE mart_classes (
        wagon_class VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_daily_by_class;")
    conn.execute("""
    CREATE TABLE mart_daily_by_class (
        booking_date DATE,
        wagon_class VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

    conn.execute("DROP TABLE IF EXISTS mart_daily_by_channel;")
    conn.execute("""
    CREATE TABLE mart_daily_by_channel (
        booking_date DATE,
        channel VARCHAR,
        total_tickets BIGINT,
        total_revenue BIGINT
    );
    """)

def process_month(conn, folder_name, month_idx):
    folder_path = os.path.join(BASE_DIR, folder_name)
    csv_pattern = os.path.join(folder_path, "*.csv").replace("\\", "/")
    
    files = glob.glob(os.path.join(folder_path, "*.csv"))
    file_count = len(files)
    t0 = time.time()
    
    print(f"[{month_idx+1}/12] Processing {folder_name} ({file_count} files)...", flush=True)

    # STEP 1: Single-pass CSV read into a compact temp table
    # This reads all CSVs for this month once, projecting and parsing only needed fields
    conn.execute(f"""
    CREATE OR REPLACE TEMP TABLE temp_month AS
    SELECT 
        CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE) as booking_date,
        MONTH(TRY_CAST("Transaction Time" AS TIMESTAMP)) as month_num,
        STRFTIME(TRY_CAST("Transaction Time" AS TIMESTAMP), '%B') as month_name,
        DAYNAME(TRY_CAST("Transaction Time" AS TIMESTAMP)) as day_of_week,
        DAYOFWEEK(TRY_CAST("Transaction Time" AS TIMESTAMP)) as day_of_week_num,
        CASE WHEN DAYOFWEEK(TRY_CAST("Transaction Time" AS TIMESTAMP)) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend,
        HOUR(TRY_CAST("Transaction Time" AS TIMESTAMP)) as booking_hour,
        CASE 
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) <= 0 THEN 'H-0 (Hari H)'
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 1 AND 3 THEN 'H-1 s.d H-3'
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 4 AND 7 THEN 'H-4 s.d H-7'
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 8 AND 14 THEN 'H-8 s.d H-14'
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 15 AND 30 THEN 'H-15 s.d H-30'
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 31 AND 45 THEN 'H-31 s.d H-45'
            ELSE '> H-45'
        END as lead_time_bucket,
        CASE 
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) <= 0 THEN 1
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 1 AND 3 THEN 2
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 4 AND 7 THEN 3
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 8 AND 14 THEN 4
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 15 AND 30 THEN 5
            WHEN date_diff('day', CAST(TRY_CAST("Transaction Time" AS TIMESTAMP) AS DATE), CAST(TRY_CAST("Tripdate" AS TIMESTAMP) AS DATE)) BETWEEN 31 AND 45 THEN 6
            ELSE 7
        END as bucket_order,
        TRIM("Origin") as origin,
        TRIM("Destination") as destination,
        TRIM("Train Name") as train_name,
        TRIM("Train Number") as train_number,
        TRIM("Channel") as channel,
        TRIM("Pay Type") as pay_type,
        TRIM("PIC Pay") as pic_pay,
        TRIM("Wagon Class") as wagon_class,
        COALESCE(TRY_CAST("Revenue" AS BIGINT), 0) as revenue,
        CASE WHEN TRY_CAST("Sales" AS INTEGER) = 1 THEN 1 ELSE 0 END as is_sales,
        CASE WHEN TRY_CAST("Cancelled" AS INTEGER) = 1 THEN 1 ELSE 0 END as is_cancelled
    FROM read_csv('{csv_pattern}', header=True, union_by_name=True, quote='"', null_padding=true)
    WHERE "Transaction Time" IS NOT NULL;
    """)

    # STEP 2: Lightning-fast insertions into all 10 analytical marts
    # 1. Daily trends
    conn.execute("""
    INSERT INTO mart_daily_trends
    SELECT 
        booking_date,
        month_num,
        month_name,
        day_of_week,
        day_of_week_num,
        is_weekend,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue,
        SUM(is_sales) as sales_tickets,
        SUM(is_cancelled) as cancelled_tickets
    FROM temp_month
    WHERE booking_date IS NOT NULL
    GROUP BY 1, 2, 3, 4, 5, 6;
    """)

    # 2. Hourly distribution
    conn.execute("""
    INSERT INTO mart_hourly_distribution
    SELECT 
        day_of_week,
        day_of_week_num,
        booking_hour,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE booking_hour IS NOT NULL
    GROUP BY 1, 2, 3;
    """)

    # 3. Lead time distribution
    conn.execute("""
    INSERT INTO mart_lead_time
    SELECT 
        lead_time_bucket,
        bucket_order,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    GROUP BY 1, 2;
    """)

    # 4. Routes
    conn.execute("""
    INSERT INTO mart_routes
    SELECT 
        origin,
        destination,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE origin IS NOT NULL AND destination IS NOT NULL
    GROUP BY 1, 2;
    """)

    # 5. Trains
    conn.execute("""
    INSERT INTO mart_trains
    SELECT 
        train_name,
        train_number,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE train_name IS NOT NULL
    GROUP BY 1, 2;
    """)

    # 6. Channels
    conn.execute("""
    INSERT INTO mart_channels
    SELECT 
        channel,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE channel IS NOT NULL
    GROUP BY 1;
    """)

    # 7. Payments
    conn.execute("""
    INSERT INTO mart_payments
    SELECT 
        pay_type,
        pic_pay,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE pay_type IS NOT NULL
    GROUP BY 1, 2;
    """)

    # 8. Classes
    conn.execute("""
    INSERT INTO mart_classes
    SELECT 
        wagon_class,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE wagon_class IS NOT NULL
    GROUP BY 1;
    """)

    # 9. Daily by class
    conn.execute("""
    INSERT INTO mart_daily_by_class
    SELECT 
        booking_date,
        wagon_class,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE booking_date IS NOT NULL AND wagon_class IS NOT NULL
    GROUP BY 1, 2;
    """)

    # 10. Daily by channel
    conn.execute("""
    INSERT INTO mart_daily_by_channel
    SELECT 
        booking_date,
        channel,
        COUNT(*) as total_tickets,
        SUM(revenue) as total_revenue
    FROM temp_month
    WHERE booking_date IS NOT NULL AND channel IS NOT NULL
    GROUP BY 1, 2;
    """)

    # Free the temp table immediately to keep memory clean
    conn.execute("DROP TABLE temp_month;")

    elapsed = time.time() - t0
    print(f"  -> Done in {elapsed:.2f}s", flush=True)

def consolidate_marts(conn):
    print("\nConsolidating and summarizing final marts...", flush=True)

    # Hourly summary
    conn.execute("DROP TABLE IF EXISTS summary_hourly;")
    conn.execute("""
    CREATE TABLE summary_hourly AS
    SELECT 
        booking_hour,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_tickets) * 100.0 / (SELECT SUM(total_tickets) FROM mart_hourly_distribution), 2) as pct_tickets
    FROM mart_hourly_distribution
    GROUP BY 1
    ORDER BY 1;
    """)

    # Lead time consolidated
    conn.execute("DROP TABLE IF EXISTS summary_lead_time;")
    conn.execute("""
    CREATE TABLE summary_lead_time AS
    SELECT 
        lead_time_bucket,
        bucket_order,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_tickets) * 100.0 / (SELECT SUM(total_tickets) FROM mart_lead_time), 2) as pct_tickets
    FROM mart_lead_time
    GROUP BY 1, 2
    ORDER BY bucket_order;
    """)

    # Channels consolidated
    conn.execute("DROP TABLE IF EXISTS summary_channels;")
    conn.execute("""
    CREATE TABLE summary_channels AS
    SELECT 
        channel,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_tickets) * 100.0 / (SELECT SUM(total_tickets) FROM mart_channels), 2) as pct_tickets
    FROM mart_channels
    GROUP BY 1
    ORDER BY total_tickets DESC;
    """)

    # Payments consolidated
    conn.execute("DROP TABLE IF EXISTS summary_payments;")
    conn.execute("""
    CREATE TABLE summary_payments AS
    SELECT 
        pay_type,
        pic_pay,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_tickets) * 100.0 / (SELECT SUM(total_tickets) FROM mart_payments), 2) as pct_tickets
    FROM mart_payments
    GROUP BY 1, 2
    ORDER BY total_tickets DESC;
    """)

    # Top Routes
    conn.execute("DROP TABLE IF EXISTS summary_top_routes;")
    conn.execute("""
    CREATE TABLE summary_top_routes AS
    SELECT 
        origin,
        destination,
        origin || ' - ' || destination as route,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_revenue) / SUM(total_tickets), 0) as avg_price
    FROM mart_routes
    GROUP BY 1, 2
    ORDER BY total_tickets DESC
    LIMIT 30;
    """)

    # Top Trains
    conn.execute("DROP TABLE IF EXISTS summary_top_trains;")
    conn.execute("""
    CREATE TABLE summary_top_trains AS
    SELECT 
        train_name,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_revenue) / SUM(total_tickets), 0) as avg_price
    FROM mart_trains
    GROUP BY 1
    ORDER BY total_tickets DESC
    LIMIT 30;
    """)

    # Classes consolidated
    conn.execute("DROP TABLE IF EXISTS summary_classes;")
    conn.execute("""
    CREATE TABLE summary_classes AS
    SELECT 
        wagon_class,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_tickets) * 100.0 / (SELECT SUM(total_tickets) FROM mart_classes), 2) as pct_tickets
    FROM mart_classes
    GROUP BY 1
    ORDER BY total_tickets DESC;
    """)

    # Monthly trends
    conn.execute("DROP TABLE IF EXISTS summary_monthly;")
    conn.execute("""
    CREATE TABLE summary_monthly AS
    SELECT 
        month_num,
        month_name,
        SUM(total_tickets) as total_tickets,
        SUM(total_revenue) as total_revenue,
        ROUND(SUM(total_revenue) / SUM(total_tickets), 0) as avg_ticket_price,
        ROUND(AVG(total_tickets), 0) as avg_daily_tickets
    FROM mart_daily_trends
    GROUP BY 1, 2
    ORDER BY month_num;
    """)

def export_json_and_csv(conn):
    print("\nExporting aggregated data to JSON and CSV for dashboard...", flush=True)

    # 1. Daily trends CSV
    daily_csv = os.path.join(DATA_DIR, "daily_summary.csv").replace("\\", "/")
    conn.execute(f"""
    COPY (
        SELECT 
            booking_date,
            month_num,
            month_name,
            day_of_week,
            total_tickets,
            total_revenue,
            ROUND(total_revenue / total_tickets, 0) as avg_ticket_price
        FROM mart_daily_trends
        ORDER BY booking_date
    ) TO '{daily_csv}' (HEADER, DELIMITER ',');
    """)

    # 2. Daily trends JSON
    daily_rows = conn.execute("""
    SELECT 
        strftime(booking_date, '%Y-%m-%d') as date,
        month_num,
        month_name,
        day_of_week,
        day_of_week_num,
        is_weekend,
        total_tickets,
        total_revenue,
        ROUND(total_revenue / total_tickets, 0) as avg_price
    FROM mart_daily_trends
    ORDER BY booking_date;
    """).fetchall()

    daily_data = [
        {
            "date": r[0],
            "month_num": r[1],
            "month_name": r[2],
            "day_of_week": r[3],
            "day_of_week_num": r[4],
            "is_weekend": bool(r[5]),
            "tickets": r[6],
            "revenue": r[7],
            "avg_price": r[8]
        }
        for r in daily_rows
    ]

    # 3. Comprehensive Summary Insights JSON
    total_tickets = sum(d["tickets"] for d in daily_data)
    total_revenue = sum(d["revenue"] for d in daily_data)
    avg_daily_tickets = round(total_tickets / len(daily_data)) if daily_data else 0
    avg_daily_revenue = round(total_revenue / len(daily_data)) if daily_data else 0

    peak_day = max(daily_data, key=lambda x: x["tickets"]) if daily_data else {}
    low_day = min(daily_data, key=lambda x: x["tickets"]) if daily_data else {}

    monthly_rows = conn.execute("SELECT month_num, month_name, total_tickets, total_revenue, avg_ticket_price, avg_daily_tickets FROM summary_monthly").fetchall()
    monthly_data = [
        {"month_num": r[0], "month_name": r[1], "tickets": r[2], "revenue": r[3], "avg_price": r[4], "avg_daily_tickets": r[5]}
        for r in monthly_rows
    ]

    hourly_rows = conn.execute("SELECT booking_hour, total_tickets, total_revenue, pct_tickets FROM summary_hourly").fetchall()
    hourly_data = [
        {"hour": r[0], "tickets": r[1], "revenue": r[2], "pct": r[3]}
        for r in hourly_rows
    ]

    lead_time_rows = conn.execute("SELECT lead_time_bucket, bucket_order, total_tickets, total_revenue, pct_tickets FROM summary_lead_time").fetchall()
    lead_time_data = [
        {"bucket": r[0], "order": r[1], "tickets": r[2], "revenue": r[3], "pct": r[4]}
        for r in lead_time_rows
    ]

    top_routes_rows = conn.execute("SELECT origin, destination, route, total_tickets, total_revenue, avg_price FROM summary_top_routes LIMIT 15").fetchall()
    top_routes_data = [
        {"origin": r[0], "destination": r[1], "route": r[2], "tickets": r[3], "revenue": r[4], "avg_price": r[5]}
        for r in top_routes_rows
    ]

    top_trains_rows = conn.execute("SELECT train_name, total_tickets, total_revenue, avg_price FROM summary_top_trains LIMIT 15").fetchall()
    top_trains_data = [
        {"train_name": r[0], "tickets": r[1], "revenue": r[2], "avg_price": r[3]}
        for r in top_trains_rows
    ]

    channels_rows = conn.execute("SELECT channel, total_tickets, total_revenue, pct_tickets FROM summary_channels").fetchall()
    channels_data = [
        {"channel": r[0], "tickets": r[1], "revenue": r[2], "pct": r[3]}
        for r in channels_rows
    ]

    payments_rows = conn.execute("SELECT pay_type, pic_pay, total_tickets, total_revenue, pct_tickets FROM summary_payments LIMIT 15").fetchall()
    payments_data = [
        {"pay_type": r[0], "pic_pay": r[1], "tickets": r[2], "revenue": r[3], "pct": r[4]}
        for r in payments_rows
    ]

    classes_rows = conn.execute("SELECT wagon_class, total_tickets, total_revenue, pct_tickets FROM summary_classes").fetchall()
    classes_data = [
        {"wagon_class": r[0], "tickets": r[1], "revenue": r[2], "pct": r[3]}
        for r in classes_rows
    ]

    # Daily by class data
    daily_class_rows = conn.execute("""
    SELECT strftime(booking_date, '%Y-%m-%d'), wagon_class, total_tickets, total_revenue
    FROM mart_daily_by_class
    ORDER BY booking_date, wagon_class;
    """).fetchall()
    daily_class_data = [
        {"date": r[0], "class": r[1], "tickets": r[2], "revenue": r[3]}
        for r in daily_class_rows
    ]

    # Daily by channel data
    daily_channel_rows = conn.execute("""
    SELECT strftime(booking_date, '%Y-%m-%d'), channel, total_tickets, total_revenue
    FROM mart_daily_by_channel
    ORDER BY booking_date, channel;
    """).fetchall()
    daily_channel_data = [
        {"date": r[0], "channel": r[1], "tickets": r[2], "revenue": r[3]}
        for r in daily_channel_rows
    ]

    # Hourly heatmap (Day of week vs Hour)
    heatmap_rows = conn.execute("""
    SELECT day_of_week, day_of_week_num, booking_hour, SUM(total_tickets) as tickets
    FROM mart_hourly_distribution
    GROUP BY 1, 2, 3
    ORDER BY day_of_week_num, booking_hour;
    """).fetchall()
    heatmap_data = [
        {"day": r[0], "day_num": r[1], "hour": r[2], "tickets": r[3]}
        for r in heatmap_rows
    ]

    insights_payload = {
        "kpi": {
            "total_tickets": total_tickets,
            "total_revenue": total_revenue,
            "total_days": len(daily_data),
            "avg_daily_tickets": avg_daily_tickets,
            "avg_daily_revenue": avg_daily_revenue,
            "peak_day": peak_day,
            "low_day": low_day
        },
        "monthly": monthly_data,
        "daily": daily_data,
        "hourly": hourly_data,
        "lead_time": lead_time_data,
        "top_routes": top_routes_data,
        "top_trains": top_trains_data,
        "channels": channels_data,
        "payments": payments_data,
        "classes": classes_data,
        "daily_by_class": daily_class_data,
        "daily_by_channel": daily_channel_data,
        "heatmap": heatmap_data
    }

    with open(os.path.join(DATA_DIR, "summary_insights.json"), "w", encoding="utf-8") as f:
        json.dump(insights_payload, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated summary_insights.json ({round(os.path.getsize(os.path.join(DATA_DIR, 'summary_insights.json'))/1024, 1)} KB)", flush=True)
    print(f"Successfully generated daily_summary.csv ({round(os.path.getsize(daily_csv)/1024, 1)} KB)", flush=True)

def run_pipeline():
    total_start = time.time()
    print("=" * 65, flush=True)
    print("STARTING OPTIMIZED ETL PIPELINE FOR 365 BOOKING FILES", flush=True)
    print(f"Base Directory: {BASE_DIR}", flush=True)
    print(f"Database: {DB_PATH}", flush=True)
    print("=" * 65, flush=True)

    conn = get_connection()
    init_tables(conn)

    for idx, folder in enumerate(MONTH_FOLDERS):
        process_month(conn, folder, idx)

    consolidate_marts(conn)
    export_json_and_csv(conn)

    conn.close()
    total_elapsed = time.time() - total_start
    print("\n" + "=" * 65, flush=True)
    print(f"ETL PIPELINE COMPLETED SUCCESSFULLY IN {total_elapsed:.2f} SECONDS!", flush=True)
    print("=" * 65, flush=True)

if __name__ == "__main__":
    run_pipeline()
