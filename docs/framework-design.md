# Framework design

Why the project is built the way it is. The README says what it does and how to run it.

## 1. Goals

1. Show how to test the parts of an AI product that ordinary test suites miss: retrieval, grounding, tool use and
   guardrails.
2. Keep every number honest: measured from code that ran, repeatable, with its limits written next to it.
3. Run anywhere for free, so anyone can reproduce a result with one command.

## 2. The parts

| Part | Role |
|---|---|
| `src/deskbot/knowledge.py` | Loads documents; drops replaced sections and sections in quarantine |
| `src/deskbot/retriever.py` | BM25 search, with the access rule applied first |
| `src/deskbot/answerer.py` | Declines, abstains, or answers with one sentence and its citation |
| `src/deskbot/tools.py` | The tools and the order data |
| `src/deskbot/agent.py` | The loop and every guardrail |
| `src/deskbot/planner.py` | The rule-based planner |
| `src/evals/` | Suites, graders, redaction, gate and report |
| `datasets/` | The knowledge base and the four case files |
| `configs/` | Run settings and gate limits |

## 3. Why no language model

A model would need a key, would cost money, and would give different results on each run. Sample answers written by hand,
the other way to run offline, would only test the checks, because nothing real would produce them.

So Deskbot is a real system without a model: its retrieval is genuine, and its failures are genuine. The price is that it
can't fail the way a model fails. It can't invent a sentence, so `tests/evals/` plants invented answers to prove the
grounding check works. It can't be persuaded, so `ScriptedPlanner` plays a model that has been.

## 4. Retrieval

BM25 is written out in about 40 lines, so a score can be explained. Title words count double. A small list maps known
synonyms, and that list was not extended to make the robustness cases pass: those cases exist to show what keyword search
can't do.

The access rule runs before scoring. Anything retrieved can reach an answer, so a filter after ranking would be one bug away
from a leak.

## 5. When to say nothing

The assistant answers only if the best section scores at least `min_score` and shares at least `min_terms` different words
with the question. The second rule came from the evals. "What is your head office telephone number?" scored well against
lost parcel claims, because "number" is rare in the documents. One shared word isn't evidence, however rare.

## 6. A miss and a wrong answer aren't the same

"I don't know" sends a customer to a person. A confident wrong answer sends them away with false information. So the suites
count `no_wrong_answer` apart from `answer_correct`. On the reworded questions, 53 % are right and 87 % aren't wrong.

## 7. Guardrails live outside the planner

In a real product the planner is a model, and it can ask for anything. So `agent.py` checks each call, in this order: the
tool exists, the arguments have the right names and types, the order belongs to the user, and a refund is positive and within
the limit. Then:

- A permission failure ends the run, because trying other things after a refusal is how data leaks.
- The same call twice stops the run: it can't give new information.
- A step limit stops plans the repeat check can't catch.
- A timeout is retried only for tools that change nothing. A timeout doesn't say the change failed, so a retry could refund
  twice (`TC-512`).
- The refund limit is per order, or several small refunds would get round it (`TC-507`).

## 8. The gate

`configs/quality_gate.toml` holds a minimum for every measure. Two checks stop a quiet pass: a suite with fewer cases than
`min_cases` fails, and a measure that wasn't produced fails instead of being skipped.

The robustness limits are a baseline, not a target. They sit just under today's values, and the comment in the file says so.

## 9. What the evals found

**Answers from one shared word.** The first run answered "What is your head office telephone number?" with lost parcel
claims. Fixed with `min_terms`.

**A staff question leaked into a wrong answer.** "When do accounts go to fraud review?" got the section on deleting accounts.
Nothing secret was shown, but a customer got a wrong answer. The same fix covers it.

**A weak stemmer.** "request" didn't match "requested", so the refund question found the account section. The stemmer now
handles `-ed` and `-ing`.

**A bug in my own grader.** The security suite showed 40 % grounded, because a polite refusal counted as an ungrounded claim.
Only an answer makes a claim, so `is_grounded` now checks `ANSWERED` only.

**A gap in the gate.** With quarantine switched off, the tests failed but the gate passed: no eval case reached the poisoned
section. `TC-311` now does.

## 10. How I know the tests can fail

I put 20 bugs in on purpose. The tests caught all 20, and the gate alone caught 8 of them, 9 once `TC-311` was added. The gate
measures behaviour on its cases, so narrow rules such as an off-by-one on the refund limit belong to the tests.

| Bug | Tests | Gate |
|---|---|---|
| Staff sections open to customers | Caught | Caught |
| Replaced sections stay usable | Caught | Caught |
| Quarantine off | Caught | Caught, after `TC-311` |
| One shared word is enough | Caught | Caught |
| Decline rule off | Caught | Caught |
| Answer adds an invented sentence | Caught | Caught |
| Wrong citation | Caught | Caught |
| Ownership check removed | Caught | Caught |
| Run continues after a block | Caught | Caught |
| Limit per refund, not per order | Caught | Not caught |
| Refund limit off by one | Caught | Not caught |
| `True` accepted as an amount | Caught | Not caught |
| Extra arguments allowed | Caught | Not caught |
| Loop check removed | Caught | Not caught |
| Changes retried after a timeout | Caught | Not caught |
| Over-refund check removed | Caught | Not caught |
| Grounding grader always passes | Caught | Not caught |
| Missing metric passes the gate | Caught | Not caught |
| Case count not checked | Caught | Not caught |
| Traces not redacted | Caught | Not caught |

## 11. Limits

- No model, so nothing here says how one behaves.
- The RAG cases were written from the documents the retriever was tuned on. There's no held-out set.
- The injection filter is a word list. It stops the obvious, not a determined attacker.
- `TC-513` shows the rule planner ignores text in tool answers, which a model might not.
- 21 sections is tiny. Retrieval quality on thousands of documents is a different question.
- No model-based judge. My llm-feature-testing repository covers that, including calibration against human labels.
