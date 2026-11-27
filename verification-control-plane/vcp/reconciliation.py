"""Read-only collector over synthetic authoritative SQLite fixture state.

No executor report is an input. No actual financial records or services used.
"""
import sqlite3
from pathlib import Path
from .models import Binding, Compare, Condition, Contract, Run
from .security import CollectorTrust, TrustPolicy, digest, seal_evidence

FACTS = ("source_complete","unique_ids","no_duplicates","amount_conserved",
         "matching_correct","unmatched_classified","destination_correct","authorized")
NOW = 1_800_000_000
SOURCE_ROWS = (("T1",10000,"INR","CMS-A"),("T2",2500,"INR","CMS-B"),("T3",700,"INR","CMS-C"))


def synthetic_policy():
    # Public fixture-only keys. Never use these in another environment.
    return TrustPolicy("synthetic-policy/1","demo","fixture-owner",b"PUBLIC-fixture-approval-key",
                       (CollectorTrust("demo","fixture-ledger","independent-reader","sqlite-snapshot",FACTS,
                                       b"PUBLIC-fixture-collector-key"),),
                       ("Trusted local Python, SQLite, adapter and fixture author",
                        "Executor cannot write collector keys, approved contract or audit database",
                        "Synthetic snapshot is authoritative only for this experiment"))


def reference_contract(policy=None):
    policy = policy or synthetic_policy()
    return Contract(id="cash-reconciliation",version=1,tenant="demo",owner="fixture-owner",approver=policy.approver,
                    objective="Reconcile the synthetic INR batch exactly",acceptance_rationale="Complete, conserved and correctly classified cash batch",
                    resource="fixture-batch/1",baseline_reference="sha256:"+digest(SOURCE_ROWS),intent_alignment_reference="HANDOFF.md:Phase1",
                    assumptions=("All amounts are integer INR minor units",),
                    limitations=("Point-in-time snapshot only; no real external effects",),trust_policy_hash=policy.fingerprint,
                    conditions=tuple(Condition(id=f,role="authorization" if f == "authorized" else "success",
                                               expression=Compare(fact=f,expected=True)) for f in FACTS),
                    bindings=tuple(Binding(fact=f,source="fixture-ledger",collector="independent-reader",method="sqlite-snapshot") for f in FACTS))


