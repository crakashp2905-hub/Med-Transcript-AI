# Local software and model inventory

The versioned machine-readable bundle is generated from checked-in Python/npm manifests, locally installed Python package metadata, the committed model registry and access audit, and local dataset license notices:

- [CycloneDX-style Python and npm SBOM](../evaluation/supply-chain/sbom-v1.json)
- [License metadata register](../evaluation/supply-chain/license-register-v1.json)
- [Model cards](../evaluation/supply-chain/model-cards-v2.json)
- [Internal architecture control matrix](../evaluation/supply-chain/architecture-compliance-matrix-v1.json)

The SBOM is an inventory, not a vulnerability scan. The local Python inventory includes packages installed in the execution environment and can therefore contain tooling beyond the declared application dependencies. The npm section comes from the committed `package-lock.json`; no registry request or package installation is performed.

The license register reports metadata as found in local package metadata and the candidate-access audit. `unknown`, `other`, and `review_required` remain explicit. A declared identifier is not a license compatibility opinion or a conclusion about commercial rights. Model weights are not included. Dataset notice files are hashed, but their presence does not establish rights to a particular use.

The architecture matrix is an internal engineering crosswalk. It names implementation files, tests, limitations, and external gates. It does not map to a regulatory framework or claim HIPAA, SOC 2, medical-device, FHIR receiver, or other certification. Independent clinical review, institutional security/privacy approval and receiver-specific EHR validation remain open.
