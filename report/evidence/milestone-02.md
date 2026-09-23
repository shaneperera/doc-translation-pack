# Milestone 2 Input Normalization Evidence

Recorded on 2026-09-23 on macOS arm64 with Python 3.11.16.

## Supplied-pack results

| Input | Pages | Raster dimensions and orientation |
|---|---:|---|
| `JPN_referral` | 1 | 1654 x 2339, portrait |
| `DEU_child_checkup` | 2 | 1166 x 1654, portrait; 1166 x 1654, portrait |
| `KOR_case_report` | 1 | 1638 x 2166, portrait |
| `ITA_adverse_reaction` | 1 | 1654 x 2339, portrait |
| `DEU_maternity_record` | 1 | 1930 x 1378, landscape |

This verifies page order, raster creation, and geometry metadata. It does not assess text recognition or visual-layout reconstruction, which occur in later milestones.

## Page geometry finding

The supplied documents do not share one page shape. Two render at approximately A4 portrait, the child check-up pages are smaller portrait pages, the journal page has different portrait proportions, and the maternity record is a custom landscape page. A global A4 portrait assumption would rescale or squash some documents, invalidating extracted coordinates and weakening layout fidelity. Page size and orientation must therefore remain per-page metadata and be carried into DOCX rendering.

## JPEG DPI finding

A synthetic JPEG with EXIF orientation but no physical-resolution unit had JFIF density `(1, 1)` with unit `0`. Unit `0` describes pixel aspect ratio rather than pixels per inch, but Pillow exposed a nominal `(72, 72)` DPI value.

Trusting that value would produce an incorrect physical page size. Normalization now treats unitless JPEG density as missing, assumes 200 DPI, and records `dpi_assumed=True`. A genuine 72 DPI value with physical units remains valid and is preserved.
