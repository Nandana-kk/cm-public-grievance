"""
Database helper module using direct mysql-connector-python connections.
Provides simple, beginner-friendly helper functions with parameterized queries,
smart port auto-detection (3306/3307), and automatic database initialization.
"""

import os
import mysql.connector
from mysql.connector import Error
from config import Config

# Cache the successfully discovered working port so subsequent queries connect immediately
_WORKING_PORT = None
_MYSQLD_STARTED = False


def ensure_local_mysqld_running():
    """
    Checks if MySQL is reachable on port 3307. If not listening,
    automatically starts the local mysqld background process so that
    running 'python app.py' directly works seamlessly without manual commands.
    """
    global _MYSQLD_STARTED
    if _MYSQLD_STARTED:
        return

    import socket
    import subprocess
    import time
    import shutil

    # Test if port 3307 is already listening
    try:
        with socket.create_connection(("127.0.0.1", 3307), timeout=0.5):
            _MYSQLD_STARTED = True
            return
    except Exception:
        pass

    # Find mysqld executable in standard Windows installation paths
    possible_mysqld_paths = [
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe",
        r"C:\xampp\mysql\bin\mysqld.exe"
    ]
    which_mysqld = shutil.which("mysqld")
    if which_mysqld:
        possible_mysqld_paths.insert(0, which_mysqld)

    mysqld_exe = next((p for p in possible_mysqld_paths if os.path.isfile(p)), None)

    # Find local mysql_data directory
    possible_datadirs = [
        r"C:\Users\nanda\.gemini\antigravity\scratch\mysql_data",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mysql_data")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "mysql_data"))
    ]
    datadir = next((d for d in possible_datadirs if os.path.isdir(d)), None)

    if mysqld_exe and datadir:
        try:
            print(f"[Database Auto-Start] Starting local MySQL server on port 3307...")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.Popen(
                [mysqld_exe, f"--datadir={datadir}", "--port=3307", "--mysqlx=0"],
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _MYSQLD_STARTED = True
            time.sleep(2)
            print("[Database Auto-Start] Local MySQL server started successfully.")
        except Exception as start_err:
            print(f"[Database Auto-Start Notice] {start_err}")


def get_db_connection(include_database=True):
    """
    Establish and return a new MySQL database connection.
    Attempts the configured port first, with auto-fallback to alternative common ports (3306/3307)
    if the configured port is unreachable or authentication differs.
    """
    global _WORKING_PORT

    # Prioritize working port if previously discovered
    ports_to_try = []
    if _WORKING_PORT:
        ports_to_try.append(_WORKING_PORT)
    if Config.DB_PORT not in ports_to_try:
        ports_to_try.append(Config.DB_PORT)

    # Prefer 3307 first if password is empty (local passwordless standalone instance)
    preferred_order = (3307, 3306) if not Config.DB_PASSWORD else (3306, 3307)
    for alt in preferred_order:
        if alt not in ports_to_try:
            ports_to_try.append(alt)

    # Ensure standalone MySQL is running if port 3307 is to be tried
    if 3307 in ports_to_try:
        ensure_local_mysqld_running()

    last_error = None

    for port in ports_to_try:
        connection_params = {
            "host": Config.DB_HOST,
            "port": port,
            "user": Config.DB_USER,
            "password": Config.DB_PASSWORD,
            "connect_timeout": 3
        }
        if include_database:
            connection_params["database"] = Config.DB_NAME

        try:
            connection = mysql.connector.connect(**connection_params)
            _WORKING_PORT = port
            return connection
        except Error as e:
            last_error = e
            # Error 1049: Unknown database -> try connecting without DB and auto-create
            if e.errno == 1049 and include_database:
                try:
                    admin_params = connection_params.copy()
                    admin_params.pop("database", None)
                    admin_conn = mysql.connector.connect(**admin_params)
                    admin_cursor = admin_conn.cursor()
                    admin_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} DEFAULT CHARACTER SET utf8mb4")
                    admin_conn.commit()
                    admin_cursor.close()
                    admin_conn.close()
                    # Now retry connecting with database
                    connection = mysql.connector.connect(**connection_params)
                    _WORKING_PORT = port
                    # Initialize tables if fresh database
                    init_db()
                    return connection
                except Exception as inner_e:
                    last_error = inner_e
            # Error 2003: Can't connect to MySQL server (port not listening) -> try next port
            elif e.errno == 2003:
                continue
            # Error 1045: Access denied (e.g. port requires password) -> log notice and try next port
            elif e.errno == 1045:
                print(f"[Database Notice] Access denied for user '{Config.DB_USER}' on port {port}. Checking alternative port...")
                continue
            else:
                continue

    # If all ports failed, print friendly diagnostic message
    print("\n" + "=" * 70)
    print("[Database Connection Error] Could not connect to MySQL server.")
    print(f"Details: {last_error}")
    print("Troubleshooting Steps:")
    print("1. Standalone MySQL on port 3307: run 'scripts\\start_local_mysql.bat' or let app auto-start it.")
    print("2. System MySQL on port 3306: check DB_PASSWORD in .env (DB_PASSWORD=your_password).")
    print("=" * 70 + "\n")
    raise last_error


def init_db(sql_filepath=None):
    """
    Initialize the MySQL database and tables by executing database.sql.
    """
    if sql_filepath is None:
        sql_filepath = os.path.join(os.path.dirname(__file__), "database.sql")

    # Connect to MySQL server without selecting database first
    conn = get_db_connection(include_database=False)
    cursor = conn.cursor()

    try:
        with open(sql_filepath, "r", encoding="utf-8") as f:
            sql_script = f.read()

        statements = []
        current_stmt = []
        for line in sql_script.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            current_stmt.append(line)
            if stripped.endswith(";"):
                statements.append("\n".join(current_stmt))
                current_stmt = []

        for statement in statements:
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
        conn.commit()
        print("[Database Initialization] All tables created and initial data seeded successfully.")
    except Error as e:
        print(f"[Database Init Error] {e}")
        raise e
    finally:
        cursor.close()
        conn.close()


def query_db(query, params=(), one=False):
    """
    Execute a SELECT query with parameterized inputs and return results as dictionaries.
    
    :param query: SQL string containing %s placeholders
    :param params: Tuple of parameters to safely inject
    :param one: If True, returns only the first row; otherwise returns a list of rows
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params)
        records = cursor.fetchall()
        return (records[0] if records else None) if one else records
    finally:
        cursor.close()
        conn.close()


def execute_db(query, params=(), return_id=False):
    """
    Execute an INSERT, UPDATE, or DELETE query with parameterized inputs.
    
    :param query: SQL string containing %s placeholders
    :param params: Tuple of parameters to safely inject
    :param return_id: If True, returns cursor.lastrowid; otherwise returns cursor.rowcount
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
        if return_id:
            return cursor.lastrowid
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()
