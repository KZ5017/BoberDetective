# AI_NOTES.md

## Purpose

This file is the handoff layer for future Codex sessions.

Read this file together with:

- `AGENTS.md`
- `README.md`
- `CURRENT_STATE.md`
- `CHANGELOG.md`, if present
- the design documents in `Design_documents/`

## Current Project State

The project has moved from pure design phase into the first implementation sprint.

Fresh-session baseline:

- `CURRENT_STATE.md` now contains the compact Session Handoff Baseline v1.
- A new session should read `AGENTS.md`, `README.md`, `AI_NOTES.md`, `CHANGELOG.md`, and `CURRENT_STATE.md`.
- Current verification baseline: latest known full suite `pytest: 392 passed`, latest targeted document-discard regression slice `59 passed`, latest targeted knowledge query/API slice `52 passed`, latest targeted relationship graph backend slice `10 passed`, latest targeted full-document/documents/RAG slice `85 passed`, latest full-document unit slice `22 passed`, latest targeted AI-asszisztens/LLM slice `23 passed`, latest focused assistant contract/UI check `tests/test_assistant.py: 6 passed`, `alembic: 0051_assistant_chats (head)`, `npm --prefix frontend run build` passed.

Latest session update:

- Manual contradiction candidate cleanup is implemented through migration `0049_contradiction_partial_pair`: contradiction candidates may have a partial/missing claim or event pair only when `review_status=corrected`, the `Találat részletei` panel exposes `A állítás leválasztása` / `B állítás leválasztása`, claim-side detach is audited and marks the candidate `Korrekcióval kizárt`, and claim/event deletion now corrects dependent contradiction candidates instead of silently deleting them. This deliberately leaves `source_validation_status` unchanged because the candidate's source basis is inherited through its input objects.
- `Teljes iratfeldolgozás` person-search evidence now stores the full source sentence around the matched person name as `source_evidence_json[].quote_text` instead of only the bare name. The LLM still supplies only the compact person fields and source label; sentence expansion is backend-owned so the worklist card shows useful local context while preserving source-derived quote text.
- The first `Szabad iratkérdés` full-document implementation slice is in place from `Design_documents/29_full_document_free_question_plan.md`: migration `0050_full_document_answers`, `FullDocumentAnswerModel`, `full_document_answer` analysis-run output support, profile-aware run branching, list/detail/delete APIs, and a frontend `Iratválasz` panel with safe Markdown rendering. It answers from the selected active document/page range plus user question and remains separate from the person-only `document_processing_items` worklist. Recent hardening made the panel refresh saved answers after deletion, moved previous-answer selection onto the shared tokenized choice-button style, and made free-question JSON recovery tolerate malformed optional metadata, unescaped internal quotes, and a missing final object brace when `answer_text` is recoverable.
- The `Áttekintési jelentés` status cleanup is implemented and documented in `Design_documents/26_review_report_status_cleanup_plan.md`. The active `new` review status is retired from backend/frontend contracts and migrated to `needs_review`; `corrected` is shown as `Korrekcióval kizárt`; merge/source-detach/source-move orphaned objects consistently become corrected/source-invalid where the model supports a separate source status; and the contradiction claim review scope no longer includes `new`.
- Destructive frontend actions now use a more consistent visual language: concrete delete/final-delete/discard-delete buttons use the shared danger color plus the `Trash2` icon, while non-destructive selection/input clearing controls remain separate.
- The `Kapcsolati térkép` technical multi-focus baseline is implemented and can be treated as the current functional state. The graph projection uses the multi-focus POST API: `RelationshipGraphMultiFocusRequest`, `focus_node_ids` / `focus_objects` response metadata, shared `build_relationship_graph_for_objects(...)`, single-focus builder delegation, and `POST /api/v1/cases/{case_id}/graph/objects`. It supports source-valid `claim`, `event`, `entity`, `missing_item_candidate`, and `contradiction_candidate` focus objects, deterministic `document -> page -> chunk -> source_reference -> object` source-location provenance with fallbacks, contradiction claim-pair edges, shared-source neighbors, and node/edge limits. The object-centered graph intentionally no longer displays `Elemzési eredet`: analysis-run and research-finding lifecycle provenance remains available through the existing analysis/audit surfaces, not as graph nodes. The frontend surface is implemented with source-valid checkbox object-card selection, `x kijelölve / 20`, `Térkép frissítése kijelölésből`, `Láthatók kijelölése`, `Láthatók levétele`, `Térkép ürítése`, `Ügy munkapad` handoff through a one-object POST request, lazy-loaded React Flow / XYFlow canvas, temporary node dragging without persistence, the current two-row inspector layout, and explicit frontend graph layer toggles. Layer order is `Irat`, `Oldal`, `Szövegrész`, `Forráshivatkozás`, `Kapcsolódó objektumok`, `Ellentmondások`; `Irat` and `Forráshivatkozás` are enabled by default. The old UUID-shaped single-focus GET endpoint and frontend helper have been retired. Next graph work is visual/UX strengthening of this baseline, not core multi-focus plumbing.
- The planned `Általános iratkérdező` is now an implemented separate work surface backed by migration `0044_rag_answers`, `0045_limit_rag_answer_modes`, `RagAnswerModel`, `/api/v1/cases/{case_id}/rag/*` endpoints, frontend query/save/list/detail/delete flows, and `tests/test_rag.py`. It is a general local RAG answer surface, not a replacement for `search_findings`, full-document person seeds, or review-object workflows.
- `Általános iratkérdező` answer modes are intentionally limited to `short` and `detailed`. Experimental `source_focused` and `strict_source` modes were removed from frontend/backend/schema/DB after live tests showed they increased false certainty and role hallucination with the current local model.
- Current `Általános iratkérdező` defaults are `retrieval_strategy=hybrid`, `max_chunks=45`, max `90`. Multi-document RAG is document-isolated: retrieval selects relevant chunks, chunks are reordered by document/page/chunk, each contributing document gets its own partial LLM answer, and a final synthesis answer is generated from those partial answers. Single-document RAG still uses one direct answer call. The separate `Tudásbázis` query surface intentionally keeps its tighter `max_chunks` default/cap at `30/60`.
- The `Általános iratkérdező` UI now follows the same work-surface rhythm as `Ügy munkapad`: top `Szemantikus index állapot` plus persistent `Utolsó iratkérdező keresés`, matching query controls, selected-document checkbox/radio source selection, answer/source two-column display, saved-answer detail scroll, and saved `source_summary` display. Backend support includes `GET /api/v1/cases/{case_id}/rag/latest-run-summary` and case-scope `document_ids` filtering for RAG queries.
- `Tudásbázis` answer parsing is deliberately tolerant because Markdown/code-heavy answers can contain many characters that stress local-model JSON formatting. `answer_text` remains required, but `source_summary` and `insufficient_source` are optional/recovered where possible; this is not a pattern to copy blindly into source-validated investigative object creation.
- `search_findings` now uses the same large-case ordering discipline before LLM calls: retrieval still ranks candidates by relevance, then selected chunks are reordered by document/page/chunk and split so a single LLM batch never mixes chunks from different documents. The UI label is now `Maximális batch méret`, default `3`; `Szövegrész plafon` defaults to `45` and is capped at `90`.
- `search_findings` prompting was tightened around QUERY relevance without backend keyword gating. The active prompt frames the model as a source-faithful finding verifier: SOURCE is only a candidate text, QUERY is the exact focus, and the model should return findings only when the quote content clearly establishes the QUERY relation. A halted backend `keyword_anchor` gating experiment was reverted; do not reintroduce it unless explicitly planned.
- JSON handling now has schema-specific fallback recovery for malformed local-model JSON caused by local-model formatting drift. `search_findings` can recover its ordered `findings` shape, full-document person processing can recover its ordered `items` shape (`item_kind`, `display_label`, `recommended_search_focus`, `source_label`), and full-document free-question answers can recover answer payloads when `answer_text` is present but optional metadata or the final object brace is malformed. These fallbacks do not bypass normal source validation for object-creation workflows.
- Full-document person-profile tuning is no longer the active next-step loop. The active profile is intentionally person-only, the prompt/output contract is compact, source-evidence construction stays backend-owned, unconfirmed items remain actionable instead of being discarded, and repeated labels are preserved with occurrence status. Future changes here should be driven by concrete live-output problems rather than broad retuning.
- The `Általános iratkérdező` is now considered a stable first implementation baseline. Live testing continues as normal use, but it is no longer the main planned implementation slice unless a concrete quality/UX issue is found.
- The focused knowledge-base Markdown parser hardening slice in `Design_documents/22_markdown_ast_chunking_plan.md` has moved from spike to active baseline. `app/services/markdown_parser.py` is now the Marko/AST parser (`markdown_marko_ast_parser_v1`, `markdown_ast_sections_v1`), the old line-based parser implementation and old-vs-AST comparison script have been removed, and user-side live testing on 121 Markdown documents / 2708 chunks passed without parser-quality regressions beyond the already fixed JSON/output handling issues.
- `Tudásbázis` answer and source display is now a stronger UX baseline: answer text and opened Markdown source chunks render through safe Markdown/GFM rendering (`skipHtml`), source cards are moved into a full-width collapsible `Felhasznált Markdown források` panel, source chunk body text is lazy-loaded only when a user opens a source, and the source card list has a local search field that filters visible cards without preloading all chunk bodies.
- The active `Tudásbázis` quality slice is retrieval hardening rather than more parser retuning. `Design_documents/23_markdown_knowledge_retrieval_hardening_plan.md` is implemented through baseline tests, Markdown-aware hybrid scoring, same-document/same-heading context expansion, and the first `Design_documents/24_markdown_section_aware_retrieval_packing_plan.md` implementation slice; backend-generated query variants were explicitly removed from the plan. Keep keyword mode as the simple baseline.
- The OWASP Top 10 cheat-sheet heading-meta retrieval gap is now implemented as the first `Tudásbázis` retrieval v2 hardening slice. Top-level Markdown headings that only appear through `heading_path` metadata can now influence keyword/hybrid retrieval, and high-priority pre-heading intro chunks can bridge into the immediately following query-matching heading branch. Bridge-expanded chunks use `retrieval_match_type=heading_bridge`; the frontend labels this and the existing section/context expansion types with Hungarian source-origin chips. The SOURCE prompt already exposed `heading_path`; this is now covered by a regression test.
- The `Tudásbázis` retrieval tuning in `Design_documents/24_markdown_section_aware_retrieval_packing_plan.md` section `12d` is implemented and accepted as the current stable baseline after user-side live feedback improved: hybrid retrieval is more keyword-dominant, semantic/hybrid starts from a larger candidate pool, seed/context splitting happens after final candidate scoring, expansion cutoff applies only to expansion seeds, and high-confidence seeds can pull more forward Markdown context.
- The first retrieval-hardening baseline test slice is implemented in `tests/test_knowledge_query.py`: semantic hit mapping, current hybrid keyword/semantic/overlap scoring, stable hybrid tie ordering, and document/path/chunk LLM input ordering are now covered without changing production retrieval behavior.
- The first Markdown-aware hybrid scoring slice is implemented: hybrid merging now adds bounded bonuses for exact query matches, heading-path term matches, technical token overlap, code language matches, and code-block presence only when the query/text/heading/language supports it. Keyword mode and standalone semantic mode are unchanged.
- The `Tudásbázis` semantic/hybrid retrieval path now has backend-controlled section-aware context expansion. Heading-relevant seeds can pull in multiple following chunks from the same compatible heading branch; section chunks use `retrieval_match_type=section_context`, direct `context_neighbor` remains a fallback, and expansion never crosses document boundaries or the hard `max_chunks` source cap.
- Document-level source packing v1 is active for `Tudásbázis`: retrieved/expanded candidates are deduplicated by document/chunk, scored per document from top candidate scores plus a small capped coverage bonus, ordered by document score, and packed in natural `chunk_index` order inside each selected document. This should address heading-heavy notes where retrieval finds the right titles but not the useful body text.
- Expansion now uses `expansion_priority` rather than raw retrieval score alone. The priority combines retrieval score, heading relevance, path/filename topic hints, and technical/code hints. High-priority seeds can pull up to 10 following compatible chunks, medium-priority seeds up to 6, and low-priority seeds get no automatic forward context. This is meant to catch cases such as a low-score `kubectl OFFENSIVE SECURITY CHEATSHEET` heading/path hit that should still bring the following body chunks.
- Preparatory refactor for the section-aware packing slice is complete: retrieval/scoring/context helper logic moved from `app/services/knowledge_query.py` into `app/services/knowledge_retrieval.py` without intended behavior change. `knowledge_query.py` should now remain the orchestration layer for document selection, prompt building, LLM calls, parsing, and response assembly.
- Heading relevance scoring is now explicit in `knowledge_retrieval.py`: matching headings produce a `HeadingRelevanceScore`, and heading level contributes a bounded bonus only when the heading actually matches the query. Higher-level headings receive stronger level bonus than deeply nested headings, but unrelated headings receive no level bonus.
- Section expansion v1 is implemented for semantic/hybrid Tudásbázis retrieval: heading-relevant seeds can pull in multiple following chunks from the same compatible heading branch, capped per seed and still constrained by the hard `max_chunks` source limit. These chunks use `retrieval_match_type=section_context`; the old direct `context_neighbor` behavior remains as fallback for non-heading seeds.
- Latest focused knowledge-retrieval verification: `.venv/bin/python -m pytest tests/test_knowledge_api.py tests/test_knowledge_query.py -q` returned `52 passed`.
- Latest relationship-graph backend verification after the source-location hierarchy slice: `.venv/bin/python -m pytest tests/test_health.py tests/test_relationship_graph.py -q` returned `10 passed`.
- Latest relationship-graph frontend verification: `npm --prefix frontend run build` passed after adding `@xyflow/react` and the graph canvas. The canvas is lazy-loaded through `frontend/src/RelationshipFlowCanvas.tsx`, so React Flow is split into a separate chunk instead of bloating the main workbench bundle. `npm --prefix frontend audit --audit-level=high` reports `found 0 vulnerabilities`; this is achieved by pinning `esbuild` to `0.28.1` via npm `overrides`, because the official Vite 8 audit fix requires Node 20+ while the current WSL runtime is Node 18. Vite build target is set to `es2022` for this modern local-app profile.
- The first `Kapcsolati térkép` horizontal visual-layout slice is implemented in `frontend/src/RelationshipFlowCanvas.tsx`: graph nodes are now placed into deterministic left-to-right layers (`document`, `page`, `chunk`, `source_reference`, `object`, `contradiction`) using the backend projection, and all focus nodes from `focus_node_ids` are recognized for labeling/logic rather than a separate focus column. The current accepted node styling is intentionally calm: all graph nodes share the same border/effect baseline, object-category nodes only receive subtle background color by object type, and node selected/focus state does not add extra visual effects. Latest verification for this slice: `npm --prefix frontend run build` passed.
- `Kapcsolati térkép` contradiction edges now follow backend graph semantics from source object to contradiction candidate: `claim A/B -> contradiction_candidate`. This makes the visual reading order `Irat -> Oldal -> Szövegrész -> Forráshivatkozás -> Objektum -> Ellentmondásjelölt`; manual and LLM-created contradiction candidates share the same node/layout treatment. Contradiction candidates intentionally do not draw their own direct source-reference legs in this object-centered graph, because their source path is read through the two input claims.
- In the frontend graph layer filter, contradiction-candidate focus views treat the input claims as source-carrier nodes. This keeps the default `Irat` and `Forráshivatkozás` layers visible for contradiction candidates even though the candidate itself has no direct source-reference leg in the object-centered map.
- `Kapcsolati térkép` can now draw frontend-only visual bridge edges when intermediate source layers are hidden. These `VISUAL_SOURCE_BRIDGE` edges connect visible source-chain nodes to the next visible graph node with a label-free dashed line, so users can inspect "which document/page belongs to which object" without showing every intermediate source-reference/chunk/page node. They are visual-only edges and do not change source truth.
- `Kapcsolati térkép` visual polish state: the object-type selector defaults to `Összes`; React Flow nodes can be temporarily moved by mouse but positions are not persisted; source-chain columns use a wider horizontal rhythm (`document/page/chunk/source_reference/object/contradiction`); real source-chain edges are explicitly solid; visual bridge edges are dashed and are not created when a real visible edge already connects the same pair.
- `Kapcsolati térkép` inspector polish state: `Kijelölt csomópont tartalma` and `Kapcsolatok` are read-only inspector panels. Their content cards do not receive selected/focus background, border, or shadow effects; only the graph canvas owns selection logic. Inspector cards and chips are now routed through graph-inspector CSS tokens while preserving the same visual language as the global compact card/chip system.
- The source-location projection cleanup is implemented in the backend: source location now follows the deterministic hierarchy `document -> page -> chunk -> source_reference -> object`, with fallbacks for missing page/chunk data (`document -> chunk -> source_reference`, `document -> page -> source_reference`, or `document -> source_reference`). For chunk-bound source references that lack an explicit `page_id`, the graph projection resolves the current document page from the page-local chunk's `page_start` when possible, so historical/partial source references can still show an `Oldal` node. This replaces the older source-reference-centered star projection for new graph responses. `Elemzési eredet` has been removed from this object-centered graph and should return only if a separate lifecycle/provenance map is intentionally designed.
- A possible future `Jogszabályi kereső` should be treated as a later specialized module if the goal becomes serious legal-corpus work: it needs its own source model around law/section/paragraph/effective-date semantics and should not be hidden inside the generic RAG surface beyond early experimentation.
- Frontend visual-system foundation is now in place in `frontend/src/styles.css`: centralized CSS tokens cover typography, colors/surfaces/borders, spacing/layout, radius, shadows, popup/dropdown surfaces, control heights, state colors, and shared choice-button/navigation values. Existing component classes now share CSS-side role primitives for worklist cards, inner panels, compact surfaces, choice buttons, and meta/status chips without requiring JSX renaming. Browser-native confirmation/prompt popups have been replaced by the shared tokenized `app-dialog` layer; new destructive or typed-confirmation flows should use that pattern instead of `window.confirm` / `window.prompt`.
- Dark mode baseline is documented in Design_documents/30_dark_mode_theme_plan.md. Treat future theme work as token-level tuning and avoid panel-by-panel overrides.
- Dark-mode token audit first slice is complete: component-level direct colors in frontend styles were routed back through existing/new role tokens, leaving direct color values in the token definition layer.
- Dark-mode baseline is accepted after live UI review: the dark token palette, persisted React light/dark theme state, and topbar theme toggle are implemented. Relationship-map live corrections are included: selected graph-node border, edge label tokens, MiniMap tokens, a taller top object-selection row cap, and a larger graph canvas/preview work area. No known concrete dark-mode blocker remains; future work should be live-issue-driven token tuning for new or changed UI elements.
- The `AI-asszisztens` work surface is implemented and accepted as the current first UI/UX baseline from `Design_documents/31_ai_assistant_chat_module_plan.md`. Migration `0051_assistant_chats` adds `assistant_chats` and `assistant_messages`; backend routes support chat list/create/detail/rename/soft-delete and message send through the existing LM Studio provider. The module is intentionally generic and independent: no case/document/RAG/object/provenance coupling. The frontend places it after `Tudásbázis` and before `Audit napló`, with a slim conversation rail, three-dot rename/delete context menu, tokenized in-app rename dialog, stable internal chat canvas, centered empty-state composer, bottom-row composer during active conversations, Markdown-rendered assistant bubbles, typing indicator, and internal message-thread scrolling so the input does not jump with conversation length. Its delete action uses the shared tokenized `app-dialog` confirmation rather than a native browser popup. New chats no longer accept create-time titles; they start with `Új beszélgetés`, auto-title from the first user message, and can later be renamed through PATCH. The shared popup role tokens now style both searchable-select dropdowns and assistant context menus. Latest verification: `.venv/bin/python -m pytest tests/test_assistant.py` returned `6 passed`, `npm --prefix frontend run build` passed, `git diff --check` passed, and Alembic is at `0051_assistant_chats (head)`. Future AI-asszisztens work should be concrete live-issue-driven UX polish or optional enhancements such as streaming/reasoning UI, not new investigative coupling.
- The live UI was user-tested after the visual pass and accepted as a good current baseline. Future visual tweaks should first adjust the token layer (`--text-*`, `--color-*`, `--layout-*`, `--radius-*`, `--shadow-*`, control height tokens) before adding one-off selector values.
- The Full HD / 1080p media query is now active and should remain viewport-specific. It uses token overrides plus a small number of role/context overrides for denser 1080p use: control/hint/option/detail/monospace text roles, compact spacing, smaller control heights, compact buttons, searchable-select clear-button alignment, source/detail quote sizing, and object-fact card layout. Future 1080p work should continue in that media query and avoid broad per-component styling outside it.
- A dedicated mobile media query now starts at `max-width: 760px` and should remain the place for phone-specific layout behavior. It stacks work-surface grids, moves the sidebar into normal flow, gives input/button rows separate lines, resets desktop dashboard heights where they hurt mobile reading, fixes long source/document text and chip overflow, and uses mobile-specific ordering/stacking for `Ügy munkapad`, `Tudásbázis`, `Teljes iratfeldolgozás`, and `Irat rendező` panels. Keep future phone tweaks in this block unless a problem also exists on desktop.
- The mobile `Tudásbázis` Markdown answer/source view has a targeted overflow guard inside the same mobile media query: long Markdown paragraphs, links, inline code, fenced code blocks, tables, source metadata, and opened full source chunks should wrap or scroll inside their own cards instead of escaping the panel.
- Searchable-select dropdown clipping should be fixed at the containing layout context when possible: z-index alone cannot escape an ancestor with clipping overflow. The analysis source-filter context already allows overflow visibly for this reason.
- Added a backend/API latest-run summary for `search_findings`: `GET /api/v1/cases/{case_id}/research-findings/latest-run-summary` reports the latest research-finding run focus, source mode, retrieval settings, selected chunk count, saved/corrected/unconfirmed/rejected counts, and validation diagnostics.
- The `Ügy munkapad` now shows `Szemantikus index állapot` and persistent `Utolsó kutatási keresés` cards in a shared top status row. The research summary persists across refreshes because it is loaded from backend analysis-run/audit/finding state.
- The `Elemzés` / `Kutatási találatok` desktop split is now `0.8fr / 1.2fr`, giving the finding worklist more room without changing the other work surfaces.
- The left sidebar is narrower, model cards are stacked vertically, and each model card uses a two-column internal layout: model name/status on the left and load/unload controls on the right.
- The old bottom analysis-run summary inside the `Elemzés` panel was removed; the useful state now lives in the top latest-run card and the research-finding worklist.
- A broad frontend visual polish pass is active: lighter font weights for document names, panel/card titles, status chips, guide/error text, dropdown values, full-document worklist titles/focus/source labels, and research/review cards; flatter global button styling with no hover/active movement; explicit control/hint/option/detail/monospace text tokens; and a Full HD media query for denser 1080p layout.
- Verification for this visual-system slice: `npm --prefix frontend run build` and `git diff --check` should be kept as the minimum check. No migration is involved.

