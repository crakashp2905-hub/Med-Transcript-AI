# Troubleshooting

The demo reports failures explicitly and does not claim a recording or note was retained unless its state says so.

| Situation | Safe action |
|---|---|
| Local model unavailable | Select an installed model or keep the job queued; no cloud fallback is implied. |
| Microphone unavailable | Check browser permission and device selection; capture remains unstarted. |
| Disk full | Stop capture, preserve completed source state, free space, then retry. |
| Session expired | Re-authenticate; do not replay or publish a stale approval automatically. |
| Codec unavailable | Convert to a supported codec locally or fail safely with the codec reason. |
| Failed job | Inspect the stage and retry count; publication stays blocked until review succeeds. |
