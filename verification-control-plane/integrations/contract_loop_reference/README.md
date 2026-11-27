# Contract Loop Complete Graph v1.1

This package defines a governed SDLC graph, its lifecycle handoffs, a change-delivery workflow, and subagent invocation contracts. It is an implementation specification; credentials, MCP servers, and production adapters are not configured.

## Workflow and subagents
- workflows/change-delivery.json defines entrypoints, nine stages, gates, branches, retries, cancellation, checkpointing, idempotency, and approval.
- workflows/change-delivery.mmd renders the lifecycle and key branches.
- subagents/registry-and-bindings.json contains all 567 catalog agents and a binding for each of the 694 skills.
- All 497 independent skills resolve to their catalog owner. The 197 SDLC skills have curated candidate pools because the source catalog does not assign a unique owner; automatic dispatch is blocked pending review.
- Agent tool strings remain raw catalog metadata. Runtime permission is none by default and must be granted per task by policy.

## Enforcement
Rules guide; skills instruct; subagents perform bounded tasks; hooks validate dispatch/tool use; permissions deny by default; contracts require evidence; reviewers are read-only; protected CI/deployment providers enforce release gates. Production, high-risk, and policy-override actions require human approval. Simulated evidence cannot certify production.

Run python3 validate_graph_package.py to validate structure.
