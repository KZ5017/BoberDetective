import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  CheckCircle2,
  Database,
  Download,
  FilePlus2,
  FolderPlus,
  Loader2,
  MessageSquare,
  Play,
  RefreshCw,
  Search,
  ShieldCheck
} from "lucide-react";
import {
  AnalysisResponse,
  AnalysisRunDetail,
  AnalysisRunRead,
  CaseRead,
  DocumentChunkRead,
  DocumentPageRead,
  DocumentRead,
  ExportDetail,
  ExportRead,
  ReviewReport,
  ReviewReportFilterValues,
  ReviewReportItem,
  createCase,
  createExport,
  getAnalysisRun,
  getReviewReport,
  importDocument,
  listDocumentChunks,
  listDocumentPages,
  listAnalysisRuns,
  listCases,
  listDocuments,
  listExports,
  reviewObject,
  runAnalysis
} from "./api";

const modules = [
  "extract_claims",
  "extract_events",
  "extract_entities",
  "summarize_case",
  "detect_contradiction_candidates",
  "detect_missing_items"
];

const objectTypes = [
  "",
  "claim",
  "event",
  "entity",
  "summary_item",
  "contradiction_candidate",
  "missing_item_candidate"
];

const reviewStatuses = ["", "needs_review", "verified", "rejected", "corrected", "new"];
const sourceValidationStatuses = ["", "source_valid", "source_invalid", "pending_source_validation"];

const busyLabels: Record<string, string> = {
  cases: "Ugylista frissitese",
  "case-create": "Ugy letrehozasa",
  "case-data": "Ugyadatok betoltese",
  "document-detail": "Irat reszletek betoltese",
  "run-detail": "Analysis run reszletek betoltese",
  exports: "Export history betoltese",
  import: "Irat importalasa",
  analysis: "Elemzes futtatasa",
  report: "Review report betoltese",
  "export-json": "JSON export keszitese",
  "export-html": "HTML export keszitese",
  "review-verify": "Review rogzítese",
  "review-reject": "Review rogzítese",
  "review-mark_needs_review": "Review rogzítese",
  "review-comment": "Komment rogzítese"
};

