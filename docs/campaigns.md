# Campaign lifecycle

```
draft -> generating -> ready -> sending -> sent
                             \-> failed
```

1. **create** — `POST /campaigns` with `name`, `tone`, `goal`.
   Status: `draft`.
2. **generate** — `POST /campaigns/{id}/generate` pulls profiles from
   info-broker and asks the LLM for one `{subject, body}` per profile.
   Drafts are saved with status `draft`. Failed generations are saved
   with status `failed` and an `error_message`. Campaign moves to
   `ready`.
3. **review** — `GET /campaigns/{id}/drafts`, then
   `PATCH /drafts/{id}` to edit subject/body, or
   `DELETE /drafts/{id}` to drop a draft entirely.
4. **send (dry-run)** — `POST /campaigns/{id}/send` with
   `{"provider":"dry-run"}`. Nothing leaves the box; each draft is
   logged and marked `sent` with a fake provider id.
5. **send (real)** — same endpoint with `{"provider":"smtp"}`. Per-row
   failures are caught and recorded; the loop never aborts.
6. **export** — `GET /campaigns/{id}/export?format=csv|xlsx|json`
   returns the drafts table for that campaign. CSV/XLSX values are
   escaped against formula injection.

The `dry-run` provider is the default everywhere. Real sending must be
explicitly opted in.
