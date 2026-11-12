@echo off
title CM Kerala Portal - Local MySQL Server (Port 3307)
echo ======================================================================
echo Starting CM Kerala Portal Local MySQL Server on port 3307...
echo Keep this window open while using the application.
echo ======================================================================
"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="C:\Users\nanda\.gemini\antigravity\scratch\mysql_data" --port=3307 --mysqlx=0 --console
if errorlevel 1 (
    echo.
    echo MySQL Server stopped or encountered an error.
    pause
)