export function App() {
  const [cases, setCases] = useState<CaseRead[]>([]);
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [analysisRuns, setAnalysisRuns] = useState<AnalysisRunRead[]>([]);
  const [exports, setExports] = useState<ExportRead[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentRead | null>(null);
  const [documentPages, setDocumentPages] = useState<DocumentPageRead[]>([]);
  const [documentChunks, setDocumentChunks] = useState<DocumentChunkRead[]>([]);
  const [analysisRunDetail, setAnalysisRunDetail] = useState<AnalysisRunDetail | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [caseName, setCaseName] = useState("");
  const [caseReference, setCaseReference] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("jegyzokonyv");
  const [moduleKey, setModuleKey] = useState("detect_missing_items");
  const [query, setQuery] = useState("Keress hivatkozott mellekletet.");
  const [limit, setLimit] = useState(5);
  const [objectType, setObjectType] = useState("");
  const [reviewStatus, setReviewStatus] = useState("needs_review");
  const [sourceValidationStatus, setSourceValidationStatus] = useState("source_valid");
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [selectedReportItem, setSelectedReportItem] = useState<ReviewReportItem | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [lastExport, setLastExport] = useState<ExportDetail | null>(null);
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [busyStartedAt, setBusyStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastActionSummary, setLastActionSummary] = useState("");

  const selectedCase = useMemo(() => cases.find((item) => item.id === selectedCaseId), [cases, selectedCaseId]);
  const busyLabel = busy ? (busyLabels[busy] ?? busy) : "Keszenlet";
  const reportFilters = useMemo<ReviewReportFilterValues>(
    () => ({
      objectType: objectType || undefined,
      reviewStatus: reviewStatus || undefined,
      sourceValidationStatus: sourceValidationStatus || undefined
    }),
    [objectType, reviewStatus, sourceValidationStatus]
  );

  useEffect(() => {
    void refreshCases();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      void refreshCaseData(false);
    } else {
      setDocuments([]);
      setAnalysisRuns([]);
      setExports([]);
      setSelectedDocument(null);
      setDocumentPages([]);
      setDocumentChunks([]);
      setAnalysisRunDetail(null);
      setSelectedReportItem(null);
      setReport(null);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    if (busyStartedAt === null) {
      setElapsedSeconds(0);
      return;
    }
    setElapsedSeconds(Math.max(0, Math.floor((Date.now() - busyStartedAt) / 1000)));
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - busyStartedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busyStartedAt]);

  async function perform(label: string, action: () => Promise<void>) {
    setBusy(label);
    setBusyStartedAt(Date.now());
    setError("");
    setNotice("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ismeretlen hiba");
    } finally {
      setBusy("");
      setBusyStartedAt(null);
    }
  }

  async function refreshCases() {
    await perform("cases", async () => {
      const response = await listCases();
      setCases(response.data);
      if (!selectedCaseId && response.data[0]) {
        setSelectedCaseId(response.data[0].id);
      }
    });
  }

  async function refreshCaseData(showNotice = true) {
    if (!selectedCaseId) return;
    await perform("case-data", async () => {
      const [documentsResponse, runsResponse, exportsResponse, reportResponse] = await Promise.all([
        listDocuments(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listExports(selectedCaseId),
        getReviewReport(selectedCaseId, reportFilters)
      ]);
      setDocuments(documentsResponse.data);
      setAnalysisRuns(runsResponse.data);
      setExports(exportsResponse.data);
      setReport(reportResponse);
      if (showNotice) {
        setNotice("Ugyadatok frissitve.");
      }
      setLastActionSummary(`${documentsResponse.data.length} irat, ${runsResponse.data.length} analysis run.`);
    });
  }

  async function applyReviewQueue(filters: ReviewReportFilterValues, summary: string) {
    if (!selectedCaseId) return;
    setObjectType(filters.objectType ?? "");
    setReviewStatus(filters.reviewStatus ?? "");
    setSourceValidationStatus(filters.sourceValidationStatus ?? "");
    await perform("report", async () => {
      const reportResponse = await getReviewReport(selectedCaseId, filters);
      setReport(reportResponse);
      setSelectedReportItem(reportResponse.items[0] ?? null);
      setNotice("Review queue betoltve.");
      setLastActionSummary(`${summary}: ${reportResponse.items.length} item.`);
    });
  }

  async function refreshExports() {
    if (!selectedCaseId) return;
    await perform("exports", async () => {
      const response = await listExports(selectedCaseId);
      setExports(response.data);
      setNotice("Export history frissitve.");
      setLastActionSummary(`${response.data.length} export.`);
    });
  }

  async function handleDocumentDetail(document: DocumentRead) {
    if (!selectedCaseId) return;
    await perform("document-detail", async () => {
      const [pagesResponse, chunksResponse] = await Promise.all([
        listDocumentPages(selectedCaseId, document.id),
        listDocumentChunks(selectedCaseId, document.id)
      ]);
      setSelectedDocument(document);
      setDocumentPages(pagesResponse.data);
      setDocumentChunks(chunksResponse.data);
      setNotice("Irat reszletek betoltve.");
      setLastActionSummary(`${document.original_filename}: ${pagesResponse.data.length} page, ${chunksResponse.data.length} chunk.`);
    });
  }

  async function handleAnalysisRunDetail(run: AnalysisRunRead) {
    if (!selectedCaseId) return;
    await perform("run-detail", async () => {
      const detail = await getAnalysisRun(selectedCaseId, run.id);
      setAnalysisRunDetail(detail);
      setNotice("Analysis run reszletek betoltve.");
      setLastActionSummary(`${run.run_type}: ${detail.inputs.length} input, ${detail.outputs.length} output.`);
    });
  }

  async function handleCreateCase() {
    await perform("case-create", async () => {
      const created = await createCase({
        case_name: caseName,
        case_reference: caseReference || undefined
      });
      setCases((current) => [created, ...current]);
      setSelectedCaseId(created.id);
      setCaseName("");
      setCaseReference("");
      setNotice("Ugy letrehozva.");
      setLastActionSummary(`Letrehozott ugy: ${created.case_name}`);
    });
  }

  async function handleImport() {
    if (!selectedCaseId || !file) return;
    await perform("import", async () => {
      await importDocument(selectedCaseId, file, documentType);
      setFile(null);
      const documentsResponse = await listDocuments(selectedCaseId);
      setDocuments(documentsResponse.data);
      setNotice("Irat import kesz.");
      setLastActionSummary(`Import kesz: ${file.name}`);
    });
  }

  async function handleRunAnalysis() {
    if (!selectedCaseId) return;
    await perform("analysis", async () => {
      const response = await runAnalysis(selectedCaseId, moduleKey, query, limit);
      setAnalysis(response);
      const [reportResponse, runsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        listAnalysisRuns(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setNotice("Elemzes lefutott, report frissitve.");
      setLastActionSummary(
        `${response.module_key}: ${response.validation_status}, ${response.selected_chunk_ids.length} chunk, ${analysisOutputCount(response)} output`
      );
    });
  }

  async function handleLoadReport() {
    if (!selectedCaseId) return;
    await perform("report", async () => {
      const reportResponse = await getReviewReport(selectedCaseId, reportFilters);
      setReport(reportResponse);
      setSelectedReportItem((current) => (current ? reportResponse.items.find((item) => item.object_id === current.object_id) ?? null : null));
      setNotice("Review report frissitve.");
      setLastActionSummary(`Report betoltve: ${reportResponse.items.length} item.`);
    });
  }

  async function handleExport(exportType: "json" | "html") {
    if (!selectedCaseId) return;
    await perform(`export-${exportType}`, async () => {
      const created = await createExport(selectedCaseId, exportType, reportFilters);
      const exportsResponse = await listExports(selectedCaseId);
      setLastExport(created);
      setExports(exportsResponse.data);
      setNotice(`${exportType.toUpperCase()} export elkeszult.`);
      setLastActionSummary(`${exportType.toUpperCase()} export kesz.`);
    });
  }

  async function handleReview(itemObjectType: string, objectId: string, actionType: "verify" | "reject" | "mark_needs_review" | "comment") {
    if (!selectedCaseId) return;
    const comment = reviewComments[objectId] ?? "";
    await perform(`review-${actionType}`, async () => {
      await reviewObject(selectedCaseId, itemObjectType, objectId, actionType, comment);
      setReviewComments((current) => ({ ...current, [objectId]: "" }));
      const reportResponse = await getReviewReport(selectedCaseId, reportFilters);
      setReport(reportResponse);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === objectId) ?? null);
      setNotice("Review rogzítve, report frissitve.");
      setLastActionSummary(`${itemObjectType} review: ${actionType}`);
    });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>BoberDetective</h1>
          <p>Lokalis nyomozati iratintelligencia munkapad</p>
        </div>
        <div className="status-strip">
          <span><ShieldCheck size={16} /> local</span>
          <span><Database size={16} /> source-cited</span>
          <span><CheckCircle2 size={16} /> review-first</span>
        </div>
      </header>

      {error && <div className="notice error">{error}</div>}
      {notice && <div className="notice success">{notice}</div>}

      <section className="workspace">
        <aside className="sidebar">
          <div className="section-heading">
            <h2>Ugyek</h2>
            <button className="icon-button" onClick={refreshCases} title="Frissites" disabled={Boolean(busy)}>
              <RefreshCw size={18} />
            </button>
          </div>
          <label>
            Aktiv ugy
            <select value={selectedCaseId} onChange={(event) => setSelectedCaseId(event.target.value)}>
              <option value="">Nincs kivalasztva</option>
              {cases.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.case_reference ? `${item.case_reference} - ` : ""}
                  {item.case_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Nev
            <input value={caseName} onChange={(event) => setCaseName(event.target.value)} />
          </label>
          <label>
            Azonosito
            <input value={caseReference} onChange={(event) => setCaseReference(event.target.value)} />
          </label>
          <button onClick={handleCreateCase} disabled={!caseName || Boolean(busy)}>
            <FolderPlus size={18} /> Ugy letrehozasa
          </button>
          <button onClick={() => refreshCaseData()} disabled={!selectedCaseId || Boolean(busy)}>
            <RefreshCw size={18} /> Ugyadatok
          </button>
        </aside>

        <section className="main-grid">
          <section className="panel hero-panel">
            <div>
              <h2>{selectedCase?.case_name ?? "Nincs aktiv ugy"}</h2>
              <p>{selectedCase?.case_reference ?? selectedCase?.status ?? "Valassz vagy hozz letre ugyet"}</p>
            </div>
            <div className="run-stack">
              <span className="run-state">{busy ? <Loader2 className="spin" size={18} /> : <CheckCircle2 size={18} />} {busyLabel}</span>
              {busy && <span className="elapsed">{formatDuration(elapsedSeconds)}</span>}
            </div>
          </section>

          <section className={`panel operation-panel ${busy ? "is-running" : ""}`}>
            <div className="section-heading">
              <h2>Muvelet allapot</h2>
              {busy ? <Loader2 className="spin" size={20} /> : <CheckCircle2 size={20} />}
            </div>
            <div className="operation-grid">
              <span>Aktualis</span>
              <strong>{busyLabel}</strong>
              <span>Eltelt ido</span>
              <strong>{busy ? formatDuration(elapsedSeconds) : "-"}</strong>
              <span>Utolso muvelet</span>
              <strong>{lastActionSummary || "Meg nincs muvelet."}</strong>
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Iratok</h2>
              <Database size={20} />
            </div>
            <div className="compact-list">
              {documents.length === 0 && <p className="muted">Nincs importalt irat.</p>}
              {documents.map((document) => (
                <article key={document.id} className="compact-item">
                  <strong>{document.original_filename}</strong>
                  <span>{document.document_type ?? "unknown"} | {document.processing_status} | {formatBytes(document.file_size_bytes)}</span>
                  <code>{document.sha256_hash}</code>
                  <button onClick={() => handleDocumentDetail(document)} disabled={Boolean(busy)}>
                    Details
                  </button>
                </article>
              ))}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="section-heading">
              <h2>Irat reszletek</h2>
              <FilePlus2 size={20} />
            </div>
            {!selectedDocument && <p className="muted">Valassz iratot a reszletekhez.</p>}
            {selectedDocument && (
              <div className="detail-stack">
                <strong>{selectedDocument.original_filename}</strong>
                <div className="metrics">
                  <span>{documentPages.length} page</span>
                  <span>{documentChunks.length} chunk</span>
                  <span>{selectedDocument.processing_status}</span>
                </div>
                <details open>
                  <summary>Pages</summary>
                  <div className="detail-list">
                    {documentPages.map((page) => (
                      <article key={page.id} className="text-sample">
                        <strong>Page {page.page_number}</strong>
                        <span>{page.text_source} | OCR {page.ocr_used ? "yes" : "no"} | {page.text_char_count} chars</span>
                        <pre>{page.extracted_text}</pre>
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Chunks</summary>
                  <div className="detail-list">
                    {documentChunks.map((chunk) => (
                      <article key={chunk.id} className="text-sample">
                        <strong>Chunk {chunk.chunk_index}</strong>
                        <span>pages {chunk.page_start}-{chunk.page_end} | chars {formatRange(chunk.char_start, chunk.char_end)}</span>
                        <pre>{chunk.chunk_text}</pre>
                      </article>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Irat import</h2>
              <FilePlus2 size={20} />
            </div>
            <div className="form-row">
              <label>
                Tipus
                <input value={documentType} onChange={(event) => setDocumentType(event.target.value)} />
              </label>
              <label>
                TXT fajl
                <input type="file" accept=".txt,text/plain" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              </label>
            </div>
            <button onClick={handleImport} disabled={!selectedCaseId || !file || Boolean(busy)}>
              <FilePlus2 size={18} /> Import
            </button>
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Elemzes</h2>
              <Search size={20} />
            </div>
            <div className="form-row">
              <label>
                Modul
                <select value={moduleKey} onChange={(event) => setModuleKey(event.target.value)}>
                  {modules.map((item) => <option key={item}>{item}</option>)}
                </select>
              </label>
              <label>
                Limit
                <input type="number" min={1} max={20} value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
              </label>
            </div>
            <label>
              Query
              <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={3} />
            </label>
            <button onClick={handleRunAnalysis} disabled={!selectedCaseId || !query || Boolean(busy)}>
              <Play size={18} /> Futtatas
            </button>
            {analysis && (
              <div className="analysis-summary">
                <div className="metrics">
                  <span>{analysis.validation_status}</span>
                  <span>{analysis.selected_chunk_ids.length} chunk</span>
                  <span>{analysis.unsupported_items.length} unsupported</span>
                  <span>{analysisOutputCount(analysis)} output</span>
                </div>
                <code>{analysis.analysis_run_id}</code>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Analysis history</h2>
              <Archive size={20} />
            </div>
            <div className="compact-list">
              {analysisRuns.length === 0 && <p className="muted">Nincs analysis run.</p>}
              {analysisRuns.slice(0, 8).map((run) => (
                <article key={run.id} className="compact-item">
                  <strong>{run.run_type}</strong>
                  <span>{run.status} | {run.validation_status ?? "no validation"} | {run.model_name ?? "no model"}</span>
                  <span>{new Date(run.started_at).toLocaleString()} {run.finished_at ? `-> ${new Date(run.finished_at).toLocaleTimeString()}` : ""}</span>
                  {run.error_message && <p className="error-text">{run.error_message}</p>}
                  <code>{run.id}</code>
                  <button onClick={() => handleAnalysisRunDetail(run)} disabled={Boolean(busy)}>
                    Details
                  </button>
                </article>
              ))}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="section-heading">
              <h2>Analysis run detail</h2>
              <Archive size={20} />
            </div>
            {!analysisRunDetail && <p className="muted">Valassz analysis runt a reszletekhez.</p>}
            {analysisRunDetail && (
              <div className="detail-stack">
                <strong>{analysisRunDetail.run.run_type}</strong>
                <div className="metrics">
                  <span>{analysisRunDetail.run.status}</span>
                  <span>{analysisRunDetail.run.validation_status ?? "no validation"}</span>
                  <span>{analysisRunDetail.inputs.length} input</span>
                  <span>{analysisRunDetail.outputs.length} output</span>
                </div>
                <code>{analysisRunDetail.run.id}</code>
                {analysisRunDetail.run.error_message && <p className="error-text">{analysisRunDetail.run.error_message}</p>}
                <details open>
                  <summary>Inputs</summary>
                  <div className="detail-list">
                    {analysisRunDetail.inputs.map((input) => (
                      <article key={input.id} className="compact-item">
                        <strong>{input.sequence_no}. {input.input_type}</strong>
                        <span>{input.related_object_type ?? "source"} {input.related_object_id ?? input.chunk_id ?? input.document_id ?? ""}</span>
                        {input.payload_json && <pre>{JSON.stringify(input.payload_json, null, 2)}</pre>}
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Outputs</summary>
                  <div className="detail-list">
                    {analysisRunDetail.outputs.map((output) => (
                      <article key={output.id} className="compact-item">
                        <strong>{output.output_position ?? 0}. {output.output_type}</strong>
                        <code>{output.output_object_id}</code>
                      </article>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </section>

          <section className="panel report-panel">
            <div className="section-heading">
              <h2>Review report</h2>
              <Archive size={20} />
            </div>
            <div className="form-row">
              <label>
                Objektum
                <select value={objectType} onChange={(event) => setObjectType(event.target.value)}>
                  {objectTypes.map((item) => <option key={item} value={item}>{item || "all"}</option>)}
                </select>
              </label>
              <label>
                Review status
                <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>
                  {reviewStatuses.map((item) => <option key={item} value={item}>{item || "all"}</option>)}
                </select>
              </label>
              <label>
                Source status
                <select value={sourceValidationStatus} onChange={(event) => setSourceValidationStatus(event.target.value)}>
                  {sourceValidationStatuses.map((item) => <option key={item} value={item}>{item || "all"}</option>)}
                </select>
              </label>
              <button onClick={handleLoadReport} disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} /> Betoltes
              </button>
            </div>
            <div className="queue-row">
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({ reviewStatus: "needs_review", sourceValidationStatus: "source_valid" }, "Review queue")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Review queue
              </button>
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({ objectType: "missing_item_candidate", reviewStatus: "needs_review", sourceValidationStatus: "source_valid" }, "Missing item queue")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Missing items
              </button>
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({ objectType: "contradiction_candidate", reviewStatus: "needs_review", sourceValidationStatus: "source_valid" }, "Contradiction queue")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Contradictions
              </button>
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({}, "All report items")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                All
              </button>
            </div>
            {report && (
              <>
                <div className="metrics">
                  <span>{report.counts.total} total</span>
                  <span>{report.counts.needs_review} review</span>
                  <span>{report.counts.verified} verified</span>
                  <span>{report.counts.rejected} rejected</span>
                </div>
                <div className="item-list">
                  {report.items.map((item) => (
                    <article key={item.object_id} className="report-item">
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.body_text}</p>
                      </div>
                      <div className="tags">
                        <span>{item.object_type}</span>
                        <span>{item.review_status}</span>
                        <span>{item.source_validation_status}</span>
                        <span>{item.reviews.length} review</span>
                        <span>{item.sources.length} source</span>
                      </div>
                      <button className="secondary-button" onClick={() => setSelectedReportItem(item)}>
                        Detail
                      </button>
                      <div className="source-list">
                        {item.sources.map((source, index) => (
                          <details key={source.source_reference_id} className="source-detail" open={index === 0}>
                            <summary>
                              Source {index + 1}: {source.document_filename ?? "document"} {source.page_number ? `p.${source.page_number}` : ""} {source.chunk_index !== null ? `chunk ${source.chunk_index}` : ""}
                            </summary>
                            <div className="source-meta">
                              <span>{source.support_type}</span>
                              <span>rank {source.relevance_rank ?? index}</span>
                              <span>{source.citation_label ?? "no citation label"}</span>
                              <span>quote {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                              <span>excerpt {formatRange(source.source_text_excerpt_char_start, source.source_text_excerpt_char_end)}</span>
                            </div>
                            <blockquote>{source.quote_text}</blockquote>
                            {source.source_text_excerpt && <p className="excerpt">{source.source_text_excerpt}</p>}
                            {source.document_sha256_hash && <code className="hash">{source.document_sha256_hash}</code>}
                          </details>
                        ))}
                      </div>
                      {item.reviews.length > 0 && (
                        <div className="history">
                          {item.reviews.map((review) => (
                            <div key={review.id}>
                              <strong>{review.action_type}</strong>
                              <span>{review.new_review_status ?? "comment"}</span>
                              <span>{new Date(review.performed_at).toLocaleString()}</span>
                              {review.review_comment && <p>{review.review_comment}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="review-row">
                        <input
                          value={reviewComments[item.object_id] ?? ""}
                          onChange={(event) => setReviewComments((current) => ({ ...current, [item.object_id]: event.target.value }))}
                          placeholder="Review megjegyzes"
                        />
                        <button title="Verify" onClick={() => handleReview(item.object_type, item.object_id, "verify")} disabled={Boolean(busy)}>
                          <CheckCircle2 size={18} />
                        </button>
                        <button title="Reject" onClick={() => handleReview(item.object_type, item.object_id, "reject")} disabled={Boolean(busy)}>
                          Reject
                        </button>
                        <button title="Needs review" onClick={() => handleReview(item.object_type, item.object_id, "mark_needs_review")} disabled={Boolean(busy)}>
                          Review
                        </button>
                        <button title="Comment" onClick={() => handleReview(item.object_type, item.object_id, "comment")} disabled={Boolean(busy)}>
                          <MessageSquare size={18} />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>

          <section className="panel detail-panel">
            <div className="section-heading">
              <h2>Object detail</h2>
              <Search size={20} />
            </div>
            {!selectedReportItem && <p className="muted">Valassz report itemet a reszletekhez.</p>}
            {selectedReportItem && (
              <div className="detail-stack">
                <strong>{selectedReportItem.title}</strong>
                <div className="metrics">
                  <span>{selectedReportItem.object_type}</span>
                  <span>{selectedReportItem.subtype}</span>
                  <span>{selectedReportItem.review_status}</span>
                  <span>{selectedReportItem.source_validation_status}</span>
                </div>
                <code>{selectedReportItem.object_id}</code>
                {selectedReportItem.body_text && <p>{selectedReportItem.body_text}</p>}
                <div className="object-facts">
                  {objectDetailFacts(selectedReportItem).map((fact) => (
                    <div key={fact.label}>
                      <span>{fact.label}</span>
                      <strong>{fact.value}</strong>
                    </div>
                  ))}
                </div>
                <details open>
                  <summary>Sources</summary>
                  <div className="detail-list">
                    {selectedReportItem.sources.map((source, index) => (
                      <article key={source.source_reference_id} className="text-sample">
                        <strong>{index + 1}. {source.document_filename ?? "document"}</strong>
                        <span>{source.citation_label ?? "no citation"} | quote {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                        <pre>{source.quote_text}</pre>
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Review history</summary>
                  <div className="detail-list">
                    {selectedReportItem.reviews.map((review) => (
                      <article key={review.id} className="compact-item">
                        <strong>{review.action_type}</strong>
                        <span>{review.new_review_status ?? "comment"} | {new Date(review.performed_at).toLocaleString()}</span>
                        {review.review_comment && <p>{review.review_comment}</p>}
                      </article>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Export</h2>
              <Download size={20} />
            </div>
            <div className="button-row">
              <button onClick={() => handleExport("json")} disabled={!selectedCaseId || Boolean(busy)}>
                <Download size={18} /> JSON
              </button>
              <button onClick={() => handleExport("html")} disabled={!selectedCaseId || Boolean(busy)}>
                <Download size={18} /> HTML
              </button>
            </div>
            {lastExport && (
              <div className="export-box">
                <strong>{lastExport.export.export_type.toUpperCase()}</strong>
                <span>{lastExport.items.length} item</span>
                <a href={`/api/v1/cases/${selectedCaseId}/exports/${lastExport.export.id}/download`}>Download</a>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Export history</h2>
              <button className="icon-button" onClick={refreshExports} title="Export history frissites" disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} />
              </button>
            </div>
            <div className="compact-list">
              {exports.length === 0 && <p className="muted">Nincs export.</p>}
              {exports.slice(0, 10).map((item) => (
                <article key={item.id} className="compact-item">
                  <strong>{item.export_type.toUpperCase()} {item.export_scope}</strong>
                  <span>{item.review_filter ?? "all"} | {new Date(item.created_at).toLocaleString()}</span>
                  {item.sha256_hash && <code>{item.sha256_hash}</code>}
                  <a href={`/api/v1/cases/${selectedCaseId}/exports/${item.id}/download`}>Download</a>
                </article>
              ))}
            </div>
          </section>
        </section>
      </section>
    </main>
  );
}

function formatRange(start: number | null, end: number | null) {
  if (start === null || end === null) {
    return "-";
  }
  return `${start}-${end}`;
}

function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function analysisOutputCount(response: AnalysisResponse) {
  return (
    response.claims.length +
    response.events.length +
    response.entities.length +
    response.summary_items.length +
    response.contradiction_candidates.length +
    response.missing_item_candidates.length
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function objectDetailFacts(item: ReviewReportItem) {
  const base = [
    { label: "Sources", value: String(item.sources.length) },
    { label: "Reviews", value: String(item.reviews.length) }
  ];
  if (item.object_type === "contradiction_candidate") {
    return [...base, { label: "Candidate kind", value: item.subtype }];
  }
  if (item.object_type === "missing_item_candidate") {
    return [...base, { label: "Referenced item", value: item.title }];
  }
  if (item.object_type === "summary_item") {
    return [...base, { label: "Summary type", value: item.subtype }];
  }
  if (item.object_type === "entity") {
    return [...base, { label: "Entity type", value: item.subtype }];
  }
  if (item.object_type === "event") {
    return [...base, { label: "Event type", value: item.subtype }];
  }
  return [...base, { label: "Claim type", value: item.subtype }];
}
