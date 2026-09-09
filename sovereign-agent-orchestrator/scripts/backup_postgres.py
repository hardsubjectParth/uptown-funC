import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description='Create a PostgreSQL custom-format backup.')
    parser.add_argument('--output-dir', default='backups')
    args = parser.parse_args()
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url.startswith(('postgresql://', 'postgresql+psycopg://')):
        raise SystemExit('DATABASE_URL must be a PostgreSQL URL')
    parsed = urlparse(database_url.replace('postgresql+psycopg://', 'postgresql://', 1))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"orchestrator_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.dump"
    env = os.environ.copy()
    if parsed.password:
        env['PGPASSWORD'] = parsed.password
    command = ['pg_dump', '--format=custom', '--no-owner', '--file', str(output), '--host', parsed.hostname or 'localhost', '--port', str(parsed.port or 5432), '--username', parsed.username or 'orchestrator', parsed.path.lstrip('/')]
    subprocess.run(command, env=env, check=True)
    print(output)


if __name__ == '__main__':
    main()
