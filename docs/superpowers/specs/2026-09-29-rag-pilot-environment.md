# RAG pilot environment and package provenance

Date: 2026-09-29. Status: isolated dependency and local smoke probe only; no runtime migration or retrieval-quality claim.

## Direct dependencies

| Distribution | Pin | Published Python requirement | Declared license | Source |
| --- | --- | --- | --- | --- |
| Docling | `2.130.0` | `>=3.10,<4.0` | MIT | [PyPI release metadata](https://pypi.org/pypi/docling/2.130.0/json) |
| Haystack AI | `3.2.0` | `>=3.10` | Apache-2.0 | [PyPI release metadata](https://pypi.org/pypi/haystack-ai/3.2.0/json) |

The upstream commits and reasons for reuse are in the [reuse assessment](2026-09-29-rag-reuse-assessment.md). These are package pins, not Git commit pins. No upstream source code was copied. `requirements.txt` and the production import path are unchanged.

## Resolution and probe

- Host: macOS Darwin arm64; Python 3.14.6; pip 26.1.2.
- Isolated environment: `/tmp/kb-rag-pilot-venv`, created with `python3 -m venv /tmp/kb-rag-pilot-venv`; installed with `/tmp/kb-rag-pilot-venv/bin/python -m pip install 'docling==2.130.0' 'haystack-ai==3.2.0'`. A dry run of `/tmp/kb-rag-pilot-venv/bin/python -m pip install --dry-run -r requirements-rag-pilot.txt` found both pins and dependencies satisfied.
- Dependency resolution: 118 installed distributions, about 1.4 GiB in the environment. `/tmp/kb-rag-pilot-venv/bin/python -m pip check` returned `No broken requirements found.` The `pip freeze` SHA-256 for this resolution was `456e1a27fc613fa1da20f24b6eb9219e1158e01587d61d071734fd27dabf6563`.
- Synthetic PDF: 606-byte local one-page PDF with only `Synthetic revenue rose in FY25.` in its text stream; SHA-256 `254251b44e382f8b7cb0ee34f27e1d3d99a885120bc686ca217a07fde9c33b8a`. It was built locally in `/tmp`; no company document or third-party PDF was fetched.
- Docling `DocumentConverter` with `NativePdfFormatOption` returned `success`, one page, and the exact text. This model-free native-PDF probe verifies installation and basic text extraction only. It does not validate the standard layout/OCR pipeline, scanned PDFs, tables, reading order, or page-citation fidelity.
- Haystack `InMemoryDocumentStore` accepted one synthetic `Document`; `InMemoryBM25Retriever` returned one hit for `revenue FY25` with the expected text. This does not establish filtered or cutoff-safe retrieval.
- No model downloads were needed for the native-PDF probe. The later standard Docling pipeline may need model artifacts and a separate license/cache review before real files are used.

## Resolved distributions and declared licenses

The table is generated from each installed distribution's `License-Expression`, short `License`, or license classifier, in that order. It records package metadata, not a legal audit of bundled files. No installed metadata declared GPL, AGPL, proprietary, or commercial-only terms. `certifi` and `tqdm` declare MPL-2.0; `pypdfium2` declares bundled dependency licenses; `torch` declares several licenses with an LLVM exception; `regex` includes CNRI-Python; and `python-dateutil` says Dual License. Inspect their license files before broader redistribution. All 118 distributions have some license declaration, but several declarations are free text instead of SPDX expressions.

| Distribution | Resolved version | Declared license metadata |
| --- | --- | --- |
| `accelerate` | `1.15.0` | Apache |
| `annotated-doc` | `0.0.5` | MIT |
| `annotated-types` | `0.8.0` | MIT |
| `antlr4-python3-runtime` | `4.9.3` | BSD |
| `anyio` | `4.15.1` | MIT |
| `attrs` | `26.1.0` | MIT |
| `backoff` | `2.2.1` | MIT |
| `beautifulsoup4` | `4.15.0` | MIT License |
| `certifi` | `2026.7.22` | MPL-2.0 |
| `charset-normalizer` | `3.5.1` | MIT |
| `click` | `8.5.0` | BSD-3-Clause |
| `colorlog` | `6.12.0` | MIT License |
| `defusedxml` | `0.7.1` | PSFL |
| `dill` | `0.4.1` | BSD-3-Clause |
| `distro` | `1.9.0` | Apache License, Version 2.0 |
| `doclang` | `0.7.3` | Apache-2.0 |
| `docling` | `2.130.0` | MIT |
| `docling-core` | `2.99.0` | MIT |
| `docling-ibm-models` | `4.0.3` | MIT |
| `docling-parse` | `7.22.1` | MIT |
| `docling-slim` | `2.130.0` | MIT |
| `docstring_parser` | `0.18.0` | MIT |
| `et_xmlfile` | `2.0.0` | MIT |
| `Faker` | `40.39.0` | MIT License |
| `filelock` | `4.0.5` | MIT |
| `filetype` | `1.2.0` | MIT |
| `fsspec` | `2026.9.0` | BSD-3-Clause |
| `h11` | `0.16.0` | MIT |
| `haystack-ai` | `3.2.0` | Apache-2.0 |
| `hf-xet` | `1.6.0` | Apache-2.0 |
| `httpcore` | `1.0.9` | BSD-3-Clause |
| `httpcore2` | `2.13.1` | BSD-3-Clause |
| `httpx` | `0.28.1` | BSD-3-Clause |
| `httpx2` | `2.13.1` | BSD-3-Clause |
| `huggingface_hub` | `1.33.0` | Apache-2.0 |
| `idna` | `3.20` | BSD-3-Clause |
| `Jinja2` | `3.1.6` | OSI Approved :: BSD License |
| `jiter` | `0.17.0` | MIT |
| `jsonref` | `1.1.0` | MIT |
| `jsonschema` | `4.26.0` | MIT |
| `jsonschema-specifications` | `2025.9.1` | MIT |
| `langcodes` | `3.5.1` | OSI Approved :: MIT License |
| `latex2mathml` | `3.81.1` | MIT |
| `lazy_imports` | `1.2.0` | Apache-2.0 |
| `lxml` | `6.1.3` | BSD-3-Clause |
| `mail-parser` | `4.6.5` | Apache-2.0 |
| `markdown-it-py` | `4.2.0` | OSI Approved :: MIT License |
| `marko` | `2.2.4` | MIT |
| `MarkupSafe` | `3.0.3` | BSD-3-Clause |
| `mdurl` | `0.1.2` | OSI Approved :: MIT License |
| `more-itertools` | `11.1.0` | MIT |
| `mpire` | `2.10.2` | MIT |
| `mpmath` | `1.3.0` | BSD |
| `multiprocess` | `0.70.19` | BSD-3-Clause |
| `networkx` | `3.7` | BSD-3-Clause |
| `numpy` | `2.5.3` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `olefile` | `0.47` | BSD |
| `omegaconf` | `2.3.1` | OSI Approved :: BSD License |
| `openai` | `3.20.0` | Apache-2.0 |
| `opencv-python` | `5.0.0.93` | Apache 2.0 |
| `openpyxl` | `3.1.5` | MIT |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause |
| `pandas` | `3.0.6` | OSI Approved :: BSD License |
| `pillow` | `12.3.0` | MIT-CMU |
| `pip` | `26.1.2` | MIT |
| `pluggy` | `1.6.0` | MIT |
| `polyfactory` | `3.3.0` | MIT |
| `posthog` | `7.60.1` | MIT |
| `psutil` | `7.2.2` | BSD-3-Clause |
| `pyclipper` | `1.4.0` | MIT |
| `pydantic` | `2.13.5` | MIT |
| `pydantic-settings` | `2.15.0` | MIT |
| `pydantic_core` | `2.46.5` | MIT |
| `Pygments` | `2.21.0` | BSD-2-Clause |
| `pylatexenc` | `2.11` | MIT |
| `pypdfium2` | `5.13.0` | BSD-3-Clause, Apache-2.0, dependency licenses |
| `python-dateutil` | `2.9.0.post0` | Dual License |
| `python-docx` | `1.2.0` | MIT |
| `python-dotenv` | `1.2.3` | BSD-3-Clause |
| `python-oxmsg` | `0.0.2` | MIT |
| `python-pptx` | `1.0.2` | MIT |
| `PyYAML` | `6.0.3` | MIT |
| `rapidocr` | `3.9.2` | Apache-2.0 |
| `referencing` | `0.37.0` | MIT |
| `regex` | `2026.9.10` | Apache-2.0 AND CNRI-Python |
| `requests` | `2.34.2` | Apache-2.0 |
| `rich` | `15.0.0` | MIT |
| `rpds-py` | `2026.6.3` | MIT |
| `rtree` | `1.4.1` | MIT |
| `safetensors` | `0.8.0` | OSI Approved :: Apache Software License |
| `scipy` | `1.18.1` | OSI Approved :: BSD License |
| `semchunk` | `3.2.5` | MIT |
| `setuptools` | `84.0.0` | MIT |
| `shapely` | `2.1.2` | BSD 3-Clause |
| `shellingham` | `1.5.4` | ISC License |
| `six` | `1.17.0` | MIT |
| `sniffio` | `1.3.1` | MIT OR Apache-2.0 |
| `soupsieve` | `2.10` | MIT |
| `sympy` | `1.14.0` | BSD |
| `tabulate` | `0.10.0` | MIT |
| `tenacity` | `9.1.4` | Apache 2.0 |
| `tokenizers` | `0.23.2` | OSI Approved :: Apache Software License |
| `torch` | `2.14.0` | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| `torchvision` | `0.29.0` | BSD |
| `tqdm` | `4.70.1` | MPL-2.0 AND MIT |
| `transformers` | `5.17.0` | Apache 2.0 License |
| `tree-sitter` | `0.26.0` | OSI Approved :: MIT License |
| `tree-sitter-c` | `0.24.2` | MIT |
| `tree-sitter-javascript` | `0.25.0` | MIT |
| `tree-sitter-python` | `0.25.0` | MIT |
| `tree-sitter-typescript` | `0.23.2` | MIT |
| `truststore` | `0.10.4` | MIT |
| `typer` | `0.26.8` | MIT |
| `typing-inspection` | `0.4.4` | MIT |
| `typing_extensions` | `4.16.0` | PSF-2.0 |
| `urllib3` | `2.8.0` | MIT |
| `websockets` | `16.1.1` | BSD-3-Clause |
| `xlsxwriter` | `3.2.9` | BSD-2-Clause |
