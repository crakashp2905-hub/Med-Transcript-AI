# Local clinical draft recovery

Unsaved transcript and note edits are debounced to browser IndexedDB while an
encounter is open. The draft is keyed by tenant, clinician and encounter, and
records the transcript and note version IDs against which it was edited. After
a reload, the application restores the draft only when both version IDs still
match. A mismatched or older than 30-day draft is discarded with a visible
message. Saving a new source or note version clears the matching local draft.
The clinician can also discard local changes and reload the saved server
version.

The browser reports whether edits were saved locally, recovered, discarded, or
could not be stored. Local recovery does not create a server note, approval or
export, and does not work across devices or browser profiles. A successful
server save remains the authoritative version.

IndexedDB data is not encrypted by this feature. It is accessible to the
operating-system account and same-origin application code in the browser
profile. Drafts may remain on disk until the encounter is reopened and expired
data is removed, or the browser profile is cleared. This is synthetic
development behavior only; institutional storage, retention, encryption and
endpoint controls remain necessary before any real-patient use.

The focused browser regression edits a synthetic source, reloads the page,
reauthenticates, and confirms the matching unsaved version is restored. See
the commit-bound acceptance report generated with that change for exact source
and artifact hashes.
