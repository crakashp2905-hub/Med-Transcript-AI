# Service and endpoint catalog

Generated from the Python source tree. Runtime reachability is a static import analysis, not proof of actual invocation.

## Module classification counts

| Classification | Modules |
| --- | ---: |
| integrated-in-production-flow | 84 |
| candidate-only | 12 |
| test-only | 184 |
| documentation-only | 11 |

## Service modules

| Module | Classification | Basis |
| --- | --- | --- |
| `services/__init__.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/acceptance_audit.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/acceptance_materials.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/accessibility_checklist.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/adversarial_replay.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/anatomy_relations.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/annotation_workflow.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/api/__init__.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/auth.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/authorization_policy.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/api/contracts.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/idempotency.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/ingest.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/job_state.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/live_uploads.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/main.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/postgres.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/record_integrity.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/request_limits.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/resumable.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/router_context.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/routers/__init__.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/routers/audio.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/routers/authorizations.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/routers/encounters.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/routers/jobs.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/routers/transcripts.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/storage.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/api/time_utils.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/application_pipeline.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/artifact_provenance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/artifact_scope.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/artifact_summary.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/__init__.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/adapter.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/admission.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/adversarial_cases.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/audio_quality.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/audio_router.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/backend.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/candidate_receipt.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/channel_capability.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/channels.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/chunk_selection.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/clinical_entities.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/clinical_lexicon.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/config_inventory.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/context_biasing.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/context_handoff.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/error_review.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/evaluation_contract.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/hypothesis_disagreement.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/lexicon_bias_eval.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/metamorphic.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/number_format.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/omi_backend.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/parakeet_backend.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/pareto.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/postprocess.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/profiles.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/provenance.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/removal_propagation.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/resource_router.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/retranscribe_span.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/risk_selector.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/rover.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/segmentation.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/subgroup_diagnostics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/timeline.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/timestamps.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/transcripts.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/asr/vad_candidates.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/asr/worker.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/audio_enhancement.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/audio_enhancement_eval.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/audio_filter_benchmark.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/audio_provenance.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/audio_waveform.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/audit_integrity.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/baseline_summary.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/benchmark_integrity.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/benchmark_progress.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/benchmark_provenance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/benchmark_ranking.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/benchmark_suite.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/benchmark_text.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/bounded_queue.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/canonical.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/capability_manifest.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/channel_detectors.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/channel_diarization.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/channel_first_baseline.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/channel_scorecard.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/channel_signal_audit.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/chunk_integrity.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/ci_provenance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/clinical_attribution.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/clinical_evaluation.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/clinical_limitations.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/clinical_metrics.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/clustering_constraints.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/comparison_scope.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/completion_evaluation.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/component_ablation.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/config_fingerprint.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/consent_guard.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/context_effects.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/conversation_errors.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/conversation_experiment.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/corpus_partition.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/critical_mutation_campaign.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/data_provenance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/dataset_ledger.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/demo_fixture.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/demo_ingest.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/detailed_benchmark.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/detailed_campaign.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/detailed_diagnostics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/detailed_drafting.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/detailed_finalize.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/detailed_recovery.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/detailed_review_materials.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/device_profile.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/diarization.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/diarization_baseline.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/diarization_evaluation.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/diarization_policy.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/doc_integrity.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/domain_contracts.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/encounter_state.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/encrypted_backup.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/endpoint_policy.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/engineering_status.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/error_codes.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/error_taxonomy.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/evaluation.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/evaluation_method.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/evidence_graph.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/evidence_io.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/expanded_summary.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/experiment_contract.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/fact_duplicates.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/fact_provenance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/fault_injection.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/feature_flags.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/full_consultation_asr.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/full_empty_reconstruction.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/immutable_reports.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/import_boundary.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/inference_slot.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/input_limits.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/interruption_matrix.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/keyword_recovery.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/latency_targets.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/launch.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/local_cost.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/local_drafting_evaluation.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/log_redaction.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/long_recording_smoke.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/maintenance.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/master_ledger.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/master_matrix.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/master_release.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/media_decoder.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/media_formats.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/medication_status.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/memory_admission.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/method_comparison.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/metric_integrity.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/metric_validation.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/model_cards.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/model_init_metrics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/module_catalog.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/module_coverage_report.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/multichannel_smoke.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/mutation_contract.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/mutation_generators.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/negative_index.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/negative_results.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/note_diff.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/note_quality_metrics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/note_style.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/novelty_policy.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/offline.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/offline_acceptance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/offline_adapters.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/offline_demo.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/offline_preflight.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/offline_sbom.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/ollama_inventory.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/omi_adapter.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/omi_empty_reconstruction.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/omi_failure_probe.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/overlap_reassembly.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/paired_asr_bootstrap.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/paraphrase_cases.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/perturbation_cases.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/prepare_detailed.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/prepare_full_consultations.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/prepare_primock.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/prepare_validation.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/prompt_ablations.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/prompt_harness.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/prompt_injection.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/proposal_integrity.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/provider_interfaces.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/provision_benchmark.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/provision_public_diarization.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/provision_qwen_asr.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/publish_expanded.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/queue_dashboard.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/qwen_adapter.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/recorder_matrix.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/recovered_job_receipt.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/regression_gate.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/relation_tuples.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/relationship_evaluation.py` | `candidate-only` | not reachable from configured runtime roots or test imports |
| `services/release_attempt_summary.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/release_gate.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/release_policy.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/release_provenance.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/release_readiness.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/report_safety.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/repro_bundle.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/resource_arbiter.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/resource_stress.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/retention_state.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/retrospective_result.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/review/__init__.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/clinical.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/clinical_models.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/clinical_routes.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/comparison.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/engine.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/metrics_routes.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/models.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/presentation.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/providers.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/relationships.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/__init__.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/amendments.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/approvals.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/exports.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/history.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/notes.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/proposals.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/transcripts.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/verification.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routers/workspace.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/routes.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review/service.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/review_gate.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/review_readiness.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/role_correction.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/role_guard.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/route_authorization.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/runtime_benchmark.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/safe_pytest.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/sbom.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/secret_scan.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/source_change_detector.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/source_coverage.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/speaker_comparison.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/speaker_results.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/speaker_review.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/stage_timing.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/status_report.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/storage_lifecycle.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/stress_scenario.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/strict_json.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/study_analysis.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/study_dashboard.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/terminology_hints.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/throughput_measurement.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/turn_diagnostics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/turn_swap_guard.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/uncertainty_classifier.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/uncertainty_report.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/unmapped_terms.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/untrusted_input.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/usability_metrics.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/validation_summary.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/verification_ablations.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/verification_challenge.py` | `documentation-only` | referenced by documentation but absent from runtime and test import graphs |
| `services/verification_metrics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/verifier_selection.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/verify.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/verify_scribe_evidence.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/worker_loop.py` | `integrated-in-production-flow` | statically reachable from configured API or worker entry point |
| `services/worker_recovery.py` | `test-only` | imported by tests but not reachable from configured runtime roots |
| `services/workflow_metrics.py` | `test-only` | imported by tests but not reachable from configured runtime roots |

