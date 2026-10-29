from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import ReviewError


def data_home() -> Path:
    hermes = os.environ.get("HERMES_HOME")
    if hermes and (Path(hermes).expanduser() / "creview-profile.json").is_file():
        return Path(hermes).expanduser().resolve() / "review-data"
    override = os.environ.get("CREVIEW_HOME")
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise ReviewError("CREVIEW_HOME must be an absolute path")
        return root
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share") / "closed-review"


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError as exc:
        raise ReviewError(f"cannot secure directory {path}: {exc}") from exc
    return path


def _windows() -> bool:
    return os.name == "nt"


def permission_problem(path: Path) -> str | None:
    """Why `path` may be readable by other users, or None when it is private.

    On macOS and Linux this checks the permission bits. Windows does not use them (Python reports
    0o777 and chmod cannot change it), so there the path must sit inside the user's profile folder,
    whose default access list admits only the user, SYSTEM, and administrators. creview does not
    read Windows access lists, so a profile folder shared by hand is not detected.
    """
    if _windows():
        home = Path(os.environ.get("USERPROFILE") or Path.home()).resolve()
        try:
            path.resolve().relative_to(home)
        except ValueError:
            return (
                f"{path} is outside your Windows user profile ({home}); creview can confirm a "
                "private store only inside it"
            )
        return None
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        return f"{path} permissions are not private: {oct(mode)}"
    return None


def secure_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError as exc:
        raise ReviewError(f"cannot secure file {path}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    ensure_private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        secure_file(tmp_path)
        os.replace(tmp_path, path)
        secure_file(path)
    finally:
        tmp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, value: str) -> None:
    ensure_private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        secure_file(tmp_path)
        os.replace(tmp_path, path)
        secure_file(path)
    finally:
        tmp_path.unlink(missing_ok=True)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewError(f"file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"cannot read JSON {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def read_statement(statement: str | None, statement_file: Path | None) -> str:
    if statement_file:
        try:
            return statement_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReviewError(f"cannot read statement file: {exc}") from exc
    return statement or ""


def assert_private_store() -> list[str]:
    problems: list[str] = []
    root = data_home()
    problem = permission_problem(root) if root.exists() else None
    if problem:
        problems.append(f"data store is not private: {problem}")
    return problems
