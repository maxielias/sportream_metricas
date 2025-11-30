import json
import psycopg2
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import urllib.parse
import logging

class PostgresDB:
    def __init__(self, host="localhost", port=5432, dbname=None, user=None, password=None, connect_timeout=10):
        # sslmode: e.g. 'require' or 'disable' or 'prefer'
        self.sslmode = None
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.connect_timeout = connect_timeout
        self._engine = None
        self.conn = None

    @classmethod
    def from_config(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cls(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 5432),
            dbname=cfg.get("dbname"),
            user=cfg.get("user"),
            password=cfg.get("password"),
            connect_timeout=cfg.get("connect_timeout", 10),
        )

    def connect(self):
        if self.conn and getattr(self.conn, "closed", 1) == 0:
            return
        connect_kwargs = dict(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            connect_timeout=self.connect_timeout,
        )
        if getattr(self, "sslmode", None):
            connect_kwargs["sslmode"] = self.sslmode
        self.conn = psycopg2.connect(**connect_kwargs)
        self.conn.autocommit = False

    def close(self):
        if self.conn and getattr(self.conn, "closed", 1) == 0:
            try:
                self.conn.close()
            finally:
                self.conn = None
        # dispose sqlalchemy engine if created
        if getattr(self, "_engine", None) is not None:
            try:
                self._engine.dispose()
            except Exception:
                pass
            finally:
                self._engine = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.conn:
            return
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.close()

    def execute(self, query, params=None, fetchone=False, fetchall=False):
        """
        Execute a statement. Use fetchone or fetchall to return results as tuples.
        For SELECTs and to get a DataFrame, use to_dataframe().
        """
        self.connect()
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            # return affected rows by default
            return cur.rowcount

    def executemany(self, query, params_list):
        self.connect()
        with self.conn.cursor() as cur:
            cur.executemany(query, params_list)
            return cur.rowcount

    def to_dataframe(self, query, params=None):
        """
        Run a SELECT and return a pandas DataFrame.
        """
        self.connect()
        # Prefer using SQLAlchemy engine with pandas to avoid DBAPI2 warnings
        try:
            from sqlalchemy import create_engine

            user_quoted = urllib.parse.quote_plus(self.user) if self.user else ""
            pwd_quoted = urllib.parse.quote_plus(self.password) if self.password else ""
            host = self.host or "localhost"
            port = int(self.port or 5432)
            dbname = self.dbname or ""
            sslmode = getattr(self, "sslmode", None)

            uri = f"postgresql+psycopg2://{user_quoted}:{pwd_quoted}@{host}:{port}/{dbname}"
            if sslmode:
                uri = uri + f"?sslmode={sslmode}"

            if not getattr(self, "_engine", None):
                # create engine and cache it for reuse
                self._engine = create_engine(uri)

            return pd.read_sql_query(query, self._engine, params=params)
        except Exception:
            # fallback to direct DBAPI connection
            return pd.read_sql_query(query, self.conn, params=params)

    def is_connected(self):
        return bool(self.conn and getattr(self.conn, "closed", 1) == 0)


# Note: Prefer the explicit `get_neondb_connection_using_keys` below which
# requires the `PGHOST`/`PGDATABASE`/... keys. This keeps the API clear and
# avoids ambiguous config shapes.


import os

# Load .env for local development if present
from pathlib import Path
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def get_neondb_connection_using_keys(path: str = "neondb_keys.json", use_json: bool = False, env_path: str = ".env") -> psycopg2.extensions.connection:
    """Return a raw psycopg2 connection using env/.env or JSON fallback.

    This is a thin compatibility wrapper that uses `load_db_config()` so
    all config lookup logic is centralized (prefer `CONNECTION_URL`, then
    `PG*` env vars, then `neondb_keys.json`).
    """
    cfg = load_db_config(path, use_json=use_json, env_path=env_path)
    if cfg.get('CONNECTION_URL'):
        return psycopg2.connect(cfg['CONNECTION_URL'])

    # Build kwargs for psycopg2.connect
    conn_kwargs = dict(
        host=cfg.get('PGHOST') or cfg.get('host'),
        database=cfg.get('PGDATABASE') or cfg.get('database') or cfg.get('dbname'),
        user=cfg.get('PGUSER') or cfg.get('user'),
        password=cfg.get('PGPASSWORD') or cfg.get('password'),
        port=cfg.get('PGPORT') or cfg.get('port'),
    )
    # remove None values
    conn_kwargs = {k: v for k, v in conn_kwargs.items() if v is not None}
    return psycopg2.connect(**conn_kwargs)


