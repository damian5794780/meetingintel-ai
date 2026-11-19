import hashlib
import hmac
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

_ACTIVE_STATES = ('queued', 'running')
_STATUS_FIELDS = 's.id, s.status, s.stage, s.revision, s.created_at, s.error'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, payload TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS evidence_snapshots (
                job_id TEXT NOT NULL, source_id TEXT NOT NULL, content_hash TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY (job_id, source_id, content_hash))''')
            db.execute('''CREATE TABLE IF NOT EXISTS job_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                stage TEXT NOT NULL, started_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS job_metadata (
                id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                status TEXT NOT NULL, stage TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, error TEXT)''')
            db.execute('CREATE INDEX IF NOT EXISTS job_metadata_status_created_idx ON job_metadata(status, created_at)')
            db.execute('''CREATE TABLE IF NOT EXISTS job_submissions (
                key_hash TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE)''')
            self._migrate_legacy_jobs(db)

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys = ON')
            yield db

    @staticmethod
    def _migrate_legacy_jobs(db):
        if db.execute('PRAGMA user_version').fetchone()[0] >= 1:
            return
        db.execute("""INSERT INTO job_metadata (id, status, stage, revision, created_at, error)
            SELECT id, json_extract(payload, '$.status'), json_extract(payload, '$.stage'),
                json_extract(payload, '$.revision'), json_extract(payload, '$.created_at'),
                json_extract(payload, '$.error')
            FROM jobs""")
        db.execute('PRAGMA user_version = 1')

    def recover(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute(
                f'SELECT {_STATUS_FIELDS} FROM job_metadata s WHERE s.status IN (?, ?)', _ACTIVE_STATES
            ).fetchall()
            for row in rows:
                self._transition(db, dict(row), status='failed', stage='failed',
                                 error='Server restarted. Please start a new briefing.')

    def create(self, job_id, token, request, *, submission=None):
        state = dict(id=job_id, status='queued', stage='queued', revision=0, created_at=_now(), error=None)
        payload = dict(request=request, result=None)
        with self.connect() as db:
            db.execute('INSERT INTO jobs (id, token_hash, payload) VALUES (?, ?, ?)',
                       (job_id, _token_hash(token), json.dumps(payload)))
            db.execute('''INSERT INTO job_metadata (id, status, stage, revision, created_at, error)
                          VALUES (:id, :status, :stage, :revision, :created_at, :error)''', state)
            if submission is not None:
                key_hash, request_hash = submission
                db.execute('INSERT INTO job_submissions (key_hash, request_hash, job_id) VALUES (?, ?, ?)',
                           (key_hash, request_hash, job_id))
        return {**payload, **state}

    def find_submission(self, key_hash):
        with self.connect() as db:
            row = db.execute('''SELECT s.id, s.status, submission.request_hash
                                FROM job_submissions submission
                                JOIN job_metadata s ON s.id = submission.job_id
                                WHERE submission.key_hash = ?''', (key_hash,)).fetchone()
            return dict(row) if row else None

    def get_status(self, job_id, token=None):
        with self.connect() as db:
            row = db.execute(f'''SELECT {_STATUS_FIELDS}, j.token_hash FROM job_metadata s
                                 JOIN jobs j ON j.id = s.id WHERE s.id = ?''', (job_id,)).fetchone()
        return self._authorized(row, token)

    def get(self, job_id, token=None):
        with self.connect() as db:
            row = db.execute(f'''SELECT {_STATUS_FIELDS}, j.token_hash, j.payload FROM job_metadata s
                                 JOIN jobs j ON j.id = s.id WHERE s.id = ?''', (job_id,)).fetchone()
        state = self._authorized(row, token)
        if state is None:
            return None
        payload = json.loads(state.pop('payload'))
        return {**payload, **state}

    @staticmethod
    def _authorized(row, token):
        if row is None or (token is not None and not hmac.compare_digest(row['token_hash'], _token_hash(token))):
            return None
        result = dict(row)
        del result['token_hash']
        return result

    @staticmethod
    def _transition(db, state, **changes):
        if 'stage' in changes:
            db.execute('INSERT INTO job_stages (job_id, stage, started_at) VALUES (?, ?, ?)',
                       (state['id'], changes['stage'], _now()))
        state.update(changes)
        state['revision'] += 1
        db.execute('''UPDATE job_metadata SET status=:status, stage=:stage, revision=:revision, error=:error
                      WHERE id=:id''', state)

    def update(self, job_id, *, only_active=False, **changes):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute(f'SELECT {_STATUS_FIELDS} FROM job_metadata s WHERE s.id=?', (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if only_active and row['status'] not in _ACTIVE_STATES:
                return
            if 'result' in changes:
                result = changes.pop('result')
                db.execute("UPDATE jobs SET payload=json_set(payload, '$.result', json(?)) WHERE id=?",
                           (json.dumps(result), job_id))
                for source in (result or {}).get('sources', []):
                    db.execute('INSERT OR REPLACE INTO evidence_snapshots VALUES (?, ?, ?, ?)',
                               (job_id, source['id'], source.get('content_hash', ''), json.dumps(source)))
            self._transition(db, dict(row), **changes)