Initial implementation exists:

- Python/FastAPI scaffold,
- `.venv`,
- `pyproject.toml`,
- `.env.example`,
- health endpoint,
- secure config loader,
- JSONL audit writer skeleton,
- secure storage path resolver,
- SQLAlchemy/psycopg DB layer,
- Alembic migration foundation,
- case create/list API,
- document/page/chunk persistence models and migration,
- first large-case text storage contract tables through migration `0035_text_layer_manifests`: `document_text_layers` and `document_chunk_manifests`,
- first keyword-search migration foundation through migration `0036_search_entries`: `document_search_entries` plus `app/services/lexical_index.py` writer helpers for page/chunk search-entry rows,
- first full-document processing backend foundation through migration `0039_doc_proc_items`: `document_processing_items`, `full_document_processing` run type, `document_processing_item` output type, profile registry, read/list/status API, bulk soft-delete API, and a run-start service/API slice that creates source-evidence-validated preparatory items from selected current document pages,
- migration `0040_drop_db_text_cols` removes legacy DB full-text storage columns `document_pages.extracted_text` and `document_chunks.chunk_text` plus their old FTS indexes; full page/chunk text is now stored in the data-root text store,
- migration `0041_detach_audit_lifecycle` detaches `audit_events.case_id` and `audit_events.analysis_run_id` from hard foreign keys so audit rows can survive full case deletion,
- migration `0042_doc_proc_person_only` removes the unfinished non-person full-document processing profile from the active database contract; `document_processing_items` now accepts only `person_search_seeds` / `person`,
- full case deletion exists through `DELETE /api/v1/cases/{case_id}` and the frontend `Ügy végleges törlése` action; it deletes case-owned database rows, requests Qdrant point deletion by `case_id`, removes the case data-root directory, and writes a global `case_deleted` audit event,
- immutable TXT import API; TXT import now also writes first physical `pages.jsonl` / `chunks.jsonl` text-store files and their manifest rows while preserving current DB-backed API behavior,
- explicit imported-document processing validation run API,
- native-text PDF import foundation with configurable `docling_then_pypdf` parser profile,
- native PDF import quality gate before page persistence: partial/low-quality parser output such as empty pages keeps the original PDF for OCR but does not create pages, text layers, chunks, or indexing material,
- clean native PDF parse results write `document_text_layers` plus `pages.jsonl` alongside current DB-backed page rows,
- Docling optional dependency installed in `.venv` and explicit Docling PDF import smoke passed,
- explicit Tesseract OCR foundation for PDF documents with page/chunk versioning,
- OCR quality decision before page persistence: clean OCR can create the text-review layer, partial OCR reports usable/failed page numbers without creating a text layer automatically, and fully unusable OCR points to discard/replace,
- partial OCR acceptance backend slice: partial OCR writes staged candidate pages under the data root, and selected usable pages can be explicitly promoted through `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr/accept-partial`,
- clean OCR and accepted partial OCR write `document_text_layers` plus `pages.jsonl`; OCR replacement marks older current text/chunk manifests non-current,
- backend-provided OCR recommendation metadata for PDF documents; the frontend shows OCR actions only when the backend marks OCR as recommended or optional, and optional OCR is labeled as an OCR check because it may duplicate/noise native text,
- document page/chunk detail endpoints list only current versions by default, keeping previous native/OCR versions auditably stored but out of the active working text view; their compatible response fields `extracted_text` / `chunk_text` now come from the text-store helper,
- native PDF import and OCR now stop at a `text_review_required` text layer with current pages but no current chunks; users explicitly create chunks after page review through the `chunk_document` workflow,
- image-only/scanned PDF imports without native text remain audit-tracked `review_required` documents for explicit OCR processing,
- average Tesseract confidence capture on a 0..1 scale and `low_ocr_confidence` quality warning,
- document page API returns OCR confidence as a numeric value and handles Decimal-backed DB values,
- generated local PDF samples and parser/OCR evaluation scripts,
- default upload limit raised to 50 MiB through `BOBERDETECTIVE_MAX_UPLOAD_BYTES`,
- deterministic TXT chunk creation during import,
- keyword search over document pages/chunks,
- source-reference persistence and quote validation,
- DB-backed `SourceTextResolver` plus JSONL page/chunk text-store helpers with SHA256 manifest hashes; TXT import, clean PDF native parse, clean/accepted OCR, and explicit chunk creation write physical text-store files, while current runtime reads remain DB-backed through the resolver until source reads are rewired,
- runtime source-text reads now use physical text-store helpers for analysis run previews, review report excerpts, research-finding excerpts, `search_findings` SOURCE blocks and quote validation, source-reference quote/span validation, source-cited smoke analysis, embedding input, explicit chunk creation, and page/chunk API responses,
- LLMProvider abstraction with LM Studio/OpenAI-compatible model-list smoke,
- analysis run provenance foundation,
- synthetic LLM model benchmark script,
- generalized analysis module endpoint now centered on `search_findings` plus downstream `detect_contradiction_candidates`,
- event persistence foundation,
- case review report API,
- JSON review report export foundation,
- HTML review report export foundation,
- export review workflow foundation,
- event review workflow foundation,
- shared review service helper,
- entity persistence foundation,
- historical entity/event/claim raw extraction foundations have been retired from active module dispatch,
- entity review workflow foundation,
- review report filtering by object type, review status, and source validation status,
- review report export filters through `report_filters`,
- expanded review report source details with document metadata, offsets, chunk/page metadata, and bounded source excerpts,
- analysis module service split now keeps common retrieval/JSON helpers, source-bound `search_findings`, and downstream claim-pair contradiction detection,
- `summary_item` has been fully removed from the active structured object model through migration `0025_remove_summary_items`; there is no current valid workflow that creates or reviews summary items,
- legacy raw chunk modules (`extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`) have been removed from active backend dispatch, frontend module selection, response schemas, module-specific service files, and prompt/validation tests; API calls with those old module keys return `Unsupported analysis module`,
- legacy raw chunk module run type names have been retired from the active analysis run constraint through `0029_retire_legacy_run_types`; historical rows are mapped to `retired_analysis_module` while preserving the original old run type in `input_parameters.retired_original_run_type`,
- analysis module retrieval fallback for broader natural-language Hungarian prompts,
- local chunk indexing foundation through LM Studio/OpenAI-compatible embeddings and model-specific Qdrant collections, with `embed_chunks` analysis run provenance and chunk-level embedding metadata; model switches make chunks eligible for reindexing instead of incorrectly treating an old-model vector id as current,
- background chunk indexing through `POST /api/v1/cases/{case_id}/indexes/chunks/jobs`; the endpoint creates an `embed_chunks` analysis run and returns immediately, while FastAPI `BackgroundTasks` performs the LM Studio/Qdrant work,
- embedding index creation uses `BOBERDETECTIVE_EMBEDDING_BATCH_SIZE` defaulting to `8`, so large documents are embedded and upserted in smaller LM Studio/Qdrant batches instead of one memory-heavy request,
- chunk index status is available through `GET /api/v1/cases/{case_id}/indexes/chunks/status`; it supports whole-case, selected-document, and explicit document-list scopes, and the frontend uses it to show semantic index readiness, latest run progress, and block semantic/hybrid focused analysis until the active source scope is indexed with the configured embedding model,
- hybrid retrieval foundation through keyword, semantic, and hybrid strategies; `search_findings` can receive `retrieval_strategy`, and analysis run chunk inputs record `retrieval_match_type`,
- configured embedding model defaults to `text-embedding-bge-m3`; embedding calls auto-ensure this model is loaded through LM Studio before `/v1/embeddings`; older raw-module smokes remain historical notes only,
- contradiction candidate persistence, source linkage, API, review workflow, and review report inclusion,
- `detect_contradiction_candidates` analysis module foundation over source-cited claim pairs,
- live `detect_contradiction_candidates` smoke passed on a two-claim time conflict sample,
- `detect_contradiction_candidates` now treats fewer than two source-valid claims as a clean `validation_status=warning` precondition result, records claim-selection metadata as analysis run input, and avoids an unnecessary LLM call,
- `detect_contradiction_candidates` now builds deterministic backend-selected claim pairs, applies safe fetch/pair limits, supports meaningful focus filtering over claim/source text, records selected pair mappings in analysis run metadata, and rejects model output that references unselected pairs,
- `detect_contradiction_candidates` requires focus text. It uses `contradiction_candidate_limit` for its candidate cap. Its focus filter works on already extracted claim text/source quotes, keeps Hungarian accents, accepts non-stopword terms from two characters, and does not use the chunk semantic/hybrid retrieval selector,
- `detect_contradiction_candidates` now uses a Hungarian system prompt for source-faithful contradiction-candidate rules and JSON shape, with the user prompt limited to dynamic `QUERY`, `MAX_CANDIDATES`, and `CLAIM_PAIRS`,
- contradiction candidate validation now deduplicates same claim-pair/type candidates, caps most model-proposed `high` severities to `medium`, and replaces model-written titles/descriptions with conservative pair-bound text generated from the two selected source-cited claims,
- `detect_contradiction_candidates` supports `claim_review_scope`; default `reviewable` uses source-valid claims with review status `needs_review`, `verified`, or `corrected`, excluding `rejected`,
- `detect_contradiction_candidates` now requires explicit contradiction qualification: persisted candidates need `is_contradiction_candidate=true` and a concrete `conflict_basis`; contextual/non-conflicting pairs are rejected or carried as unsupported items,
- manual contradiction candidate creation now exists as a separate claim-pair workflow: the frontend exposes `Kezi ellentmondasjelolt`, only source-valid/non-rejected claims are selectable, selected claim text and sources are readonly-previewed, and the backend persists the candidate through a `manual_entry` analysis run,
- historical deduplication still matters for existing structured objects; new raw-module auto-creation has been retired in favor of finding conversion and manual source-bound object creation,
- ambiguous entity identity decisions should be handled through the explicit entity merge workflow, not by automatic alias guessing,
- claim, entity, event, and missing item candidate merge are available from report item cards and the object detail panel where applicable; merge remains same-main-type, but subtype matching is intentionally not enforced,
- source links can be moved, detached, parked, and reattached for claims, entities, events, and missing item candidates; these operations remain same-main-type, but subtype matching is intentionally not enforced,
- claim/entity/event/missing item candidate source links can be detached manually through audit-tracked `detach_source` review actions; frontend source details show `Levalasztas` only when a concrete source-link id is available,
- detached source links are parked in `detached_source_items` with the source reference plus object/source snapshots, and the frontend shows them under `Levalasztott forrasok`,
- detached sources can be reattached from the parked-source panel or permanently deleted from the parked-source worklist; the old irrelevant/discarded parked-source state has been removed,
- selected readonly chunk text can be attached directly to an existing same-case claim/entity/event/missing item candidate through a manual source attachment workflow; the backend validates active source material, target ownership/type, and exact duplicate source attachments,
- review-report items with `source_valid` and non-`corrected` review status can have title/description edited from the object detail panel through an audited backend endpoint; `corrected` or `source_invalid` items can instead be permanently deleted from the report workflow,
- searchable overlay selectors are now used for large target lists in merge, source move, manual contradiction selection, and detached-source reattach flows, so long 100+ item cases are easier to navigate,
- source details can also directly move a source to another same-main-type target object without a manual detach/reattach round,
- document lifecycle/parking is implemented with `active`, `excluded`, and `archived` states plus audit-tracked status changes; only active documents can be used as new source material for indexing, retrieval, analysis, source-reference creation, manual source-bound object creation, detached-source reattachment, source move/detach/merge, and contradiction candidate creation/claim selection,
- existing review findings from excluded/archived documents remain visible for historical review, and review report source details expose the source document lifecycle status,
- early document discard/delete is allowed only before the document has become analysis/source material; otherwise documents should be excluded or archived rather than physically removed. The discard path now explicitly removes document search entries, chunk manifests, and text layers before deleting discardable analysis runs, fixing the PDF/text-review FK failure seen on active zero-chunk documents,
- first `research_finding` backend foundation exists through migration `0021_research_findings`: `research_findings` table, SQLAlchemy model, schemas, internal create/list/get service, read-only list/detail API, and analysis-run output summary support,
- minimal LLM-backed source-bound finding search exists as backend module `search_findings` through migration `0022_search_findings_run_type`; it creates source references, persists `research_finding` rows, records analysis run inputs/outputs, and treats `suggested_type` as non-binding,
- `search_findings` quote validation is three-stage: exact `quote_text` matches are saved as `source_valid`; LLM items with a valid `source_label` and a meaningful partially recoverable quote are repaired by replacing `quote_text` with the best exact substring and are also saved as `source_valid` / `unconfirmed`; valid-label findings whose quote cannot be repaired are saved as `source_invalid` / `unconfirmed` with unresolved quote spans instead of being discarded. Quote repair requires at least one 30+ normalized-character part or at least two 12+ normalized-character parts recovered from the claimed source chunk.
- Source-invalid research findings remain actionable worklist items: the frontend labels them as `Nincs érvényes forráshivatkozás` with warning styling, and conversion to claim/event/missing item candidate preserves `source_invalid`; entity conversion creates the entity without a validated mention/source link so the review workflow still treats it as source-invalid.
- For unrepaired `source_invalid` research findings, the research-finding API deliberately returns the full referenced chunk/page text as `source_text_excerpt` even though the invalid quote itself has no exact span. This is only context for human inspection, not proof that the LLM quote was valid.
- The same inspection-context rule applies after conversion into structured review objects: review-report source rendering returns the referenced chunk/page text for `source_invalid` objects when the invalid quote has no exact span, so users can still inspect the source region without treating it as a valid quote.
- Detached-source reattach must not promote invalid quote sources to `source_valid`: claim/event/missing-item reattach paths now recompute object source validation from linked source references, and entity report status now validates mention source references instead of treating any mention as source-valid.
- The detached-source API now enriches parked source items with the referenced chunk/page text context. The frontend shows this in `Leválasztott forráshivatkozások` as a separate `Szövegrész megtekintése` details block, so users can inspect the source region before reattaching or creating a new object.
- first frontend workflow for research findings exists: `Kutatási találatok keresése` can be run from the analysis panel and the `Kutatási találatok` panel sits above `Áttekintési jelentés`, listing worklist findings with type suggestion, relevance reason, source validation/worklist status, and source-reference quote,
- human-controlled `research_finding` conversion exists: the backend endpoint reuses the finding source reference through the manual-entry path, creates a structured claim/entity/event/missing item candidate, marks the finding `converted`, stores target object metadata, and writes a conversion audit event; converted findings are hidden from the active worklist and the created structured object carries the later review/source workflow,
- research findings are now worklist items through migration `0024_research_findings_worklist`, not human-review objects; `research_findings.review_status` and the `research_finding` human-review object type were removed. Worklist operations are set aside, restore, single delete, and bulk delete. `ignored` means "félretéve", not rejected,
- users can select readonly text from document chunks and create source-bound manual claim/entity/event/missing item candidate objects through `manual_entry` provenance runs,
- detached source items can also create new source-bound manual claim/entity/event/missing item candidate objects and then store the created object as their handled target,
- missing item candidate persistence, source linkage, API, review workflow, and review report inclusion,
- missing item candidate review/export/manual workflows remain available, but the raw `detect_missing_items` analysis module has been retired,
- missing item candidate JSON/HTML export smoke coverage,
- analysis retrieval fallback improvement for short/inflected Hungarian query terms,
- minimal React/Vite frontend workbench scaffold,
- frontend review actions for review report items,
- frontend source detail and review history display for report items,
- frontend long-running operation feedback with elapsed time and last action summary,
- frontend document list and analysis run history views,
- frontend document page/chunk and analysis run input/output drill-down with human-readable selected-source and output summaries,
- frontend TXT/PDF import selection and OCR action for review-required/no-page PDF documents,
- frontend source scope controls now serve `search_findings`; old raw module options have been removed from the module selector,
- frontend contradiction-candidate UI now reflects the claim-pair workflow: the analysis panel requires focus and exposes claim review scope plus contradiction candidate cap for contradiction detection, claim-selection metrics and selected pairs are rendered in analysis run details, analysis summaries show claim-pair based execution, and review report items include a conservative review note,
- frontend analysis focus text starts empty for every module; module-specific examples are placeholders only and are not sent as query text unless the user types actual text,
- frontend review filter controls and object detail panel,
- frontend export history and review report filter controls,
- pytest smoke tests.

