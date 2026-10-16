# Privacy rules for journal-article-review

These rules ship with the installed creview package. Hermes's skill self-improvement does not edit
them, so follow them even where the skill text says otherwise.

## Before reading a manuscript

- `creview session start` must pass first. If it fails, stop and report its error. Do not work
  around it, and do not install packages, alter profiles, switch providers, or use cloud fallback.
- Ask the user to confirm that the journal permits this local AI assistance, or that permission was
  obtained, unless the current conversation already states that explicitly. Accept only an
  explicit, case-specific reply and record it verbatim. Silence, earlier reviews, or the review
  request itself are not confirmation.

## Confidential material

- Do not call any network-capable command directly: no web tools, `curl`, `wget`, `ssh`, remote
  APIs, or another agent or provider.
- Do not send manuscript text, excerpts, claims, titles, author identities, or review findings to
  an external service.
- Do not put manuscript text in shell arguments.
- Keep confidential material in the current Hermes conversation, its attached local files, a
  user-selected local export, or the optional private case store.
- When you improve this skill or its reference files, write only generic lessons. Do not include
  manuscript text, quotations, titles, topics specific enough to identify the work, author or
  institution names, or review findings. Skill files may be committed to version control and shared.

## External scholarly lookup

External lookup is disabled until the exact outbound request is persisted and displayed.

- For an individual literature query, create it with `creview lookup request`, show its provider,
  query, and URL, wait for explicit approval, then record the reply and run only that request.
- For requested mechanical metadata verification, create a frozen manifest with
  `creview references request-metadata`. Show every query and URL in that manifest. One explicit
  approval covers only that exact set; any change requires a new manifest and approval.

Never add, reformulate, or retry a different query under an existing approval. Crossref and
OpenAlex results are bibliographic identity evidence only. They do not verify a work's substantive
claims; request the source itself when that verification matters.

## What these rules are

They are instructions, not enforcement. `creview` enforces only its own actions: it never sends
manuscript text to a model, keeps its store private, and runs lookups only from an approved
request. The profile's model routes are checked when `creview` runs, not during the session. Only
network isolation of the Hermes host can stop a command from reaching the internet.
