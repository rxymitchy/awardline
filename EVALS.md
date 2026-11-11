# Evaluation

Run `python -m awardline eval`. All eleven tasks pass. `python -m pytest` runs the same tasks plus tests of the agent loop, the officer gate, and the snapshot refresh.

The snapshot behind the agent is 4,956 Kenya PPIP awards from the 2025/2026 and 2026/2027 release packages. The tasks below use a small fixed history so the numbers do not move when the portal updates. T9 and the supplier test in `tests/test_tasks.py` also check supplier matching against spellings taken from the real snapshot.

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
| T9 supplier Ltd and Limited are one firm, known different firms stay apart | pass | `KIOLI INVESTMENTS LIMITED`, `Kioli Investments Ltd`, and `M/S KIOLI INVESTMENTS LIMITED` match. `Kioli Holdings Ltd`, a `(KENYA)` or `(K)` variant, and an empty or suffix-only name do not |
| T10 a loosely related award is not used as a comparable | pass | A fuel quote is compared only with fuel awards. Tyre awards that share "motor vehicles" are left out, and each source lists the words that matched |
| T11 supplier history merges spellings and shows them | pass | The note lists both spellings it merged for the quoting supplier and leaves out a different firm with a similar name |

## T9, fixed

PPIP's supplier identifiers do not follow a usable scheme, so the name is the only key. `supplier_key` now ignores case, punctuation, a leading `M/S` or `Messrs`, a trailing postal address, and the legal-form words `Ltd`, `Limited`, `Co`, `Company`, and `PLC`. It keeps every other word, including `Kenya`, `(K)`, and `Holdings`, because those can mark a different firm.

Before using it in a finding we checked it against known pairs in both directions: six spellings of one firm that must match, taken from the snapshot, and six pairs that must stay apart. Across the 4,956 awards it merges 190 groups of names that differ by more than case and spacing. We read all 190 and found no merge of two different firms. Near misses stay apart, such as `BRITAM GENERAL INSURANCE COMPANY` and its `(KENYA)` variant, and `STAR DISCOVER INSURANCE` and `STAR DISCOVERY INSURANCE`. Supplier history is shown on the note with every name it merged, so the committee can see a bad merge, and it never raises or removes a price flag.

## Agent recovery

`tests/test_tasks.py` also runs the LangGraph loop against a scripted model. The model calls a tool that does not exist, then calls `search_awards` with no buyer and no description, then stops. Both errors are returned to the model. That test passes.

On the first live run, Qwen 2.5 3B searched the right purchase and then passed KES 200,000 for a KES 2,000,000 quote. The graph now returns that mismatch and asks for the amount in the request. A scripted test covers that refusal.

That earlier demo compared a fuel quote with 12 awards, most of them tyre and repair contracts that shared only "motor vehicles". With rarity weighting, that purchase has a single genuine comparable, so it now gets no flag, and the demo picks a purchase with enough real history: Kitui Water & Sanitation Company's work injury and group personal accident cover (WIBA/GPA), quoted by Jubilee Health Insurance.

Two live failures shaped the current agent. Qwen first left the supplier out of `flag_price_outlier`; the graph now returns that call and names the supplier from the request. The next run passed the supplier, but the full flag, with eight sources and the supplier history, overflowed Qwen's 4,096-token context and the model call timed out after 180 seconds. The model now sees a compact summary of each tool result, and scripted tests cover both changes.

The latest live run searched four times, called `flag_price_outlier` with KES 9,616,530.00 and `JUBILEE HEALTH INSURANCE LIMITED`, drafted the note, and stopped before filing, in about five minutes on CPU. The note flags the quote at 4.0 times the median of 8 published insurance awards, marks the one source won by the same supplier, and lists the two spellings of Jubilee Health Insurance it merged.
