# Google Workspace sign-in and investor showcase

This is a hardened synthetic-data research demonstration, not a clinically validated product. OAuth implementation is complete; live provider activation and hosted verification require the operator's Google registration and infrastructure.

## Activate Google Workspace sign-in

1. Register a Google Cloud OAuth **Web application** client. Configure the consent screen and permitted test users/internal audience. Register the exact callback `https://YOUR_HOST/v1/auth/callback`. No wildcard callbacks. Sign-in scopes are only `openid email`; this does not request Drive, Gmail or clinical data access.
2. Copy `.env.production.example` to `.env.production`. Set the public HTTPS origin, client ID, Workspace domain and local secret-file path. Store the Google client secret as the file contents (no quotes/newline required). Never paste secrets into chat, commit them, put them in browser code, or include them in a demo recording.
3. Copy `config/members.example.json` to `config/members.json`. Use actual invited email addresses and UUIDs. Set roles to `clinician` or `viewer`. For a clinician's existing local encounters, use that clinician and tenant UUID from local configuration without exposing the access key. A viewer may deliberately map to the prepared synthetic demo clinician's UUID to inspect the same encounters. Different mappings remain isolated by existing authorization checks.
4. Set `sub` to the Google account subject when known. Otherwise omit it: the first verified invited sign-in pins email to its Google subject in the database; subsequent subject changes are denied. Invitations are checked on every request, so removing a user revokes access immediately. Changing a pinned subject requires an operator-reviewed database migration, not automatic reassignment.
5. Run `docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml config --quiet`, then start it behind an operator-controlled HTTPS reverse proxy. The API remains bound to host loopback; the proxy must preserve the exact public Host header. Google token/certificate validation needs outbound HTTPS from the API. The worker and database stay on the private network. Provision the database password using the template. Confirm secret/membership file permissions for UID 10001.
6. On loopback development only, use `MED_TRANSCRIPT_AUTH_MODE=google` with `MED_TRANSCRIPT_PUBLIC_ORIGIN=http://127.0.0.1:8002` and the matching registered callback, client credentials/secret file, domain and invitations. Set `MED_TRANSCRIPT_ENV=production` only with HTTPS. The default local-key development mode continues to work exclusively on loopback.

Google configuration reference: https://developers.google.com/identity/openid-connect/openid-connect

## Implemented controls

- Authorization code flow with S256 PKCE, random nonce, single-use five-minute state and an HttpOnly browser binding cookie. Fixed Google endpoints; no user-supplied issuer or token endpoint.
- Google's official verification library validates signatures, issuer, audience, issued-at and expiry; app additionally checks nonce, authorized party, verified email and Workspace hosted domain. Uninvited users are denied. No provider access/refresh tokens or ID tokens are persisted.
- Opaque server-side sessions, hashed session identifiers in storage, Secure/HttpOnly/SameSite cookies on HTTPS, eight-hour absolute and thirty-minute idle expiry, rotation on sign-in and revocation on local sign-out. Signing out of this app does not sign out of Google.
- Exact-Origin and CSRF token checks for cookie-authenticated writes. No session tokens in browser localStorage. Multiple API processes share persistent flow/session/throttle records.
- Read-only investor accounts cannot create, modify, process, approve, export-new-artifacts or delete encounters. Only clinicians can perform authenticated writes. Approval is still bound to exact source, note and verification versions.
- Streaming request bounds (8 MiB for JSON; 512 MiB for audio), including chunked bodies without a Content-Length header.
- Login/callback throttling, sanitized authentication errors, no-store responses, CSP, anti-framing, content sniffing protection, microphone-only permissions and hosted HSTS. Production disables API schema/docs, rejects unexpected Host headers and ignores local bearer keys.
- Public binding requires production Google mode; the launcher no longer prints access keys. Container deployment uses non-root processes, read-only root filesystems, private database/worker network, dropped capabilities, resource limits and a mounted secret file.

## Operator checks before an investor session

- Use an isolated synthetic-only database and asset volume. Prepare an encounter and source-linked note with a clinician account; invite viewers to that synthetic demo identity. Do not reuse clinical or personal recordings.
- Verify actual Google login/callback, viewer denial of edits/approval, clinician write access, sign-out, invitation revocation and reload after idle expiry on the chosen HTTPS domain. Automated tests use a simulated provider plus real cryptographic verification; they are not a live Google acceptance test.
- Enforce HTTPS redirects, bounded upload sizes/timeouts and connection/rate limits at the reverse proxy. Keep proxy access logs from recording OAuth callback query strings. Trust only configured proxy addresses; restrict inbound traffic to the proxy. Run a deployment-specific security review.
- Test encrypted backups/restore and retention/deletion with the new database migration. Backups now contain authentication flow/session records and invitation email/subject bindings; handle them as sensitive. Protect database/storage with encryption, limited access and a documented key custodian. Use dedicated demo credentials; rotate/revoke them after the event.
- Do not expose a public anonymous demo. No medical regulatory, privacy-law or security certification is claimed. No qualified independent clinical reviewers, pilot institution, country approval or real hardware validation has been supplied.

## Five-minute investor demonstration

1. **Problem:** documentation competes with attention during a consultation. Present correction-time savings as a study hypothesis, not an achieved result.
2. **Workflow:** sign in, open a prepared detailed public mock consultation, play a cited source interval and inspect its note statement.
3. **Trust:** show uncertainty and severity warnings, a preserved correction/version comparison, and exact-version clinician approval. An investor viewer observes these prepared records; the clinician presenter performs any live edits.
4. **Evidence:** show the study dashboard's completed and failed experiments, evidence hashes and the unchanged 5% WER gate. No model is promoted unless it satisfies the real requirements. Reference-transcript demos are labelled and are not live ASR results.
5. **Ask:** seek clinical research partners and evaluation resources to establish accuracy, omissions, correction time and usefulness. Keep model quality, clinical validation and security deployment work as separately measured milestones.

The prototype demonstrates a reviewable workflow and engineering controls. Clinical effectiveness, time savings, hardware suitability, tenant deployment readiness and receiving-EHR compatibility remain unproven until their respective acceptance checks are performed.

## No domain or Workspace account yet

The demo can run on `http://127.0.0.1:8002` without buying a domain or hosting. Register an OAuth web client with the exact callback `http://127.0.0.1:8002/v1/auth/callback`, configure the consent screen/test users, and set client ID plus a local client secret file and membership file. Leave `GOOGLE_WORKSPACE_DOMAIN` empty to allow only explicitly invited, verified personal `gmail.com`/`googlemail.com` accounts. Third-party-domain Google accounts are rejected in this mode; use a matching Workspace domain for those. This avoids treating a non-authoritative external email claim as ownership proof.

Set `MED_TRANSCRIPT_AUTH_MODE=google` and `MED_TRANSCRIPT_PUBLIC_ORIGIN=http://127.0.0.1:8002` for loopback development; do not set production mode for HTTP. The launcher refuses public binding in this mode. If OAuth credentials have not been registered, continue the local-key demo and describe Google sign-in as implemented but not yet activated. No Google credentials or hosted domain were supplied for this release, so live provider authentication and public deployment are not claimed.
