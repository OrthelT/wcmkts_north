from sqlalchemy import create_engine, text, select, NullPool
import streamlit as st
# os.environ.setdefault("RUST_LOG", "debug")
import libsql
from logging_config import setup_logging
import sqlite3 as sql
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models import UpdateLog
import threading
from contextlib import suppress, contextmanager


logger = setup_logging(__name__)

# Global lock to serialize sync operations within the process
_SYNC_LOCK = threading.Lock()


class RWLock:
    """Read-Write lock implementation.

    Allows multiple concurrent readers OR one exclusive writer.
    Writers wait for all readers to finish before acquiring.
    """
    def __init__(self):
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.Lock())
        self._write_ready = threading.Condition(threading.Lock())

    def acquire_read(self):
        """Acquire a read lock. Multiple readers can hold the lock simultaneously."""
        self._read_ready.acquire()
        try:
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
        finally:
            self._read_ready.release()

    def release_read(self):
        """Release a read lock."""
        self._read_ready.acquire()
        try:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()
        finally:
            self._read_ready.release()

    def acquire_write(self):
        """Acquire a write lock. Exclusive access - blocks all readers and writers."""
        self._write_ready.acquire()
        self._writers += 1
        self._write_ready.release()

        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        """Release a write lock."""
        self._writers -= 1
        self._read_ready.notify_all()
        self._read_ready.release()

    @contextmanager
    def read_lock(self):
        """Context manager for read lock."""
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write_lock(self):
        """Context manager for write lock."""
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()

