# Release integrity gate

The release gate requires successful migrations, matching evidence hashes,
supported schemas, no stale approvals and complete critical verification. Any
missing/false prerequisite blocks the build; a model verdict cannot override
the gate. This engineering gate is separate from the external clinical-release
requirements, which remain blocked.
