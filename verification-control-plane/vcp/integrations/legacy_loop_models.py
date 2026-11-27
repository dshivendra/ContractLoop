from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Protocol
import hashlib, json, uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def canonicalize(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(k): canonicalize(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [canonicalize(v) for v in payload]
    if isinstance(payload, set):
        return sorted((canonicalize(v) for v in payload), key=lambda x: repr(x))
    return payload

def digest(payload: Any) -> str:
    raw = json.dumps(canonicalize(payload), sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class Goal:
    id: str
    statement: str
    required_outcomes: tuple[str, ...]
    domain: str | None = None

@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    domain: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    prerequisites: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    reliability: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Evidence:
    id: str
    run_id: str
    capability_id: str
    type: str
    subject: str
    passed: bool
    source: str
    observed_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Observation:
    id: str
    run_id: str
    capability_id: str
    outputs: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    success: bool
    observed_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Verification:
    id: str
    run_id: str
    goal_id: str
    passed: bool
    verified_outcomes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...] = ()
    verifier: str = "deterministic"
    created_at: str = field(default_factory=now_iso)

@dataclass(frozen=True)
class LoopClosure:
    id: str
    run_id: str
    goal_id: str
    status: str
    verification_id: str | None
    reason: str
    closed_at: str = field(default_factory=now_iso)

@dataclass(frozen=True)
class Connection:
    source: str
    target: str
    via: tuple[str, ...]
    satisfied_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    score: float

@dataclass(frozen=True)
class LoopPlan:
    id: str
    run_id: str
    goal_id: str
    capability_ids: tuple[str, ...]
    connections: tuple[Connection, ...]
    expected_outcomes: tuple[str, ...]
    plan_digest: str
    created_at: str = field(default_factory=now_iso)
    route_steps: tuple[dict[str, Any], ...] = ()
    graph_spec: dict[str, Any] = field(default_factory=dict)

@dataclass
class LoopState:
    run_id: str
    goal: Goal
    status: str = "running"
    context: set[str] = field(default_factory=set)
    completed_capabilities: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)
    effect_ids: list[str] = field(default_factory=list)
    verification_ids: list[str] = field(default_factory=list)
    closure_id: str | None = None
    step_count: int = 0
    non_progress_steps: int = 0
    transition_history: list[dict[str, object]] = field(default_factory=list)
    last_fingerprint: str | None = None

    def as_dict(self):
        return asdict(self)

class CapabilityExecutor(Protocol):
    def execute(self, capability: Capability, state: LoopState) -> Observation: ...
