# Document pack — Heidi AI take-home

Five clinical documents, six pages, four languages (Japanese, German, Korean,
Italian). None of the PDFs contains a single character of embedded text: each one was
flattened to a 200 dpi raster, and `page.get_text()` returns `""` on all of them.
That is deliberate — the pipeline you are asked to build starts from pixels.

Every document was downloaded from the public internet: official forms published by
health ministries and public bodies, and one open-access journal case report.
`SOURCES.md` gives the URL and the licence for each. There is no patient data here.

## Layout

```
documents/      the five image-only PDFs — this is your input
manifest.json   language, page count, and what makes each one hard
SOURCES.md      where each document came from, and under what licence
```

## No labels

There is no ground truth in this pack, and that is on purpose. Nobody hands you a
labelled reference in the field either: a clinic sends a scan and asks whether the
translation can be trusted.

So deciding what to measure your output against is part of the assignment. Whatever
you choose, say what it is and be straight about what it cannot see.

## The documents

Listed easiest first. Three of them should be within reach of a working pipeline,
one will punish a rigid table model, and one is genuinely awkward. Work down the
list — if you run out of time, we would rather see four good documents and an honest
note about the fifth than five rushed ones.

| Document | Language | Pages | Level | What it is |
|---|---|---|---|---|
| `JPN_referral` | Japanese | 1 | easy | Inter-hospital referral letter. A sparse grid of ruled boxes, a signature block, footnotes at 7pt. **Shipped as a photocopy** — greyscale, speckled, JPEG-compressed. Start here. |
| `DEU_child_checkup` | German | 2 | easy | Child health check-up record, the U4 examination: history on one page, findings on the other. A clean, modern, well-printed form — the easiest scan in the pack. Checkbox pairs, and measurement fields that carry their units (`g`, `cm`). |
| `KOR_case_report` | Korean | 1 | easy | Published case report. The only running prose here, and the only page with no ruled table at all — two journal columns, a running header, and a reference list **already in English** that should stay that way. |
| `ITA_adverse_reaction` | Italian | 1 | medium | Adverse drug reaction report form. Numbered sections in a dense field grid, checkbox rows, sub-tables nested inside sections, and labels long enough to reflow if your column widths are not honest. |
| `DEU_maternity_record` | German | 1 | hard | Maternity record — the Gravidogramm. Sixteen column headers set on the diagonal at roughly 47 degrees over a 14-row visit grid, and two more that are horizontal, so rotating every header is wrong. A two-line watermark crosses the page at 45 degrees and is not part of the record. **Landscape, and not A4**: a pipeline that assumes A4 portrait will quietly squash it. |

Levels are our own reading, not a promise. If you find the medium one harder than
the hard one, that is a finding — put it in the report.

## Quick look

```bash
# There is no text in these files. Confirm it before you plan around it.
python -c "
import pymupdf, glob
for p in sorted(glob.glob('documents/*.pdf')):
    d = pymupdf.open(p)
    print(f'{p:40s} {d.page_count} pages, {sum(len(pg.get_text().strip()) for pg in d)} chars of text')
"

# Render the hardest page in the pack and go look at it
python -c "
import pymupdf
pymupdf.open('documents/DEU_maternity_record.pdf')[0].get_pixmap(dpi=200).save('gravidogramm.png')
"

# Every page as a PNG, to work against directly
python -c "
import pymupdf, glob, pathlib
pathlib.Path('pages').mkdir(exist_ok=True)
for p in sorted(glob.glob('documents/*.pdf')):
    name = pathlib.Path(p).stem
    for i, pg in enumerate(pymupdf.open(p)):
        pg.get_pixmap(dpi=200).save(f'pages/{name}_p{i + 1}.png')
        print(f'pages/{name}_p{i + 1}.png')
"
```
