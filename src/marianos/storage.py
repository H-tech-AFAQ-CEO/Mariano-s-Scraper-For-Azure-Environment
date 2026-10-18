"""Storage abstraction: atomic text writes + per-job run lock. Local (dev/tests) and Azure Blob (prod)."""
import contextlib
import json
import os
import threading
import time
from pathlib import Path

from .common import LockHeld


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key):
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise ValueError("key escapes root")
        return p

    def read_text(self, key):
        p = self._p(key)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def write_text(self, key, text):
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + f".tmp{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)  # atomic

    def write_bytes(self, key, data):
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def exists(self, key):
        return self._p(key).exists()

    def list(self, prefix):
        base = self._p(prefix) if prefix else self.root
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace(os.sep, "/") for p in base.rglob("*") if p.is_file())

    def delete(self, key):
        p = self._p(key)
        if p.exists():
            p.unlink()

    @contextlib.contextmanager
    def lock(self, name, stale_after_s=12 * 3600):
        p = self._p(f"locks/{name}.lock")
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            age = time.time() - p.stat().st_mtime
            if age < stale_after_s:
                raise LockHeld(f"run lock '{name}' is held (age {int(age)}s)")
            p.unlink()
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        try:
            yield
        finally:
            with contextlib.suppress(FileNotFoundError):
                p.unlink()


class AzureBlobStorage:
    """Atomic overwrite = single upload_blob(overwrite=True). Lock = 60s blob lease renewed by a thread
    (a crashed container's lease expires on its own, so no manual unlock is ever needed)."""

    def __init__(self, container, account_url=None, connection_string=None):
        from azure.storage.blob import BlobServiceClient  # lazy: not needed for local/dev
        if connection_string:
            svc = BlobServiceClient.from_connection_string(connection_string)
        else:
            from azure.identity import DefaultAzureCredential
            svc = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
        self.c = svc.get_container_client(container)
        try:
            self.c.create_container()
        except Exception:
            pass

    def read_text(self, key):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return self.c.download_blob(key).readall().decode("utf-8")
        except ResourceNotFoundError:
            return None

    def write_text(self, key, text):
        self.c.upload_blob(key, text.encode("utf-8"), overwrite=True)

    def write_bytes(self, key, data):
        self.c.upload_blob(key, data, overwrite=True)

    def exists(self, key):
        return self.c.get_blob_client(key).exists()

    def list(self, prefix):
        return sorted(b.name for b in self.c.list_blobs(name_starts_with=prefix))

    def delete(self, key):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            self.c.delete_blob(key)
        except ResourceNotFoundError:
            pass

    @contextlib.contextmanager
    def lock(self, name, **_):
        from azure.core.exceptions import HttpResponseError
        key = f"locks/{name}.lock"
        bc = self.c.get_blob_client(key)
        if not bc.exists():
            try:
                bc.upload_blob(b"lock", overwrite=False)
            except HttpResponseError:
                pass
        try:
            lease = bc.acquire_lease(lease_duration=60)
        except HttpResponseError as e:
            raise LockHeld(f"run lock '{name}' is held: {e}") from e
        stop = threading.Event()

        def renew():
            while not stop.wait(20):
                try:
                    lease.renew()
                except Exception:
                    return

        t = threading.Thread(target=renew, daemon=True)
        t.start()
        try:
            yield
        finally:
            stop.set()
            try:
                lease.release()
            except Exception:
                pass


def make_storage(settings):
    s = settings.get("storage", {})
    if s.get("backend") == "azure":
        return AzureBlobStorage(
            s.get("azure_container", "marianos-scraper"),
            account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        )
    return LocalStorage(s.get("local_root", "./data"))


def jdump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)
