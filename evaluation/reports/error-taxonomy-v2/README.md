# Saved public-mock error diagnostics

PriMock57: A Dataset Of Primary Care Mock Consultations, Alex Papadopoulos Korfiatis, Francesco Moramarco, Radmila Sarac and Aleksandar Savkov (2022), Babylon Health. CC BY 4.0. Source: https://github.com/babylonhealth/primock57; MedDistractAudio: Vishwanath et al. (2026), https://huggingface.co/datasets/NYU-OLAB/MedDistractAudio

CSV contains every non-match token edit for all saved cases, including failed and partial runs. Case accounting, hashes, role buckets and CER denominators are in report.json. Extract the complete CSV with `python -m zipfile -e all-errors.csv.zip DESTINATION`; its uncompressed SHA-256 is in report.json. This is retrospective development analysis, not an independent acceptance cohort or clinical gold. No primary references or WER gates were changed.
