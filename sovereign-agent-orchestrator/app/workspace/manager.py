from pathlib import Path
class Workspace:
    def __init__(self,root): self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def create(self,jid):
        p=self.root/jid
        for x in ('input','working','output','logs'): (p/x).mkdir(parents=True,exist_ok=True)
        return p
    def safe(self,jid,value,create=False):
        root=(self.root/jid).resolve(); p=Path(value); p=(root/p) if not p.is_absolute() else p; p=p.resolve()
        try:p.relative_to(root)
        except ValueError: raise ValueError('PATH_OUTSIDE_JOB_WORKSPACE')
        if create:p.parent.mkdir(parents=True,exist_ok=True)
        return p
