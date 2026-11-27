"""Local synthetic HMAC trust boundary; keys belong to the trusted harness."""
import hashlib
import hmac
import json
from dataclasses import dataclass
from .models import Approval, Contract, Evidence


def canonical(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sign(value, key):
    return hmac.new(key, canonical(value).encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class CollectorTrust:
    tenant: str
    source: str
    collector: str
    method: str
    facts: tuple[str, ...]
    key: bytes


@dataclass(frozen=True)
class TrustPolicy:
    version: str
    tenant: str
    approver: str
    approval_key: bytes
    collectors: tuple[CollectorTrust, ...]
    assumptions: tuple[str, ...]

    @property
    def fingerprint(self):
        return digest({"version": self.version, "tenant": self.tenant, "approver": self.approver,
                       "approval_key_digest": hashlib.sha256(self.approval_key).hexdigest(),
                       "collectors": [dict(tenant=c.tenant, source=c.source, collector=c.collector,
                                           method=c.method, facts=c.facts,
                                           key_digest=hashlib.sha256(c.key).hexdigest()) for c in self.collectors],
                       "assumptions": self.assumptions})


def approve(contract: Contract, policy: TrustPolicy, at: int) -> Approval:
    if (contract.tenant, contract.approver, contract.trust_policy_hash) != (policy.tenant, policy.approver, policy.fingerprint):
        raise PermissionError("approval authority/policy mismatch")
    body = dict(contract_hash=digest(contract), actor=policy.approver, approved_at=at)
    return Approval(**body, signature=sign(body, policy.approval_key))


def approved(contract, approval, policy, now):
    body = approval.model_dump(exclude={"signature"})
    return (contract.tenant == policy.tenant and contract.approver == policy.approver
            and contract.trust_policy_hash == policy.fingerprint
            and approval.actor == policy.approver and approval.contract_hash == digest(contract)
            and approval.approved_at <= now
            and hmac.compare_digest(approval.signature, sign(body, policy.approval_key)))


def seal_evidence(body, key):
    content_hash = digest(body)
    return Evidence(**body, content_hash=content_hash, signature=sign(dict(body, content_hash=content_hash), key))
