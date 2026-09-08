import json
import threading
from datetime import datetime, timezone
from sqlalchemy import create_engine, text


class Store:
    def __init__(self, url='sqlite:///./orchestrator.db'):
        self.url = url
        self.engine = create_engine(url, future=True, pool_pre_ping=True)
        self.lock = threading.Lock()
        self._create_schema()

    def _create_schema(self):
        integer = 'INTEGER PRIMARY KEY AUTOINCREMENT' if self.url.startswith('sqlite') else 'BIGSERIAL PRIMARY KEY'
        with self.engine.begin() as db:
            db.execute(text('CREATE TABLE IF NOT EXISTS jobs(id VARCHAR(255) PRIMARY KEY, data TEXT NOT NULL)'))
            db.execute(text(f'CREATE TABLE IF NOT EXISTS events(id {integer}, job_id VARCHAR(255), type VARCHAR(255), data TEXT, created_at VARCHAR(255))'))
            db.execute(text(f'CREATE TABLE IF NOT EXISTS approvals(id {integer}, job_id VARCHAR(255), approved INTEGER, reviewer VARCHAR(255), created_at VARCHAR(255))'))
            db.execute(text('CREATE TABLE IF NOT EXISTS files(id VARCHAR(255) PRIMARY KEY, owner_id VARCHAR(255) NOT NULL, tenant_id VARCHAR(255) NOT NULL, name VARCHAR(255) NOT NULL, path TEXT NOT NULL, metadata TEXT NOT NULL)'))
            db.execute(text(f'CREATE TABLE IF NOT EXISTS audit_events(id {integer}, actor_id VARCHAR(255), tenant_id VARCHAR(255), action VARCHAR(255) NOT NULL, resource VARCHAR(255), data TEXT, created_at VARCHAR(255))'))
            db.execute(text('CREATE TABLE IF NOT EXISTS job_queue(job_id VARCHAR(255) PRIMARY KEY, status VARCHAR(32) NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, created_at VARCHAR(255) NOT NULL)'))

    def save(self, job):
        values = {'id': job['job_id'], 'data': json.dumps(job)}
        with self.lock, self.engine.begin() as db:
            statement = 'INSERT OR REPLACE INTO jobs(id,data) VALUES(:id,:data)' if self.url.startswith('sqlite') else 'INSERT INTO jobs(id,data) VALUES(:id,:data) ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data'
            db.execute(text(statement), values)

    def get(self, jid):
        with self.engine.connect() as db:
            row = db.execute(text('SELECT data FROM jobs WHERE id=:id'), {'id': jid}).first()
        return json.loads(row[0]) if row else None

    def event(self, jid, typ, data):
        with self.lock, self.engine.begin() as db:
            db.execute(text('INSERT INTO events(job_id,type,data,created_at) VALUES(:job,:type,:data,:created)'), {'job': jid, 'type': typ, 'data': json.dumps(data), 'created': datetime.now(timezone.utc).isoformat()})

    def events(self, jid):
        with self.engine.connect() as db:
            rows = db.execute(text('SELECT id,type,data,created_at FROM events WHERE job_id=:job ORDER BY id'), {'job': jid}).fetchall()
        return [{'event_id': str(row[0]), 'type': row[1], 'data': json.loads(row[2]), 'timestamp': row[3]} for row in rows]

    def approval(self, jid, approved, reviewer):
        with self.lock, self.engine.begin() as db:
            db.execute(text('INSERT INTO approvals(job_id,approved,reviewer,created_at) VALUES(:job,:approved,:reviewer,:created)'), {'job': jid, 'approved': int(approved), 'reviewer': reviewer, 'created': datetime.now(timezone.utc).isoformat()})

    def register_file(self, file_id, owner_id, tenant_id, name, path, metadata):
        with self.engine.begin() as db:
            db.execute(text('INSERT INTO files(id,owner_id,tenant_id,name,path,metadata) VALUES(:id,:owner,:tenant,:name,:path,:metadata)'), {'id': file_id, 'owner': owner_id, 'tenant': tenant_id, 'name': name, 'path': path, 'metadata': json.dumps(metadata)})

    def file_for(self, file_id, identity):
        with self.engine.connect() as db:
            row = db.execute(text('SELECT id,owner_id,tenant_id,name,path,metadata FROM files WHERE id=:id AND tenant_id=:tenant'), {'id': file_id, 'tenant': identity['tenant_id']}).first()
        return dict(row._mapping) if row and (row.owner_id == identity['user_id'] or identity.get('role') == 'admin') else None

    def audit(self, actor_id, tenant_id, action, resource, data=None):
        with self.engine.begin() as db:
            db.execute(text('INSERT INTO audit_events(actor_id,tenant_id,action,resource,data,created_at) VALUES(:actor,:tenant,:action,:resource,:data,:created)'), {'actor': actor_id, 'tenant': tenant_id, 'action': action, 'resource': resource, 'data': json.dumps(data or {}), 'created': datetime.now(timezone.utc).isoformat()})

    def enqueue(self, job_id):
        with self.engine.begin() as db:
            db.execute(text('INSERT INTO job_queue(job_id,status,created_at) VALUES(:job,:status,:created)'), {'job': job_id, 'status': 'queued', 'created': datetime.now(timezone.utc).isoformat()})

    def claim_next(self):
        with self.lock, self.engine.begin() as db:
            row = db.execute(text("SELECT job_id FROM job_queue WHERE status='queued' ORDER BY created_at LIMIT 1")).first()
            if not row:
                return None
            db.execute(text("UPDATE job_queue SET status='running', attempts=attempts+1 WHERE job_id=:job AND status='queued'"), {'job': row[0]})
        return self.get(row[0])

    def finish_queue(self, job_id, failed=False):
        with self.engine.begin() as db:
            db.execute(text('UPDATE job_queue SET status=:status WHERE job_id=:job'), {'status': 'failed' if failed else 'done', 'job': job_id})