## Discovered HTTP endpoints

| Method | Path | Handler | Module |
| --- | --- | --- | --- |
| `GET` | `/` | `clinician_web` | `services.api.main` |
| `GET` | `/health` | `health` | `services.api.routers.encounters` |
| `GET` | `/v1/auth/callback` | `callback` | `services.api.auth` |
| `GET` | `/v1/auth/config` | `config` | `services.api.auth` |
| `GET` | `/v1/auth/login` | `login` | `services.api.auth` |
| `POST` | `/v1/auth/logout` | `logout` | `services.api.auth` |
| `GET` | `/v1/auth/session` | `session` | `services.api.auth` |
| `GET` | `/v1/deletion-requests/{rid}` | `deletion_status` | `services.review.routers.history` |
| `POST` | `/v1/demo` | `demo` | `services.review.routers.workspace` |
| `GET` | `/v1/demo-cases` | `demo_cases` | `services.review.routers.workspace` |
| `GET` | `/v1/encounters` | `list_encounters` | `services.review.routers.workspace` |
| `POST` | `/v1/encounters` | `create_encounter` | `services.api.routers.encounters` |
| `POST` | `/v1/encounters/{eid}/amendments` | `amend` | `services.review.routers.amendments` |
| `POST` | `/v1/encounters/{eid}/approvals` | `approve` | `services.review.routers.approvals` |
| `GET` | `/v1/encounters/{eid}/audio/{upload_id}` | `audio` | `services.review.routers.workspace` |
| `GET` | `/v1/encounters/{eid}/audio/{upload_id}/waveform` | `audio_waveform` | `services.review.routers.workspace` |
| `GET` | `/v1/encounters/{eid}/audit` | `audit_trail` | `services.review.routers.history` |
| `GET` | `/v1/encounters/{eid}/clinical-proposals/{pid}` | `proposal` | `services.review.clinical_routes` |
| `POST` | `/v1/encounters/{eid}/deletion-requests` | `delete_request` | `services.review.routers.history` |
| `POST` | `/v1/encounters/{eid}/draft-proposals` | `draft_proposal` | `services.review.routers.proposals` |
| `GET` | `/v1/encounters/{eid}/draft-proposals/{did}` | `get_draft_proposal` | `services.review.routers.proposals` |
| `POST` | `/v1/encounters/{eid}/drafts` | `draft` | `services.review.routers.notes` |
| `POST` | `/v1/encounters/{eid}/exports` | `export` | `services.review.routers.exports` |
| `GET` | `/v1/encounters/{eid}/exports/{xid}` | `download` | `services.review.routers.exports` |
| `POST` | `/v1/encounters/{eid}/fact-proposals` | `extract` | `services.review.clinical_routes` |
| `GET` | `/v1/encounters/{eid}/facts` | `facts` | `services.review.routers.transcripts` |
| `POST` | `/v1/encounters/{eid}/findings/{fid}/resolve` | `resolve` | `services.review.routers.verification` |
| `POST` | `/v1/encounters/{eid}/manual-transcripts` | `manual_transcript` | `services.review.routers.transcripts` |
| `GET` | `/v1/encounters/{eid}/notes/{before}/compare/{after}` | `compare_notes` | `services.review.routers.history` |
| `GET` | `/v1/encounters/{eid}/notes/{nid}` | `note` | `services.review.routers.notes` |
| `PATCH` | `/v1/encounters/{eid}/notes/{nid}` | `edit_note` | `services.review.routers.notes` |
| `POST` | `/v1/encounters/{eid}/retranscriptions` | `retranscribe` | `services.review.clinical_routes` |
| `GET` | `/v1/encounters/{eid}/review-sessions` | `sessions` | `services.review.metrics_routes` |
| `POST` | `/v1/encounters/{eid}/review-sessions` | `start` | `services.review.metrics_routes` |
| `POST` | `/v1/encounters/{eid}/review-sessions/{sid}/complete` | `finish` | `services.review.metrics_routes` |
| `POST` | `/v1/encounters/{eid}/semantic-checks` | `verify` | `services.review.clinical_routes` |
| `GET` | `/v1/encounters/{eid}/stream-uploads` | `pending` | `services.api.live_uploads` |
| `POST` | `/v1/encounters/{eid}/stream-uploads` | `create` | `services.api.live_uploads` |
| `GET` | `/v1/encounters/{eid}/stream-uploads/{uid}/recovery` | `recovery` | `services.api.live_uploads` |
| `POST` | `/v1/encounters/{eid}/stream-uploads/{uid}/seal` | `seal` | `services.api.live_uploads` |
| `PATCH` | `/v1/encounters/{eid}/transcripts/{tid}` | `edit_transcript` | `services.review.routers.transcripts` |
| `POST` | `/v1/encounters/{eid}/transcripts/{tid}/speaker-roles` | `speaker_roles` | `services.review.routers.transcripts` |
| `GET` | `/v1/encounters/{eid}/uploads` | `uploads` | `services.review.routers.workspace` |
| `GET` | `/v1/encounters/{eid}/verification` | `verification` | `services.review.routers.verification` |
| `GET` | `/v1/encounters/{eid}/versions` | `versions` | `services.review.routers.history` |
| `GET` | `/v1/encounters/{eid}/workspace` | `workspace` | `services.review.routers.workspace` |
| `GET` | `/v1/encounters/{encounter_id}` | `get_encounter` | `services.api.routers.encounters` |
| `POST` | `/v1/encounters/{encounter_id}/audio-uploads` | `create_upload` | `services.api.routers.audio` |
| `GET` | `/v1/encounters/{encounter_id}/audio-uploads/{upload_id}` | `get_upload` | `services.api.routers.audio` |
| `POST` | `/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/complete` | `complete_upload` | `services.api.routers.audio` |
| `PATCH` | `/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/content` | `append` | `services.api.resumable` |
| `PUT` | `/v1/encounters/{encounter_id}/audio-uploads/{upload_id}/content` | `upload_content` | `services.api.routers.audio` |
| `POST` | `/v1/encounters/{encounter_id}/authorizations` | `authorize` | `services.api.routers.authorizations` |
| `POST` | `/v1/encounters/{encounter_id}/authorizations/{authorization_id}/withdraw` | `withdraw` | `services.api.routers.authorizations` |
| `GET` | `/v1/encounters/{encounter_id}/processing-permission` | `permission` | `services.api.routers.authorizations` |
| `POST` | `/v1/encounters/{encounter_id}/transcriptions` | `create_transcription` | `services.api.routers.jobs` |
| `GET` | `/v1/encounters/{encounter_id}/transcripts/{version}` | `get_transcript` | `services.api.routers.transcripts` |
| `GET` | `/v1/jobs/{job_id}` | `get_job` | `services.api.routers.jobs` |
| `POST` | `/v1/jobs/{job_id}/retry` | `retry_transcription` | `services.api.routers.jobs` |
| `GET` | `/v1/session` | `session` | `services.review.routers.workspace` |
| `GET` | `/v1/study-dashboard` | `study_dashboard` | `services.review.routers.workspace` |

## Runtime roots

- `services.api.main`
- `services.worker_loop`

## Limitations

- Reachability is inferred from static imports, including function-local imports; it does not prove a helper was executed in production.
- Dynamic imports built from non-literal values may be missed; human confirmation is required before treating a module as deployed.
- Endpoint discovery reads FastAPI-style decorators and may omit routes registered by runtime-generated code.
