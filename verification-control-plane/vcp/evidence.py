import hmac
from .security import digest, sign


def validate_evidence(record, binding, run, policy, now):
    scope = (record.tenant, record.task_id, record.execution_id, record.contract_hash,
             record.resource, record.state_version)
    expected = (run.tenant, run.task_id, run.execution_id, run.contract_hash,
                run.resource, run.state_version)
    if scope != expected:
        return "scope-or-state-mismatch"
    if binding is None or (record.fact, record.source, record.collector, record.method) != (
            binding.fact, binding.source, binding.collector, binding.method):
        return "binding-mismatch"
    candidates = [c for c in policy.collectors if (c.tenant, c.source, c.collector, c.method) == (
        record.tenant, record.source, record.collector, record.method) and record.fact in c.facts]
    if len(candidates) != 1 or record.collector == run.executor or record.source == run.executor:
        return "untrusted-or-dependent-collector"
    body = record.model_dump(mode="json", exclude={"content_hash", "signature"})
    if not hmac.compare_digest(digest(body), record.content_hash):
        return "content-tampering"
    if not hmac.compare_digest(sign(dict(body, content_hash=record.content_hash), candidates[0].key), record.signature):
        return "inauthentic"
    if not 0 <= now - record.observed_at <= binding.max_age_seconds:
        return "stale-or-future"
    if record.coverage != "point":
        return "unsupported-coverage"
    # artifact_hash identifies the snapshot. Authenticity of that snapshot is a
    # declared collector assumption, not something an envelope signature proves.
    if len(record.artifact_hash) != 64 or any(c not in "0123456789abcdef" for c in record.artifact_hash):
        return "invalid-artifact-hash"
    return None


def resolve(records, contract, run, policy, now):
    bindings = {b.fact: b for b in contract.bindings}
    rejected, valid, duplicate_ids = [], {}, set()
    id_payloads = {}
    for r in records:
        payload = digest(r)
        if r.id in id_payloads and id_payloads[r.id] != payload:
            duplicate_ids.add(r.id)
        id_payloads[r.id] = payload
    for r in sorted(records, key=lambda x: (x.id, digest(x))):
        if r.id in duplicate_ids:
            rejected.append(r.id + ":id-equivocation")
            continue
        error = validate_evidence(r, bindings.get(r.fact), run, policy, now)
        if error:
            rejected.append(r.id + ":" + error)
        else:
            valid.setdefault(r.fact, {})[r.id] = r
    facts, support = {}, {}
    for fact, entries in valid.items():
        values = {digest(r.value) for r in entries.values()}
        support[fact] = tuple(sorted(entries))
        if len(values) == 1:
            facts[fact] = next(iter(entries.values())).value
        else:
            rejected.append(fact + ":conflict")
    return facts, support, tuple(sorted(set(rejected)))
