@echo off
title KAI Booking Data ETL Pipeline
echo ===================================================
echo   Menjalankan ETL Pipeline 365 File Data Booking
echo ===================================================
"d:\Histori Booking\.venv\Scripts\python.exe" -u "d:\Histori Booking\pipeline\clean_and_aggregate.py"
echo.
echo Mengenerate Laporan HTML Mandiri...
"d:\Histori Booking\.venv\Scripts\python.exe" "d:\Histori Booking\export_static_report.py"
echo.
echo Selesai! Tekan sembarang tombol untuk keluar.
pause
