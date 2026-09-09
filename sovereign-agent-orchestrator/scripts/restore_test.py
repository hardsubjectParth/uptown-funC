import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description='Restore a backup into a disposable PostgreSQL database for a restore drill.')
    parser.add_argument('archive')
    parser.add_argument('--database-url', required=True, help='Disposable target database URL')
    args = parser.parse_args()
    archive = Path(args.archive)
    if not archive.is_file():
        raise SystemExit(f'Backup not found: {archive}')
    parsed = urlparse(args.database_url.replace('postgresql+psycopg://', 'postgresql://', 1))
    env = os.environ.copy()
    if parsed.password:
        env['PGPASSWORD'] = parsed.password
    command = ['pg_restore', '--clean', '--if-exists', '--single-transaction', '--no-owner', '--host', parsed.hostname or 'localhost', '--port', str(parsed.port or 5432), '--username', parsed.username or 'orchestrator', '--dbname', parsed.path.lstrip('/'), str(archive)]
    subprocess.run(command, env=env, check=True)
    print(f'Restore drill completed: {archive} -> {parsed.path.lstrip("/")}')


if __name__ == '__main__':
    main()
