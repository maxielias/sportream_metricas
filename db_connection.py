import json
import psycopg2
import pandas as pd
import numpy as np
from typing import Optional
import urllib.parse

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
    load_dotenv(Path('.') / '.env')
except Exception:
    pass


def get_neondb_connection_using_keys(path: str = "neondb_keys.json") -> psycopg2.extensions.connection:
    """Load Neon DB credentials and connect using explicit PG* keys.

    This uses the exact mapping requested: `PGHOST`, `PGDATABASE`, `PGUSER`,
    `PGPASSWORD`, `PGSSLMODE`. A KeyError is raised if any required key
    is missing so the caller can fix their `neondb_keys.json`.
    """
    # Prefer environment variables first (suitable for local or CI),
    # then fall back to reading the local JSON file.
    if os.getenv("PGHOST"):
        keys = {
            'PGHOST': os.getenv('PGHOST'),
            'PGDATABASE': os.getenv('PGDATABASE'),
            'PGUSER': os.getenv('PGUSER'),
            'PGPASSWORD': os.getenv('PGPASSWORD'),
            'PGPORT': os.getenv('PGPORT'),
            'PGSSLMODE': os.getenv('PGSSLMODE'),
        }
    else:
        # last resort: try file directly to provide clearer error
        with open(path, "r", encoding="utf-8") as f:
            keys = json.load(f)

    # Use the exact keys as requested
    try:
        conn = psycopg2.connect(
            host=keys.get('PGHOST') or keys.get('host'),
            database=keys.get('PGDATABASE') or keys.get('database') or keys.get('dbname'),
            user=keys.get('PGUSER') or keys.get('user'),
            password=keys.get('PGPASSWORD') or keys.get('password'),
            sslmode=keys.get('PGSSLMODE') or keys.get('sslmode')
        )
    except KeyError as e:
        raise KeyError(f"Missing required key in {path}: {e}") from e
    return conn


def get_postgresdb_from_neon_keys(path: str = "neondb_keys.json") -> PostgresDB:
    """Return a configured `PostgresDB` instance built from Neon keys file."""
    # Prefer environment variables first; fall back to local file.
    if os.getenv("PGHOST"):
        keys = {
            'PGHOST': os.getenv('PGHOST'),
            'PGPORT': os.getenv('PGPORT'),
            'PGDATABASE': os.getenv('PGDATABASE'),
            'PGUSER': os.getenv('PGUSER'),
            'PGPASSWORD': os.getenv('PGPASSWORD'),
            'PGSSLMODE': os.getenv('PGSSLMODE'),
        }
    else:
        with open(path, "r", encoding="utf-8") as f:
            keys = json.load(f)
    # Prefer explicit PG* keys. Fall back to tolerant keys if needed.
    host = keys.get("PGHOST") or keys.get("host")
    port = int(keys.get("PGPORT") or keys.get("port") or 5432)
    dbname = keys.get("PGDATABASE") or keys.get("database") or keys.get("dbname")
    user = keys.get("PGUSER") or keys.get("user")
    password = keys.get("PGPASSWORD") or keys.get("password")
    sslmode = keys.get("PGSSLMODE") or keys.get("sslmode")

    db = PostgresDB(
        host=host or "localhost",
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )
    db.sslmode = sslmode
    return db