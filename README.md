# ContractLoop

[![GitHub stars](https://img.shields.io/github/stars/dshivendra/contractloop?style=flat-square)](https://github.com/dshivendra/contractloop/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/dshivendra/contractloop?style=flat-square)](https://github.com/dshivendra/contractloop/network/members)
[![GitHub issues](https://img.shields.io/github/issues/dshivendra/contractloop?style=flat-square)](https://github.com/YOUR_GITHUB_USERNAME/contractloop/issues)
[![GitHub license](https://img.shields.io/github/license/dshivendra/contractloop?style=flat-square)](LICENSE)

ContractLoop is a contract-first, verification-first execution engine for reliable, policy-governed automation.
### Define the contract. Execute the action. Verify the outcome.

ContractLoop is a contract-first, verification-first execution engine for reliable, policy-governed automation.

It transforms goals into explicit contracts, validates preconditions and permissions, executes actions through external capabilities, observes real-world state, verifies postconditions, and closes the loop only when success is proven.

> No satisfied contract, no execution. No verified postcondition, no closure.

## Why ContractLoop?

Most automation systems are action-centric:

```
Receive request → Call tool → Get response → Mark successful
```

However, a successful tool response does not necessarily mean that the intended outcome was achieved.

An API may return `200 OK` while:

* The requested state was not actually applied.

* The external system is eventually consistent.

* A downstream process failed.

* The wrong resource was modified.

* The operation partially completed.

* The result became stale or conflicted.

* The business condition remains unsatisfied.

ContractLoop separates action execution from outcome verification.

```
Goal
  ↓
Contract
  ↓
Validate
  ↓
Authorize
  ↓
Execute
  ↓
Observe external state
  ↓
Verify postconditions
  ↓
Close or recover
```

## Core Principle

ContractLoop is based on the following execution model:

```
{ Preconditions } Action { Postconditions }
```

An action is permitted only when its preconditions are satisfied and the applicable policies allow execution.

The loop can terminate successfully only when its postconditions are verified using acceptable evidence.

```
Action success ≠ Business success
Response received ≠ Outcome verified
```


## Conventional Automation vs ContractLoop

| Conventional Automation | ContractLoop |
|---|---|
| Action-centric | Contract-centric |
| Implicit assumptions | Explicit preconditions |
| Tool response treated as success | External state used as evidence |
| Permissions handled separately | Permissions enforced through execution policy |
| Unbounded retries | Bounded recovery strategies |
| Arbitrary response chaining | Verified state-transition chaining |
| Success declared after execution | Success declared after postcondition verification |
| Limited execution context | Complete, auditable execution trace |

## Execution Lifecycle

```
Trigger
  ↓
Goal
  ↓
Contract Resolution
  ↓
Precondition Validation
  ↓
Policy and Permission Check
  ↓
Action Execution
  ↓
Observation Collection
  ↓
Postcondition Verification
  ├── Verified → Close
  ├── Failed   → Recover
  ├── Unknown  → Refresh or Escalate
  └── Conflict → Reconcile or Stop
```

### 1. Trigger

An external event, user request, schedule, system signal, or another verified workflow transition initiates execution.

### 2. Goal

The desired outcome is expressed as a structured, machine-checkable objective.

### 3. Contract

The goal is mapped to a contract defining:

* Preconditions

* Action or capability

* Postconditions

* Invariants

* Permissions

* Verification requirements

* Recovery strategies

* Termination limits

* Audit requirements

### 4. Validate

The runtime evaluates whether:

* Required inputs are present.

* Preconditions are satisfied.

* Required resources exist.

* The requested action is valid.

* Invariants can be preserved.

* The contract is internally consistent.

### 5. Authorize

The runtime checks whether the action is permitted under the applicable policy.

Authorization may consider:

* Actor identity

* Resource ownership

* Scope

* Environment

* Risk level

* Approval requirements

* Rate limits

* Separation-of-duty rules

* Operational constraints

### 6. Execute

The runtime invokes an external capability through an adapter or tool interface.

Execution results are recorded, but are not treated as proof of final success.

### 7. Observe

The runtime collects fresh observations from one or more state sources.

Observations may include:

* Resource state

* Database records

* API responses

* Events

* Logs

* Metrics

* Files

* Device telemetry

* Human confirmation

* Independent verification sources

### 8. Verify

The runtime evaluates the observed state against the contract’s postconditions.

Verification must consider:

* Evidence freshness

* Source authority

* Completeness

* Conflicting observations

* Required invariants

* Verification policy

* Business success criteria

### 9. Close or Recover

The loop closes only when the success predicate is satisfied.

If verification fails or remains uncertain, the runtime follows a bounded recovery strategy.

## Contract Example

The following example is illustrative:

YAML

```
name: provision-storage-resource
version: "1.0"

goal:
  description: "Provision a storage resource for the application"

preconditions:
  - id: subscription-active
    predicate: "subscription.status == 'active'"

  - id: resource-name-available
    predicate: "resource.name does not exist"

  - id: deployment-authorized
    predicate: "policy.allows('storage.create') == true"

action:
  capability: storage.create
  input:
    name: application-storage
    region: central-region
    tier: standard

postconditions:
  - id: resource-exists
    predicate: "resource.name == 'application-storage'"

  - id: resource-is-available
    predicate: "resource.status == 'available'"

  - id: resource-is-private
    predicate: "resource.public_access == false"

invariants:
  - id: no-public-access
    predicate: "resource.public_access == false"

verification:
  mode: authoritative-observation
  source: storage-control-plane
  require_fresh_observation: true

recovery:
  on:
    - verification_failed
    - observation_stale
  strategies:
    - refresh
    - reconcile
    - retry
    - escalate

termination:
  max_attempts: 3
  max_duration_seconds: 120
  on_unknown: stop
```

## Verification-First Execution

ContractLoop maintains a strict separation between three stages:

```
Action Result
    ↓
External Observation
    ↓
Verification Decision
```

An action result may indicate that a request was accepted. The observation determines what actually exists in the external system. The verification decision determines whether the contract has been satisfied.

Possible verification states include:

```
SATISFIED
UNSATISFIED
UNKNOWN
STALE
CONFLICTED
VERIFIED
UNVERIFIED
```

A successful execution response alone cannot close a verification-first loop.

## Verified Chaining

ContractLoop does not chain workflows merely because one tool returned a response.

A downstream action may execute only when the upstream transition has been verified:

```
VerifiedPostconditions(A)
AND Preconditions(B)
AND PolicyAllows(B)
AND InvariantsPreserved
```

Example:

```
Create resource
  ↓
Verify resource exists
  ↓
Verify resource is available
  ↓
Verify security configuration
  ↓
Enable dependent service
```

Each step consumes verified state rather than untrusted intermediate output.

## Canonical State

ContractLoop represents external state using a canonical, provenance-aware model.

Each state value may include:

* Value

* Source

* Timestamp

* Freshness

* Confidence

* Version

* Verification status

* Conflicts

* Resource identity

* Observation metadata

This allows the runtime to distinguish between:

```
Known and verified
Known but stale
Observed but unverified
Unknown
Conflicting
Unavailable
```

Canonical state becomes the foundation for:

* Preconditions

* Postconditions

* Invariants

* Capability transitions

* Recovery decisions

* Verified chaining

* Auditability

## Recovery Model

Failure is not treated as an invitation to retry indefinitely.

ContractLoop uses explicit, bounded recovery strategies such as:

* Refresh state

* Retry action

* Repair resource

* Reconcile conflicting state

* Compensate a completed action

* Reauthorize

* Replan

* Request human approval

* Escalate

* Stop deterministically

Every recovery attempt must remain within the contract’s:

* Retry limit

* Time limit

* Cost limit

* Risk limit

* Permission boundary

* Termination policy

## Deterministic Termination

Every loop must have explicit terminal conditions.

A loop may terminate because:

* The success predicate was verified.

* A required postcondition failed.

* The state is unknown after allowed recovery.

* Conflicting observations cannot be reconciled.

* A safety invariant was violated.

* The operation was cancelled.

* The retry limit was reached.

* The time or cost budget was exhausted.

* Human approval was denied.

* The contract became invalid.

The runtime must never continue indefinitely without a defined termination decision.

## Execution Trace

Each execution produces an auditable trace containing:

```
Execution ID
Goal
Resolved Contract
Input State
Precondition Results
Policy Decisions
Selected Capability
Action Request
Action Response
Observed State
Verification Evidence
Verification Decision
Recovery Attempts
State Transitions
Final Outcome
Termination Reason
```

This trace supports:

* Debugging

* Compliance

* Incident analysis

* Reproducibility

* Reliability measurement

* Policy audits

* Failure analysis

## What ContractLoop Does Not Assume

ContractLoop is designed to be domain-independent.

It does not require a specific:

* Programming language

* AI model

* Agent framework

* Cloud provider

* Database

* API protocol

* Workflow engine

* Messaging system

* Industry

* Deployment environment

The runtime can work with any external capability that exposes a sufficiently precise contract and supports observable state.

Potential application areas include:

* Software automation

* Cloud infrastructure

* Distributed systems

* Business workflows

* Financial operations

* Data engineering

* Robotics

* Industrial automation

* Security operations

* Enterprise operations

* Infrastructure management

## MVP Scope

The initial MVP focuses on proving one central property:

> A real external action can be initiated from a goal, and the loop closes only after independent or authoritative verification proves that the intended outcome was achieved.

The MVP lifecycle is:

```
Submit goal
  ↓
Load contract
  ↓
Evaluate preconditions
  ↓
Check permissions
  ↓
Execute external action
  ↓
Observe external state
  ↓
Verify postconditions
  ↓
Record terminal result
```

The MVP should support:

* Contract loading

* Precondition evaluation

* Policy enforcement

* Capability execution

* State observation

* Postcondition verification

* Bounded retries

* Deterministic termination

* Structured execution traces

## Proposed Repository Structure

```
contractloop/
├── contracts/
│   ├── examples/
│   └── schemas/
├── engine/
│   ├── contract/
│   ├── policy/
│   ├── state/
│   ├── execution/
│   ├── verification/
│   ├── recovery/
│   └── termination/
├── adapters/
├── traces/
├── tests/
├── docs/
│   ├── architecture.md
│   ├── contracts.md
│   ├── state-model.md
│   ├── verification.md
│   ├── recovery.md
│   ├── termination.md
│   └── security.md
└── README.md
```

## Project Status

ContractLoop is currently under active design and development.

The project is focused on establishing a reliable execution foundation based on:

1. Explicit contracts

2. Policy-controlled actions

3. Canonical state

4. Evidence-based verification

5. Verified state transitions

6. Bounded recovery

7. Deterministic termination

8. Complete execution traces

## Final Statement

ContractLoop treats automation as a closed-loop state transition problem, not merely a sequence of tool calls.

It makes the intended outcome explicit, validates the conditions for action, observes the real world, verifies the result, and refuses to declare success without sufficient evidence.

> Define the contract. Execute the action. Verify the outcome.