def get_postgresdb_from_neon_keys(path: str = "neondb_keys.json", use_json: bool = False, env_path: str = ".env") -> PostgresDB:
    """Return a configured `PostgresDB` instance built from env/.json.

    Uses `load_db_config()` to centralize config loading; if a
    `CONNECTION_URL` exists it will be parsed for components, otherwise
    PG* env vars or the JSON file are used.
    """
    cfg = load_db_config(path, use_json=use_json, env_path=env_path)

    if cfg.get('CONNECTION_URL'):
        parsed = urllib.parse.urlparse(cfg['CONNECTION_URL'])
        dbname = parsed.path.lstrip('/') if parsed.path else None
        host = parsed.hostname
        port = parsed.port or 5432
        user = parsed.username
        password = parsed.password
        sslmode = None
    else:
        host = cfg.get('PGHOST') or cfg.get('host') or 'localhost'
        port = int(cfg.get('PGPORT') or cfg.get('port') or 5432)
        dbname = cfg.get('PGDATABASE') or cfg.get('database') or cfg.get('dbname')
        user = cfg.get('PGUSER') or cfg.get('user')
        password = cfg.get('PGPASSWORD') or cfg.get('password')
        sslmode = cfg.get('PGSSLMODE') or cfg.get('sslmode')

    db = PostgresDB(host=host, port=port, dbname=dbname, user=user, password=password)
    db.sslmode = sslmode
    return db


def load_db_config(path: str = "neondb_keys.json", use_json: bool = False, env_path: str = ".env") -> Dict[str, Any]:
    """Load DB configuration.

    Default preference: load variables from `.env` (via python-dotenv) then
    read `os.environ` (so .env values are respected). If `use_json=True`,
    the function will prefer the JSON file at `path` instead.

    Returns a dict with possible keys: CONNECTION_URL, PGHOST, PGPORT, PGDATABASE,
    PGUSER, PGPASSWORD, PGSSLMODE
    """
    cfg: Dict[str, Any] = {}

    # If dotenv available, load it to populate os.environ (do not error if missing)
    if load_dotenv is not None and env_path:
        try:
            load_dotenv(Path(env_path))
        except Exception:
            # non-fatal; proceed to read environment/JSON
            pass

    # If caller explicitly requests JSON, try that first
    if use_json:
        p = Path(path)
        if p.exists():
            try:
                with p.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                return {k: data.get(k) for k in data}
            except Exception as e:
                logging.warning('Failed to read %s: %s', path, e)
                # fall through to environment checks

    # Connection URL first from environment (which may have been populated by dotenv)
    conn_url = os.getenv('CONNECTION_URL') or os.getenv('CONN_URL')
    if conn_url:
        cfg['CONNECTION_URL'] = conn_url
        return cfg

    # Then explicit PG* env vars
    if os.getenv('PGHOST'):
        cfg.update(
            PGHOST=os.getenv('PGHOST'),
            PGPORT=os.getenv('PGPORT'),
            PGDATABASE=os.getenv('PGDATABASE'),
            PGUSER=os.getenv('PGUSER'),
            PGPASSWORD=os.getenv('PGPASSWORD'),
            PGSSLMODE=os.getenv('PGSSLMODE'),
        )
        return cfg

    # Final fallback: JSON file if present
    p = Path(path)
    if p.exists():
        try:
            with p.open('r', encoding='utf-8') as f:
                data = json.load(f)
            return {k: data.get(k) for k in data}
        except Exception as e:
            logging.warning('Failed to read %s: %s', path, e)
            return {}

    return {}


if __name__ == "__main__":
    # Quick runtime self-test. Does NOT print secrets; prints counts and sample ids.
    try:
        cfg = load_db_config()
        method = 'CONNECTION_URL' if cfg.get('CONNECTION_URL') else 'PG* env or JSON'
        print(f"Using config source: {method}")

        # Try high-level helper first (returns PostgresDB)
        db = get_postgresdb_from_neon_keys()
        with db:
            # count activity-details rows
            try:
                cnt = db.execute("SELECT count(*) FROM webhooks WHERE type = 'activity-details'", fetchone=True)
            except Exception:
                # If the table or privileges differ, surface a friendly message
                print("Could not run COUNT query against table 'webhooks'. Check schema and permissions.")
                raise
            print("activity-details rows:", cnt[0] if cnt else 0)

            # fetch last 3 ids
            try:
                rows = db.execute("SELECT id, created_at FROM webhooks WHERE type = 'activity-details' ORDER BY created_at DESC LIMIT 3", fetchall=True)
                if rows:
                    print("Last activity ids:")
                    for r in rows:
                        print(" -", r[0], "@", r[1])
                else:
                    print("No recent activity-details rows found.")
            except Exception:
                print("Could not fetch recent rows; query failed.")
    except Exception as e:
        print("Self-test failed:", str(e))