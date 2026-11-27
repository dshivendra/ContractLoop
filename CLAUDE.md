# Working in ContractLoop

Work in `verification-control-plane/`. Read HANDOFF.md before changing semantics.
Reuse existing components. Keep scope inside Phase 1 unless the owner explicitly
authorizes another phase. Follow root REVIEW.md for review priorities.

For PR Steward: fix concrete CI failures and review findings in small commits.
Never weaken predicates, evidence checks, independent tests, mutation expectations
or approval policy to obtain a green check. Semantic changes need the handoff's
change-control evidence and owner approval. Report blocked work explicitly.
Do not merge, approve, change branch rules, enable services, introduce credentials,
or access real financial data/production infrastructure as part of a code fix.

Validation commands from `verification-control-plane/`:

```bash
python -m pip install -e '.[qa]'
python tools/run_acceptance.py --output "$(mktemp -d)"
python -m vcp
```

The output directory must be new and empty. Keep committed `evidence/` immutable.
If contract models change, explicitly regenerate and review CONTRACT_SCHEMA.json;
CI rejects schema drift. Explain the defect, fix, commands/results and remaining
limitations in each report. Avoid marking unavailable checks as passed.