Completed design documents:

- `Design_documents/00_project_context_for_codex.md`
- `Design_documents/01_concept_and_mvp_requirements.md`
- `Design_documents/02_technical_architecture_v1.md`
- `Design_documents/03_database_schema_v1.md` with v1.1 pre-implementation refinements folded in
- `Design_documents/03a_database_schema_pre_implementation_review.md`
- `Design_documents/04_runtime_and_deployment_v1.md`
- `Design_documents/05_api_design_v1.md`
- `Design_documents/06_document_processing_pipeline_v1.md`
- `Design_documents/07_prompt_and_json_schema_collection_v1.md`
- `Design_documents/08_mvp_backlog_and_implementation_sequence.md`
- `Design_documents/09_environment_verification_and_security_baseline.md`
- `Design_documents/10_analysis_batch_processing_plan.md`
- `Design_documents/11_document_taxonomy_and_source_filtering_plan.md`
- `Design_documents/12_source_bound_findings_model_plan.md`
- `Design_documents/13_legacy_analysis_module_retirement_plan.md`
- `Design_documents/14_work_surface_ui_architecture_plan.md`
- `Design_documents/15_full_document_processing_plan.md`
- `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`
- `Design_documents/17_storage_migration_impact_review.md`
- `Design_documents/18_keyword_search_text_store_migration_plan.md`
- `Design_documents/19_document_taxonomy_retirement_plan.md`
- `Design_documents/20_general_rag_question_answering_plan.md`
- `Design_documents/21_markdown_knowledge_base_module_plan.md`
- `Design_documents/22_markdown_ast_chunking_plan.md`
- `Design_documents/23_markdown_knowledge_retrieval_hardening_plan.md`
- `Design_documents/24_markdown_section_aware_retrieval_packing_plan.md`
- `Design_documents/25_relationship_map_graph_view_plan.md`
- `Design_documents/26_review_report_status_cleanup_plan.md`
- `Design_documents/27_relationship_map_graph_implementation_plan.md`
- `Design_documents/28_relationship_map_horizontal_layout_plan.md`
- `Design_documents/29_full_document_free_question_plan.md`
- `Design_documents/30_dark_mode_theme_plan.md`

