import json, sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .settings import DATABASE_URL

@contextmanager
def connect():
    if DATABASE_URL.startswith('sqlite:///'):
        db=sqlite3.connect(DATABASE_URL.removeprefix('sqlite:///'),timeout=30)
        db.row_factory=sqlite3.Row
    else:
        import psycopg
        from psycopg.rows import dict_row
        db=psycopg.connect(DATABASE_URL.replace('postgresql+psycopg://','postgresql://'),row_factory=dict_row)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback(); raise
    finally: db.close()

def query(db,sql,args=()):
    return db.execute(sql if DATABASE_URL.startswith('sqlite') else sql.replace('?','%s'),args)

def initialize():
    with connect() as db:
        for ddl in [
          'CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)',
          'CREATE TABLE IF NOT EXISTS districts (id TEXT PRIMARY KEY, name TEXT NOT NULL, division TEXT NOT NULL, lat DOUBLE PRECISION NOT NULL, lon DOUBLE PRECISION NOT NULL, aez TEXT, wilting_point DOUBLE PRECISION, field_capacity DOUBLE PRECISION, estimate_method TEXT NOT NULL)',
          'CREATE TABLE IF NOT EXISTS observations (district_id TEXT NOT NULL REFERENCES districts(id), day TEXT NOT NULL, source TEXT NOT NULL, source_timestamp TEXT NOT NULL, ingested_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(district_id,day,source))',
          'CREATE TABLE IF NOT EXISTS ingestion_runs (source TEXT NOT NULL, finished_at TEXT NOT NULL, success INTEGER NOT NULL, message TEXT NOT NULL)',
          'CREATE INDEX IF NOT EXISTS observations_lookup ON observations(district_id,source,day)']:
            query(db,ddl)
        query(db,'INSERT INTO schema_version(version) VALUES (1) ON CONFLICT(version) DO NOTHING')

def get_district(db,key):
    r=query(db,'SELECT * FROM districts WHERE id=?',(key,)).fetchone()
    return dict(r) if r else None

def observations(db,district,start='0000-01-01',end='9999-12-31',sources=('power','imerg','smap')):
    placeholders=','.join('?' for _ in sources)
    rows=query(db,f'SELECT * FROM observations WHERE district_id=? AND day>=? AND day<=? AND source IN ({placeholders}) ORDER BY day',
               (district,start,end,*sources)).fetchall()
    return [{**dict(r),'values':json.loads(r['payload'])} for r in rows]

def upsert(db,district,day,source,values,timestamp):
    query(db,'INSERT INTO observations(district_id,day,source,source_timestamp,ingested_at,payload) VALUES (?,?,?,?,?,?) ON CONFLICT(district_id,day,source) DO UPDATE SET source_timestamp=excluded.source_timestamp, ingested_at=excluded.ingested_at, payload=excluded.payload',
          (district,day.isoformat(),source,timestamp.isoformat(),datetime.now(timezone.utc).isoformat(),json.dumps(values,allow_nan=False)))

def record_run(source,success,message):
    with connect() as db:
        query(db,'INSERT INTO ingestion_runs VALUES (?,?,?,?)',(source,datetime.now(timezone.utc).isoformat(),int(success),message))
