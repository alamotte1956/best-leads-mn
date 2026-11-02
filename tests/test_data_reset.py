import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from tools.reset_customer_records import reset_database


class DataResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.path=self.root/'customers.db';self.backup=self.root/'customers-backup.db'
        with closing(sqlite3.connect(self.path)) as c:
            c.executescript('''PRAGMA foreign_keys=ON;
                CREATE TABLE contractors(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE leads(id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE lead_offers(id INTEGER PRIMARY KEY, contractor_id INTEGER REFERENCES contractors(id),lead_id INTEGER REFERENCES leads(id));
                CREATE TABLE provider_deliveries(id INTEGER PRIMARY KEY,offer_id INTEGER REFERENCES lead_offers(id),recipient TEXT);
                CREATE TABLE consumer_status(id INTEGER PRIMARY KEY,lead_id INTEGER REFERENCES leads(id),delivery_id INTEGER REFERENCES provider_deliveries(id));
                CREATE TABLE contractor_market_applications(id INTEGER PRIMARY KEY,contractor_id INTEGER REFERENCES contractors(id));
                CREATE TABLE admin_login_attempts(id INTEGER PRIMARY KEY);
                CREATE TABLE market_lead_benchmarks(id INTEGER PRIMARY KEY);
                INSERT INTO contractors VALUES(1,'Synthetic Contractor');INSERT INTO leads VALUES(1,'Synthetic Consumer');
                INSERT INTO lead_offers VALUES(1,1,1);INSERT INTO provider_deliveries VALUES(1,1,'synthetic@example.com');
                INSERT INTO consumer_status VALUES(1,1,1);INSERT INTO contractor_market_applications VALUES(1,1);
                INSERT INTO admin_login_attempts VALUES(1);INSERT INTO market_lead_benchmarks VALUES(1);''')
        self.program=self.root/'app.py';self.program.write_text('preserve program files')

    def tearDown(self):self.tmp.cleanup()

    def count(self,path,table):
        with closing(sqlite3.connect(path)) as c:return c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]

    def test_dry_run_changes_no_rows_and_creates_no_backup(self):
        result=reset_database(self.path)
        self.assertFalse(result['applied']);self.assertEqual(result['counts']['contractors'],1)
        self.assertEqual(self.count(self.path,'leads'),1);self.assertFalse(self.backup.exists())

    def test_only_customer_rows_deleted_after_recoverable_verified_snapshot(self):
        result=reset_database(self.path,apply=True,backup=self.backup)
        self.assertTrue(result['applied'])
        for table in result['counts']:
            self.assertEqual(self.count(self.path,table),0);self.assertEqual(self.count(self.backup,table),1)
        self.assertEqual(self.count(self.path,'admin_login_attempts'),1)
        self.assertEqual(self.count(self.path,'market_lead_benchmarks'),1)
        self.assertEqual(self.program.read_text(),'preserve program files')
        with closing(sqlite3.connect(self.path)) as c:
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(len(c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()),8)

    def test_missing_or_existing_backup_cannot_delete_records(self):
        for backup in (None,self.path,self.program):
            with self.assertRaises(ValueError):reset_database(self.path,apply=True,backup=backup)
            self.assertEqual(self.count(self.path,'contractors'),1)

    def test_database_must_exist_and_cannot_be_a_program_file_or_url(self):
        for path in (self.root/'missing.db',self.program,'postgresql://example.invalid/private'):
            with self.assertRaises((ValueError,FileNotFoundError,OSError)):reset_database(path,apply=True,backup=self.backup)
        self.assertFalse((self.root/'missing.db').exists());self.assertEqual(self.program.read_text(),'preserve program files')

    def test_constraint_failure_rolls_back_all_deletes(self):
        with closing(sqlite3.connect(self.path)) as c:
            c.execute("CREATE TRIGGER prevent_delete BEFORE DELETE ON contractors BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):reset_database(self.path,apply=True,backup=self.backup)
        for table in ('contractors','leads','lead_offers','provider_deliveries','consumer_status'):
            self.assertEqual(self.count(self.path,table),1)
        self.assertEqual(self.count(self.backup,'contractors'),1)

    def test_protected_operational_dependencies_require_review(self):
        with closing(sqlite3.connect(self.path)) as c:
            c.execute('ALTER TABLE market_lead_benchmarks ADD COLUMN contractor_id INTEGER REFERENCES contractors(id)')
        with self.assertRaises(ValueError):reset_database(self.path,apply=True,backup=self.backup)
        self.assertEqual(self.count(self.path,'contractors'),1)