## Project Summary

The project is a fully local, auditable investigative document intelligence system.

It is meant to process case-related documents and create structured, source-cited, human-reviewable outputs:

- document inventory,
- entities and mentions,
- event timeline,
- claims,
- contradiction candidates,
- missing item candidates,
- source-cited summaries,
- exports.

The system must not make autonomous legal or investigative decisions.

## Core Constraints

The most important design constraints:

- local-first / offline-capable,
- no cloud dependency,
- sensitive-data-safe,
- original documents immutable,
- page-level text stored,
- chunks stored and searchable,
- every AI-generated object source-cited,
- every AI-generated object traceable to an analysis run,
- human review required for meaningful use,
- exports must be auditable,
- legal RAG remains a later specialized corpus profile; the general local RAG question-answering layer described in `Design_documents/20_general_rag_question_answering_plan.md` now has a stable first implementation baseline, so the next larger planned slice is the dedicated `Tudásbázis` module for Markdown-based structured knowledge material. The dedicated `Audit napló` workflow over `audit_events` remains the following larger work surface.

Mandatory rule:

```text
No source -> no claim.
```

## Runtime Direction

The current runtime direction is:

```text
Windows 11 host:
  - VS Code / Codex / browser
  - LM Studio native runtime

WSL2 Ubuntu:
  - application runtime
  - backend
  - workers
  - PostgreSQL
  - Qdrant
  - document processing
  - OCR / NLP
  - audit logs
  - exports
```