class DatabaseConfig:

    wcdbmap = "wcmktnorth2" #master config variable for the database to use

    _db_paths = {
        "wcmktnorth2": "wcmktnorth2.db", #production database
        "sde": "sdelite.db",
        "build_cost": "buildcost.db",
        "wcmkt3": "wcmkt3.db" #testing db

    }

    _db_turso_urls = {
        "wcmktnorth2_turso": st.secrets.wcmktnorth2_turso.url,
        "sde_turso": st.secrets.sde_lite_turso.url,
        "build_cost_turso": st.secrets.buildcost_turso.url,
        "wcmkt3_turso": st.secrets.wcmkt3_turso.url,
    }

    _db_turso_auth_tokens = {
        "wcmktnorth2_turso": st.secrets.wcmktnorth2_turso.token,
        "sde_turso": st.secrets.sde_lite_turso.token,
        "build_cost_turso": st.secrets.buildcost_turso.token,
        "wcmkt3_turso": st.secrets.wcmkt3_turso.token,
    }

    # Shared handles per-alias to avoid multiple simultaneous connections to the same file
    _engines: dict[str, object] = {}
    _remote_engines: dict[str, object] = {}
    _libsql_connects: dict[str, object] = {}
    _libsql_sync_connects: dict[str, object] = {}
    _sqlite_local_connects: dict[str, object] = {}
    _local_locks: dict[str, RWLock] = {}  # Changed from RLock to RWLock
    _ro_engines: dict[str, object] = {}

    def __init__(self, alias: str, dialect: str = "sqlite+libsql"):
        if alias == "wcmkt":
            alias = self.wcdbmap
        elif alias == "wcmkt2" or alias == "wcmkt3":
            logger.warning(f"Alias {alias} is deprecated, using {self.wcdbmap} instead")
            alias = self.wcdbmap

        if alias not in self._db_paths:
            raise ValueError(f"Unknown database alias '{alias}'. "
                             f"Available: {list(self._db_paths.keys())}")
        self.alias = alias
        self.path = self._db_paths[alias]
        self.url = f"{dialect}:///{self.path}"
        self.turso_url = self._db_turso_urls[f"{self.alias}_turso"]
        self.token = self._db_turso_auth_tokens[f"{self.alias}_turso"]
        self._engine = None
        self._remote_engine = None
        self._libsql_connect = None
        self._libsql_sync_connect = None
        self._sqlite_local_connect = None
        self._ro_engine = None

    @property
    def engine(self):
        eng = DatabaseConfig._engines.get(self.alias)
        if eng is None:
            eng = create_engine(self.url)
            DatabaseConfig._engines[self.alias] = eng
        return eng

    @property
    def remote_engine(self):
        eng = DatabaseConfig._remote_engines.get(self.alias)
        if eng is None:
            turso_url = self._db_turso_urls[f"{self.alias}_turso"]
            auth_token = self._db_turso_auth_tokens[f"{self.alias}_turso"]
            eng = create_engine(
                f"sqlite+{turso_url}?secure=true",
                connect_args={"auth_token": auth_token},
            )
            DatabaseConfig._remote_engines[self.alias] = eng
        return eng

    @property
    def libsql_local_connect(self):
        conn = DatabaseConfig._libsql_connects.get(self.alias)
        if conn is None:
            conn = libsql.connect(self.path)
            DatabaseConfig._libsql_connects[self.alias] = conn
        return conn

    @property
    def libsql_sync_connect(self):
        conn = DatabaseConfig._libsql_sync_connects.get(self.alias)
        if conn is None:
            conn = libsql.connect(self.path, sync_url=self.turso_url, auth_token=self.token)
            DatabaseConfig._libsql_sync_connects[self.alias] = conn
        return conn

    @property
    def sqlite_local_connect(self):
        conn = DatabaseConfig._sqlite_local_connects.get(self.alias)
        if conn is None:
            conn = sql.connect(self.path)
            DatabaseConfig._sqlite_local_connects[self.alias] = conn
        return conn

    @property
    def ro_engine(self):
        """SQLAlchemy engine to the local file, read-only, no pooling."""
        eng = DatabaseConfig._ro_engines.get(self.alias)
        if eng is not None:
            return eng
        else:
        # URI form with read-only flags
            uri = f"sqlite+pysqlite:///file:{self.path}?mode=ro&uri=true"
            eng = create_engine(
                uri,
                poolclass=NullPool,                  # no long-lived pooled handles
                connect_args={"check_same_thread": False},
            )
            DatabaseConfig._ro_engines[self.alias] = eng
        return eng

    def _dispose_local_connections(self):
        """Dispose/close all local connections/engines to safely allow file operations.
        This helps prevent corruption during sync by ensuring no open handles.
        """
        # Dispose SQLAlchemy engine (local file) shared across instances
        eng = DatabaseConfig._engines.pop(self.alias, None)
        if eng is not None:
            with suppress(Exception):
                eng.dispose()

        # Close libsql direct connection if any
        conn = DatabaseConfig._libsql_connects.pop(self.alias, None)
        if conn is not None:
            with suppress(Exception):
                conn.close()

        # Close libsql sync connection if any (avoid reusing for sync)
        sconn = DatabaseConfig._libsql_sync_connects.pop(self.alias, None)
        if sconn is not None:
            with suppress(Exception):
                sconn.close()

        # Close raw sqlite3 connection if any
        sqlite_conn = DatabaseConfig._sqlite_local_connects.pop(self.alias, None)
        if sqlite_conn is not None:
            with suppress(Exception):
                sqlite_conn.close()

        # Close read-only engine if any
        ro_engine = DatabaseConfig._ro_engines.pop(self.alias, None)
        if ro_engine is not None:
            with suppress(Exception):
                ro_engine.dispose()

    def _get_local_lock(self) -> RWLock:
        """Get or create a read-write lock for this database alias."""
        lock = DatabaseConfig._local_locks.get(self.alias)
        if lock is None:
            lock = RWLock()
            DatabaseConfig._local_locks[self.alias] = lock
        return lock

    @contextmanager
    def local_access(self, write: bool = False):
        """Guard local DB access to avoid overlapping with sync.

        Args:
            write: If True, acquire exclusive write lock. If False, acquire shared read lock.
                   Multiple readers can access simultaneously, but writes are exclusive.
        """
        lock = self._get_local_lock()
        if write:
            with lock.write_lock():
                logger.debug(f"local_access() write lock acquired for {self.alias}")
                yield
        else:
            with lock.read_lock():
                logger.debug(f"local_access() read lock acquired for {self.alias}")
                yield

    def integrity_check(self) -> bool:
        """Run PRAGMA integrity_check on the local database.

        Returns True if the result is 'ok', False otherwise or on error.
        """
        try:
            # Use a short-lived connection
            with self.engine.connect() as conn:
                result = conn.execute(text("PRAGMA integrity_check")).fetchone()
                logger.debug(f"integrity_check() result: {result}")
            status = str(result[0]).lower() if result and result[0] is not None else ""
            logger.info(f"integrity_check() status: {status}")
            if not status:
                logger.error(f"integrity_check() status is None for {self.alias}")
                return False
            
            harmless = all("never used" in msg for msg in status)
            ok = status == "ok" or harmless
            if not ok:
                logger.warning(f"Integrity check found issues: {status}")
            return ok
            
        except Exception as e:
            logger.error(f"Integrity check error ({self.alias}): {e}")
            return False

    def sync(self):
        """Synchronize the local database with the remote Turso replica safely.

        Uses a write lock to block all access during sync, and disposes local
        connections to prevent corruption. Read-only engine is preserved for
        minimal disruption to concurrent reads after sync completes.
        """
        logger.info(f"current database info: {self.read_dbinfo()}")
        logger.info("-"*40)
        # Acquire write lock to block all access during sync
        lock = self._get_local_lock()
        with lock.write_lock():
            with _SYNC_LOCK:
                self._dispose_local_connections()
                logger.debug("Disposing local connections and syncing database…")
                conn = None
                try:
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    # Explicitly manage connection lifecycle; avoid relying on context manager
                    conn = libsql.connect(self.path, sync_url=self.turso_url, auth_token=self.token)
                    conn.sync()
                except Exception as e:
                    logger.error(f"Database sync failed: {e}")
                    raise
                finally:
                    if conn is not None:
                        with suppress(Exception):
                            conn.close()
                            logger.info("Connection closed")

                update_time = datetime.now(timezone.utc)
                logger.info(f"Database synced at {update_time} UTC")
                logger.info(f"new database info: {self.read_dbinfo()}")
                logger.info("-"*40)

                # Post-sync integrity validation
                ok = self.integrity_check()
                if not ok:
                    logger.error("Post-sync integrity check failed.")

                # For market DBs, also validate last_update parity if integrity ok
                if self.alias == "wcmktnorth2":
                    validation_test = self.validate_sync() if ok else False
                    st.session_state.sync_status = "Success" if validation_test else "Failed"
                    if st.session_state.sync_status == "Success":
                        st.toast("Database synced successfully", icon="✅")
                    else:
                        st.toast("Database sync failed", icon="❌")
                st.session_state.sync_check = False
                logger.debug(f"Write lock will be released for {self.alias}")

    def validate_sync(self, manual: bool = False)-> bool:
        alias = self.alias
        with self.remote_engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(last_update) FROM marketstats")).fetchone()
            remote_last_update = result[0]
            conn.close()
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(last_update) FROM marketstats")).fetchone()
            local_last_update = result[0]
            conn.close()
        
        logger.info("-"*40)
        logger.info(f"alias: {alias} validate_sync()")
        timestamp = datetime.now(timezone.utc)
        local_timestamp = datetime.now()
        logger.info(f"time: {local_timestamp.strftime('%Y-%m-%d %H:%M:%S')} (local); {timestamp.strftime('%Y-%m-%d %H:%M:%S')} (utc)")
        logger.info(f"remote_last_update: {remote_last_update}")
        logger.info(f"local_last_update: {local_last_update}")
        logger.info("-"*40)
        validation_test = remote_last_update == local_last_update
        if manual:
            return validation_test, remote_last_update, local_last_update
        logger.info(f"validation_test: {validation_test}")
        return validation_test

    def get_table_list(self, local_only: bool = True)-> list[tuple]:
        if local_only:
            engine = self.engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [table.name for table in tables if "sqlite" not in table.name]
                conn.close()
                return table_list
        else:
            engine = self.remote_engine
            with engine.connect() as conn:
                stmt = text("PRAGMA table_list")
                result = conn.execute(stmt)
                tables = result.fetchall()
                table_list = [table.name for table in tables if "sqlite" not in table.name]
                conn.close()
                return table_list

    def get_table_columns(self, table_name: str, local_only: bool = True, full_info: bool = False) -> list[dict]:
        """
        Get column information for a specific table.

        Args:
            table_name: Name of the table to inspect
            local_only: If True, use local database; if False, use remote database

        Returns:
            List of dictionaries containing column information
        """
        if local_only:
            engine = self.engine
        else:
            engine = self.remote_engine

        with engine.connect() as conn:
            # Use string formatting for PRAGMA since it doesn't support parameterized queries well
            stmt = text(f"PRAGMA table_info({table_name})")
            result = conn.execute(stmt)
            columns = result.fetchall()
            if full_info:
                column_info = []
                for col in columns:
                    column_info.append({
                    "cid": col.cid,
                    "name": col.name,
                    "type": col.type,
                    "notnull": col.notnull,
                    "dflt_value": col.dflt_value,
                    "pk": col.pk
                })
            else:
                column_info = [col.name for col in columns]
            conn.close()
            return column_info

    def get_most_recent_update(self, table_name: str, remote: bool = False)-> datetime:
        """
        Get the most recent update time for a specific table
        Args:
            table_name: str - The name of the table to get the most recent update time for
            remote: bool - If True, get the most recent update time from the remote database, if False, get the most recent update time from the local database

        Returns:
            The most recent update time for the table
        """
        engine = self.remote_engine if remote else self.engine
        session = Session(bind=engine)
        with session.begin():
            updates = select(UpdateLog.timestamp).where(UpdateLog.table_name == table_name).order_by(UpdateLog.timestamp.desc())
            result = session.execute(updates).fetchone()

            update_time = result[0] if result is not None else None
            update_time = update_time.replace(tzinfo=timezone.utc) if update_time is not None else None
        session.close()
        engine.dispose()
        return update_time

    def get_time_since_update(self, table_name: str = "marketstats", remote: bool = False):
        status = self.get_most_recent_update(table_name, remote=remote)
        now = datetime.now(timezone.utc)
        time_since = now - status
        logger.info(f"update_time: {status} utc")
        logger.info(f"time_since: {time_since}")
        return time_since if time_since is not None else None

    def read_dbinfo(self)-> dict:
        """
        Read database information from the local database
        """
        with open(f"{self.path}-info", "r") as f:
            data = f.read()
            return data

if __name__ == "__main__":
    pass
