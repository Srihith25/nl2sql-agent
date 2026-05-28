"""Shared pytest fixtures.

We build a tiny DuckDB once per session — small enough that even slow runners
finish in <2s. Tests use this DB; no real LLM calls happen anywhere.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

# Force the hash embedder + mock LLM before any app module loads config.
os.environ.setdefault("EMBEDDER", "hash")
os.environ.setdefault("LLM_PROVIDER", "mock")

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def tmp_root(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("nl2sql")


@pytest.fixture(scope="session")
def db_path(tmp_root: Path) -> str:
    path = tmp_root / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE region(r_regionkey INTEGER, r_name TEXT);
        INSERT INTO region VALUES (0, 'AFRICA'), (1, 'AMERICA'), (2, 'ASIA'), (3, 'EUROPE');
        CREATE TABLE nation(n_nationkey INTEGER, n_name TEXT, n_regionkey INTEGER);
        INSERT INTO nation VALUES
          (0, 'ALGERIA', 0), (1, 'ARGENTINA', 1),
          (6, 'FRANCE', 3),  (7, 'GERMANY', 3),
          (24, 'UNITED STATES', 1);
        CREATE TABLE customer(c_custkey INTEGER, c_name TEXT, c_nationkey INTEGER, c_mktsegment TEXT);
        INSERT INTO customer VALUES
          (1, 'Customer#1', 6, 'BUILDING'),
          (2, 'Customer#2', 7, 'AUTOMOBILE'),
          (3, 'Customer#3', 24, 'BUILDING'),
          (4, 'Customer#4', 24, 'MACHINERY');
        CREATE TABLE orders(o_orderkey INTEGER, o_custkey INTEGER, o_totalprice DOUBLE, o_orderdate DATE, o_orderstatus TEXT);
        INSERT INTO orders VALUES
          (1, 1, 100.0, DATE '1995-02-01', 'F'),
          (2, 2, 250.0, DATE '1995-06-15', 'O'),
          (3, 3, 500.0, DATE '1995-09-10', 'F'),
          (4, 4, 175.0, DATE '1996-01-22', 'O');
        CREATE TABLE lineitem(
          l_orderkey INTEGER, l_partkey INTEGER, l_suppkey INTEGER,
          l_extendedprice DOUBLE, l_discount DOUBLE, l_quantity INTEGER,
          l_shipmode TEXT, l_returnflag TEXT
        );
        INSERT INTO lineitem VALUES
          (1, 1, 1, 100.0, 0.0, 5, 'AIR',  'N'),
          (2, 2, 1, 250.0, 0.1, 7, 'SHIP', 'R'),
          (3, 3, 2, 500.0, 0.0, 9, 'AIR',  'N'),
          (4, 1, 2, 175.0, 0.0, 4, 'RAIL', 'N');
    """)
    con.close()
    return str(path)


@pytest.fixture(scope="session")
def vector_db_path(tmp_root: Path, db_path: str) -> str:
    """Build a vector index over the test warehouse."""
    from app.embed import HashEmbedder
    from app.retriever import build_index

    path = tmp_root / "vectors.duckdb"
    build_index(
        db_path=db_path,
        vector_db_path=str(path),
        embedder=HashEmbedder(),
    )
    return str(path)


@pytest.fixture
def retriever(vector_db_path: str):
    from app.embed import HashEmbedder
    from app.retriever import Retriever

    return Retriever(vector_db_path=vector_db_path, embedder=HashEmbedder())