LM Studio is now the default development LLM provider.

The backend must use an `LLMProvider` abstraction so LM Studio can later be replaced by:

- Ollama,
- llama.cpp / llama-server,
- another local runtime.

## Database Schema Review Notes

The database schema v1 is already drafted, and the main schema document has been updated with the review's most important pre-implementation refinements.

The incorporated refinements are:

1. Add page/chunk versioning:
   `version_no`, `is_current`, `superseded_by_id`.
2. `summary_items` were originally promoted during schema planning, but this path has since been reversed: migration `0025_remove_summary_items` removed the active table/API/model because no current workflow can produce semantically valid summary items.
3. Add `source_validation_status` to AI-output tables.
4. Keep `source_references` as a central table.
5. Keep `analysis_runs` as the central provenance table.
7. Use `text + CHECK` instead of PostgreSQL ENUM in early migrations.
8. Do not implement trigger-based audit in the first MVP.
9. Use explicit application-level audit service plus append-only JSONL.

## WSL Migration Context

The user has created or prepared a dedicated WSL2 Ubuntu environment.

The intended WSL-side project location is:

```text
~/projects/Codex_BoberDetective
```

The intended data location is:

```text
~/boberdetective-data
```

The user may manually copy this repository into the WSL path and then open it with:

```bash
cd ~/projects/Codex_BoberDetective
code .
```

Future sessions should assume the project may now be opened from WSL rather than the original Windows path.

Previously unverified items now checked:

- WSL can reach the Windows-hosted LM Studio API at `http://127.0.0.1:1234/v1`.
- Whether LM Studio embedding support is sufficient, or a separate embedding provider is needed.
- Whether the selected local model is good enough for Hungarian claim/event/contradiction extraction.
- Historical user-side semantic/hybrid retrieval smoke with the former Qwen embedding profile found no obvious quality regression, but that embedding path is now retired. The active embedding profile is `text-embedding-bge-m3`, and semantic/hybrid comparison requires reindexing into the new model-specific Qdrant collection.
- Document/case source modes now use retrieval-aware source selection from explicit focus text. Empty focus is rejected for raw-chunk modules so large cases are not processed blindly; document-mode retrieval is constrained to the selected document.
- Raw-chunk source-selection query variants keep Hungarian accents and accept non-stopword terms from two characters; the original focus text remains the first retrieval query.
- Backend raw-chunk analysis source selection still supports optional `page_start` / `page_end` filters inside selected-document source scope for API compatibility. The frontend no longer exposes selected-document page-range controls; selected-document UI searches use the full selected document.
- Whole-case raw-chunk analysis has no page-range fields or backend page-range requirement. If API callers omit page fields for document scope, the backend uses the full document and rejects only out-of-document ranges.
- Historical user-side retrieval/analysis smoke after selected-document page-range filtering produced precise results, but the current UI direction favors full selected-document search because typical documents are expected to be about 30-50 pages.
- Recent local-LLM quality testing showed that module-first raw chunk extraction is too rigid for the long-term workflow: `extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, and `detect_missing_items` force object categories too early and can create noisy or artificial outputs. The active research workflow is source-bound `research_finding` records first, with human-controlled conversion into structured objects later.
- The planned `research_finding` schema should be graph-view compatible from the start: keep source-reference -> finding -> structured-object relationships explicit and queryable, but do not introduce a graph database or graph UI prematurely.
- A loose first direction for that future graph UI is now recorded in `Design_documents/25_relationship_map_graph_view_plan.md`: a dedicated `Kapcsolati térkép` module should start as a read-only, object-centered React Flow / XYFlow visualization over existing source-valid structured objects and backend-derived node/edge projections. It should not introduce a graph database, AI-generated graph edges, or source-invalid focus objects in the first version.
- `Design_documents/26_review_report_status_cleanup_plan.md` records the implemented review-report status cleanup: the active `new` review status is retired, the user-facing `corrected` label is `Korrekcióval kizárt`, and merge/source-detach/source-move orphaned objects consistently appear with corrected/source-invalid semantics where applicable.
- A promising full-document prompt experiment extracted person-focused search seeds from a whole coherent document instead of selected chunks. This should become a separate, well-defined work surface later, not a replacement for the current source-bound research workflow.
- Large-case storage/retrieval has been promoted to a design gate before full-document backend implementation. The current DB-centric page/chunk text storage is not the desired long-term shape for 5000+ document cases; `Design_documents/16_large_case_document_storage_and_retrieval_plan.md` defines the proposed split between PostgreSQL metadata/workflow/audit, data-root text store, and Qdrant retrieval index.
- The first code-level impact review for that redesign is captured in `Design_documents/17_storage_migration_impact_review.md`. It maps current dependencies on `document_pages.extracted_text` and `document_chunks.chunk_text` across import, source references, keyword search, vector indexing, analysis prompts, review report excerpts, research-finding excerpts, and analysis-run previews.
- Storage-refactor code slices are implemented through the strict DB-text removal point: `app/services/text_store.py` defines JSONL-backed text-store helpers, and source-text reads in source-reference validation, `search_findings` prompt/quote validation, embedding input creation, analysis run previews, review report excerpts, research-finding excerpts, source-cited smoke, explicit chunk creation, and page/chunk detail API responses go through this abstraction. Migration `0035_text_layer_manifests` adds `document_text_layers` and `document_chunk_manifests`, imports/chunking write physical `pages.jsonl` / `chunks.jsonl` plus manifest rows, and migration `0040_drop_db_text_cols` removes `document_pages.extracted_text`, `document_chunks.chunk_text`, and the old DB FTS indexes.
- The first full-document processing backend run-start slice is implemented. `POST /cases/{case_id}/documents/{document_id}/full-document-processing/runs` creates a `full_document_processing` analysis run, reads current page text from the data-root text store, and sends the selected page range to the local chat model in one request. The compact prompt asks only for the named character/item, compact `recommended_search_focus`, and `source_label`; it no longer asks the model for `short_description` or `unsupported_items`. The backend then builds source evidence by finding the returned `display_label` on the selected source page. Matching is OCR-spacing tolerant, but stored evidence uses the exact original source substring/span. The request has no artificial item cap; it uses a 9000-token output safety ceiling to stop runaway repetition, while long local LLM calls use the configured 900 second timeout. These items remain preparatory worklist records tied to a document and analysis run.
- Repeated exact full-document item labels are no longer discarded. They remain available as candidates, and list responses expose `occurrence_status` so the frontend can show `Egyedi` or `Többször előforduló`.
- Full-document processing currently keeps only the stable `person_search_seeds` profile. The earlier `entity_search_seeds` idea has been removed from active backend/frontend workflow and should be reintroduced only after a separate prompt and validation design.
- Person-profile focus uses a separate LLM-provided `recommended_search_focus`. The prompt now avoids unused LLM fields and asks only for `display_label`, `recommended_search_focus`, and `source_label`; the backend uses the LLM focus when present and falls back to `display_label` only when missing.
- Full-document source evidence construction now repairs common LLM `source_label` mistakes: it first checks the returned page label, then searches all selected source pages for the validated display label and stores the actual matching page. Items whose label cannot be found anywhere are no longer discarded; they are saved into the same worklist with empty `source_evidence_json`, warning metadata, and a frontend `Nem megerősített` label/style so they can be focused, set aside, or deleted like other worklist items.
- The `Teljes iratfeldolgozás` frontend surface is now connected to backend profiles, selected page-range run-start execution, active/set-aside item listing, inline source-evidence display, set-aside/restore status changes, deletion marking, all-visible deletion marking, bulk soft-delete, worklist name search, and focus handoff back to the `Ügy munkapad` search workflow.
- Keyword search migration is implemented past the old-column dependency: `DocumentSearchEntryModel`, migration `0036_search_entries`, and `app/services/lexical_index.py` writer helpers maintain `document_search_entries`. Active keyword search queries `document_search_entries.search_vector`; quotes/full excerpts are read from the physical text-store path.
- Document taxonomy is now retired from active workflow rather than the future large-case source-narrowing strategy. `Design_documents/19_document_taxonomy_retirement_plan.md` captures the staged cleanup. The frontend taxonomy workflow has been removed from import, document detail, and analysis source filters; import now accepts multiple TXT/PDF files and uploads them sequentially through the existing backend endpoint. Backend taxonomy API/filter/reclassification workflow has also been retired, and migration `0037_remove_doc_taxonomy` removes the remaining taxonomy DB/model/search-entry columns and related indexes/constraints.
- Full-case deletion is implemented and smoke-checked: `DELETE /api/v1/cases/{case_id}` removes case-owned DB rows, case files, and Qdrant points by `case_id`, while migration `0041_detach_audit_lifecycle` lets `audit_events` preserve historical `case_id` / `analysis_run_id` metadata after the case and run rows are gone. A user-side two-PDF import/OCR/chunk/index/search/convert smoke completed successfully before deletion, and post-delete checks found no remaining business rows, case files, or Qdrant points outside intentionally preserved audit/user records.

## Suggested Next Steps

Likely next steps, in order:

1. Read the handoff docs and design documents.
2. Treat the `Tudásbázis` module as a stable first baseline. Batch-only Markdown import, Marko/AST parsing, knowledge indexing/querying, lifecycle controls, Markdown-rendered answers, lazy full-source inspection, and the current Markdown-aware retrieval/packing behavior are implemented and live-tested.
3. Treat the `Áttekintési jelentés` status cleanup as implemented. `new` is retired, `corrected` is shown as `Korrekcióval kizárt`, orphaned corrected objects are source-invalid where applicable, and destructive frontend actions use the shared danger/kuka visual language.
4. Continue `Design_documents/27_relationship_map_graph_implementation_plan.md` as the current larger planned slice: the multi-focus `Kapcsolati térkép` backend and frontend baseline are implemented; next step is live testing and focused UX/bug tuning.
5. First graph slice should be read-only and object-centered: backend graph-projection API over existing source-valid structured objects, then React Flow / XYFlow visualization in the frontend.
6. Do not introduce a graph database, AI-generated edges, predictive/risk semantics, or source-invalid focus objects in the first graph version.
7. Treat the first `Szabad iratkérdés` implementation slice from `Design_documents/29_full_document_free_question_plan.md` as backend/frontend baseline: it persists `full_document_answers` and shows an `Iratválasz` panel. Next work here should be live-test driven UX/prompt hardening, not another data-model redesign.
8. Keep the dedicated `Audit napló` backend/API/panel over `audit_events` as a later larger work surface unless explicitly reprioritized.
9. Continue opportunistic live-test driven fixes for implemented `Általános iratkérdező`, `Tudásbázis`, full-document person profile, desktop/1080p/mobile UI, and prompt/JSON fallback paths, but do not treat them as the main planned slice unless a concrete bug or quality issue appears.

Strategic rationale:

- The frontend is currently usable enough for the MVP workflow and now has Hungarian visible labels.
- The work-surface UI architecture is planned in `Design_documents/14_work_surface_ui_architecture_plan.md`; the first shell slice is implemented with `Ügy munkapad`, `Teljes iratfeldolgozás`, and `Audit napló` surfaces. The `Teljes iratfeldolgozás` surface is now a working backend-connected surface, not only a scaffold.
- Latest UI polish is intentionally broad but still within the existing token/role system: `Tudásbázis` now has a two-column desktop layout and mobile wrapping/stacking, `Teljes iratfeldolgozás` has a stable 1:1 top row plus full-width worklist row, and `Irat rendező` has a cleaner selected-collection layout, no auto-selected first collection, stable document/collection heights, and mobile full-width collection actions.
- Full-document processing backend contract is planned in `Design_documents/15_full_document_processing_plan.md`; it keeps full-document extraction outputs as separate preparatory `document_processing_item` records before any human-driven conversion or research workflow handoff. The current slice includes the stable person-only profile, run-start, source-evidence validation, active/set-aside worklist views, restore, deletion marking with bulk delete, and focus handoff. Non-person full-document profiles are intentionally not active.
- The `Szabad iratkérdés` full-document profile is captured separately in `Design_documents/29_full_document_free_question_plan.md` and has its first implementation slice. It uses selected active document pages plus a user question, writes persistent `full_document_answers`, and displays an `Iratválasz` style answer surface with one-line question input, automatic saved-answer refresh after deletion, previous-answer choice buttons, and tolerant answer JSON recovery. It is intentionally separate from `document_processing_items`, `search_findings`, `Általános iratkérdező`, and `Tudásbázis`.
- Large-case storage/retrieval planning is captured in `Design_documents/16_large_case_document_storage_and_retrieval_plan.md`. The critical text-store-first slices needed by the full-document backend are implemented; the intended long-term direction remains PostgreSQL for metadata/workflow/audit/source references, data-root text store for extracted pages/chunks, and Qdrant for retrieval indexes.
- The document ingestion foundation now handles native PDF parsing, explicit OCR, review-required states, confidence metadata, and medium scanned PDF uploads well enough to move forward.
- The raw-chunk analysis modules are batch-capable and live-smoke passed on document/case source modes, but they are now retirement candidates rather than the future main workflow.
- Large-case usability should no longer depend on import-time structured document taxonomy. Frontend import/detail/analysis taxonomy controls, backend taxonomy API/filter/reclassification code, and the remaining taxonomy DB/model/search-entry columns have been retired. Do not reintroduce uncontrolled free-text document classification either.
- Historical `document_reclassified` audit events may remain useful for the future audit log, but no active reclassification endpoint/workflow remains.
- Document lifecycle is now an active-source gate. Inactive documents remain historically visible where already cited, but must not become new source material unless restored to `active`.
- The current `Elemzesi elozmenyek` panel lists `analysis_runs` only. Import/OCR/chunking appear there because they create provenance runs; pure audit events such as `document_reclassified` belong in a future separate `Audit naplo` panel backed by `audit_events`.
- Contradiction detection is downstream of source-cited claims, so it should remain claim-pair based and preserve `no source -> no claim` through claim/source-reference provenance.
- The previous major product directions, the `Általános iratkérdező` and the dedicated `Tudásbázis` module, both have stable implementation baselines. The current Tudásbázis retrieval state is the accepted stable baseline after live validation; further work here should be concrete-example-driven hardening. The current larger planned work surface is the `Kapcsolati térkép` graph-view direction from `Design_documents/25_relationship_map_graph_view_plan.md`: the single-focus read-only projection baseline is implemented, and the next meaningful slice is multi-focus object selection plus a unified graph endpoint. The dedicated `Audit napló` API/panel over `audit_events` remains a later larger work surface unless explicitly reprioritized, while RAG/full-document/UI work should continue as live-test driven hardening rather than broad new implementation.

Environment verification notes:

- WSL Ubuntu 24.04 is ready.
- Python 3.12, Git, Node/npm, curl, Make, Docker CLI, Docker Compose, PostgreSQL CLI, Tesseract, and ShellCheck are available.
- Git repository is initialized on branch `main` and tracks `origin/main`.
- Docker daemon access works for `bober`.
- PostgreSQL and Qdrant are running through Docker Compose.
- PostgreSQL is reachable at `127.0.0.1:5432`.
- Qdrant is reachable at `127.0.0.1:6333`.
- Tesseract has `hun` language data installed.
- LM Studio is reachable from WSL at `http://127.0.0.1:1234/v1`.

Implementation status:

