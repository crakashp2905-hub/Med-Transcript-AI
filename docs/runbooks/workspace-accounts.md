# Workspace account administration

This guide describes the current Google Workspace invitation prototype. It is
not a deployment approval or a claim that the account store is suitable for a
regulated production service.

## Configure the first administrator

1. Copy `config/members.example.json` to a protected local configuration path.
2. Set a unique tenant ID, a physician clinician ID, and a separate user ID for
   the administrator. Seed at least one physician and one administrator in the
   same tenant. The first verified Google sign-in can bind an omitted Google
   subject; after that, the subject is pinned to the account.
3. Set `MED_TRANSCRIPT_MEMBERS_FILE` to that file. The Google-authenticated API
   reads it at startup and on each request. The configured file must be writable
   for invitation and removal actions; the production Compose overlay mounts it
   read-write for this purpose.
4. Back up the file before changing it. Keep backups and host-level access logs
   under the clinic's access and retention controls. The in-file account audit
   is bounded to the latest 500 changes and is operational evidence, not a
   tamper-proof audit record.

## Roles

| Role | Workspace access |
| --- | --- |
| Physician | Prepare, review, approve and amend encounters scoped to the physician ID. |
| Scribe | Prepare and correct encounters scoped to the assigned physician; cannot approve, amend, revoke approval, or request encounter deletion. |
| Administrator | Invite and remove same-tenant accounts and inspect account audit events; cannot read encounter or study content. |
| Viewer | Read-only access limited to assigned synthetic encounters. |
| Legacy clinician | Retained as a migration-compatible physician-equivalent role. |

An administrator invites scribes and viewers by selecting an existing
physician. Each account has its own user ID; the assigned clinician ID is used
to scope its workspace. Removing an account deletes its invitation and stored
sessions; the next request also fails membership validation.

## Recovery and current limits

Before account changes, copy the membership file to a restricted backup
location. To restore, stop the API, restore the reviewed file with the original
owner and permissions, then restart and confirm `/health` and the account list
using a synthetic test account. Do not restore an old file without reconciling
its invitations and audit events against the latest authorized backup.

The current implementation writes the membership document atomically within a
single API process and serializes updates in that process. It does not provide
cross-process update locking, external audit immutability, administrator
provisioning recovery, or independent backup/restore evidence. Keep the API at
one worker while this file-backed implementation is in use. A clinic should
not treat these controls as completed operational readiness until those gaps
have been addressed and validated in its environment.
