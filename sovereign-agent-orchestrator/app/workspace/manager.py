from pathlib import Path


class Workspace:
    """Per-job filesystem with path-traversal protection.

    Layout for each job:
        <root>/<job_id>/input/     files copied from the upload store
        <root>/<job_id>/working/   intermediate job files
        <root>/<job_id>/output/    generated artifacts exposed through the API
        <root>/<job_id>/logs/      reserved for job-specific logs
    """

    SUBDIRS = ('input', 'working', 'output', 'logs')

    def __init__(self, root):
        # Resolve to an absolute path so callers can freely mix ``root`` with
        # the absolute paths returned by ``safe()`` (e.g. ``Path.relative_to``).
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, job_id):
        job_root = self.root / job_id
        for name in self.SUBDIRS:
            (job_root / name).mkdir(parents=True, exist_ok=True)
        return job_root

    def safe(self, job_id, relative_path, create=False):
        """Resolve ``relative_path`` under the job workspace.

        Raises ``ValueError('PATH_OUTSIDE_JOB_WORKSPACE')`` if the resolved path
        escapes ``<root>/<job_id>`` (via ``..``, an absolute path, or a symlink).
        With ``create=True`` the parent directory is created.
        """
        job_root = (self.root / job_id).resolve()
        target = (job_root / relative_path).resolve()
        if target != job_root and not target.is_relative_to(job_root):
            raise ValueError('PATH_OUTSIDE_JOB_WORKSPACE')
        if create:
            target.parent.mkdir(parents=True, exist_ok=True)
        return target
