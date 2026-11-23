# Editable preferences

The program reads UTF-8 text as configuration data; it never evaluates Python, shell commands, templates or expressions. Demo uses the explicit example file. Live use requires an explicit personal file such as ignored `preferences.txt`; there is no fallback to personal constants.

Create your file once from `preferences.example.txt` and edit it in a plain text editor. Keep the `.txt` extension (avoid `preferences.txt.txt`). Existing files are never written by the application. A missing/invalid file stops processing before Gmail authorization or workbook changes, with a numbered line and an English explanation. Input values/whole lines are not echoed in errors.

## Syntax

One setting/rule per line. Blank lines are allowed. A comment occupies an entire line beginning with `#` after optional indentation. Inline ` # comment` is rejected; `C#` remains a valid literal term. Keys are lowercase and case-sensitive. `=`, `|`, `||` and `;` are separators, not regex operators; do not use separators inside a term.

All five integer settings are mandatory:

```text
score_min = 0
score_max = 100
consider_score = 1
good_score = 15
strong_score = 30
```

Require `0 <= score_min < consider_score < good_score < strong_score <= score_max <= 10000`. A score below consider is Discarded; otherwise categories are Consider, Good and Strong at their respective thresholds. Values exactly at thresholds enter that category. Exclusions override this category.

| Rule | Meaning |
|---|---|
| `weight = 20 \| python` | Add +20 if this literal term matches. Negative points subtract. Nonzero integer points, -9999 through 9999. |
| `all = 15 \| python; automation` | Add +15 once when every term matches somewhere in the searched fields. |
| `pair = 9 \| csv; data cleaning \|\| api; pipeline` | Add +9 once if any term in the first group AND any in the second matches. |
| `cap = 12 \| spreadsheet \|\| python; api` | Cap the final score at 12 when any first-group term matches and no second-group term matches. Caps must be within the score range. |
| `exclude = unpaid trial` | Explicitly exclude a matching job regardless of positive scores. Keep the score and explanation, and route it to Discarded with Match = Excluded. |

The literal syntax inside the table escapes pipes for Markdown display; in the actual TXT file use ordinary `|` characters, as in the included example. No backslash escapes or quoted-string syntax is implemented. Duplicate normalized rules/groups, unknown keys, malformed numbers, empty terms and invalid thresholds fail explicitly. Terms are limited to 120 characters, the file to 64 KiB, and rules to 200.

## Matching and score order

Only **title, category, skills and description** are searched. Budget, sender, URLs, level and human notes do not influence scores. Text is case-folded, decomposed using Unicode NFKD and stripped of combining marks. Thus `Café` and `cafe` match; not every distinct Unicode letter is equivalent. Whitespace is collapsed. Literal phrases use flexible whitespace but preserve punctuation: `data cleaning` matches across a line break within a field, but not `data-cleaning`. Phrases do not cross field boundaries; combination rules may match terms in different fields.

Both ends of a match must be outside Unicode word characters (letters/digits/underscore). `python` does not match `pythonic` or `pre_python`; `api` does not match `apiary`. Regex metacharacters in terms are escaped: `C++` is literal. A repeated word fires a given rule only once, regardless of repetition or the number of matching fields. Separate overlapping rules can each fire; a keyword weight and an all-term combination intentionally add together.

First add all matching weight/all/pair points. Clamp to score_min/score_max. Apply matching caps using the lowest cap; then assign the category. Exclusions always route the row to Discarded. Explanations retain the configured term spellings, rule line numbers, signed points, raw and final score, and a 12-character SHA-256 configuration fingerprint. The fingerprint is not a security guarantee or a copy of the preferences file.

Each worksheet sorts by descending score, then platform text and canonical identity in ascending lexicographic order. Ties do not depend on email arrival order. They are a deterministic display order, not a claim that one tied opportunity is better. Duplicate identities are skipped before scoring; the first encountered opportunity supplies the stored details.

## Worked invented examples

Using the exact example file:

| Invented opportunity | Arithmetic | Result |
|---|---|---|
| Python CSV automation; category Automation; description includes API | Python 20 + automation 10 + API 8 + CSV 6 + all-term bonus 15 + paired-group bonus 9 | 68, Strong |
| Data cleaning helper; skills CSV, API | data cleaning 7 + CSV 6 + API 8 + paired-group bonus 9 | 30, Strong |
| Spreadsheet automation with no Python/API signal | spreadsheet 4 + automation 10, then cap 12 | 12, Consider |
| Unpaid trial API task; skills Python | unpaid -40 + API 8 + Python 20 = -12; clamp to 0; explicit exclusion | 0, Excluded |
| Documentation checklist with no configured matches | 0 | 0, Discarded |

Incoming jobs may be in Portuguese, English or another language. Use terms in the language actually present in those jobs; the program does not translate them. For example, a Portuguese term such as `automação` can match `automacao` under the normalization above. English interface/column names do not require English preference terms. Your matched terms may consequently appear in another language in your private score explanations.

Changing preferences does not silently rewrite historical scores. Existing rows retain their first-seen details, scores and explanations, including their prior fingerprint. To compare rules, run the offline fixtures into a different new workbook; preserve your live review history. No automatic historical rescore or merge of different live workbooks is implemented.
