# Claude Ship pilot

Repository-side configuration is implemented in this change. Service activation
requires the repository's Claude organization and GitHub administrative settings;
committing these files alone does not activate Claude Ship.

## GitHub Actions

`.github/workflows/verification.yml` runs on every PR targeting main, pushes to
main, merge queues and manual dispatches. No path filters can leave documentation
or policy PRs waiting on a skipped check. Python 3.11 and 3.12 each install the
kernel/QA dependencies and run tests, schema/graph validation, 70 synthetic cases,
replay, seven mutations and the legacy demo. Each job has a 10-minute limit and
uploads fresh run evidence for 14 days even after a failure.

The workflow uses read-only repository permissions, pinned action commits and no
stored checkout credentials. It runs PR code in the normal pull_request context;
it does not use pull_request_target, secrets or model API keys.

Once check runs exist, require both checks on main in GitHub branch rules:

- `Phase 1 gate (Python 3.11)`
- `Phase 1 gate (Python 3.12)`

Require pull requests, at least one approval, and dismissal of stale approvals or
approval of the latest push. Keep the Claude App outside the bypass list. These
are administrative settings, not guarantees created by workflow YAML. A solo
maintainer needs another eligible human reviewer before enforcing that review rule.

## Claude configuration

An eligible Team/Enterprise Claude organization needs usage credits, the Claude
GitHub App installed on ContractLoop and its GitHub connection linked. An Owner
uses Organization settings > Claude Ship to add this repository, choose Code
Review settings and select Manual (@claude steward) for Steward. Set organization
and repository spend limits before starting paid work; no budget is assumed here.

`REVIEW.md` supplies review criteria. `CLAUDE.md` gives Steward concrete validation
commands and scope limits. `.claude/approvals.yml` starts in `mode: observe`, uses
`claude: comments` everywhere and retains Code Review via `advisory`. An eligible
human who is not a PR author is required by the proposed policy; nested policies
cannot silently relax the explicit sensitive-path rule. It does not allow automatic
Claude approvals, and observe mode does not block merges.

Approvals reads policy from the default branch. Review the policy change separately
and merge it only after Claude validates it. Then test Approvals with a new PR.
The current PR cannot activate its own proposed policy. Do not make observe-mode
Claude Approvals a replacement for independently required deterministic CI checks.

After the App is connected and Steward is Manual, start a pilot on a non-draft PR
with `@claude steward`. Confirm the `claude-pr-steward-watching` label and a Claude
PR Steward comment. Remove that label or comment `@claude stop` to stop it.
No activation comment is sent automatically while service readiness is unknown.

## Pilot measurements

For the first five eligible PRs record time opened, first review, first green CI,
human approval and merge; Steward commits, reviewer interventions, model spend and
any reverted change. Compare with recent manually handled PRs. No speedup is claimed
until those observations exist. Keep manual Steward and human approval during this
pilot; changes to the verification kernel remain subject to contract change control.

Sources checked 2026-11-27:

- https://code.claude.com/docs/en/claude-ship
- https://code.claude.com/docs/en/pr-steward-setup
- https://code.claude.com/docs/en/approvals-setup
- https://code.claude.com/docs/en/approvals-policy
