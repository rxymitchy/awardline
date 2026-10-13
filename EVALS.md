# Evaluation

Run `python -m awardline eval`. Eight tasks pass. T9 fails on purpose and is not fixed.

The snapshot behind the agent is 4,956 Kenya PPIP awards from the 2025/2026 and 2026/2027 release packages. The tasks below use a small fixed history so the numbers do not move when the portal updates. T9 is the real gap in supplier matching.

| Task | Result | What it checks |
| --- | --- | --- |
| T1 search finds a buyer | pass | A buyer name returns that buyer's awards |
| T2 search with no clue asks again | pass | An empty search returns an error the agent can recover from, instead of a guessed list |
| T3 a quote at 4x median is flagged and sourced | pass | KES 500,000 against a median near KES 102,500 is flagged, and every source has an OCID |
| T4 a quote near the median is not flagged | pass | KES 100,000 is reported as within range, still with sources |
| T5 thin history does not flag | pass | Three comparables is not enough. No flag |
| T6 draft cites flag sources and refuses to invent | pass | The note contains each OCID from the flag. A different purchase with no flag is refused |
| T7 filing without an officer is refused | pass | The file is not written |
| T8 an approved note can be filed | pass | Officer Amina Yusuf's approval lets the note through, and the OCID is in the file |
| T9 supplier Ltd and Limited are still different | fail | `KIOLI INVESTMENTS LIMITED` and `Kioli Investments Ltd` are not treated as one supplier |

## T9, left unfixed

PPIP's supplier identifiers do not follow a usable scheme, so the name is the only key. Awardline only case-folds that name. `Ltd` and `Limited` stay different, which means a repeat award to the same firm can look like two suppliers.

Next attempt: strip `ltd`, `limited`, and `company` before comparing, then check the result against a handful of known pairs before using it in a finding. That is not done here, because a bad merge would attach a price flag to the wrong firm.

## Agent recovery

`tests/test_tasks.py` also runs the LangGraph loop against a scripted model. The model calls a tool that does not exist, then calls `search_awards` with no buyer and no description, then stops. Both errors are returned to the model. That test passes.

On the first live run, Qwen 2.5 3B searched the right purchase and then passed KES 200,000 for a KES 2,000,000 quote. The graph now returns that mismatch and asks for the amount in the request. A scripted test covers that refusal. The next live run copied KES 2,000,000.00, flagged it at 2.74 times the median of 12 published awards, and stopped before filing.
