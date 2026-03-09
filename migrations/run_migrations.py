"""
Migration runner for the MST project.

Connects to your local MySQL database and runs all pending SQL migrations
in order. Tracks which migrations have already been applied in a
`_migration_history` table so they are never run twice.

Usage:
    cd <project_root>
    python migrations/run_migrations.py

By default it reads the DATABASE_URL env var (same one Flask uses).
Fallback: mysql+pymysql://root:8888@localhost/exam
"""

import os
import sys
import glob

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://root:8888@localhost/exam",
)

MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def get_engine():
    return create_engine(DATABASE_URL)


def ensure_history_table(conn):
    """Create the migration tracking table if it doesn't exist."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS `_migration_history` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `filename` VARCHAR(255) NOT NULL,
            `applied_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_migration_filename` (`filename`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """))
    conn.commit()


def already_applied(conn, filename):
    """Check whether a migration file has already been applied."""
    result = conn.execute(
        text("SELECT COUNT(*) FROM `_migration_history` WHERE `filename` = :f"),
        {"f": filename},
    )
    return result.scalar() > 0


def record_migration(conn, filename):
    """Record a migration as applied."""
    conn.execute(
        text("INSERT INTO `_migration_history` (`filename`) VALUES (:f)"),
        {"f": filename},
    )
    conn.commit()


def run_migrations():
    engine = get_engine()
    sql_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

    if not sql_files:
        print("No SQL migration files found.")
        return

    with engine.connect() as conn:
        ensure_history_table(conn)

        applied_count = 0
        skipped_count = 0

        for filepath in sql_files:
            filename = os.path.basename(filepath)

            if already_applied(conn, filename):
                print(f"  SKIP  {filename} (already applied)")
                skipped_count += 1
                continue

            print(f"  RUN   {filename} ... ", end="", flush=True)
            with open(filepath, "r") as f:
                sql_content = f.read()

            # Execute each statement separately (split on semicolons)
            statements = [s.strip() for s in sql_content.split(";") if s.strip()]
            try:
                for stmt in statements:
                    # Skip comment-only blocks
                    lines = [
                        l for l in stmt.splitlines()
                        if l.strip() and not l.strip().startswith("--")
                    ]
                    if not lines:
                        continue
                    conn.execute(text(stmt))
                conn.commit()
                record_migration(conn, filename)
                print("OK")
                applied_count += 1
            except Exception as exc:
                print(f"FAILED\n    Error: {exc}")
                conn.rollback()
                sys.exit(1)

        print(f"\nDone. Applied: {applied_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    run_migrations()
