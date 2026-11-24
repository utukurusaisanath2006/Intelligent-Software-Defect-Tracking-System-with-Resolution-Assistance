"""Simple database inspector script for IntelliTrack."""
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'intellitrack.db')

def view_database(target='summary'):
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database file not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("=" * 65)
    print("      INTELLITRACK DATABASE VIEWER (instance/intellitrack.db)")
    print("=" * 65)

    # 1. List all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cur.fetchall()]

    if target == 'summary' or not target:
        print("\n[+] Tables in Database:")
        for t in tables:
            cur.execute(f"SELECT count(*) FROM {t};")
            count = cur.fetchone()[0]
            print(f"   • {t:<22} : {count:>4} rows")

        print("\n" + "-" * 65)
        print("  Tip: Run 'python view_db.py users' to inspect user accounts.")
        print("  Tip: Run 'python view_db.py issues' to inspect defect tickets.")
        print("-" * 65)

    if target in ('users', 'all'):
        print("\n[+] Table: users (Showing Passwords Stored in DB)")
        print(f"{'Role':<12} | {'Username':<14} | {'Email':<25} | {'Password Hash (First 25 chars)'}")
        print("-" * 75)
        cur.execute("SELECT role, username, email, password_hash FROM users;")
        for r, u, e, h in cur.fetchall():
            print(f"{r:<12} | {u:<14} | {e:<25} | {h[:25]}...")

    if target in ('issues', 'all'):
        print("\n[+] Table: issues (Sample Defect Records)")
        print(f"{'Key':<10} | {'Status':<16} | {'Severity':<10} | {'Title'}")
        print("-" * 75)
        cur.execute("SELECT issue_key, status, severity, title FROM issues LIMIT 6;")
        for k, s, sev, title in cur.fetchall():
            print(f"{k:<10} | {s:<16} | {sev:<10} | {title[:35]}")

    if target in ('projects', 'all'):
        print("\n[+] Table: projects")
        print(f"{'Key':<8} | {'Name':<30} | {'Status'}")
        print("-" * 55)
        cur.execute("SELECT key, name, status FROM projects;")
        for k, n, s in cur.fetchall():
            print(f"{k:<8} | {n:<30} | {s}")

    conn.close()

if __name__ == '__main__':
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    view_database(arg)
