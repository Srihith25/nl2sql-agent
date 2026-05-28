"""Generate a small TPC-H DuckDB warehouse.

Default behaviour: try DuckDB's TPC-H extension at sf=0.01 (~10MB). If the
extension cannot be downloaded (offline machines, locked-down CI runners),
fall back to a small synthetic dataset with the same schema and column names.

Usage:
    python data/seed_tpch.py                  # try real, fall back to synthetic
    python data/seed_tpch.py --sf 0.1         # bigger real dataset (~100MB)
    python data/seed_tpch.py --synthetic      # force the synthetic mini dataset
"""
from __future__ import annotations

import argparse
import pathlib
import random
import sys
import time
from datetime import date, timedelta

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "warehouse.duckdb"


# ---------- Real TPC-H via extension ----------

def seed_real(db_path: pathlib.Path, sf: float) -> dict[str, int]:
    con = duckdb.connect(str(db_path))
    con.install_extension("tpch")
    con.load_extension("tpch")
    con.execute(f"CALL dbgen(sf = {sf})")
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    con.close()
    return counts


# ---------- Synthetic fallback ----------

def seed_synthetic(db_path: pathlib.Path, seed: int = 42) -> dict[str, int]:
    """Build a small synthetic TPC-H-shaped warehouse.

    Volumes (~1 MB total):
      region 5  ·  nation 25  ·  supplier 100  ·  customer 1500
      part 200  ·  partsupp 800  ·  orders 1500  ·  lineitem ~6000
    """
    rng = random.Random(seed)
    con = duckdb.connect(str(db_path))

    # ----- Static reference tables -----
    con.execute("""
        CREATE TABLE region(r_regionkey INTEGER, r_name VARCHAR, r_comment VARCHAR);
        INSERT INTO region VALUES
          (0,'AFRICA','lar deposits'),
          (1,'AMERICA','hs use ironic'),
          (2,'ASIA','ges. thinly even'),
          (3,'EUROPE','ly final courts'),
          (4,'MIDDLE EAST','uickly special accounts');

        CREATE TABLE nation(n_nationkey INTEGER, n_name VARCHAR, n_regionkey INTEGER, n_comment VARCHAR);
        INSERT INTO nation VALUES
          (0,'ALGERIA',0,''), (1,'ARGENTINA',1,''), (2,'BRAZIL',1,''),
          (3,'CANADA',1,''),  (4,'EGYPT',4,''),     (5,'ETHIOPIA',0,''),
          (6,'FRANCE',3,''),  (7,'GERMANY',3,''),   (8,'INDIA',2,''),
          (9,'INDONESIA',2,''), (10,'IRAN',4,''),   (11,'IRAQ',4,''),
          (12,'JAPAN',2,''),  (13,'JORDAN',4,''),   (14,'KENYA',0,''),
          (15,'MOROCCO',0,''),(16,'MOZAMBIQUE',0,''),
          (17,'PERU',1,''),   (18,'CHINA',2,''),    (19,'ROMANIA',3,''),
          (20,'SAUDI ARABIA',4,''),(21,'VIETNAM',2,''),
          (22,'RUSSIA',3,''), (23,'UNITED KINGDOM',3,''),(24,'UNITED STATES',1,'');
    """)

    # ----- Supplier -----
    con.execute(
        "CREATE TABLE supplier(s_suppkey INTEGER, s_name VARCHAR, s_address VARCHAR, "
        "s_nationkey INTEGER, s_phone VARCHAR, s_acctbal DOUBLE, s_comment VARCHAR)"
    )
    suppliers = [
        (i, f"Supplier#{i:09d}", f"addr-{i}", rng.randrange(25),
         f"{rng.randrange(10,99)}-{rng.randrange(100,999)}-{rng.randrange(1000,9999)}",
         round(rng.uniform(-1000, 9000), 2), "")
        for i in range(1, 101)
    ]
    con.executemany("INSERT INTO supplier VALUES (?,?,?,?,?,?,?)", suppliers)

    # ----- Customer -----
    segments = ["BUILDING", "AUTOMOBILE", "MACHINERY", "HOUSEHOLD", "FURNITURE"]
    con.execute(
        "CREATE TABLE customer(c_custkey INTEGER, c_name VARCHAR, c_address VARCHAR, "
        "c_nationkey INTEGER, c_phone VARCHAR, c_acctbal DOUBLE, c_mktsegment VARCHAR, c_comment VARCHAR)"
    )
    customers = [
        (i, f"Customer#{i:09d}", f"addr-{i}", rng.randrange(25),
         f"{rng.randrange(10,99)}-{rng.randrange(100,999)}-{rng.randrange(1000,9999)}",
         round(rng.uniform(-1000, 9000), 2), rng.choice(segments), "")
        for i in range(1, 1501)
    ]
    con.executemany("INSERT INTO customer VALUES (?,?,?,?,?,?,?,?)", customers)

    # ----- Part -----
    brands = [f"Brand#{i:02d}" for i in range(11, 56)]
    types = ["STANDARD", "ECONOMY", "PROMO", "LARGE", "MEDIUM", "SMALL"]
    mfgrs = [f"Manufacturer#{i}" for i in range(1, 6)]
    con.execute(
        "CREATE TABLE part(p_partkey INTEGER, p_name VARCHAR, p_mfgr VARCHAR, "
        "p_brand VARCHAR, p_type VARCHAR, p_size INTEGER, p_container VARCHAR, "
        "p_retailprice DOUBLE, p_comment VARCHAR)"
    )
    parts = [
        (i, f"part-{i}", rng.choice(mfgrs), rng.choice(brands), rng.choice(types),
         rng.randrange(1, 50), rng.choice(["SM BOX", "LG BOX", "JUMBO PKG", "WRAP CAN"]),
         round(rng.uniform(900, 1100), 2), "")
        for i in range(1, 201)
    ]
    con.executemany("INSERT INTO part VALUES (?,?,?,?,?,?,?,?,?)", parts)

    # ----- PartSupp -----
    con.execute(
        "CREATE TABLE partsupp(ps_partkey INTEGER, ps_suppkey INTEGER, "
        "ps_availqty INTEGER, ps_supplycost DOUBLE, ps_comment VARCHAR)"
    )
    partsupp = []
    for p in range(1, 201):
        for _ in range(4):  # 4 suppliers per part
            partsupp.append((p, rng.randrange(1, 101), rng.randrange(1, 10000),
                             round(rng.uniform(100, 1000), 2), ""))
    con.executemany("INSERT INTO partsupp VALUES (?,?,?,?,?)", partsupp)

    # ----- Orders -----
    statuses = ["F", "O", "P"]
    priorities = ["1-URGENT", "2-HIGH", "3-MEDIUM", "4-NOT SPECIFIED", "5-LOW"]
    con.execute(
        "CREATE TABLE orders(o_orderkey INTEGER, o_custkey INTEGER, o_orderstatus VARCHAR, "
        "o_totalprice DOUBLE, o_orderdate DATE, o_orderpriority VARCHAR, "
        "o_clerk VARCHAR, o_shippriority INTEGER, o_comment VARCHAR)"
    )
    start = date(1992, 1, 1)
    orders = []
    for i in range(1, 1501):
        days = rng.randrange(0, 365 * 7)  # 1992 → 1998
        orders.append((i, rng.randrange(1, 1501), rng.choice(statuses),
                       round(rng.uniform(800, 350000), 2), start + timedelta(days=days),
                       rng.choice(priorities), f"Clerk#{rng.randrange(1, 100):09d}", 0, ""))
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders)

    # ----- LineItem -----
    shipmodes = ["AIR", "TRUCK", "SHIP", "RAIL", "MAIL", "REG AIR", "FOB"]
    returnflags = ["N", "R", "A"]
    linestatuses = ["O", "F"]
    con.execute(
        "CREATE TABLE lineitem("
        "l_orderkey INTEGER, l_partkey INTEGER, l_suppkey INTEGER, l_linenumber INTEGER, "
        "l_quantity INTEGER, l_extendedprice DOUBLE, l_discount DOUBLE, l_tax DOUBLE, "
        "l_returnflag VARCHAR, l_linestatus VARCHAR, "
        "l_shipdate DATE, l_commitdate DATE, l_receiptdate DATE, "
        "l_shipinstruct VARCHAR, l_shipmode VARCHAR, l_comment VARCHAR)"
    )
    lineitems = []
    for order_row in orders:
        o_key = order_row[0]
        o_date = order_row[4]
        n_lines = rng.randrange(1, 7)
        for ln in range(1, n_lines + 1):
            qty = rng.randrange(1, 51)
            price = round(qty * rng.uniform(900, 1100), 2)
            disc = round(rng.uniform(0, 0.1), 2)
            ship = o_date + timedelta(days=rng.randrange(1, 120))
            lineitems.append((
                o_key, rng.randrange(1, 201), rng.randrange(1, 101), ln,
                qty, price, disc, round(rng.uniform(0, 0.08), 2),
                rng.choice(returnflags), rng.choice(linestatuses),
                ship, ship + timedelta(days=rng.randrange(1, 30)), ship + timedelta(days=rng.randrange(1, 30)),
                "DELIVER IN PERSON", rng.choice(shipmodes), ""
            ))
    con.executemany(
        "INSERT INTO lineitem VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        lineitems,
    )

    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    con.close()
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--sf", type=float, default=0.01)
    ap.add_argument("--synthetic", action="store_true",
                    help="Skip the TPC-H extension and use the built-in mini dataset.")
    args = ap.parse_args()

    db_path = pathlib.Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        print(f"[seed] removing existing {db_path}")
        db_path.unlink()

    t0 = time.time()
    counts: dict[str, int] = {}
    if not args.synthetic:
        print(f"[seed] attempting real TPC-H at sf={args.sf}")
        try:
            counts = seed_real(db_path, args.sf)
        except Exception as e:  # noqa: BLE001
            print(f"[seed] real TPC-H unavailable ({type(e).__name__}: {e}); falling back to synthetic.")
            if db_path.exists():
                db_path.unlink()

    if not counts:
        print("[seed] building synthetic mini-TPC-H")
        counts = seed_synthetic(db_path)

    print(f"[seed] done in {time.time()-t0:.1f}s. tables: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
