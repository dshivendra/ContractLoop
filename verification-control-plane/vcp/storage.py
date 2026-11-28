"""SQLite append-only API with hash chain. DB administrator remains trusted."""
import json
import sqlite3
from pathlib import Path
from .security import canonical, digest


class Ledger:
    def __init__(self, path, *, read_only=False):
        self.read_only = read_only
        if read_only:
            self.db = sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True,timeout=5)
            return
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS ledger (
          seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, identity TEXT NOT NULL,
          payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL,
          UNIQUE(kind, identity));
        CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON ledger
          BEGIN SELECT RAISE(ABORT, 'append-only'); END;
        CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON ledger
          BEGIN SELECT RAISE(ABORT, 'append-only'); END;
        """)

    def close(self):
        self.db.close()

    def append(self, kind, identity, payload):
        if self.read_only:
            raise PermissionError("read-only ledger")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            hashed = self.append_in_transaction(kind,identity,payload)
            self.db.execute("COMMIT")
            return hashed
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def append_in_transaction(self,kind,identity,payload):
        """Append using an already-open effects transaction; no independent commit."""
        if self.read_only:raise PermissionError("read-only ledger")
        if not self.db.in_transaction:raise RuntimeError("active transaction required")
        encoded=canonical(payload)
        old=self.db.execute("SELECT payload,hash FROM ledger WHERE kind=? AND identity=?",(kind,identity)).fetchone()
        if old:
            if old[0]!=encoded:raise ValueError("immutable identity collision")
            return old[1]
        last=self.db.execute("SELECT seq,hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        seq,previous=(last[0]+1,last[1]) if last else (1,"0"*64)
        hashed=digest(dict(seq=seq,kind=kind,identity=identity,payload=json.loads(encoded),previous_hash=previous))
        self.db.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?)",(seq,kind,identity,encoded,previous,hashed))
        return hashed

    def records(self):
        return [dict(seq=r[0],kind=r[1],identity=r[2],payload=json.loads(r[3]),previous_hash=r[4],hash=r[5])
                for r in self.db.execute("SELECT * FROM ledger ORDER BY seq")]

    def check(self):
        previous = "0"*64
        for seq, record in enumerate(self.records(), 1):
            if record["seq"] != seq or record["previous_hash"] != previous:
                raise ValueError("broken audit sequence")
            body = {k:v for k,v in record.items() if k != "hash"}
            if digest(body) != record["hash"]:
                raise ValueError("audit hash mismatch")
            previous = record["hash"]
        return previous


class ContractRepository:
    def __init__(self, ledger):
        self.ledger = ledger

    def put(self, contract, approval, policy, now):
        from .security import approved
        if not approved(contract, approval, policy, now):
            raise PermissionError("invalid approval")
        identity = canonical([contract.tenant,contract.id,contract.version])
        # First approval binds this version permanently, including approval time.
        self.ledger.append("contract",identity,dict(contract=contract.model_dump(mode="json"),approval=approval.model_dump(mode="json")))
