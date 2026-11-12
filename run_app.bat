@echo off
title CM Kerala Grievance Redressal Portal
echo ======================================================================
echo CM KERALA - CHIEF MINISTER'S PUBLIC GRIEVANCE REDRESSAL PORTAL
echo ======================================================================
cd /d "%~dp0"

echo [1/2] Checking MySQL database connectivity...
python scripts\test_db_connection.py
if errorlevel 1 (
    echo.
    echo [ERROR] Could not connect to MySQL.
    echo If using local MySQL port 3307, please run scripts\start_local_mysql.bat first.
    echo If using standard port 3306, please update DB_PASSWORD in .env.
    pause
    exit /b 1
)

echo.
echo [2/2] Starting Flask Application on http://127.0.0.1:5000 ...
python app.py
pause
