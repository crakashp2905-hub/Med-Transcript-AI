"""Static subsystem capabilities with explicit evidence and execution limits."""


def build():
    return {
        "schema_version": "subsystem_capability_manifest_v1",
        "manifest_kind": "declared_capabilities_not_runtime_measurements",
        "asr": {
            "real_model_inference": {
                "availability": "conditional_on_registered_local_model",
                "runtime_marker": "transcript.provenance.inference_mode=real_model_inference",
                "inference_executed": True,
            },
            "synthetic_transcript_replay": {
                "availability": "synthetic_fixture_only",
                "adapter_marker": "provider_mode=synthetic_fixture",
                "inference_executed": False,
                "text_may_be_predeclared": True,
            },
            "silent_audio_transport": {
                "availability": "measured_pcm_silence_short_circuit",
                "runtime_marker": "digital_silence=true",
                "inference_executed": False,
                "transcript_text_generated": False,
            },
            "timestamped_output": "backend_dependent; only validated native or declared timestamps are exposed",
        },
        "drafting": {
            "default": "deterministic",
            "optional_model_processing": "explicit_opt_in_synthetic_sources_only",
            "clinician_approval": "required; model output is never an approved note",
        },
        "extraction": {
            "default": "deterministic_rules",
            "optional_local_model": "explicit_opt_in_synthetic_sources_only",
            "clinical_validation": "not_established",
        },
        "verification": {
            "deterministic_rules": "available",
            "optional_local_model": "synthetic_only_proposal",
            "model_can_clear_approval_gate": False,
        },
        "diarization": {
            "availability": "conditional_on_registered_local_artifacts",
            "speaker_role_assignment": "clinician_confirmation_required",
        },
        "limitations": [
            "The manifest describes declared behavior and is not proof that a model artifact is installed or that inference ran.",
            "Runtime inference provenance is recorded per transcript; fixture replay and measured digital silence are separately labeled.",
            "No entry establishes clinical accuracy, qualification, or deployment approval.",
        ],
        "clinical_release_authorized": False,
    }
