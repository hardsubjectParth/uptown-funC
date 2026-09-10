import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Validate a PostgreSQL backup archive without modifying a database.')
    parser.add_argument('archive')
    args = parser.parse_args()
    archive = Path(args.archive)
    if not archive.is_file():
        raise SystemExit(f'Backup not found: {archive}')
    subprocess.run(['pg_restore', '--list', str(archive)], check=True)
    print(f'Backup archive is readable: {archive}')


if __name__ == '__main__':
    main()
