"""
Database Connectivity Diagnostic & Auto-repair Tool
Tests MySQL connectivity across configured ports (3306 and 3307),
verifies cm_kerala_portal database, and checks user credentials.
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import mysql.connector
from config import Config


def test_connection():
    print("=" * 70)
    print("CM KERALA PORTAL - MYSQL CONNECTIVITY DIAGNOSTIC TOOL")
    print("=" * 70)
    print(f"Configured in .env:")
    print(f"  DB_HOST     : {Config.DB_HOST}")
    print(f"  DB_PORT     : {Config.DB_PORT}")
    print(f"  DB_USER     : {Config.DB_USER}")
    print(f"  DB_PASSWORD : {'******' if Config.DB_PASSWORD else '(empty)'}")
    print(f"  DB_NAME     : {Config.DB_NAME}")
    print("-" * 70)

    # Test configured port first
    ports_to_try = [Config.DB_PORT]
    # Add alternate port
    if Config.DB_PORT != 3306:
        ports_to_try.append(3306)
    if Config.DB_PORT != 3307:
        ports_to_try.append(3307)

    working_port = None
    working_conn = None

    for port in ports_to_try:
        print(f"Testing connection to 127.0.0.1:{port} with user '{Config.DB_USER}'...")
        try:
            conn = mysql.connector.connect(
                host=Config.DB_HOST,
                port=port,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                connect_timeout=3
            )
            print(f"  [SUCCESS] Connected to MySQL on port {port}!")
            print(f"  Server Version: {conn.get_server_info()}")
            working_port = port
            working_conn = conn
            break
        except mysql.connector.Error as err:
            if err.errno == 2003:
                print(f"  [FAIL] Port {port} is not listening or not reachable (Error 2003).")
            elif err.errno == 1045:
                print(f"  [FAIL] Port {port} is active, but access was denied (Error 1045: Invalid Password).")
            else:
                print(f"  [FAIL] Port {port} connection failed: {err}")

    if not working_conn:
        print("\n" + "!" * 70)
        print("ERROR: Could not establish a connection to any MySQL port.")
        print("Solutions:")
        print("1. If using your system MySQL (port 3306):")
        print("   Update your .env file with your real MySQL root password:")
        print("   DB_PORT=3306")
        print("   DB_PASSWORD=your_actual_password")
        print("2. If using the project's standalone local MySQL (port 3307):")
        print("   Run: scripts/start_local_mysql.bat")
        print("!" * 70)
        return False

    # Check database cm_kerala_portal
    print("-" * 70)
    print(f"Checking database '{Config.DB_NAME}' on port {working_port}...")
    cursor = working_conn.cursor()
    cursor.execute("SHOW DATABASES LIKE %s", (Config.DB_NAME,))
    db_exists = cursor.fetchone()

    if not db_exists:
        print(f"  Database '{Config.DB_NAME}' does not exist yet. Creating it now...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} DEFAULT CHARACTER SET utf8mb4")
        working_conn.commit()
        print(f"  [SUCCESS] Database '{Config.DB_NAME}' created.")
        from database import init_db
        print("  Running database.sql initialization...")
        init_db()
    else:
        print(f"  [SUCCESS] Database '{Config.DB_NAME}' exists.")

    working_conn.database = Config.DB_NAME
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"  Found {len(tables)} tables: {', '.join(tables)}")

    cursor.close()
    working_conn.close()

    print("=" * 70)
    print("DATABASE DIAGNOSTIC COMPLETED: SQL CONNECTOR IS WORKING PROPERLY!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
