#!/usr/bin/env python3
"""
VITAMAN — Safe JSON Data Store
===============================

Drop-in replacement for the scattered load_json / save_json functions
across bot_new.py, bot_referral.py, fb_content_calendar.py, etc.

Problems this module solves:
  1. Race conditions  — file-level locking via ``filelock``
  2. Data corruption  — atomic writes (write-to-temp then os.replace)
  3. No backups       — automatic timestamped backups before every write
  4. No validation    — lightweight schema enforcement per file

Usage (drop-in):
    from data_store import load_json, save_json
    # Signatures are identical to the old ones.

Usage (safe read-modify-write — preferred):
    from data_store import read_modify_write

    def add_order(db):
        db.setdefault("orders", []).append(new_order)
        return db

    read_modify_write(ORDERS_FILE, {"orders": []}, add_order)

Usage (atomic counter):
    from data_store import next_sequence
    seq = next_sequence(COUNTERS_FILE, "last_order_seq")
    order_id = f"VT-{seq:04d}"
"""

import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    from filelock import FileLock, Timeout as LockTimeout
except ImportError:
    raise ImportError(
        "The 'filelock' package is required.  Install it:\n"
        "    pip install filelock\n"
        "Then add 'filelock>=3.12,<4' to requirements.txt."
    )

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

LOCK_TIMEOUT_SECONDS = 10          # max wait to acquire a file lock
MAX_BACKUPS_PER_FILE = 20          # rolling backup window
BACKUP_ENABLED = True              # toggle off for unit tests

# ─── Schemas ─────────────────────────────────────────────────
# Minimal structural schemas: {top-level-key: expected_type}.
# Checked on every read *and* write so corrupt shapes are caught early.

_SCHEMAS: Dict[str, Dict[str, type]] = {
    "users.json":            {"users": list},
    "orders.json":           {"orders": list},
    "reviews.json":          {"reviews": list},
    "counters.json":         {"last_order_seq": int},
    "coupons.json":          {"codes": dict},
    "referrals.json":        {"referrals": dict, "uses": list},
    "content_calendar.json": None,           # top-level list, handled separately
}

_DEFAULTS: Dict[str, Any] = {
    "users.json":            {"users": []},
    "orders.json":           {"orders": []},
    "reviews.json":          {"reviews": []},
    "counters.json":         {"last_order_seq": 0},
    "coupons.json":          {"codes": {}},
    "referrals.json":        {"referrals": {}, "uses": []},
    "content_calendar.json": [],
}


# ─── Validation ──────────────────────────────────────────────

class DataValidationError(Exception):
    """Raised when data fails schema validation."""


def _schema_for(path: str) -> Optional[Dict[str, type]]:
    """Return the schema dict for a known file, or None."""
    basename = os.path.basename(path)
    return _SCHEMAS.get(basename)


def _validate(path: str, data: Any) -> None:
    """
    Validate *data* against the registered schema for *path*.
    Raises DataValidationError on mismatch.
    """
    basename = os.path.basename(path)
    schema = _SCHEMAS.get(basename)

    if schema is None and basename == "content_calendar.json":
        # Top-level must be a list
        if not isinstance(data, list):
            raise DataValidationError(
                f"{basename}: expected top-level list, got {type(data).__name__}"
            )
        return

    if schema is None:
        # Unknown file — skip validation
        return

    if not isinstance(data, dict):
        raise DataValidationError(
            f"{basename}: expected top-level dict, got {type(data).__name__}"
        )

    for key, expected_type in schema.items():
        if key not in data:
            raise DataValidationError(
                f"{basename}: missing required key '{key}'"
            )
        if not isinstance(data[key], expected_type):
            raise DataValidationError(
                f"{basename}: key '{key}' should be "
                f"{expected_type.__name__}, got {type(data[key]).__name__}"
            )


# ─── Lock helpers ────────────────────────────────────────────

def _lock_path(path: str) -> str:
    """Return the .lock path that corresponds to a data file."""
    return path + ".lock"


def _acquire_lock(path: str) -> "FileLock":
    """Create and acquire a FileLock. Caller must release."""
    lock = FileLock(_lock_path(path), timeout=LOCK_TIMEOUT_SECONDS)
    lock.acquire()
    return lock


# ─── Backup ──────────────────────────────────────────────────

def _backup(path: str) -> None:
    """
    Copy *path* into BACKUP_DIR with a timestamp suffix.
    Prunes old backups beyond MAX_BACKUPS_PER_FILE.
    """
    if not BACKUP_ENABLED:
        return
    if not os.path.exists(path):
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    basename = os.path.basename(path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{basename}.{stamp}.bak"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    try:
        shutil.copy2(path, backup_path)
    except OSError as exc:
        logger.warning("Backup failed for %s: %s", path, exc)
        return

    # Prune old backups for this file
    prefix = f"{basename}."
    existing = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith(prefix) and f.endswith(".bak")
    )
    while len(existing) > MAX_BACKUPS_PER_FILE:
        victim = existing.pop(0)
        try:
            os.remove(os.path.join(BACKUP_DIR, victim))
        except OSError:
            pass


# ─── Atomic write ────────────────────────────────────────────

def _atomic_write(path: str, data: Any) -> None:
    """
    Write JSON to *path* atomically:
      1. Serialize to a temp file in the *same* directory (required for
         os.replace to be atomic on the same filesystem).
      2. Flush + fsync so bits hit disk.
      3. os.replace() — atomic on POSIX; on Windows it is atomic for
         NTFS since Python 3.3.
    """
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix=".store_",
        dir=dir_name,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


# ─── Public API (drop-in replacements) ───────────────────────

