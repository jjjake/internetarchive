# Follow mode for archive.org task logs — design

**Date:** 2026-05-28
**Status:** Approved (pending spec review)
**Repo:** jjjake/internetarchive

## Goal

Let users monitor an archive.org task log live as the task runs — the
equivalent of `tail -f` — via the `ia tasks` CLI and the Python library. Today
you can fetch a whole task log (or a truncated one via `lines`), but there is
no way to follow it as it grows.

## Background / current state

- `ArchiveSession.get_task_log(task_id, *, params=None, request_kwargs=None)`
  and the static `CatalogTask.get_task_log(...)` fetch a task log. They do
  `r.content.decode('utf-8', errors='surrogateescape')` and **discard the
  `requests.Response`**, so the status code and `Last-Modified` header are
  unavailable to callers.
- `ia tasks -G <task_id>` fetches a log once and `sys.exit(0)`
  (`internetarchive/cli/ia_tasks.py:134-138`). It is already a standalone
  branch in `main()`.
- `-p/--parameter` passes query params to the Tasks API. `lines=N` returns the
  first N lines (negative N = last N).
- Endpoint: `https://catalogd.archive.org/services/tasks.php?task_log=<id>`,
  S3-authed.
- Task status is observable: `get_tasks(params={'task_id': ID, 'catalog': 1,
  'history': 1})` returns a `CatalogTask` whose `category`/`color` signals
  state (queued / running / paused = active; done / error = terminal). A
  finished task remains queryable when `history=1`.

## Decisions (settled during brainstorming)

1. **Stop condition: auto-stop on task completion.** Follow until the task
   finishes, then exit 0. Ctrl-C remains a clean manual exit. This requires a
   task-status poll (a second endpoint).
2. **CLI surface: a dedicated `--follow-task-log ID` option**, mutually
   exclusive with `-G/--get-task-log`. Avoids overloading `-G` and any
   flag-combination ambiguity.
3. **Fetch mechanism: full re-fetch + delta-print, with `If-Modified-Since`
   for a cheap `304` short-circuit.** No `Range`. Degrades gracefully if the
   server ignores `If-Modified-Since` (we just re-fetch and diff).
4. **No `Range` support, ever** — too low-level to surface to end users.
5. **No `--interval` flag.** Poll interval is hardcoded to **2 seconds**.
6. **`lines` composes and is respected literally** — same semantics as `-G`
   and the Tasks API (positive = first N, negative = last N; omitted = whole
   log). For tail-style behavior, users pass `-p lines=-10`. No sign
   reinterpretation.

## Architecture

Three layers, matching the existing library structure.

### 1. Low-level: response-returning helper

Extract the HTTP fetch out of `CatalogTask.get_task_log` into an internal
static helper that returns the raw `Response`:

```python
@staticmethod
def _request_task_log(task_id, session, *, params=None,
                      request_kwargs=None) -> requests.Response:
    ...
```

`get_task_log()` becomes a thin wrapper:

```python
r = CatalogTask._request_task_log(task_id, session, params=params,
                                  request_kwargs=request_kwargs)
return r.content.decode('utf-8', errors='surrogateescape')
```

**No public signature or behavior change.** Existing callers (including
`ia tasks -G`) are untouched. This is the smallest change that unblocks
follow mode's need for the status code and `Last-Modified` header.

Rejected alternatives:
- `return_response=True` kwarg on `get_task_log` → `Union[str, Response]`
  return type, mypy-hostile, easy to misuse.
- Public typed `TaskLog` dataclass → more surface than v1 needs. Deferred to a
  follow-up if library users ask for structured access.

### 2. Mid-level: the follow generator

```python
@staticmethod
def follow_task_log(task_id, session, *, lines=None,
                    request_kwargs=None) -> Iterator[str]:
    """Yield new task-log text as it is appended (tail -f style)."""
```

- `lines: int | None` — how much existing backlog to emit before following.
  Applied **client-side** to the first full fetch, replicating Tasks API
  semantics exactly (positive → first N lines, negative → last N lines,
  `None` → whole log). Never sent to the server (that would truncate the body
  and break the delta math).
- Follow always auto-stops when the task reaches a terminal state (there is no
  use case for following a finite log forever).

Algorithm:

1. **Anchor fetch:** fetch the full log via `_request_task_log` (no `lines`
   param). Let `body` be the decoded text.
   - Initial yield: `lines` applied client-side to `body` (whole log if
     `lines is None`).
   - `seen = len(body)` (decoded-string length — consistent because we always
     re-decode the whole body).
   - Store `Last-Modified` from the response.
