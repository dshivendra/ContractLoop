from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

Scalar = Union[StrictBool, StrictInt, StrictStr]
Name = Annotated[str, Field(min_length=1, max_length=200, strict=True)]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Compare(Model):
    kind: Literal["compare"] = "compare"
    fact: Name
    op: Literal["eq", "ne", "ge", "le"] = "eq"
    expected: Scalar

    @model_validator(mode="after")
    def ordered_integer(self):
        if self.op in ("ge", "le") and type(self.expected) is not int:
            raise ValueError("ordered comparisons require integer minor units/counts")
        return self


class All(Model):
    kind: Literal["all"] = "all"
    items: Annotated[tuple["Expression", ...], Field(min_length=1, max_length=64)]


class AnyOf(Model):
    kind: Literal["any"] = "any"
    items: Annotated[tuple["Expression", ...], Field(min_length=1, max_length=64)]


class Not(Model):
    kind: Literal["not"] = "not"
    item: "Expression"


Expression = Annotated[Union[Compare, All, AnyOf, Not], Field(discriminator="kind")]
for _model in (All, AnyOf, Not):
    _model.model_rebuild()


class Condition(Model):
    id: Name
    role: Literal["success", "failure", "precondition", "constraint", "invariant", "authorization"]
    stage: Literal["V0", "V1", "V2", "V3", "V4"] = "V3"
    temporal: Literal["point", "always", "eventual", "stability", "deadline"] = "point"
    expression: Expression


class Binding(Model):
    fact: Name
    source: Name
    collector: Name
    method: Name
    max_age_seconds: Annotated[int, Field(strict=True, ge=0, le=86400)] = 60


class Contract(Model):
    schema_version: Literal["phase1/1"] = "phase1/1"
    id: Name
    version: Annotated[int, Field(strict=True, ge=1)]
    tenant: Name
    owner: Name
    approver: Name
    objective: Name
    acceptance_rationale: Name
    resource: Name
    environment: Literal["synthetic"] = "synthetic"
    baseline_reference: Name
    intent_alignment_reference: Name
    assumptions: Annotated[tuple[Name, ...], Field(min_length=1)]
    limitations: tuple[Name, ...]
    trust_policy_hash: Name
    conditions: Annotated[tuple[Condition, ...], Field(min_length=1, max_length=64)]
    bindings: Annotated[tuple[Binding, ...], Field(min_length=1, max_length=128)]
    max_evidence: Annotated[int, Field(strict=True, ge=1, le=1024)] = 256
    required_assurance: Literal["synthetic-point", "historical", "production"] = "synthetic-point"

    @model_validator(mode="after")
    def validate_semantics(self):
        from .logic import validate_contract
        validate_contract(self)
        return self


class Approval(Model):
    contract_hash: Name
    actor: Name
    approved_at: Annotated[int, Field(strict=True, ge=0)]
    signature: Name


class Run(Model):
    tenant: Name
    task_id: Name
    execution_id: Name
    executor: Name
    contract_hash: Name
    resource: Name
    state_version: Name


class Evidence(Model):
    id: Name
    tenant: Name
    task_id: Name
    execution_id: Name
    contract_hash: Name
    resource: Name
    state_version: Name
    fact: Name
    source: Name
    collector: Name
    method: Name
    observed_at: Annotated[int, Field(strict=True, ge=0)]
    value: Scalar
    coverage: Literal["point", "interval"] = "point"
    artifact_hash: Name
    content_hash: Name
    signature: Name


class Claim(Model):
    execution_status: Literal["completed", "failed", "partial", "unknown"]
    message: Name


class Assessment(Model):
    condition_id: Name
    truth: Literal["TRUE", "FALSE", "UNKNOWN"]
    evidence_ids: tuple[Name, ...]
    reason: str


class Verdict(Model):
    id: Name
    tenant: Name
    task_id: Name
    execution_id: Name
    contract_hash: Name
    contract_version: Annotated[int, Field(strict=True, ge=1)]
    engine_version: Name
    policy_hash: Name
    evaluated_at: Annotated[int, Field(strict=True, ge=0)]
    execution_status: Literal["completed", "failed", "partial", "unknown"]
    verdict: Literal["SUCCESS", "FAILURE", "UNKNOWN"]
    assurance: Literal["synthetic-point", "insufficient"]
    trust_assumptions: tuple[str, ...]
    assessments: tuple[Assessment, ...]
    rejected_evidence: tuple[str, ...]
    faults: tuple[str, ...]
    attestation_status: Literal["not-issued"] = "not-issued"
