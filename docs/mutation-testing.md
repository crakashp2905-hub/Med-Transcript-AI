# Critical-safety mutation contract

The mutation contract names deliberate bypass classes for medication/dose swaps,
negation flips, stale approvals and cross-tenant access. Each injected mutant
must produce a blocking guard result; a true/unknown result fails closed. This
is a deterministic mutation contract, not a claim that every possible code
mutation has been exhaustively generated.