- `.venv` exists and project dependencies are installed.
- `pyproject.toml` and `.env.example` exist.
- Initial FastAPI scaffold exists under `app/`.
- Health endpoint works.
- SQLAlchemy/psycopg DB layer exists.
- Alembic migrations through `0034_review_edit_text` are applied.
- `users`, `cases`, `case_users`, `audit_events`, `documents`, `document_pages`, `document_chunks`, `source_references`, `analysis_runs`, `analysis_run_inputs`, `analysis_run_outputs`, `claims`, `claim_sources`, `entities`, `entity_mentions`, `human_reviews`, `events`, `event_sources`, `exports`, `export_items`, `contradiction_candidates`, `contradiction_candidate_sources`, `missing_item_candidates`, `missing_item_candidate_sources`, `research_findings`, and `detached_source_items` tables exist.
- Case create/list API works.
- Case creation writes DB audit event and JSONL audit event.
- Document/page/chunk persistence foundation exists.
- Immutable TXT import works through `POST /api/v1/cases/{case_id}/documents`.
- Native-text PDF import works through `POST /api/v1/cases/{case_id}/documents` using `BOBERDETECTIVE_PDF_PARSER`; the default `docling_then_pypdf` profile prefers Docling when installed and falls back to local `pypdf`.
- Explicit `BOBERDETECTIVE_PDF_PARSER=docling` import smoke passed with parser `docling` and `parse_document` validation `passed`.
- PDF parser hardening now covers multi-page native PDFs, corrupt PDFs, partially empty PDFs, and image-only PDFs; partially empty native-text PDFs and no-native-text PDFs become `review_required` with analysis run validation `warning`.
- The Docling adapter uses native-text mode with OCR/table/remote services disabled, but the first run downloaded local model artifacts; offline deployments should pre-cache these dependencies/artifacts.
- Explicit document processing validation works through `POST /api/v1/cases/{case_id}/documents/{document_id}/process`.
- Explicit PDF OCR works through `POST /api/v1/cases/{case_id}/documents/{document_id}/ocr` with `ocr_document` analysis run provenance.
- OCR test coverage includes a generated scanned-style/image-only PDF fixture: native parsing reports no source text, then Tesseract extracts OCR text from the rendered page.
- OCR API smoke passed: document `processed`, run `ocr_document`, validation `passed`, and current page text source `ocr`.
- Synthetic PDF samples exist under `samples/pdf/`: native-text, good scanned, weak scanned, and mixed empty-page PDFs.
- `scripts/evaluate_pdf_samples.py` reports native parse outcome, OCR text length, confidence, and quality issues; current weak scanned sample triggers `low_ocr_confidence`.
- Frontend now exposes backend OCR recommendations and a separate `Szovegreszek letrehozasa` action for `text_review_required` documents; after OCR it refreshes document status/pages, and after chunk creation it refreshes chunks and analysis run history.
- `Design_documents/10_analysis_batch_processing_plan.md` remains useful for batching/source-selection background, but the active raw-source workflow is now `search_findings`, not module-specific raw extraction.
- Historical raw-module live smokes remain useful as implementation history only. Current live smokes should use `search_findings`, research-finding conversion, manual source-bound object creation, and downstream `detect_contradiction_candidates`.
- Frontend now exposes source scope controls for `search_findings`: selected document, whole case, iratgyűjtemény, required focus text, `Szovegresz plafon` defaulting to 45 and capped at 90, retrieval strategy, and `Maximalis batch meret` defaulting to 3 with backend validation between 1 and 15. Retrieval ranking is used for chunk selection, but LLM input batches are now reordered by document/page/chunk and never mix chunks from different documents. Selected-document mode no longer exposes page-range controls and searches the full selected document from the UI. Retired raw module options are no longer available; `detect_contradiction_candidates` keeps its claim-pair workflow with required focus.
- Frontend analysis run details render selected chunk inputs as Hungarian source summaries with document/page/chunk, retrieval match type/score, batch position, and the full source chunk text that was sent to processing. Output rows show short object/source summaries, deleted or missing outputs show a human-readable unavailable notice, and `manual_entry` runs are rendered as the selected source plus the object created or attached from it. `input_kind=claim_selection` payloads remain rendered as Hungarian claim-selection summaries with selected pair rows; claim inputs show which selected pairs include the claim.
- Analysis run list/detail APIs expose frontend-oriented metadata for the current readable details view: list items include `display_label` for the research query or manual-created object title, and output summaries include source-reference document/page/chunk/quote fields when available.
- Frontend analysis panel marks contradiction focus as required, shows a claim-pair module note, and exposes `Allitaskor` (`reviewable`, `verified`, `needs_review`, `all_source_valid`) plus `Ellentmondasjelolt plafon` for `detect_contradiction_candidates`; analysis summaries show `claim-par alapu` instead of implying raw chunk selection.
- Frontend focus placeholders are informational only; raw-chunk module runs are disabled until the user types focus text, and the backend enforces the same rule.
- Frontend contradiction report items and detail view show a conservative note that the object is an ellenorizendo jelolt, not a proven contradiction.
- TXT import stores the original bytes under UUID-based immutable storage paths.
- TXT import creates the first `document_pages` record and now also writes a current `document_text_layers` row plus `pages.jsonl`.
- TXT import still creates deterministic page-local `document_chunks` directly and now writes a current `document_chunk_manifests` row plus `chunks.jsonl`. Native PDF import and OCR create current pages first, then explicit chunk creation produces page-local `document_chunks` with `char_window_v2`; chunking stays within a single processed page for source-location fidelity, prefers paragraph breaks, then sentence-end breaks, then line breaks/spaces before a hard character limit.
- Document chunks are available through `GET /api/v1/cases/{case_id}/documents/{document_id}/chunks`.
- TXT import writes DB + JSONL audit with chunk count metadata.
- Keyword search works through `POST /api/v1/cases/{case_id}/search/keyword`.
- Keyword search uses PostgreSQL full-text search over current pages/chunks with parameterized SQLAlchemy queries.
- Keyword search returns source object identifiers, document metadata, page ranges, scores, and plain-text quotes.
- Source references work through `POST /api/v1/cases/{case_id}/source-references`.
- Source reference validation works through `POST /api/v1/cases/{case_id}/source-references/validate`.
- Source reference creation validates page/chunk ownership and quote presence/span before persistence.
- Source reference creation writes DB + JSONL audit.
- LLMProvider abstraction exists in `app/services/llm.py`.
- LM Studio smoke works through `GET /api/v1/system/llm/smoke`.
- Current LM Studio smoke result: reachable at `http://127.0.0.1:1234/v1`; configured chat and embedding models are available.
- Analysis run list/detail API works through `GET /api/v1/cases/{case_id}/analysis-runs`.
- Analysis run lifecycle helpers write started/succeeded/failed/cancelled audit events.
- Analysis run inputs and outputs can explicitly record the source objects used and produced by a run.
- Synthetic LLM benchmark exists at `scripts/run_llm_benchmark.py`.
- Benchmark result from 2026-05-11 with OpenAI-compatible `/v1/chat/completions`: `meta-llama-3.1-8b-instruct` reached `10/12` on the tuned source-faithfulness smoke; `qwen/qwen3.5-9b` produced empty final `content` because reasoning output consumed the response path.
- Benchmark result from 2026-05-12 with LM Studio native `/api/v1/chat` and `reasoning: "off"` for Qwen: final run gave `qwen/qwen3.5-9b` `12/12` in 18.3s and `meta-llama-3.1-8b-instruct` `10/12` in 6.2s.
- Current interpretation: Qwen is the better first quality candidate when called through LM Studio native API with reasoning disabled; Llama remains the faster fallback/control model.
- LM Studio native API notes captured in `Design_documents/04_runtime_and_deployment_v1.md`: use `max_output_tokens`, not `maxTokens`; prefer `store: false`; prefer `system_prompt`; send `reasoning: "off"` only for reasoning-capable models such as Qwen.
- Backend now supports explicit LM Studio native chat-model loading through `POST /api/v1/system/llm/load-chat-model`.
- LM Studio native chat calls now auto-ensure the configured chat model is loaded before sending `/api/v1/chat`; loaded instance ids are reused when present, and the configured load profile is applied only when no matching instance is loaded.
- Current preferred chat-model LM Studio load profile is configured as `context_length=61440`, `eval_batch_size=4096`, `flash_attention=true`, and `offload_kv_cache_to_gpu=true`.
- Embedding model load uses the active `text-embedding-bge-m3` profile with `context_length=4096`; LM Studio currently rejects `eval_batch_size`, `flash_attention`, and `offload_kv_cache_to_gpu` for embedding models, so those are intentionally not sent for embedding load.
- The previous Qwen embedding profile is intentionally retired and should not be restored as the default. The current balanced two-model profile uses chat `context_length=61440`, chat `eval_batch_size=4096`, BGE-M3 embedding `context_length=4096`, and LLM request timeout `900` seconds for long full-document runs.
- Live model-load smoke accepted the profile and returned `qwen/qwen3.5-9b:2`, `status=loaded`, `load_time_seconds=10.784`, with echoed `parallel=4`.
- Future native provider refinement: switch benchmark/runtime payload from locally tested `input.type="text"` to documented `input.type="message"` if local testing confirms compatibility.
- First source-cited analysis smoke works through `POST /api/v1/cases/{case_id}/analysis/source-cited-smoke`.
- The smoke endpoint retrieves a chunk by keyword search, records query/chunk as analysis run inputs, calls Qwen through LM Studio native API with reasoning disabled, validates quote text against the chunk, creates a source reference, persists a claim, records outputs, and finishes the run with validation status.
- Claims work through `GET /api/v1/cases/{case_id}/claims` and `GET /api/v1/cases/{case_id}/claims/{claim_id}`.
- Claim creation requires a same-case analysis run and source reference in service logic.
- Live smoke result: `analysis 200`, `validation_status=passed`, claim persisted with one source, `source_validation_status=source_valid`.
- Claim review works through `POST /api/v1/cases/{case_id}/claims/{claim_id}/reviews`.
- Supported claim review actions now: `verify`, `reject`, `mark_needs_review`, `comment`.
- Claim review writes append-only `human_reviews` records and `claim_review_recorded` audit events.
- Live review smoke result: claim moved to `verified`, review history count 1.
- Generalized analysis module execution now exists through `POST /api/v1/cases/{case_id}/analysis/modules/{module_key}`.
- Currently supported analysis module keys: `search_findings`, `detect_contradiction_candidates`.
- Analysis module implementation is split across `app/services/analysis_module_common.py`, `analysis_module_findings.py`, and `analysis_module_contradictions.py`; `analysis_modules.py` remains the thin public facade.
- The retired raw module keys (`extract_claims`, `extract_events`, `extract_entities`, `summarize_case`, `detect_missing_items`) are no longer accepted by the backend and no longer appear in the frontend module selector.
- The `search_findings` module performs source-bound retrieval, records query/chunk inputs, calls LM Studio native with the flexible finding prompt, validates returned quotes against labeled source chunks, creates source references, persists research finding worklist items, records outputs, and finishes the analysis run.
- Current `search_findings` prompt strategy: the Hungarian system prompt contains the task, source-faithfulness, QUERY-focus, output-field, quote-text, source-label, and valid-JSON rules. The user prompt contains only dynamic run data (`QUERY`, `BATCH`, `SOURCE`), so the model sees one stable instruction contract plus changing source material.
- The expected `search_findings` JSON shape now puts `source_label` as the first field of every finding object. This is deliberate local-model steering: recent live testing showed it reduces omitted `source_label` failures without adding another backend special case.
- The frontend `Kutatási találatok` panel keeps the latest `search_findings` run diagnostics in session state and displays validation status, saved findings, corrected-quote findings, non-confirmed findings, backend-validation rejected candidates, and the first rejection reasons above the research-finding worklist. Backend validation messages distinguish unknown `source_label` from quote exactness losses. Valid-label / invalid-quote items are persisted as actionable `source_invalid` / `unconfirmed` worklist items with warning styling, not as a separate response-only workflow.
- The `detect_contradiction_candidates` module takes existing source-cited claims, builds deterministic selected claim pairs, records claim-selection/pair metadata and selected claims as analysis inputs, calls LM Studio native with the `detect_contradiction_candidates_v1` prompt only when at least one selected pair exists, validates returned claim labels against the selected pair set, persists contradiction_candidates/contradiction_candidate_sources, records outputs, and finishes the analysis run.
- Empty/precondition smoke result: on a case with 0 source-valid claims, `detect_contradiction_candidates` returned `HTTP 200`, `validation_status=warning`, 0 candidates, an unsupported item explaining that at least two source-valid claims are required, and an analysis run `filter` input with `input_kind=claim_selection`.
- Claim-rich pair-selection smoke result: on case `a9ccf14e-093d-40db-970e-856e19df826f`, focused query `Kovacs Anna Nagy Peter telefonhivas` selected 8 fetched claims, 6 focus-matched claims, 8 backend-selected pairs, returned `HTTP 200`, `validation_status=passed`, and 2 `time_conflict` candidates.
- Latest contradiction quality smoke on the same case returned conservative deterministic titles, pair-bound descriptions from the two selected claim texts, and `severity_hint=medium` for time conflicts.
- Latest contradiction qualification smoke returned `HTTP 200`; the model marked some selected pairs as unsupported because they were related but not conflicting, while time-conflict-like pairs were still persisted as conservative `medium` candidates.
- Historical `detect_contradiction_candidates` smoke result used claims produced by the former raw module path. Current smokes should use manually created or finding-converted claims before running contradiction detection.
- Review report smoke for `object_type=contradiction_candidate` returned the candidate with expanded source details.
- Analysis module retrieval now tries the original query, a normalized significant-term query, and individual normalized terms. This keeps the public search API strict while making analysis modules less brittle for natural Hungarian prompts.
- Historical `summarize_case` smokes no longer describe an active module; summary item APIs and tables have been removed from the active system.
- Unsupported module keys are rejected before execution.
- Event list/detail works through `GET /api/v1/cases/{case_id}/events` and `GET /api/v1/cases/{case_id}/events/{event_id}`.
- Event review works through `POST /api/v1/cases/{case_id}/events/{event_id}/reviews`.
- Supported event review actions: `verify`, `reject`, `mark_needs_review`, `comment`.
- Event review updates `events.review_status`, writes append-only `human_reviews` records, and writes `event_review_recorded` audit events.
- Live event review smoke result: `review 200`, event moved to `verified`, review history count 1.
- Entity list/detail works through `GET /api/v1/cases/{case_id}/entities` and `GET /api/v1/cases/{case_id}/entities/{entity_id}`.
- Live `extract_entities` module smoke result: `analysis 200`, `validation_status=passed`, 2 persisted person entities with mentions and source references.
- Entity review works through `POST /api/v1/cases/{case_id}/entities/{entity_id}/reviews`.
- Supported entity review actions: `verify`, `reject`, `mark_needs_review`, `comment`.
- Entity review updates `entities.review_status`, writes append-only `human_reviews` records, and writes `entity_review_recorded` audit events.
- Live entity review smoke result: `review 200`, entity moved to `verified`, review history count 1.
- Shared review helper exists in `app/services/reviews.py`.
- Claim, entity, event, and export review workflows now use the shared helper for status mapping, review history listing, append-only review record creation, and audit writing.
- Contradiction candidate list/create/detail/review API exists through `/api/v1/cases/{case_id}/contradiction-candidates`.
- Contradiction candidate creation requires a same-case analysis run, at least two same-case source references, and either a same-case claim pair or event pair.
- Contradiction candidate reviews use append-only `human_reviews` with `object_type=contradiction_candidate`.
- Contradiction candidates are included in the case review report and can be selected through `object_type=contradiction_candidate`.
- Missing item candidate list/create/detail/review API exists through `/api/v1/cases/{case_id}/missing-item-candidates`.
- Missing item candidate creation requires a same-case analysis run and at least one same-case source reference.
- Missing item candidate reviews use append-only `human_reviews` with `object_type=missing_item_candidate`.
- Missing item candidates are included in the case review report and can be selected through `object_type=missing_item_candidate`.
- The raw `detect_missing_items` analysis module has been removed. Missing item candidates can still exist as structured review objects through manual/finding-conversion workflows.
- Missing item candidate export smoke result: JSON and HTML review report exports with `object_type=missing_item_candidate`, `needs_review`, and `require_source_valid=true` each created 1 tracked export item; downloads included `missing_item_candidate`.
- Analysis retrieval now strips common short Hungarian accusative suffixes, so terms such as `mellekletet` and `kamerafelvetelt` can fall back to `melleklet` and `kamerafelvetel`.
- The formerly failing short query `Keress hivatkozott mellekletet.` now succeeds in live smoke: `analysis 200`, `validation_status=passed`, 1 source-cited `attachment` candidate.
- Minimal frontend scaffold exists under `frontend/`.
- Frontend currently supports case list/create, TXT import, analysis module run, review report loading/filtering, and JSON/HTML export creation/download.
- Frontend now supports review actions for report items: `verify`, `reject`, `mark_needs_review`, and `comment`.
- Review action calls use a frontend allowlist that maps known object types to their review endpoints; unsupported object types are rejected client-side.
- Frontend report items now show all source references with citation labels, page/chunk hints, quote/excerpt offsets, source excerpts, document hashes, and review history.
- Frontend now shows current operation, elapsed time, last action summary, and analysis output count to make long LM Studio calls less ambiguous.
- Frontend now shows LM Studio model status in a thin global top bar above the case/work-surface area. It checks status on page load, groups chat and embedding model labels with their own load/unload buttons, and keeps `Állapot frissítése` as a labeled refresh action.
- Frontend AI operation status now lives in a compact strip below the work-surface selector. It shows the current AI operation, last AI operation, result, and duration; the old `Művelet állapot` panel inside `Ügy munkapad` is no longer used for this.
- Frontend now shows selected-case documents and recent analysis runs; import and analysis execution refresh those lists.
- Frontend document details show imported pages and chunks with source text; analysis run details show recorded inputs/outputs as readable source-to-result rows rather than raw technical blocks.
- Frontend `Elemzési előzmények` separates `Kutatási találatok keresése` and `Kézi rögzítés`, highlights the selected history card, and uses the backend-provided `display_label` so history cards show the research focus or manually created object title.
- Frontend review report controls can filter by object type, review status, and source validation status. Exports use the same selected filters.
- Frontend object detail panel shows object-specific facts, sources, and review history for the selected report item.
- Frontend review report filtering is handled through object type, review status, and source validation dropdown controls.
- Frontend export history lists prior JSON/HTML exports and download links.
- Frontend visible UI text is localized to Hungarian, with backend enum/internal values mapped to Hungarian labels before display.
- Frontend uses Vite proxy from `/api` to `http://127.0.0.1:8000`; backend CORS was not loosened.
- After machine restart, start the local runtime in WSL from the repo root with `docker compose up -d`, then start backend/frontend. In interactive terminals use `.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` and `npm --prefix frontend run dev -- --host 0.0.0.0`.
- Codex-started backend/frontend must be detached with `setsid -f`; otherwise a non-interactive WSL shell can clean up the process after it prints `ready`, leaving no listener. Use:
  - backend: `setsid -f sh -c ".venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/boberdetective-backend.log 2>&1 < /dev/null"`
  - frontend: `setsid -f sh -c "npm --prefix frontend run dev -- --host 0.0.0.0 > /tmp/boberdetective-frontend.log 2>&1 < /dev/null"`
  Always confirm with `ss -ltnp | grep -E ":(8000|5173)"`, backend health `curl -fsS http://127.0.0.1:8000/api/v1/system/health`, and frontend `curl -I http://127.0.0.1:5173`.