2. **Loop** (every 2 s):
   - Fetch the full log, sending `If-Modified-Since` from the stored
     `Last-Modified`.
   - `304 Not Modified` → no new content this round.
   - `200` → decode `body`.
     - If `len(body) < seen` (rotation/truncation): reset `seen = 0` and yield
       the whole `body` (re-emit) — defensive, rare.
     - Else yield `body[seen:]` if non-empty; advance `seen = len(body)`;
       update stored `Last-Modified`.
   - **If nothing new this round:** poll task status. If
     terminal, do one final full fetch to catch trailing bytes, yield any
     remaining delta, then `return`. (Status is only polled when the log did
     not grow — while it is actively appending it is obviously still running,
     so we skip the extra request in the common case.)
   - `sleep(2)`.

Because every fetch decodes the **complete** body, a multibyte UTF-8 character
can never be split at a byte boundary — that whole class of bug (which
`Range`-based partial reads would introduce) does not exist here.

Status check uses `session.get_tasks(params={'task_id': task_id, 'catalog': 1,
'history': 1})` and inspects the returned task's `category`/`color`. Terminal =
done or error (not queued/running/paused).

A thin `ArchiveSession.follow_task_log(...)` wrapper mirrors the existing
`get_task_log` wrapper and delegates to `CatalogTask.follow_task_log`.

### 3. CLI

In `internetarchive/cli/ia_tasks.py`:

- Add `-F`/`--follow-task-log` (takes the task id) in an argparse
  **mutually exclusive group** with `-G`/`--get-task-log`.
- New branch in `main()`:

  ```python
  elif args.follow_task_log:
      lines = args.parameter.get("lines")  # may be str from -p; coerce to int
      try:
          for chunk in args.session.follow_task_log(args.follow_task_log,
                                                     lines=lines):
              sys.stdout.write(
                  chunk.encode("utf-8", errors="surrogateescape")
                       .decode("utf-8", errors="replace"))
              sys.stdout.flush()
      except KeyboardInterrupt:
          pass
      sys.exit(0)
  ```

  (Reuses the same `surrogateescape → replace` encoding dance the `-G` branch
  already uses, applied per chunk.)
- `-p lines=N` composes: `lines` is pulled out of `args.parameter` and passed
  through. Other `-p` params are not meaningful in follow mode and are ignored.
- No `--interval` flag.

## Error / edge-case handling

- **Ctrl-C:** caught in the CLI branch → clean exit 0. In the library, the
  generator simply stops being iterated; `KeyboardInterrupt` propagates
  naturally.
- **Task already complete when follow starts:** anchor fetch yields the
  backlog, first status poll sees terminal, generator returns. Behaves like a
  one-shot fetch.
- **Log rotation / shrink:** `len(body) < seen` → reset and re-emit.
- **Server ignores `If-Modified-Since`:** we always get `200` and diff
  normally — no harm, just no bandwidth savings.
- **HTTP errors:** `_request_task_log` calls `raise_for_status()` as today;
  the exception propagates.

## Testing

All tests use `responses`-mocked HTTP — no live calls. `time.sleep` is patched
so tests do not actually wait.

- **Delta:** successive bodies (`"l1\n"`, then `"l1\nl2\n"`) → generator yields
  `"l1\n"` then `"l2\n"`.
- **304 short-circuit:** a `304` response yields nothing that round.
- **Auto-stop:** mock the `get_tasks` status response as terminal → generator
  performs a final fetch and stops; assert it terminates.
- **`lines` seed:** `lines=-2` on a multi-line backlog yields only the last 2
  lines initially; `lines=2` yields the first 2; `lines=None` yields all.
- **Rotation reset:** a shorter body after a longer one → whole body re-emitted.
- **CLI:** `ia tasks -F ID` prints streamed output; `-G ID -F ID` errors via the
  mutually-exclusive group.

## Documentation / housekeeping

- Update the `ia tasks` docs page under `docs/source/` with `--follow-task-log`
  usage and the `-p lines=-N` tail idiom.
- Note the new follow capability in the internet-archive-skills doc
  (per CLAUDE.md's "Related" section) since the CLI interface changes.
- Add a `HISTORY.rst` entry under `5.10.0 (unreleased)`.
- Bump the dev version if needed per the versioning policy.

## Scope

**This PR:**
- `_request_task_log` helper refactor (no public change).
- `CatalogTask.follow_task_log` + `ArchiveSession.follow_task_log` wrapper.
- CLI `-F/--follow-task-log`, mutually exclusive with `-G`; `-p lines=`
  composition; hardcoded 2 s interval; auto-stop on completion.
- Tests, docs, `HISTORY.rst`, version bump.

**Deferred follow-ups (documented, not built):**
- A public typed `TaskLog` result object, if library users want structured
  access to status/headers.
- (No `Range` work — explicitly out of scope permanently.)
