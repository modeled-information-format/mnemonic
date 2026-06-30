# Reference: org governance & release runbooks

This repository follows the shared governance, CI, and release process of the
[`modeled-information-format`](https://github.com/modeled-information-format) organization. Those
processes are maintained once, centrally, in the org
[`.github`](https://github.com/modeled-information-format/.github) repository and apply to every
repo that adopts the attested-delivery backbone — including this one. The runbooks below are the
authoritative, governing process; this page makes them reachable from here.

## Runbooks

| Runbook | What it governs |
| --- | --- |
| [Release runbook](https://github.com/modeled-information-format/.github/blob/main/docs/runbooks/release-runbook.md) | The required, audit-gated **attested release process**: punch-list audit, epics + sub-issues, a decision log, a release workplan issue, one PR per epic under GitHub Flow, and the attested cutover. |
| [Branch-protection runbook](https://github.com/modeled-information-format/.github/blob/main/docs/runbooks/branch-protection-runbook.md) | The required-checks, single-review, and linear-history rules applied to protected branches. |
| [Dependabot auto-merge runbook](https://github.com/modeled-information-format/.github/blob/main/docs/runbooks/dependabot-automerge-runbook.md) | The policy and rollout for auto-merging **patch** Dependabot updates via the org CI app — minor/major and non-semver bumps stay manual for review. |
| [Labels runbook](https://github.com/modeled-information-format/.github/blob/main/docs/runbooks/labels-runbook.md) | The org-wide label taxonomy and the reusable label-sync that keeps every repo consistent. |

## Reusable CI/release workflows

This repo's CI and release gates are **thin SHA-pinned callers** of the org's reusable workflows
in [`.github/.github/workflows/`](https://github.com/modeled-information-format/.github/tree/main/.github/workflows).
The architecture is recorded in the org
[ADR-002: reusable quality-gate architecture](https://github.com/modeled-information-format/.github/blob/main/docs/adr/ADR-002-reusable-quality-gate-architecture.md).
