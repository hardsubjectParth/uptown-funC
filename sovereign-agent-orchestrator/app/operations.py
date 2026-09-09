import os
import socket
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException
from prometheus_client import Counter, Histogram


REQUESTS = Counter('orchestrator_http_requests_total', 'HTTP requests', ['method', 'path', 'status'])
REQUEST_LATENCY = Histogram('orchestrator_http_request_seconds', 'HTTP request latency', ['method', 'path'])
UPLOADS = Counter('orchestrator_uploads_total', 'Document uploads', ['status'])
JOBS = Counter('orchestrator_jobs_total', 'Jobs created', ['kind'])
RETRIEVALS = Counter('orchestrator_retrievals_total', 'RAG retrieval requests', ['method'])


class RequestLimiter:
    def __init__(self, requests_per_minute=120):
        self.limit = requests_per_minute
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= 60:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


class MalwareScanner:
    def __init__(self, host='', port=3310, required=False):
        self.host = host
        self.port = port
        self.required = required

    def scan(self, data):
        if not self.host:
            if self.required:
                raise HTTPException(503, 'MALWARE_SCANNER_UNAVAILABLE')
            return {'status': 'skipped', 'reason': 'CLAMAV_NOT_CONFIGURED'}
        try:
            with socket.create_connection((self.host, self.port), timeout=5) as connection:
                connection.sendall(b'zINSTREAM\x00')
                for start in range(0, len(data), 1024 * 1024):
                    chunk = data[start:start + 1024 * 1024]
                    connection.sendall(len(chunk).to_bytes(4, 'big') + chunk)
                connection.sendall((0).to_bytes(4, 'big'))
                result = connection.recv(4096).decode('utf-8', errors='replace')
            if 'FOUND' in result:
                raise HTTPException(422, 'MALWARE_DETECTED')
            return {'status': 'clean', 'engine': 'clamav'}
        except HTTPException:
            raise
        except OSError as exc:
            if self.required:
                raise HTTPException(503, 'MALWARE_SCANNER_UNAVAILABLE') from exc
            return {'status': 'skipped', 'reason': 'CLAMAV_UNREACHABLE'}


class RuntimeControls:
    def __init__(self, store, settings):
        self.store = store
        self.max_upload_bytes = settings.max_upload_bytes
        self.quota_bytes = settings.user_storage_quota_bytes
        self.limiter = RequestLimiter(settings.rate_limit_per_minute)
        self.scanner = MalwareScanner(settings.clamav_host, settings.clamav_port, settings.malware_scan_required)

    def authorize_request(self, identity):
        if not self.limiter.allow(f"{identity.get('tenant_id')}:{identity.get('user_id')}"):
            raise HTTPException(429, 'RATE_LIMIT_EXCEEDED')

    def authorize_upload(self, identity, size):
        if size > self.max_upload_bytes:
            raise HTTPException(413, 'UPLOAD_TOO_LARGE')
        current = self.store.user_storage_bytes(identity)
        if current + size > self.quota_bytes:
            raise HTTPException(413, 'USER_STORAGE_QUOTA_EXCEEDED')
        return self.scanner.scan
