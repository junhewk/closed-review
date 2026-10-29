# Historical scan workflow (legacy)

> Historical legacy scan workflow. The default skill now uses independent medical support modules;
> see [Medical methodological support](support.md). Legacy findings and commands remain separate.

For the current `/journal-article-review` command, use
[Medical methodological support](support.md). It selects independent modules and supplies a
compact summary/dossier; it does not enter the historical one-finding-at-a-time queue below.

The following describes the deliberately invoked legacy `creview scan` and direct-record
interfaces. They remain available for compatibility with existing records, not as the support
deployment path or evidence that the new modules are qualified. Do not migrate legacy findings
or treat their old qualification scores as new medical-support evidence.

The legacy scan reads a manuscript part by part using your own model, then presents findings
one at a time, each with manuscript quotations. It targets checkable claims such as counts and
aim/design correspondence, but neither matching text nor a completed scan establishes that its
criticisms are correct. Scientific judgment, wording and any publication recommendation remain
the reviewer's responsibility. These historical interaction rules do not replace the current
support skill's privacy gate, explicit scope selection or optional reviewer decisions.

## What happens

1. **Checks.** `creview session start` checks the Hermes profile's model routes against your
   trusted gateway and returns the privacy rules. The agent asks whether the journal permits this
   local AI assistance, unless you already said so. Your answer remains in the Hermes conversation
   but is not separately recorded by creview; checking the journal's policy is your responsibility.
2. **Design profiles.** After reading the manuscript, the agent proposes up to three design
   profiles (qualitative, quantitative, systematic review, scoping review, normative argument,
   legal analysis), with a reason for each, and asks you to confirm or correct them. A profile lists
   where that kind of work usually fails, which flaws are major in it, and which concerns are
   common false alarms. It guides where to look; it contains no prepared comments.
3. **The scan**, modelled on the segment-based structure of Google's
   [Deep Review](https://research.google/blog/analyzing-technical-documents-with-deep-review/) but
   run on your model (see [References](references.md)). creview hands the agent one task at a time,
   checks each answer, and refuses one it cannot verify with what to fix:
   - **Orientation**: the initial summary (what the article asks, does, and concludes, with the
     authors' own considerations quoted) and the reading plan, written before any read.
   - **Reads**, one per part, in order. Each sees the concerns found so far and adds to them or
     raises a new one, quoting verbatim. Arithmetic the text implies is computed by creview, not
     the model.
   - **Checks** of each listed major flaw a read flagged, against the whole manuscript.
   - **The sweep** sorts everything into the distinct concerns a reviewer would report.
   - **Second checks** of concerns rated major on judgement; unconfirmed ones become minor.
   - **Screening** sets aside concerns that only repeat a limitation the authors state, or a
     profile's common false alarm with nothing in the text making it apply.

   The agent reports only the stage and task number while it works. Hermes can also display its
   file edits and tool details, including unfinished findings; see the display settings in
   [Install](install.md) to hide inline diffs and avoid verbose progress. A scan can take several
   minutes, depending on the manuscript, model and checks. If it needs more tool calls than the
   profile's `agent.max_turns`, Hermes pauses and replying "continue" resumes it.
4. **Findings, one at a time.** First the initial summary, then the majors, one per turn (those a
   check confirmed first), then the minors in batches of up to three. Each shows the passage it is
   about, what later parts of the manuscript add, the authors' own answers to it, what each check
   found, and why it survives the authors' strongest reply. You answer each (accept, keep
   developing, defer, or dismiss) before the next appears, and the agent never says how many remain.
   Only nine minors are shown unless you ask for more.
5. **Your own points.** Raise any issue at any time; the agent tests it against the manuscript
   before returning to the scan's findings.

## Severity

creview sets it in code: major when a check confirmed a listed major flaw with verbatim quotes, or
when a computed mismatch is in a figure the manuscript reuses. Otherwise it is the model's rating,
labelled as judgement.

A check for a misread source needs both the manuscript's claim and the source's own words as
quoted in the manuscript. Those words remain manuscript-reported: they have not been checked
against the source itself. An uncited claim alone cannot confirm a misreading.

## Your words

Your decisions and lookup approvals are recorded only with your own words: a message you typed in
the session after the item was shown, or your answer to a question Hermes asked (clarify). creview
reads them from the profile's `state.db` and refuses words you did not write, including the skill
text Hermes stores with the slash command.

## Literature

Web and browser tools are never used. The agent may propose a Crossref or OpenAlex query built from
public bibliographic terms only, shows you the exact query and URL, and runs it only after you
approve. A result shows that a work exists and what it is, not what it argues. Each finding labels
the works it cites (`manuscript_reported`, or `model_lead` when only the model recalls it).

On request, `creview references check` compares the manuscript's citations with its reference list
without network access; an approved metadata check can then verify the entries' identity.

## Saving

When you ask, the agent compiles your accepted findings into separate drafts for the authors and
the editor, keeps a private development record of everything you decided, and writes an
[export receipt](receipts.md) beside them. A recommendation appears only if you give it with your
reasoning. Afterwards the agent offers to delete the scan's private records.

The historical instructions also described passage-level conversations without a scan, using
the old profiles and one-at-a-time records. That is not a fallback instruction for the current
support skill; use its selected-module workflow and privacy requirements instead.
