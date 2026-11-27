# Codex Ship for ContractLoop

This is the repository's Codex-based review/repair/policy implementation. It uses
OpenAI Codex, the existing deterministic acceptance kernel and GitHub Actions.
No Anthropic account, Claude App or Claude approval policy is used.

## Implemented flow

1. Review: exact PR head and repository are checked before Codex reads the diff.
   The official `openai/codex-action` runs a structured read-only review. Findings
   are advisory JSON artifacts, not verified business outcomes or approvals.
2. Repair: a writer manually dispatches `Codex Ship` with mode `fix`, PR number
   and exact head SHA. One Codex invocation may propose at most 10 Python files
   under `verification-control-plane/vcp/` and 400 changed lines. Tests, schema,
   policy, workflows, evidence, symlinks, renames and deletions are excluded.
3. Verify: a fresh GitHub-hosted job applies the exported content to the original
   clean commit, independently recounts the diff and runs the original acceptance
   suite and demo. It never relies on a model's test/completion claim.
4. Propose: only after verification, a separate job with write permissions checks
   that the source PR head is still current, creates a new repair branch and opens
   a draft PR into the original PR's branch. It never overwrites the source branch,
   approves or merges. Another human reviews the repair before incorporating it.

Model and validation jobs have read-only repository access. Publishing has a
separate short-lived job and never executes proposed code. The official Codex
Action's `drop-sudo` strategy and read-only/workspace permission profiles are used
on disposable GitHub-hosted Ubuntu runners. There is one repair attempt per run,
a 15-minute model-job deadline and file/line/size budgets. These bound work; they
are not a hard dollar cap. Use a dedicated API project with a spending limit.

`.github/codex/ship.py` also computes a deterministic observe-mode decision:
explicit failed required CI => BLOCKED; absent/stale/untrusted CI => UNKNOWN;
all required checks green => NEEDS_HUMAN. It never returns an automatic approval.
Policy results are reported by the controller, not asserted by the model.
`AGENTS.md` and `REVIEW.md` supply contributor and review guidance.

## Run and enable

The normal verification workflow runs immediately on PRs without an API key. It
tests both Python versions and the independent shipping-controller tests.

The Codex workflow is manual-first. After this workflow is reviewed and merged
onto the default branch, set the GitHub repository secret `OPENAI_API_KEY` to an
OpenAI project credential, then run **Actions > Codex Ship > Run workflow** with
the PR number, its current head SHA and `review` or `fix`. Never paste keys into
chat or commit them. The Actions job does not inherit this ChatGPT session's
authentication. This key is required only for independent background Actions
runs; working with Codex in this chat needs no Claude sign-in or added API key.

Automatic reviews remain off until repository variable `CODEX_SHIP_ENABLED` is
set to `true`; then eligible same-repository non-draft PR updates trigger review.
Forks and GitHub Actions bot events are excluded. Repairs stay manual. GitHub must
allow Actions to create pull requests for the final repair-proposal job; otherwise
the validated receipt/evidence remain available but publication fails explicitly.

Required GitHub branch checks should include both `Phase 1 gate (Python 3.11)`
and `Phase 1 gate (Python 3.12)`, plus `Codex shipping policy`. Require a human PR
approval with stale approvals dismissed/latest-push approval, and no bot bypass.
The connected repository tool cannot change these administrative settings; the
JSON observe policy does not itself enforce GitHub merge protection.

Codex reviews/repairs require live credentials and model access. Offline tests and
normal CI prove controller and kernel behavior, not that a paid model run occurred.
Policy/receipt inputs and workflow configuration remain inside the trusted GitHub
runner boundary. Prompt injection, compromised dependencies, correlated tests and
model errors remain risks; independent CI and human review reduce, not erase, them.

Sources checked 2026-11-27:
https://github.com/openai/codex-action
https://developers.openai.com/codex/github-action

The Codex Action is pinned to `306c6a196a99dcc6582530c396a19d2672d5e9ec`.
