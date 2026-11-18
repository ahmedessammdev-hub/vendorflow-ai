# Reviewing the model output

For the paired run on the updated prompt, see [fixed model vs. automatic routing](routing-comparison.md). The case analysis below covers the earlier baseline.

The archived FreeLLMAPI run used the requested alias `auto`. It returned a valid summary on 13 of 20 cases and a grounded recommendation on 13 of 20. Both were available together on 7 cases. Eight recommendations matched the expected label. That is 8/13 conditional on the reviewer having a usable recommendation and 8/20 across the submitted workload. The archived NVIDIA run stopped after the first case returned no usable stage. Its single attempted case cannot support a provider ranking.

Source revisions are `2c58be4` for FreeLLMAPI and `b5857ce` for NVIDIA. Reproduce the counts from the repository root with `uv run --project backend python scripts/compare_evals.py docs/evaluation.json docs/evaluation-nvidia.json`. The original case-level artifacts include per-attempt outcomes, model names and latency. [FreeLLMAPI run](evaluation.json) · [NVIDIA run](evaluation-nvidia.json)

## Where recommendations diverged

| Cases | Request evidence | Expected advice | Returned advice |
|---|---|---|---|
| G02 | Limited stationery work with public material and a declared registration | Approve for review | Request information |
| G04, G11 | A known geographic gap in critical recovery coverage, or sensitive access during emergency operations | Escalate | Request information |
| G09, G17 | Undisclosed hosting region, or an outstanding question about subcontractors | Request information | Approve for review |

These are comparisons against the prewritten synthetic labels. The archived run stored the label and validated citation result, without the model's full explanation. A matching citation checks the field and value against the request. Whether the citation supports the recommendation still needs human judgment. Across the archived FreeLLMAPI run, 13 attempts were unavailable and eight returned invalid output. Their detailed reasons were not recorded. [Labeled cases](../sample_data/eval/golden.jsonl)

## How to compare a new run

The revised prompt tells the model to distinguish a missing material fact from a known exposure. It leaves scoring, workflow transitions and human approval to the application. The original cases informed this revision, so a repeat measures regression on known cases. An independent set is needed to estimate generalization.

For a controlled comparison, use the same revision, input hash, prompt version, timeout and token settings for each requested model. Keep separate output files. Report the number of complete assessments, agreement across all submitted cases, agreement among usable recommendations and which models the gateway returned. Per-stage diagnostics capture a bounded reason for new failures. A model name on a failed call can be the requested alias.

The live harness supports `--review-samples .runtime/review-samples.json` for a local copy of validated synthetic outputs. For each sample, check whether the summary preserves the facts, the cited evidence supports the advice, and any missing information is stated accurately. Record a short supporting example for each disagreement. Keep raw service responses and credentials out of shared reports.
