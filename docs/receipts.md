# Export receipts

Every export writes a `receipt.json` beside the drafts, through `creview direct finalize EXPORT_ID`
after the agent writes them. Each receipt is also appended to the private local log
`receipts.jsonl` in creview's private store. Nothing is sent
anywhere.

A receipt records the creview version, a SHA-256 of the installed package's file list
(`sha256sum` format, excluding `__pycache__`), the model name, the endpoint as a category
(`loopback`, `private-network`, `hostname`, or `public`) rather than its address, the profile check
result, and for each exported draft both the file's SHA-256 and a `text_sha256`. The text hash is
computed after NFKC normalization and collapsing all whitespace, so text pasted into and copied back
out of a journal's submission system still matches while any change of wording does not. The
`receipt_id` is the SHA-256 of the receipt's sorted, compact JSON without that field.

Receipts also record the profile check's view of the skill's privacy block and a `preflight`:
whether `creview session start` passed in the session that exported (see
[Skill self-improvement](privacy.md#skill-self-improvement-and-the-privacy-block)).

Receipts are self-reported (`"attestations": [{"type": "self"}]`). They detect accidental change to
the exported text or the installed tool; they are not signed, so they do not prove that the tool was
unmodified or that no other AI tool was used.

## Verifying a receipt

Hermes's skill self-improvement never writes to the `creview` installation, but the agent's terminal
could, and a modified `creview` could also fake its own checks. Verify a receipt with a copy of
`creview` that did not run on the reviewed machine, installed fresh from the release named in the
receipt:

```bash
uvx --from git+https://github.com/junhewk/closed-review.git@vVERSION creview receipts verify receipt.json
```

The verifier checks the `receipt_id`, compares each exported file beside the receipt (an exact
match, or `text_match` after normalization), and compares the receipt's `tool.sums_sha256` with its
own installed files. A receipt from another version reports the tool as `not_checked`.

To compare against a saved reference instead, pass `--sums FILE`. Each release on the
[releases page](https://github.com/junhewk/closed-review/releases) attaches `creview-sums-VERSION.txt`, the package hashes of a clean install of that
release; it is the `sums` field of `creview receipts sums`, byte for byte.
