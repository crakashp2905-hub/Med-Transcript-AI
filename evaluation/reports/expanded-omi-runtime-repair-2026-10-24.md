# Omi expanded-run runtime repair

The first complete attempt processed 118 clips and scored all reference words. Its first 36 clips succeeded; the remaining 82 failed after the Windows DLL search-directory limit was reached (`WinError 206`) while repeatedly constructing the Omi C API. The first attempt's normalized WER was 1,617/2,264 = 71.42%, with failures retained as full-reference deletions. It failed the quality gate.

The complete failed attempt is preserved at `evaluation/runs/primock57-expanded-v1/attempts/omi-med-stt-v1-windows-dll-registration-failure.json`, SHA-256 `6b19760cde34c4cc2185483ac92cd5cce4b574c2d2ec0fefcb23567345a86abf`.

Inspection of pinned omi-med-stt 0.2.1 showed that `_ParakeetCAPI.close()` frees the model context but does not close its `os.add_dll_directory` handles. Calling the top-level transcription helper separately for each clip therefore accumulated registrations. The six- and thirty-clip earlier runs were too short to expose the limit.

The project-owned adapter now loads the pinned CPU C API once, keeps it for the whole benchmark, and explicitly closes the Windows directory handles after freeing the model. It uses the same GGUF artifact, four CPU threads, TDT decoder, PCM conversion and unknown-token rendering as the pinned wrapper. Automatic installation and hosted inference stay disabled. The new runtime configuration records `adapter_revision: reuse_capi_close_windows_dll_directories_v1`, giving the repaired configuration a distinct profile hash. The vendor package was not edited.

The repaired configuration is rerun on **all 118 clips**. The first attempt is not silently overwritten or mixed with selected successful rerun clips. The main ranking uses the full repaired attempt and links to this repair record. Any failures remaining after repair still fail the 5% gate and count as full-reference deletions. This is a loader lifecycle fix, not a model, reference or scorer change.

A partial repair probe completed 16 clips successfully, then was deliberately stopped when it overlapped both original workers during large-v3 initialization and available physical memory dropped to about 326 MB. Its log remains under ignored data storage; it contributes no quality result. The entire repaired Omi run is scheduled after the other lanes, avoiding that extra concurrency.

The 16 successful partial-probe status lines are preserved in `evaluation/runs/primock57-expanded-v1/attempts/omi-med-stt-v1-memory-interrupted.log`; they contain no scored hypotheses and are excluded from the main comparison.
