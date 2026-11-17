<p align="center"><img src="images/hero.svg" alt="raven" width="720"></p>

# Raven Gaia2: samples

<p align="center"><b>Five sample tasks from Raven, a corpus of agentic assistant work over dense, messy personal estates for evaluating autonomous agents.</b></p>

<p align="center"><a href="#summary"><img src="https://img.shields.io/badge/samples-5%2F5-845EF7" alt="samples: 5/5"></a> <a href="#summary"><img src="https://img.shields.io/badge/harbor_schema-1.4-845EF7" alt="harbor schema: 1.4"></a> <a href="#trials"><img src="https://img.shields.io/badge/difficulty-unsolved_by_frontier-845EF7" alt="difficulty: unsolved by frontier"></a></p>

<p align="center"><sub><a href="#abstract">Abstract</a> | <a href="#summary">Summary</a> | <a href="#tasks">Tasks</a> | <a href="#trials">Trials</a> | <a href="#coverage">Coverage</a> | <a href="#dataset-structure">Dataset structure</a> | <a href="#reproduction">Reproduction</a> | <a href="#cite">Cite</a> | <a href="#contact">Contact</a></sub></p>

## Abstract

Raven is a corpus of hard, realistic evaluation tasks in [Harbor](https://github.com/laude-institute/harbor) format, drawn from everyday agentic assistant work over a person's own apps: mail, calendar, messaging and chats, staff directories and personal contacts, files, travel, accommodation, and shopping. This is based on Gaia2 / ARE (Meta's Agents Research Environments). Every task ships a sandbox image, the instruction the agent reads, a verifier hidden from the agent, and a reference solution. The reward is continuous from 0 to 1: a deterministic verifier grades the concrete write actions the agent took against the estate's own records, and an LLM-judged rubric grades the free-text facets of its prose.

This repository holds the five-task sample. Three tasks are dense single-turn triage: the agent reads a flooded inbox, calendar, and chats, resolves requests the user gives only by role, relationship, or event rather than by any id, acts on the ones that resolve to a single truthful write, and reports the ones that are ambiguous, already cancelled, or point at the wrong target. Two tasks are live-estate deadline work: the agent drives a running simulation on an authoritative backend clock through the `raven-ar9` MCP server, rescheduling a client review or recovering a disrupted trip before a backend-enforced deadline, adapting as new facts arrive and earlier facts are overtaken.

Each sample ships one trial by Claude Code with `claude-opus-5-5`, scored by the task's own verifier. None of the five trials reached reward 1, so every task keeps headroom above `claude-opus-5-5`.

## Summary

| Property | Value |
| --- | --- |
| Samples | 5/5 |
| Target Benchmark | Gaia2 / ARE |
| Domains | Office & white-collar (mobile assistant triage); operations (crisis coordination); agentic tool use (live-estate deadline work) |
| Format | Harbor task, schema 1.4 |
| Platforms | linux/amd64, linux/arm64 |
| Base image | `python:3.12-slim`, digest-pinned |
| Reward | Continuous 0 to 1, from a deterministic write-action verifier and an LLM-judged rubric |
| Agent | Claude Code with `claude-opus-5-5` |
| Judge | `gpt-6.1-sol` |
| Trials | 1 per task |
| Solved by `claude-opus-5-5` | 0 of 5 |
| Mean reward | 0.4941 |
| Mean cost per trial | 0.59 USD |
| Mean agent time | 2m 8s |

## Tasks

| Task | Category | Area | Objective |
| --- | --- | --- | --- |
| [`832c4f92`](832c4f92-1f69-562a-9c84-f80e797bc46b/) | Office & white-collar | Mobile assistant | Triage a dense back-from-leave estate: resolve each request given only by role, relationship, or event across mail, calendar, chats, and contacts, carry out the ones that resolve to a single truthful write, and report the ambiguous, cancelled, or wrong-target ones. |
| [`8afa7574`](8afa7574-b51b-5926-ad9c-8d443f4c2919/) | Operations | Crisis coordination | Coordinate an apartment complex through a 24-hour power and water outage: relay only information confirmed by management or the provider, honor privacy, consent, and a 500 dollar per-vendor spend cap, and flag rather than act on anything unconfirmed, unauthorized, or over cap. |
| [`9add9d25`](9add9d25-484f-592d-910c-106c533a3f12/) | Office & white-collar | Mobile assistant | Work a jumbled single-turn brain-dump over a large, noisy estate: join across apps to resolve each target past two or three near-miss candidates, do the parts that resolve, and report the parts that do not, without guessing. |
| [`b17f60d7`](b17f60d7-548a-5e75-a5c3-b0e99e185178/) | Agentic tool use | Temporal deadline | On a live MCP estate on an authoritative backend clock, reschedule and relocate a client review, arrange travel and an agenda, and confirm before a backend-enforced deadline, adapting as rooms, attendees, and the deadline itself are overtaken mid-episode. |
| [`438d8f60`](438d8f60-c96d-50f8-b1fe-3eb98714bde9/) | Agentic tool use | Temporal deadline | On a live MCP estate, recover a disrupted Dublin-to-Lisbon trip before the arrival and confirm-by deadlines, honoring the spend cap and hotel cutoff, as the first flight is delayed and the onward connection is missed mid-episode. |

## Trials

Each task was run once by Claude Code with `claude-opus-5-5`, and scored by the task's own verifier. Trials are stored in each task's `trials/opus-5-5/`.

| Task | Reward | Cost (USD) | Agent time |
| --- | ---: | ---: | ---: |
| [`832c4f92-1f69-562a-9c84-f80e797bc46b`](832c4f92-1f69-562a-9c84-f80e797bc46b/trials/opus-5-5/) | 0.5939 | 0.32 | 1m 17s |
| [`8afa7574-b51b-5926-ad9c-8d443f4c2919`](8afa7574-b51b-5926-ad9c-8d443f4c2919/trials/opus-5-5/) | 0.4430 | 0.20 | 1m 14s |
| [`9add9d25-484f-592d-910c-106c533a3f12`](9add9d25-484f-592d-910c-106c533a3f12/trials/opus-5-5/) | 0.6545 | 0.36 | 1m 16s |
| [`b17f60d7-548a-5e75-a5c3-b0e99e185178`](b17f60d7-548a-5e75-a5c3-b0e99e185178/trials/opus-5-5/) | 0.2888 | 1.25 | 4m 7s |
| [`438d8f60-c96d-50f8-b1fe-3eb98714bde9`](438d8f60-c96d-50f8-b1fe-3eb98714bde9/trials/opus-5-5/) | 0.4901 | 0.85 | 2m 44s |
| **mean** | **0.4941** | **0.59** | **2m 8s** |

The **mean** row averages reward, cost, and agent time over the five trials. The reward is continuous: a deterministic dimension grades the concrete write actions against the estate's own records, and an LLM-judged rubric grades the free-text facets of the agent's prose. No trial reached reward 1, so each keeps headroom above `claude-opus-5-5`.

Each trial folder is Harbor's trial output:

| Path | Contents |
| --- | --- |
| `config.json`, `lock.json` | Trial configuration and resolved run settings |
| `result.json` | Agent, model, token usage, cost, timings, and verifier reward |
| `agent/` | Agent trajectory (`trajectory.json`), Claude Code session transcript (`sessions/`), and agent output (`claude-code.txt`) |
| `verifier/` | `reward.json`, `reward.txt`, grading details (`score.json` or `reward-details.json`), and test output |
| `artifacts/` | Files the agent produced, collected from the paths declared in `task.toml` |

## Coverage

| Keyword | Tasks |
| --- | --- |
| abstention | 1 |
| agentic | 2 |
| ambiguity | 2 |
| are | 4 |
| authorization | 2 |
| consent | 1 |
| crisis-coordination | 1 |
| cross-app-join | 2 |
| density | 2 |
| gaia2 | 4 |
| mobile | 3 |
| over-abstention | 2 |
| privacy | 1 |
| search-hardness | 1 |
| temporal-deadline-compliance | 2 |
| triage | 1 |
| underspecified-intent | 5 |
| unverified-information | 1 |
| wrong-target | 2 |
| write-action-verifier | 3 |

## Dataset structure

Each task is one Harbor task in a directory named by its uuid.

| Task | Keywords |
| --- | --- |
| [`832c4f92-1f69-562a-9c84-f80e797bc46b`](832c4f92-1f69-562a-9c84-f80e797bc46b/) | ambiguity, are, cross-app-join, density, gaia2, mobile, over-abstention, triage, underspecified-intent, wrong-target, write-action-verifier |
| [`8afa7574-b51b-5926-ad9c-8d443f4c2919`](8afa7574-b51b-5926-ad9c-8d443f4c2919/) | authorization, consent, crisis-coordination, density, mobile, over-abstention, privacy, underspecified-intent, unverified-information, wrong-target, write-action-verifier |
| [`9add9d25-484f-592d-910c-106c533a3f12`](9add9d25-484f-592d-910c-106c533a3f12/) | ambiguity, are, cross-app-join, gaia2, mobile, search-hardness, underspecified-intent, write-action-verifier |
| [`b17f60d7-548a-5e75-a5c3-b0e99e185178`](b17f60d7-548a-5e75-a5c3-b0e99e185178/) | agentic, are, gaia2, temporal-deadline-compliance, underspecified-intent |
| [`438d8f60-c96d-50f8-b1fe-3eb98714bde9`](438d8f60-c96d-50f8-b1fe-3eb98714bde9/) | abstention, agentic, are, authorization, gaia2, temporal-deadline-compliance, underspecified-intent |

```
<uuid>/
├── task.toml         runner manifest
├── instruction.md    objective the agent reads
├── environment/      sandbox image, with a service sidecar where the task uses one
├── tests/            verifier, hidden from the agent
├── solution/         reference solution
└── trials/
    └── opus-5-5/     Claude Code trials with claude-opus-5-5
        └── <trial>/  one scored trial
```

## Reproduction

Each task directory is a complete Harbor task: `task.toml` is the runner manifest, `instruction.md` the objective, `environment/` the sandbox image (the two live-estate tasks also run a service sidecar the agent reaches through the `raven-ar9` MCP server), `tests/` the verifier, and `solution/` the reference solution. The trials above were produced with:

```bash
harbor run -p <task-dir> -a claude-code -m anthropic/claude-opus-5-5
```

Run `harbor run -p <task-dir> -a oracle` to score a task's reference solution. The verifier's LLM-judged rubric uses `gpt-6.1-sol` through an OpenAI-compatible endpoint.

## Cite

A citation for Raven will be published here once it releases its first evidence-backed dataset. The grounding benchmark it builds on is Gaia2 / ARE.

```bibtex
@misc{are2026,
  title        = {ARE: Scaling Up Agent Environments and Evaluations},
  author       = {{Meta FAIR}},
  year         = {2026}
}
```

## Contact

Raven Gaia2 is built by [Ethara.AI](https://github.com/Ethara-Ai). For questions about the benchmark or dataset, contact [research@ethara.ai](mailto:research@ethara.ai).

Copyright (c) 2026 Green Rider Technology LLP (Ethara AI). All rights reserved.
