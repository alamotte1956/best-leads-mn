"""Explicit idempotent pre-deploy migration: creates additive QBO and administrator recovery tables."""
from pathlib import Path
from sqlalchemy import text
from app import app,db

def main():
    with app.app_context():
        if db.engine.dialect.name!='postgresql':raise RuntimeError('Hosted QuickBooks migration requires PostgreSQL.')
        # PostgreSQL transaction advisory lock prevents overlapping release runners.
        bodies=[(Path(__file__).parent/'migrations'/name).read_text() for name in ('024_quickbooks_online.sql','025_admin_recovery.sql')]
        with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            with connection.connection.cursor() as cursor:
                try:
                    cursor.execute('BEGIN')
                    cursor.execute('SELECT pg_advisory_xact_lock(724024)')
                    for body in bodies:
                        cursor.execute(body.removeprefix('-- Additive only. No existing financial/customer rows are changed.\nBEGIN;').removeprefix('BEGIN;').removesuffix('COMMIT;\n'))
                    cursor.execute('COMMIT')
                except Exception:
                    cursor.execute('ROLLBACK');raise
        print('QuickBooks and administrator recovery additive schema verified. Existing records unchanged.')
if __name__=='__main__':main()
