# Real public articles: engineering fixtures

These six published articles were selected autonomously after the user removed the requirement
to approve test inputs. They are **not** synthetic, known-error manuscripts, clean controls,
a representative validation sample, or a medical-quality reference set. No errors were inserted.
Each original article's Europe PMC JATS declares CC BY licensing; attribution and original
license text are retained in the derived manuscripts.

| Module | Original article | Identifier |
| --- | --- | --- |
| Statistics | [Two randomized trials of visual prognostic information](https://bmjopen.bmj.com/content/13/6/e067624) | PMC10277048; 10.1136/bmjopen-2022-067624 |
| Qualitative study | [Interviews with UK health/care professionals about health-inequality data](https://pmc.ncbi.nlm.nih.gov/articles/PMC11381701/) | PMC11381701; 10.1136/bmjopen-2024-084352 |
| Systematic review | [Closed-loop oxygen control: systematic review and meta-analysis](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0304745) | PMC11168613; 10.1371/journal.pone.0304745 |
| Scoping review | [The role of patients' stories in medicine](https://doi.org/10.1186/s12904-023-01319-w) | PMC10714554; 10.1186/s12904-023-01319-w |
| Narrative review | [What about Happiness?](https://doi.org/10.5334/pme.856) | PMC10253238; 10.5334/pme.856 |
| Logic | [Deference or critical engagement with clinical ethics guidance](https://doi.org/10.1007/s40592-023-00186-8) | PMC11369004; 10.1007/s40592-023-00186-8 |

## Discovery and its limits

Public web searches located the branch-specific candidates. The medical-literature-search
skill also ran a bounded, assistant-authored PCC discovery question for qualitative patient
experiences: English, 2023-01-01 through 2024-12-31, at most 20 records per source, no MeSH.
OpenAlex retained 20 records; Semantic Scholar failed after four HTTP 429 attempts and retained
none. Neither source filtered any returned record. PubMed/PMC CLI connectors were unavailable
because `NCBI_EMAIL` was not configured; Scopus was unconfigured. No credentials were invented.
The final six are a purposive web/full-text selection, **not** a subset claimed to have come
from that one narrow PCC search or a systematic search result.

`question.json`, `discovery-strategy.json` and `discovery-summary.json` retain the bounded search
and its degradations. OpenAlex searches indexed free text rather than PubMed fields/MeSH;
Semantic Scholar's attempted quick query lost Boolean synonym groups and used year-level dates.
The pinned CLI was version 0.3.0 / commit `d0933405e2dcf4c49ced6ef852bae79c0fa05f19`.

Full texts were obtained individually through Europe PMC's `/{PMCID}/fullTextXML` service,
not bulk scraping of PMC article pages. Their titles, DOI/PMCID and CC BY declarations were
verified from the original XML. `articles.json` is the fixed selection;
`article-provenance.json` records original XML and derived-text hashes, original license text,
literal-text checks and explicit unassessed fidelity. There are eight source tables altogether.

## Reproduction and interpretation

The originals are retained locally at `/tmp/creview-public-corpus.2dm9mWnN/*.xml`. The final
frozen text corpus is `/tmp/creview-public-corpus.2dm9mWnN/manuscripts-v2`. An earlier conversion
draft is preserved separately and was not used for inference. `manifest.json` records exact
derived-source hashes; its manuscript paths are relative to the generated corpus directory.

```bash
uv run --frozen python scripts/prepare-support-public-corpus.py \
  --selection evals/support-public-articles/articles.json \
  --xml-dir /tmp/creview-public-corpus.2dm9mWnN \
  --output /tmp/NEW-public-text-corpus
```

The converter normalizes whitespace and flattens inline styling. It retains the main article's
abstract, prose, references, all table header rows/cells and footnotes. It explicitly records
merged-cell geometry; covered positions are blank, not missing data or repeated observations.
Literal paragraph/cell/reference retention checks are not semantic/layout certification.
Graphics are omitted with captions retained. Linked supplements, raw data and cited full texts
are not fetched. Public peer-review subarticles bundled inside an original XML are excluded
from the manuscript fixture and are not transferred to the model host. Formulae requiring
reconstruction are outside this converter's scope. This is not native-PDF qualification.

Only the derived manuscripts and key-free manifest are supplied to Hermes. Original XML,
source-selection/validation artifacts, private keys and completed human audits stay off that
host. The b14 pilot uses Korean responses and one paired support/ordinary-Hermes run per branch,
with new disposable profiles and the same existing local model. Results are engineering and
readability candidates only: no automatic precision, recall, scientific-validity or deployment
approval follows. Published status is not a clean-control label.