def create_fixture(path, variant="correct"):
    path = Path(path)
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE meta (state_version TEXT, resource TEXT, authorized INTEGER);
    CREATE TABLE source (id TEXT, amount_minor INTEGER, currency TEXT, expected_account TEXT);
    CREATE TABLE bank (id TEXT, amount_minor INTEGER, currency TEXT);
    CREATE TABLE destination (id TEXT, amount_minor INTEGER, currency TEXT, account TEXT, status TEXT);
    CREATE TABLE manifest (source_count INTEGER);
    INSERT INTO meta VALUES ('state/1','fixture-batch/1',1);
    INSERT INTO manifest VALUES (3);
    INSERT INTO source VALUES ('T1',10000,'INR','CMS-A'),('T2',2500,'INR','CMS-B'),('T3',700,'INR','CMS-C');
    INSERT INTO bank VALUES ('T1',10000,'INR'),('T2',2500,'INR');
    INSERT INTO destination VALUES ('T1',10000,'INR','CMS-A','matched'),('T2',2500,'INR','CMS-B','matched'),('T3',700,'INR','CMS-C','unmatched');
    """)
    mutations = {"partial":"DELETE FROM destination WHERE id='T2'",
                 "false_success":"UPDATE destination SET amount_minor=1 WHERE id='T1'",
                 "duplicate":"INSERT INTO destination SELECT * FROM destination WHERE id='T1'",
                 "source_missing":"DELETE FROM source WHERE id='T3'",
                 "wrong_match":"UPDATE destination SET status='matched' WHERE id='T3'",
                 "wrong_destination":"UPDATE destination SET account='CMS-WRONG' WHERE id='T2'",
                 "wrong_currency":"UPDATE destination SET currency='USD' WHERE id='T1'",
                 "unauthorized":"UPDATE meta SET authorized=0",
                 "extra_bank":"INSERT INTO bank VALUES ('BANK-ONLY',900,'INR')"}
    if variant in mutations:
        db.execute(mutations[variant])
    elif variant != "correct":
        db.close()
        raise ValueError("unknown fixture variant")
    db.commit()
    db.close()


def read_snapshot(path):
    # URI mode=ro prevents accidental fixture writes by the collector.
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN")
        def rows(table):
            return tuple(tuple(row) for row in db.execute("SELECT * FROM " + table + " ORDER BY rowid"))
        snapshot = {t:rows(t) for t in ("meta","manifest","source","bank","destination")}
        db.rollback()
        return snapshot
    finally:
        db.close()


def observation_facts(snapshot,baseline_reference):
    source,bank,dest = snapshot["source"],snapshot["bank"],snapshot["destination"]
    if len(snapshot["meta"]) != 1 or len(snapshot["manifest"]) != 1:
        raise ValueError("malformed fixture metadata")
    if any(type(r[1]) is not int or type(r[2]) is not str or not r[2].strip() for r in (*source,*bank,*dest)):
        raise ValueError("amounts must be integer minor units with explicit nonempty currency")
    ids = lambda rows: [r[0] for r in rows]
    source_ids,bank_ids,dest_ids = ids(source),ids(bank),ids(dest)
    unique = all(len(v) == len(set(v)) for v in (source_ids,bank_ids,dest_ids))
    src = {r[0]:r for r in source}
    bank_map = {r[0]:r for r in bank}
    def totals(rows):
        amounts = {}
        for row in rows:
            amounts[row[2]] = amounts.get(row[2],0)+row[1]
        return amounts
    matched,unmatched,destination = True,True,True
    for row in dest:
        identity,amount,currency,account,status = row
        expected = src.get(identity)
        if expected is None:
            matched = unmatched = destination = False
            continue
        bank_row = bank_map.get(identity)
        should_match = bank_row is not None and bank_row[1:3] == expected[1:3]
        matched &= (status == "matched") == should_match
        unmatched &= status in ("matched","unmatched") and ((status == "unmatched") == (not should_match))
        destination &= (amount,currency,account) == expected[1:4]
    exact_ids = set(dest_ids) == set(source_ids)
    bank_ids_covered = set(bank_ids).issubset(set(source_ids))
    return dict(source_complete=len(source) == snapshot["manifest"][0][0] and "sha256:"+digest(tuple(sorted(source))) == baseline_reference,unique_ids=unique,
                no_duplicates=len(dest_ids) == len(set(dest_ids)),amount_conserved=totals(source) == totals(dest),
                matching_correct=bool(matched and exact_ids and bank_ids_covered),unmatched_classified=bool(unmatched and exact_ids and bank_ids_covered),
                destination_correct=bool(destination and exact_ids),authorized=snapshot["meta"][0][2] == 1)


def run_for(contract, task_id="task/1",execution_id="execution/1"):
    return Run(tenant=contract.tenant,task_id=task_id,execution_id=execution_id,executor="untrusted-executor",
               contract_hash=digest(contract),resource=contract.resource,state_version="state/1")


def collect(path, contract, run, policy=None, observed_at=NOW):
    policy = policy or synthetic_policy()
    snapshot = read_snapshot(path)
    resource = snapshot["meta"][0][1]
    state_version = snapshot["meta"][0][0]
    if resource != run.resource or state_version != run.state_version:
        raise ValueError("snapshot resource/version mismatch")
    values,artifact = observation_facts(snapshot,contract.baseline_reference),digest(snapshot)
    collector = policy.collectors[0]
    evidence = []
    for fact in FACTS:
        body = dict(tenant=run.tenant,task_id=run.task_id,execution_id=run.execution_id,contract_hash=run.contract_hash,
                    resource=resource,state_version=state_version,fact=fact,source=collector.source,
                    collector=collector.collector,method=collector.method,observed_at=observed_at,
                    value=values[fact],coverage="point",artifact_hash=artifact)
        body["id"] = "ev-"+digest(body)
        evidence.append(seal_evidence(body,collector.key))
    return tuple(evidence)