def load_json(path: str, default: Any = None) -> Any:
    """
    Thread-safe JSON read with file locking.

    Drop-in replacement for the old ``load_json(path, default)``.
    """
    if default is None:
        basename = os.path.basename(path)
        default = _DEFAULTS.get(basename, {})

    if not os.path.exists(path):
        return default

    lock = _acquire_lock(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            logger.warning("Empty file detected: %s — returning default", path)
            return default
        data = json.loads(content)
        try:
            _validate(path, data)
        except DataValidationError as exc:
            logger.warning("Validation warning on read %s: %s", path, exc)
            # Still return data — validation is advisory on reads
        return data
    except json.JSONDecodeError as exc:
        logger.error("Corrupt JSON in %s: %s — returning default", path, exc)
        # Salvage the corrupt file for forensics
        _backup(path)
        return default
    except Exception as exc:
        logger.warning("Failed reading %s: %s", path, exc)
        return default
    finally:
        lock.release()


def save_json(path: str, data: Any) -> None:
    """
    Thread-safe, atomic JSON write with backup + validation.

    Drop-in replacement for the old ``save_json(path, data)``.
    """
    lock = _acquire_lock(path)
    try:
        _validate(path, data)
        _backup(path)
        _atomic_write(path, data)
    finally:
        lock.release()


def read_modify_write(
    path: str,
    default: Any,
    modifier: Callable[[Any], Any],
) -> Any:
    """
    The **correct** pattern for concurrent JSON updates.

    Holds the lock for the entire read → modify → write cycle so no
    other process/thread can interleave.

    Parameters
    ----------
    path : str
        Path to the JSON file.
    default : Any
        Default value if the file does not exist.
    modifier : callable
        ``modifier(data) -> data``.  Receives the current contents,
        must return the new contents to be saved.

    Returns
    -------
    The value returned by *modifier* (i.e. the new state).

    Example
    -------
    ::
        def add_user(db):
            db["users"].append({"id": 123})
            return db

        read_modify_write(USERS_FILE, {"users": []}, add_user)
    """
    lock = _acquire_lock(path)
    try:
        # --- Read ---
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                data = json.loads(content) if content.strip() else default
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("read_modify_write: corrupt %s (%s), using default", path, exc)
                _backup(path)
                data = default
        else:
            data = default

        # --- Modify ---
        data = modifier(data)

        # --- Write ---
        _validate(path, data)
        _backup(path)
        _atomic_write(path, data)
        return data
    finally:
        lock.release()


# ─── Specialised helpers ─────────────────────────────────────
# These replace the most race-prone functions in bot_new.py.

def next_sequence(path: str, key: str = "last_order_seq") -> int:
    """
    Atomically increment a counter and return the new value.

    Replaces the dangerous non-locked read-then-write in
    ``next_order_id()``.
    """
    result: Dict[str, int] = {}

    def _inc(data):
        seq = int(data.get(key, 0)) + 1
        data[key] = seq
        result["seq"] = seq
        return data

    read_modify_write(path, {key: 0}, _inc)
    return result["seq"]


def append_record(path: str, collection_key: str, record: Dict[str, Any]) -> None:
    """
    Atomically append *record* to the list at ``data[collection_key]``.

    Replaces patterns like::
        db = load_json(path, {"orders": []})
        db["orders"].append(order)
        save_json(path, db)
    """
    def _append(data):
        data.setdefault(collection_key, []).append(record)
        return data

    default = _DEFAULTS.get(os.path.basename(path), {collection_key: []})
    read_modify_write(path, default, _append)


def upsert_record(
    path: str,
    collection_key: str,
    match_field: str,
    match_value: Any,
    record: Dict[str, Any],
) -> None:
    """
    Atomically insert-or-update a record inside a list.

    If an existing record has ``record[match_field] == match_value``,
    it is updated in place; otherwise *record* is appended.
    """
    def _upsert(data):
        items = data.setdefault(collection_key, [])
        existing = next(
            (r for r in items if r.get(match_field) == match_value), None
        )
        if existing is not None:
            existing.update(record)
        else:
            items.append(record)
        return data

    default = _DEFAULTS.get(os.path.basename(path), {collection_key: []})
    read_modify_write(path, default, _upsert)


def update_field(
    path: str,
    collection_key: str,
    match_field: str,
    match_value: Any,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Atomically update specific fields on a matched record.

    Returns the updated record, or None if not found.
    """
    result: Dict[str, Any] = {"found": None}

    def _update(data):
        for item in data.get(collection_key, []):
            if item.get(match_field) == match_value:
                item.update(updates)
                result["found"] = item
                break
        return data

    default = _DEFAULTS.get(os.path.basename(path), {collection_key: []})
    read_modify_write(path, default, _update)
    return result["found"]


# ─── Initialization ──────────────────────────────────────────

def ensure_data_files() -> None:
    """
    Ensure the data directory and all default JSON files exist.

    Safe replacement for the old ``ensure_data_files()`` in bot_new.py
    and bot.py.  Uses atomic writes so even initial creation is safe.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    file_defaults = {
        os.path.join(DATA_DIR, "users.json"):            {"users": []},
        os.path.join(DATA_DIR, "orders.json"):           {"orders": []},
        os.path.join(DATA_DIR, "reviews.json"):          {"reviews": []},
        os.path.join(DATA_DIR, "counters.json"):         {"last_order_seq": 0},
        os.path.join(DATA_DIR, "coupons.json"):          {
            "codes": {
                "SAVE10": {"type": "percent", "value": 10},
                "VIP20":  {"type": "percent", "value": 20},
            }
        },
        os.path.join(DATA_DIR, "referrals.json"):        {"referrals": {}, "uses": []},
        os.path.join(DATA_DIR, "content_calendar.json"): [],
    }

    for path, default in file_defaults.items():
        if not os.path.exists(path):
            _atomic_write(path, default)
            logger.info("Created default data file: %s", path)