- Frontend verification: `npm run build` passed after contradiction claim-pair UI updates.
- End-to-end frontend/API smoke history passed through live backend and Vite dev server: case creation, TXT import, document/chunk/search checks, review report/filter, claim review, JSON export/list/download, frontend index, and Vite `/api` proxy.
- Source-bound finding search no longer falls back to first current case chunks when retrieval has no hits; it returns a clear source-selection error instead of sending unrelated chunks to the LLM.
- Historical `extract_claims` / `extract_events` smoke results are pre-retirement notes only; those modules are no longer active.
- Keyword search now uses sanitized prefix `to_tsquery` terms so simple Hungarian suffix cases like `kapu` matching `kaput` are less brittle.
- Case review report works through `GET /api/v1/cases/{case_id}/review-report`.
- The review report is read-only and returns combined claim/entity/event items with review status, source validation status, source references, quote text, analysis run id, and review history.
- Review report supports optional query filters: `object_type`, `review_status`, and `source_validation_status`.
- Review report sources now include document filename/SHA256, quote offsets, chunk/page metadata, and bounded source text excerpts for human verification.
- Live review report smoke result: `report 200`, 3 total items, 3 `needs_review`, each with 1 source.
- Entity items are included in review report and JSON/HTML review report exports through their source-linked mentions.
- Live entity report/export smoke result: `report 200`, 2 entity items with sources; HTML export `201`, 2 entity export items.
- JSON review report export works through `POST /api/v1/cases/{case_id}/exports`.
- Export list/detail/download work through `GET /api/v1/cases/{case_id}/exports`, `GET /api/v1/cases/{case_id}/exports/{export_id}`, and `GET /api/v1/cases/{case_id}/exports/{export_id}/download`.
- Export creation writes a JSON file under the case export directory, records SHA256, creates `export_items`, and writes DB + JSONL audit.
- Supported first export request: `export_type=json` or `html`, `export_scope=review_report`, with `review_filter` values `all`, `verified_only`, `needs_review`, `rejected`, `require_source_valid`, and optional `report_filters`.
- Live export smoke result: `export 201`, 3 export items, JSON download `200`, SHA256 recorded.
- HTML review report export works through the same export endpoint with `export_type=html`.
- HTML export escapes item text, body text, citation labels, and quote text before rendering.
- Live HTML export smoke result: `export 201`, 3 export items, `.html` file, download `200`, `text/html`.
- Export review works through `POST /api/v1/cases/{case_id}/exports/{export_id}/reviews`.
- Supported export review actions use the shared human review request shape: `verify`, `reject`, `mark_needs_review`, `comment`.
- Export detail responses now include append-only review history.
- Export review writes `human_reviews` records with `object_type=export` and `export_review_recorded` audit events.
- Live export review smoke result: `review 200`, one review entry, `new_review_status=verified`.
- Storage path traversal protection is covered by tests.
- Live filtered report/export smoke result: `report 200`, entity-only `needs_review` and `source_valid` filter returned 2 items; JSON export `201`, 2 entity export items.
- Latest test run: `392 passed`, 1 Docling deprecation warning.

## Suggested Prompt For A New Codex Session

Use this when starting a fresh session:

```text
Read AGENTS.md, AI_NOTES.md, CHANGELOG.md if it exists, and the existing README.md first.

Do not edit anything yet.

After reading them, summarize:
1. what this project does
2. the current architecture
3. the most important constraints
4. the current project state from AI_NOTES.md
5. recent notable changes from CHANGELOG.md, if available
6. the likely next steps
7. which files are most relevant for the task I will give you next

Then wait for my actual task.
```

## Notes For Future Agents

- The user prefers deliberate design before implementation.
- The current emphasis is architecture, runtime, database schema, auditability, and source traceability.
- Do not assume the project should become a chatbot.
- Do not treat LLM output as truth.
- Do not add cloud integrations.
- Do not begin coding unless explicitly asked.
- Keep assumptions and unverified items clearly marked.
- Keep future visible frontend text Hungarian; do not expose raw English enum/internal values directly in the UI unless they are technical identifiers intentionally shown in code/hash/id contexts.
