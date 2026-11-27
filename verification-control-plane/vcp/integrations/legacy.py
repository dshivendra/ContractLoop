from dataclasses import asdict
from .legacy_loop_models import Observation
from ..models import Claim, Model, Name
from ..security import digest


class ImportedClaim(Model):
    origin: Name
    source_hash: Name
    legacy_run_id: Name
    claim: Claim
    authoritative_evidence_count: int = 0


def import_loop_observation(observation: Observation) -> ImportedClaim:
    """Preserve lineage without promoting legacy success/evidence IDs to proof."""
    if not isinstance(observation, Observation) or type(observation.success) is not bool:
        raise ValueError("expected legacy Loop Engine Observation with boolean success")
    return ImportedClaim(origin="loop-engine/0.8.8",source_hash=digest(asdict(observation)),
                         legacy_run_id=observation.run_id,
                         claim=Claim(execution_status="completed" if observation.success else "failed",
                                     message="Legacy observation " + observation.id + " (untrusted outcome claim)"))


def import_graph_result(payload: dict) -> ImportedClaim:
    """The Contract Loop Evidence Envelope is an executor report, not a signature."""
    required = ("evidence_id","run_id","contract_id","contract_version","layer_id","attempt",
                "artifact_digest","checks","producer","timestamp")
    if any(k not in payload for k in required):
        raise ValueError("incomplete legacy graph evidence envelope")
    if not isinstance(payload["checks"],list) or not payload["checks"]:
        status = "unknown"
    else:
        checks = payload["checks"]
        if not all(isinstance(c,dict) and type(c.get("passed")) is bool for c in checks):
            raise ValueError("checks must contain explicit boolean passed claims")
        status = "completed" if all(c["passed"] for c in checks) else "failed"
    return ImportedClaim(origin="contract-loop/1",source_hash=digest(payload),legacy_run_id=payload["run_id"],
                         claim=Claim(execution_status=status,message="Legacy graph envelope " + payload["evidence_id"]))
