import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, payload TEXT NOT NULL)''')
            # Additive migration: existing job snapshots remain readable unchanged.
            db.execute('''CREATE TABLE IF NOT EXISTS evidence_snapshots (
                job_id TEXT NOT NULL, source_id TEXT NOT NULL, content_hash TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY (job_id, source_id, content_hash))''')
            db.execute('''CREATE TABLE IF NOT EXISTS job_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                stage TEXT NOT NULL, started_at TEXT NOT NULL)''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def recover(self):
        with self.connect() as db:
            rows = db.execute('SELECT id, payload FROM jobs').fetchall()
            for job_id, payload in rows:
                job = json.loads(payload)
                if job['status'] in ('queued', 'running'):
                    job.update(status='failed', stage='failed', error='Server restarted. Please start a new briefing.')
                    db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(job), job_id))

    def create(self, job_id, token, request):
        job = dict(id=job_id, status='queued', stage='queued', revision=0,
                   created_at=datetime.now(timezone.utc).isoformat(), request=request,
                   result=None, error=None)
        with self.connect() as db:
            db.execute('INSERT INTO jobs VALUES (?, ?, ?)',
                       (job_id, hashlib.sha256(token.encode()).hexdigest(), json.dumps(job)))
        return job

    def get(self, job_id, token=None):
        with self.connect() as db:
            row = db.execute('SELECT token_hash, payload FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return None
        if token is not None and not hmac.compare_digest(row[0], hashlib.sha256(token.encode()).hexdigest()):
            return None
        return json.loads(row[1])

    def update(self, job_id, **changes):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
            job = json.loads(row[0])
            job.update(changes)
            job['revision'] += 1
            db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(job), job_id))
            if 'stage' in changes:
                db.execute('INSERT INTO job_stages (job_id, stage, started_at) VALUES (?, ?, ?)',
                           (job_id, changes['stage'], datetime.now(timezone.utc).isoformat()))
            if changes.get('result'):
                for source in changes['result'].get('sources', []):
                    db.execute('INSERT OR REPLACE INTO evidence_snapshots VALUES (?, ?, ?, ?)',
                               (job_id, source['id'], source.get('content_hash', ''), json.dumps(source)))

    def active_count(self):
        with self.connect() as db:
            rows = db.execute('SELECT payload FROM jobs').fetchall()
        return sum(json.loads(r[0])['status'] in ('queued', 'running') for r in rows)
