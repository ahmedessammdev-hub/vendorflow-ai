# Acceptance evidence

Generated 2026-11-18T19:29:13+00:00 at commit `a05d0151a6785ecadf31d3a84a046bd8160ac188`. Windows-11-10.0.26300-SP0, AMD64, Python 3.12.14, Node v24.19.0.

Local gates use Jira simulation. Randomized tests and load measurements use offline or fixture AI. Load measurements use 200 observations per endpoint through in-process ASGI and include background work. The separate live evaluation used auto at `2c58be43293bafa17a3f8db5817e623eda63fb35`, 20/20 cases attempted.

| ID | Result | Executed evidence |
|---|---|---|
| VF-01 | PASS offline | `test_vf01_draft_persists_across_new_engine_and_html_is_text`, `test_vf01_field_validation_and_body_limits` |
| VF-02 | PASS offline | `test_vf02_return_correct_resubmit_and_vf03_risk`, `test_vf03_score_and_vf02_checklist` |
| VF-03 | PASS offline | `test_vf02_return_correct_resubmit_and_vf03_risk`, `test_vf03_score_and_vf02_checklist` |
| VF-04 | PASS offline | `test_vf04_bounded_and_grounded_vf05_paused`, `test_vf04_sdk_contract_and_fallback`, `test_vf04_submit_sends_202_before_model_finishes`. See the separate live results in [metrics](metrics.md). |
| VF-05 | PASS offline | `test_vf04_bounded_and_grounded_vf05_paused`, `test_vf05_vf09_vf10_random_action_sequences` |
| VF-06 | PASS offline | `test_vf06_interrupted_model_call_is_not_sent_again`, `test_vf06_restart_and_vf09_concurrent_approvals`, `test_vf06_under_review_and_committed_before_resume_recovery` |
| VF-07 | PASS offline | `test_vf07_simulated_reconciliation_and_confirmation` |
| VF-08 | SKIPPED live | Requires explicit approval for one issue in a test project. |
| VF-09 | PASS offline | `test_vf05_vf09_vf10_random_action_sequences`, `test_vf06_restart_and_vf09_concurrent_approvals`, `test_vf09_crash_after_remote_create_reconcile_after_restart`, `test_vf09_delivery_matrix_vf10_sanitized` |
| VF-10 | PASS offline | `test_vf05_vf09_vf10_random_action_sequences`, `test_vf09_delivery_matrix_vf10_sanitized`, `test_vf10_configured_modes_expose_only_public_fields`, `test_vf10_nested_secrets_and_values_redacted`, `test_vf10_restrict_site` |
| VF-11 | PASS offline | `test_vf11_metrics_and_checklist_reflect_workspace`, `test_vf11_modes_without_credentials` |

[Commands, exit codes and measured targets](metrics.md) · [Browser captures](screenshots/)
