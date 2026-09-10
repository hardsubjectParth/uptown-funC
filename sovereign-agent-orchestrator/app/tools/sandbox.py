"""Run a single generated script with no network and hard resource caps.

Isolation is layered, best-available-wins:

  1. nsjail / bwrap / firejail  -- Linux namespace isolation, no network at all
  2. sandbox-exec               -- macOS Seatbelt profile that denies all network
  3. rlimits only               -- portable floor: CPU / address-space / file-size
                                  caps and `python -I -S -B` so nothing from the
                                  host environment or site-packages leaks in

The deployment target is a Linux GPU box, where 1 applies; 2/3 keep the coding
demo runnable on a developer laptop. The result always reports which layer ran.
"""
import os
import shutil
import subprocess
import sys

_MEM_BYTES = 512 * 1024 * 1024
_FSIZE_BYTES = 16 * 1024 * 1024
_MACOS_PROFILE = '(version 1)(allow default)(deny network*)(deny network-outbound)(deny network-inbound)'


def _wrap(argv, run_dir, wall_limit):
    """Prefix argv with the strongest available OS isolation wrapper."""
    if shutil.which('nsjail'):
        return 'nsjail', [
            'nsjail', '--quiet', '--mode', 'o', '--disable_proc', '--iface_no_lo',
            '--rlimit_as', '512', '--rlimit_fsize', '16', '--time_limit', str(wall_limit),
            '--cwd', str(run_dir), '--really_quiet', '--', *argv,
        ]
    if shutil.which('bwrap'):
        return 'bwrap', [
            'bwrap', '--unshare-all', '--die-with-parent', '--new-session',
            '--ro-bind', '/usr', '/usr', '--ro-bind', '/bin', '/bin', '--ro-bind', '/lib', '/lib',
            '--ro-bind-try', '/lib64', '/lib64', '--ro-bind-try', '/etc/alternatives', '/etc/alternatives',
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--bind', str(run_dir), str(run_dir),
            '--chdir', str(run_dir), '--', *argv,
        ]
    if shutil.which('firejail'):
        return 'firejail', ['firejail', '--quiet', '--net=none', '--private-tmp', f'--private={run_dir}', '--', *argv]
    if sys.platform == 'darwin' and shutil.which('sandbox-exec'):
        return 'sandbox-exec(deny-network)', ['sandbox-exec', '-p', _MACOS_PROFILE, *argv]
    return 'rlimits-only', argv


def _preexec(cpu_limit):
    if os.name != 'posix':
        return None

    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (_MEM_BYTES, _MEM_BYTES))
        except (ValueError, OSError):
            pass
        resource.setrlimit(resource.RLIMIT_FSIZE, (_FSIZE_BYTES, _FSIZE_BYTES))
        os.setsid()

    return limits


def run_script(path, run_dir, timeout=15):
    """Execute ``path`` (a .py file) inside ``run_dir``. Never raises for script
    errors -- the caller inspects ``exit_code`` / ``passed``."""
    timeout = max(1, min(int(timeout), 30))
    from pathlib import Path
    path = Path(path).resolve()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, '-I', '-S', '-B', str(path)]
    kind, wrapped = _wrap(argv, run_dir, timeout + 2)
    env = {
        'PATH': '/usr/bin:/bin',
        'HOME': str(run_dir),
        'TMPDIR': str(run_dir),
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONNOUSERSITE': '1',
        'PYTHONPATH': '',
    }
    try:
        # nsjail / bwrap / firejail enforce their own caps; add rlimits ourselves
        # only for the macOS profile and the portable floor.
        needs_rlimits = kind in ('rlimits-only', 'sandbox-exec(deny-network)')
        proc = subprocess.run(
            wrapped, cwd=str(run_dir), env=env,
            capture_output=True, text=True, timeout=timeout + 3,
            preexec_fn=_preexec(timeout) if needs_rlimits else None,
        )
        return {
            'tool': 'run_python', 'path': str(path), 'sandbox': kind,
            'exit_code': proc.returncode, 'timed_out': False,
            'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:],
            'passed': proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'tool': 'run_python', 'path': str(path), 'sandbox': kind,
            'exit_code': None, 'timed_out': True,
            'stdout': (exc.stdout or '')[-4000:] if isinstance(exc.stdout, str) else '',
            'stderr': (exc.stderr or '')[-4000:] if isinstance(exc.stderr, str) else 'killed after timeout',
            'passed': False,
        }
    except FileNotFoundError as exc:
        return {
            'tool': 'run_python', 'path': str(path), 'sandbox': kind,
            'exit_code': None, 'timed_out': False, 'stdout': '', 'stderr': f'sandbox launch failed: {exc}',
            'passed': False,
        }
