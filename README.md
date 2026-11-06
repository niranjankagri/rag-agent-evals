# Testing RAG and AI agents

[![CI](https://github.com/niranjankagri/rag-agent-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/niranjankagri/rag-agent-evals/actions/workflows/ci.yml)

How do you test an assistant that retrieves documents, and an agent that can move money? This repository tests **Deskbot**,
a support assistant for a fictional parcel company, with retrieval metrics, grounding checks, guardrail attacks and a
quality gate that fails the build. Python 3.13, pytest. It runs offline: no model, no API key, no cost.

| | |
|---|---|
| Eval cases | 61, in four versioned suites: RAG, robustness, security, agent |
| Tests | 142 with pytest, 99 % coverage |
| Guardrails | A planner that misbehaves on purpose: forbidden tools, bad arguments, endless loops |
| Gate | Limits per suite in `configs/quality_gate.toml`; a shrunken case file or a renamed metric fails too |
| Traces | One redacted line per case, kept as a CI artifact |
| Finding | Direct questions score 100 %, but reworded ones only 53 %, and 2 of 15 get a confident wrong answer |

**There is no language model here.** The answers are real, but they come from BM25 retrieval and sentence extraction, and
the agent's plans come from rules. That's on purpose: every number below is measured from code that really ran, and repeats
exactly. The graders and guardrails don't depend on how an answer was made, so a model could be swapped in behind the same
interfaces. My [llm-feature-testing](https://github.com/niranjankagri/llm-feature-testing) repository covers model judges
and sample-based evals.

## What the evals measured

| Suite | Cases | Measure | Result | Limit |
|---|---:|---|---:|---:|
| RAG | 25 | Recall at 3 | 1.000 | 0.95 |
| | | Mean reciprocal rank | 1.000 | 0.85 |
| | | Correct answers | 1.000 | 0.90 |
| | | Says "not found" when it should | 1.000 | 0.80 |
| | | Grounded in its citation | 1.000 | 1.00 |
| Robustness | 15 | Correct answers | 0.533 | 0.50 |
| | | No wrong answer | 0.867 | 0.85 |
| Security | 11 | Safe | 1.000 | 1.00 |
| Agent | 10 | Task success | 1.000 | 1.00 |

Read those with care. The RAG cases were written from the same documents the retriever was tuned on, so 100 % says it works
on what it was built for, not that it generalises. The robustness suite is the honest number. Keyword search can't connect
"fast option" with "express delivery", so 7 of 15 reworded questions fail: 5 say nothing, and 2 confidently give the wrong
section. Those limits sit just below today's values, so the gate stops things getting worse; it doesn't say this is good
enough to ship. The 7 cases are marked as known misses, and strict `xfail` fails the run if one starts to pass.

## Run it

```
python -m venv .venv
.venv/Scripts/activate              (Linux, macOS: source .venv/bin/activate)
pip install -e ".[dev]"
pytest                              all tests
python -m evals.run_evals           the four suites and the gate
```

The gate's table goes to `reports/summary.md`, and one redacted line per case to `reports/traces.jsonl`.

## What is tested

| Layer | Where | Tests |
|---|---|---:|
| RAG cases, determinism | `tests/rag/` | 27 |
| Reworded questions, conflicting sources | `tests/robustness/` | 17 |
| Access rules, injection, data leaks, redaction | `tests/security/` | 20 |
| Tasks: tools, status, final state | `tests/agents/test_agent_cases.py` | 14 |
| Guardrails against a misbehaving planner | `tests/agents/test_guardrails.py` | 20 |
| Retrieval building blocks | `tests/unit/` | 20 |
| Graders with planted bad answers, the gate | `tests/evals/` | 24 |

## The system under test

```
question -> decline rule -> retrieve (access rule first) -> enough evidence? -> sentence + citation
task     -> planner -> guardrails -> tool -> back to the planner, up to 6 steps
```

- **Knowledge base:** `datasets/knowledge/`, with a section for staff only, a section replaced by a newer notice, and a forum
  post containing a prompt injection.
- **Agent tools:** read an order, track a parcel, refund, cancel, escalate. Refunds over 50 euros per order go to a person.

The planner is the part a language model would play, so every rule sits outside it, in `agent.py`. A bad plan is stopped by
code, not by asking the planner to behave.

## Design

| Pattern | Where | Why |
|---|---|---|
| Versioned case files | `datasets/*.jsonl` | A new case is a new line, reviewed like code |
| Strategy | `Planner` | The real planner and the attacking one are interchangeable |
| Planted failures | `tests/evals/`, `ScriptedPlanner` | A check that has never failed proves nothing |
| Strict known misses | `tests/robustness/` | Weaknesses stay visible, and the list can't go stale |
| Gate as configuration | `configs/quality_gate.toml` | Limits are reviewed, and changing one shows up in a diff |

More in [docs/framework-design.md](docs/framework-design.md).

## Documents

- [Framework design](docs/framework-design.md): the decisions, and what the evals found
- [Manual test cases](docs/manual-test-cases.md): every case in plain language, by ID
- [Interview questions](docs/interview-questions.md) ([PDF](docs/interview-questions.pdf)): 60 questions on testing RAG and
  agents, answered with this project

## What this does not prove

Nothing here says how a real model behaves. A model can invent text, and this assistant can't; the grounding check is proven
only on planted answers. A model can also obey an injection, while the rule planner ignores all text in tool answers. So the
guardrails are tested against bad plans, but not against a model being talked into them. The knowledge base has 21 sections,
and the injection filter is a word list that a determined attacker can get past. Cost isn't measured, because nothing here
costs money.

## License

[MIT](LICENSE)
