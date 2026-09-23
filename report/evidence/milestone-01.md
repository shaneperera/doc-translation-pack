# Milestone 1 Repository Foundation Evidence

Recorded on 2026-09-23 on macOS arm64.

## Toolchain

- Python 3.11.16
- uv 0.12.17
- Dependency resolution: 66 packages in `uv.lock`

## Findings

The scaffold is pinned to Python 3.11 with uv 0.12.17. LibreOffice is not installed on the development machine, so independent DOCX round-trip validation remains a later environment requirement rather than a Milestone 1 capability.

## Supplied pack integrity

The pack moved under `data/` without changing file bytes. All five manifest paths resolve relative to `data/manifest.json`.

| File | SHA-256 |
|---|---|
| `data/README.md` | `101cd100dba40a591795afe3b202ce7571ebe665afb68b53ad41f2cb732f11a8` |
| `data/SOURCES.md` | `e676e5ed42b881bac859fdd8732bb95ad72cbcbec2219483202628c489366677` |
| `data/manifest.json` | `1867ca5dce2cbdc28116cfb9c07449092db383c80c95c345555bc11ae1a9f113` |
| `data/documents/DEU_child_checkup.pdf` | `aa6555a1ecf1f2d01304adf420d09aa8be12d9ada0dc059eea3ad977d77267c8` |
| `data/documents/DEU_maternity_record.pdf` | `c0820ce39d5c56c884469f3082c0ca47c992a4c5b4beeee7fce7cc8c6858bd0f` |
| `data/documents/ITA_adverse_reaction.pdf` | `558e1a03f77f960cf168b0dee92b44832087b6a65b2f60e126655776e3c2cd26` |
| `data/documents/JPN_referral.pdf` | `743a2ed3e2839e6f334f2419f807d59616eba5b86a029932c823d603b3c22bb4` |
| `data/documents/KOR_case_report.pdf` | `3f9204724f0491b2b1fae105dd7acf16c38e77af1160b769dcb4878cccf37fb5` |
