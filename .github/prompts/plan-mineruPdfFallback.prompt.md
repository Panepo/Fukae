# Plan: MinerU PDF Fallback

Add a self-hosted MinerU 4 V1 API service to the GX10 Petallia deployment and use it only when Docling cannot produce usable PDF elements. Keep Docling as the primary parser and normalize MinerU structured output into the existing Stage 1 element and picture contracts so stages 2-6 need no behavioral changes.

## Steps

1. Add the pinned `mineru:4.0.10` service to `d:/Github/Fukae/.github/reference/gx10-petallia/compose.yml`, running `mineru-kit api-server --host 0.0.0.0 --port 8000 --tier standard`. Configure `ipc: host`, `shm_size: 32gb`, an all-NVIDIA-GPU device reservation, `restart: unless-stopped`, a health check against `/v1/health`, and persistent named/bind mounts for model and upload data. Do not publish port 8000 to the host: Fukae will use Compose DNS.
2. Update the `fukae` service in the same Compose file to depend on MinerU becoming healthy and pass `MINERU_BASE_URL=http://mineru:8000`, `MINERU_API_KEY`, `MINERU_TIER=standard`, and MinerU poll/timeout settings. Add matching non-secret defaults to `d:/Github/Fukae/.github/reference/gx10-petallia/.env`; leave the API key unset for the trusted internal network unless deployment policy requires it.
3. Add `d:/Github/Fukae/core/mineru.py`. Implement `MinerUInference` using the existing `httpx` dependency and the MinerU 4 V1 HTTP API: health/capability discovery; SHA-256-aware upload creation; same-origin authenticated byte upload; parse-job submission requesting structured content plus asset-bearing ZIP output; bounded polling with explicit completed/partial/failed/canceled handling; redirected artifact download without forwarding credentials cross-origin; and typed, redacted exceptions. Reuse `SERVER_TIMEOUT` and introduce narrowly named configuration defaults where distinct polling bounds are needed.
4. Update `d:/Github/Fukae/indexer/indexer.py` to construct one `MinerUInference` and pass it into `stage1_parse.parse`, preserving the public `DocumentIndexer.load` and `load_directory` APIs.
5. Update `d:/Github/Fukae/indexer/stage1_parse.py` so `.pdf` files attempt Docling first. Treat transport errors, terminal job failures, malformed envelopes, and zero usable parsed elements as a Docling failure. For PDFs only, invoke MinerU when `MINERU_BASE_URL` is configured. Do not alter the existing Docling route for DOCX, HTML, or other extensions.
6. Add a MinerU result normalizer in `stage1_parse.py`, or a small dedicated normalizer module if the response handling would otherwise obscure parser dispatch. Map structured pages and blocks to the current flat elements contract: headings, text/list/code, and tables using the existing Docling-compatible `table_data` shape. Materialize output images from the downloaded artifact into `tmp_dir`, then emit aligned `picture` elements and `pic_info` records with zero-based MinerU pages converted to the pipeline’s one-based page convention. Preserve order, captions, sections, MIME type, and image paths. Fall back to Markdown parsing only if the service advertises no structured-content capability.
7. Define the failure policy at the Stage 1 boundary: log the Docling failure and fallback attempt without source content or credentials; return MinerU results when non-empty; otherwise raise a single parser exception carrying both redacted causes. This avoids silently indexing an empty or partially parsed document. Treat MinerU `partial` as failure unless its structured content identifies completed pages and the product requirement explicitly permits partial indexing.
8. Add focused mocked tests in `d:/Github/Fukae/tests/test_stage1_parse.py` and client protocol tests in `d:/Github/Fukae/tests/test_mineru.py`. Cover Docling success (MinerU untouched), Docling exception and MinerU structured success, Docling empty output fallback, both parsers failing, non-PDF Docling failure with no MinerU attempt, normalization of headings/tables/images/page numbers, authenticated same-origin upload, and cross-origin redirect credential stripping. Keep live-service tests opt-in rather than skip-on-any-error.
9. Update `d:/Github/Fukae/README.md` with the MinerU fallback behavior and required deployment variables. Document that the MinerU image must be built from the official MinerU 4 NVIDIA Dockerfile and version-checked before Compose startup, because the official build otherwise resolves a floating 4.x package range.

## Relevant Files

- `d:/Github/Fukae/.github/reference/gx10-petallia/compose.yml` - add internal MinerU V1 service, its GPU/storage/health configuration, and Fukae wiring.
- `d:/Github/Fukae/.github/reference/gx10-petallia/.env` - add internal MinerU endpoint and non-secret defaults; do not commit real credentials.
- `d:/Github/Fukae/core/mineru.py` - new MinerU 4 V1 adapter and its protocol/error boundary.
- `d:/Github/Fukae/indexer/indexer.py` - construct and inject the adapter.
- `d:/Github/Fukae/indexer/stage1_parse.py` - PDF-only fallback orchestration and output normalization.
- `d:/Github/Fukae/indexer/config.py` - add MinerU configuration values only when they differ from shared server timeout.
- `d:/Github/Fukae/tests/test_stage1_parse.py` - new deterministic parser/fallback tests.
- `d:/Github/Fukae/tests/test_mineru.py` - new mocked V1 client tests.
- `d:/Github/Fukae/README.md` - deployment and operational documentation.

## Verification

1. Build the pinned MinerU image from its official NVIDIA Dockerfile, assert its installed MinerU version is exactly `4.0.10`, then run `docker compose -f d:/Github/Fukae/.github/reference/gx10-petallia/compose.yml config`.
2. Start the MinerU and Fukae services, verify `GET http://mineru:8000/v1/health` from the Fukae network context reports structured-content and ZIP output support, and confirm no MinerU port is exposed on the host.
3. Run `pytest tests/test_mineru.py tests/test_stage1_parse.py` to validate protocol handling and fallback decisions without live GPU services.
4. Run `pytest tests/` to check regression coverage.
5. Manually index a normal PDF and confirm Docling is used; then simulate Docling failure for a scanned/table-heavy PDF and confirm MinerU provides text, tables, and saved picture assets that reach stages 2-3. Confirm a failure in both services produces a task error containing parser names and no leaked secrets or source bytes.

## Decisions

- MinerU 4 self-hosted V1 API is the chosen backend, not legacy `magic-pdf` or `/file_parse` APIs.
- MinerU is a PDF-only fallback; Docling remains primary for its current supported types.
- Structured content plus ZIP assets is required for the first implementation, so tables remain available to Stage 2 and images to Stage 3.
- MinerU is allocated all GPUs as requested. This may contend with Docling and vLLM; monitor GPU memory and queue time before enabling concurrent high-volume indexing.
- The requested Compose edit is deliberately deferred: this session is in Plan mode, which permits planning but not repository modifications. It is the first execution step once the plan is handed off.

## Scope Boundaries

- Includes the GX10 Petallia reference deployment and Fukae’s parser/client/test/documentation changes.
- Excludes exposing MinerU through Nginx, changing non-PDF parser routing, introducing a persistent MinerU job store, and changing downstream chunking/table/vision interfaces.
