"""Transactional, immutable SQLite records. Audit events commit with their records."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import local


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, allow_nan=False, sort_keys=True)


class Store:
    def __init__(self, path):
        self.path = str(path)
        self._local = local()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS samples(id TEXT PRIMARY KEY, description TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS lots(id TEXT PRIMARY KEY, reagent TEXT NOT NULL, expires_on TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS plates(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                lot_id TEXT NOT NULL REFERENCES lots(id), unit TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS wells(plate_id INTEGER NOT NULL REFERENCES plates(id), well TEXT NOT NULL,
                role TEXT NOT NULL, sample_id TEXT REFERENCES samples(id), concentration REAL,
                dilution_factor REAL NOT NULL, PRIMARY KEY(plate_id,well));
            CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY, plate_id INTEGER NOT NULL REFERENCES plates(id),
                name TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL, signals TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(plate_id,sha256));
            CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id),
                model TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS protocols(id INTEGER PRIMARY KEY, plate_id INTEGER NOT NULL REFERENCES plates(id),
                kind TEXT NOT NULL, request TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL,
                action TEXT NOT NULL, entity TEXT NOT NULL, detail TEXT NOT NULL);
            """)
            for table in ["samples", "lots", "plates", "wells", "imports", "analyses", "protocols", "audit"]:
                for action in ["UPDATE", "DELETE"]:
                    db.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action}
                        BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only records'); END""")

            conflicts = {
                "samples": "id=NEW.id",
                "lots": "id=NEW.id",
                "plates": "id=NEW.id OR name=NEW.name",
                "wells": "plate_id=NEW.plate_id AND well=NEW.well",
                "imports": "id=NEW.id OR (plate_id=NEW.plate_id AND sha256=NEW.sha256)",
                "analyses": "id=NEW.id",
                "protocols": "id=NEW.id",
                "audit": "id=NEW.id",
            }
            # REPLACE performs implicit deletion without delete triggers on ordinary
            # SQLite connections. Reject conflicting inserts before that can happen.
            for table, condition in conflicts.items():
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS no_replace_{table}
                    BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition})
                    BEGIN SELECT RAISE(ABORT,'append-only records: conflicting insert'); END""")

    @contextmanager
    def connection(self):
        active = getattr(self._local, "db", None)
        if active is not None:
            yield active
            return
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        """Share one transaction across related store operations on this thread."""
        with self.connection() as db:
            if getattr(self._local, "db", None) is not None:
                raise RuntimeError("Nested explicit transactions are not supported")
            db.execute("BEGIN IMMEDIATE")
            self._local.db = db
            try:
                yield
            finally:
                self._local.db = None

    def audit(self, db, actor, action, entity, detail):
        db.execute(
            "INSERT INTO audit(at,actor,action,entity,detail) VALUES(?,?,?,?,?)",
            (now(), actor, action, str(entity), encode(detail)),
        )

    def list_records(self, table):
        if table not in ["samples", "lots", "plates", "audit"]:
            raise ValueError("Unsupported record type")
        with self.connection() as db:
            rows = [dict(r) for r in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        if table == "audit":
            for row in rows:
                row["detail"] = json.loads(row["detail"])
        return rows

    def create_sample(self, data, actor):
        with self.connection() as db:
            db.execute("INSERT INTO samples(id,description) VALUES(?,?)", (data["id"], data["description"]))
            self.audit(db, actor, "sample.register", data["id"], data)
        return data

    def create_lot(self, data, actor):
        with self.connection() as db:
            db.execute(
                "INSERT INTO lots(id,reagent,expires_on) VALUES(?,?,?)",
                (data["id"], data["reagent"], data["expires_on"]),
            )
            self.audit(db, actor, "lot.register", data["id"], data)
        return data

    def create_plate(self, data, actor):
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM lots WHERE id=?", (data["lot_id"],)).fetchone():
                raise ValueError("Register the reagent lot before creating a plate")
            for well in data["wells"]:
                if (
                    well.get("sample_id")
                    and not db.execute("SELECT 1 FROM samples WHERE id=?", (well["sample_id"],)).fetchone()
                ):
                    raise ValueError(f"Register sample {well['sample_id']} before assigning it")
            plate_id = db.execute(
                "INSERT INTO plates(name,lot_id,unit,created_at) VALUES(?,?,?,?)",
                (data["name"], data["lot_id"], data["unit"], now()),
            ).lastrowid
            for well in data["wells"]:
                db.execute(
                    "INSERT INTO wells(plate_id,well,role,sample_id,concentration,dilution_factor) VALUES(?,?,?,?,?,?)",
                    (
                        plate_id,
                        well["well"],
                        well["role"],
                        well.get("sample_id"),
                        well.get("concentration"),
                        well.get("dilution_factor", 1),
                    ),
                )
            self.audit(db, actor, "plate.create", plate_id, data)
        return self.get_plate(plate_id)

    def get_plate(self, plate_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM plates WHERE id=?", (plate_id,)).fetchone()
            if row is None:
                raise KeyError("Plate not found")
            data = dict(row)
            data["lot"] = dict(db.execute("SELECT * FROM lots WHERE id=?", (data["lot_id"],)).fetchone())
            data["wells"] = [
                {k: v for k, v in dict(r).items() if k != "plate_id" and v is not None}
                for r in db.execute("SELECT * FROM wells WHERE plate_id=? ORDER BY well", (plate_id,))
            ]
            data["imports"] = [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,sha256,created_at FROM imports WHERE plate_id=? ORDER BY id", (plate_id,)
                )
            ]
            data["analyses"] = [
                dict(r)
                for r in db.execute(
                    """SELECT a.id,a.import_id,a.model,a.created_at
                FROM analyses a JOIN imports i ON a.import_id=i.id WHERE i.plate_id=? ORDER BY a.id""",
                    (plate_id,),
                )
            ]
        return data

    def add_import(self, plate_id, name, content, signals, actor):
        plate = self.get_plate(plate_id)
        if set(signals) != {w["well"] for w in plate["wells"]}:
            raise ValueError(
                "Imported wells must exactly match the saved plate map; use a partial long export for a partial map"
            )
        digest = hashlib.sha256(content).hexdigest()
        with self.connection() as db:
            import_id = db.execute(
                "INSERT INTO imports(plate_id,name,sha256,content,signals,created_at) VALUES(?,?,?,?,?,?)",
                (plate_id, Path(name).name, digest, content, encode(signals), now()),
            ).lastrowid
            self.audit(
                db,
                actor,
                "reader.import",
                import_id,
                dict(plate_id=plate_id, sha256=digest, wells=len(signals)),
            )
        return dict(id=import_id, sha256=digest)

    def get_import(self, import_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM imports WHERE id=?", (import_id,)).fetchone()
        if row is None:
            raise KeyError("Import not found")
        data = dict(row)
        data["signals"] = json.loads(data["signals"])
        return data

    def save_analysis(self, import_id, model, result, actor):
        with self.connection() as db:
            analysis_id = db.execute(
                "INSERT INTO analyses(import_id,model,result,created_at) VALUES(?,?,?,?)",
                (import_id, model, encode(result), now()),
            ).lastrowid
            self.audit(
                db,
                actor,
                "assay.analyse",
                analysis_id,
                dict(import_id=import_id, model=model, version=result["version"], passed=result["passed"]),
            )
        return self.get_analysis(analysis_id)

    def get_analysis(self, analysis_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if row is None:
            raise KeyError("Analysis not found")
        data = dict(row)
        data["result"] = json.loads(data["result"])
        return data

    def save_protocol(self, plate_id, kind, request, source, actor):
        self.get_plate(plate_id)
        with self.connection() as db:
            protocol_id = db.execute(
                "INSERT INTO protocols(plate_id,kind,request,source,created_at) VALUES(?,?,?,?,?)",
                (plate_id, kind, encode(request), source, now()),
            ).lastrowid
            self.audit(
                db,
                actor,
                "protocol.generate",
                protocol_id,
                dict(
                    plate_id=plate_id,
                    kind=kind,
                    request=request,
                    sha256=hashlib.sha256(source.encode()).hexdigest(),
                ),
            )
        return dict(id=protocol_id, source=source)

    def get_protocol(self, protocol_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM protocols WHERE id=?", (protocol_id,)).fetchone()
        if row is None:
            raise KeyError("Protocol not found")
        return dict(row)
