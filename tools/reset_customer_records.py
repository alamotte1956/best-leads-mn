"""Explicit local SQLite customer-data reset; never modifies program files or schemas.

Dry-run by default. Hosted/PostgreSQL databases are intentionally unsupported.
Use an existing database, stop local app/workers, review the dry-run, then apply
with a new backup path. No production database credentials are accepted.
"""
import argparse
import json
from pathlib import Path
import sqlite3

# Root records include unlinked application receipts, contact suppression and
# contractor login metadata. FK descendants are discovered, never guessed away.
ROOTS = {'contractors', 'leads', 'provider_deliveries', 'sms_suppressions',
         'contractor_login_attempts', 'reward_businesses'}
PRESERVE = {'admin_login_attempts', 'provider_events', 'market_lead_benchmarks', 'lead_price_catalog'}


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def customer_tables(connection):
    names={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    dependencies={name:{row[2] for row in connection.execute('PRAGMA foreign_key_list('+quoted(name)+')')} for name in names}
    selected=names & ROOTS
    while True:
        updated=selected | {name for name, parents in dependencies.items() if parents & selected}
        if updated == selected:break
        selected=updated
    if selected & PRESERVE:
        raise ValueError('Customer dependencies unexpectedly include protected operational tables. Manual review required.')
    # Children are deleted before their parents. Cycles require manual review.
    ordered=[]
    remaining=set(selected)
    while remaining:
        leaves=sorted(name for name in remaining if not any(name in dependencies[child] for child in remaining))
        if not leaves:raise ValueError('Cyclic customer dependencies require manual review.')
        ordered.extend(leaves);remaining.difference_update(leaves)
    return ordered


def reset_database(database, *, apply=False, backup=None):
    path=Path(database).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in ('.db','.sqlite','.sqlite3'):
        raise ValueError('Choose an existing local SQLite database file. Program files are not accepted.')
    # mode=rw never creates a missing database.
    connection=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=10)
    connection.execute('PRAGMA foreign_keys=ON')
    backup_path=None
    try:
        if apply:
            if not backup:raise ValueError('A new backup path is required before deleting customer records.')
            backup_path=Path(backup).resolve()
            if backup_path==path or backup_path.exists() or backup_path.suffix.lower() not in ('.db','.sqlite','.sqlite3'):
                raise ValueError('Choose a new SQLite backup file, separate from the database and program files.')
            if not backup_path.parent.is_dir():raise ValueError('The backup directory must already exist.')
            # Hold the single SQLite writer lock before the independent backup
            # snapshot. Workers cannot insert/change records between backup/reset.
            connection.execute('BEGIN IMMEDIATE')
        else:
            connection.execute('BEGIN')
        tables=customer_tables(connection)
        counts={name:connection.execute('SELECT COUNT(*) FROM '+quoted(name)).fetchone()[0] for name in tables}
        if apply:
            # Exclusive creation avoids overwriting any existing file.
            with backup_path.open('xb'):pass
            source=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)
            destination=sqlite3.connect(backup_path)
            try:
                source.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed. No records were deleted.')
                if destination.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise ValueError('The existing database has foreign-key errors. Manual review required.')
            finally:
                destination.close();source.close()
            for name in tables:connection.execute('DELETE FROM '+quoted(name))
            if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ValueError('Reset would leave broken references. Changes rolled back.')
            connection.commit()
        else:connection.rollback()
        return {'applied':apply,'counts':counts,'backup_created':bool(apply),'program_files_changed':False}
    except Exception:
        connection.rollback()
        raise
    finally:connection.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True,help='Existing local SQLite database file; never a URL')
    parser.add_argument('--apply',action='store_true',help='Delete customer rows after a verified backup')
    parser.add_argument('--backup',help='New local SQLite backup filename (required with --apply)')
    args=parser.parse_args()
    print(json.dumps(reset_database(args.database,apply=args.apply,backup=args.backup),indent=2))


if __name__=='__main__':main()
