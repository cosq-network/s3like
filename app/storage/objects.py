import hashlib
import os
import uuid
from pathlib import Path

class ObjectStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir).resolve(); self.objects = self.root / "objects"; self.multipart = self.root / "multipart"; self.tmp = self.root / "tmp"
        for p in (self.objects, self.multipart, self.tmp): p.mkdir(parents=True, exist_ok=True)
    def new_temp(self): p = self.tmp / uuid.uuid4().hex; p.touch(); return p
    def new_id(self): return uuid.uuid4().hex
    def final_path(self, sid):
        p = (self.objects / sid).resolve()
        if self.objects not in p.parents: raise ValueError("invalid storage path")
        return p
    def commit(self, source, sid):
        with Path(source).open('r+b') as f:
            os.fsync(f.fileno())
        p = self.final_path(sid); os.replace(source, p)
        try:
            fd = os.open(self.objects, os.O_RDONLY); os.fsync(fd); os.close(fd)
        except OSError: pass
        return p
    @staticmethod
    def remove(path):
        try: Path(path).unlink()
        except FileNotFoundError: pass
    @staticmethod
    def digest(path):
        h = hashlib.md5(usedforsecurity=False); size = 0
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk); size += len(chunk)
        return size, '"' + h.hexdigest() + '"'
