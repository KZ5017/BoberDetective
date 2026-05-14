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
  AnalysisSourceMode,
  CaseRead,
  ClaimReviewScope,
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
  runAnalysis,
  runDocumentOcr
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
const analysisSourceModes: AnalysisSourceMode[] = ["focused_query", "document", "case"];
const claimReviewScopes: ClaimReviewScope[] = ["reviewable", "verified", "needs_review", "all_source_valid"];

const busyLabels: Record<string, string> = {
  cases: "Ugylista frissitese",
  "case-create": "Ugy letrehozasa",
  "case-data": "Ugyadatok betoltese",
  "document-detail": "Iratreszletek betoltese",
  "document-ocr": "OCR futtatasa",
  "run-detail": "Elemzesi futas reszleteinek betoltese",
  exports: "Export elozmenyek betoltese",
  import: "Irat importalasa",
  analysis: "Elemzes futtatasa",
  report: "Attekintesi jelentés betoltese",
  "export-json": "JSON export keszitese",
  "export-html": "HTML export keszitese",
  "review-verify": "Felulvizsgalat rogzítese",
  "review-reject": "Felulvizsgalat rogzítese",
  "review-mark_needs_review": "Felulvizsgalat rogzítese",
  "review-comment": "Megjegyzes rogzítese"
};

const moduleLabels: Record<string, string> = {
  extract_claims: "Allitasok kinyerese",
  extract_events: "Esemenyek kinyerese",
  extract_entities: "Entitasok kinyerese",
  summarize_case: "Ugyosszefoglalo keszitese",
  detect_contradiction_candidates: "Ellentmondasjeloltek keresese",
  detect_missing_items: "Hianyzo iratok keresese"
};

const analysisSourceModeLabels: Record<AnalysisSourceMode, string> = {
  focused_query: "Fokuszalt kereses",
  document: "Kivalasztott irat",
  case: "Teljes ugy"
};

const claimReviewScopeLabels: Record<ClaimReviewScope, string> = {
  reviewable: "Ellenorizheto allitasok",
  verified: "Csak ellenorzott",
  needs_review: "Ellenorzesre varok",
  all_source_valid: "Minden forraservenyes"
};

const objectTypeLabels: Record<string, string> = {
  claim: "Allitas",
  event: "Esemeny",
  entity: "Entitas",
  summary_item: "Osszefoglalo elem",
  contradiction_candidate: "Ellentmondasjelolt",
  missing_item_candidate: "Hianyzo irat jelolt",
  export: "Export"
};

const reviewStatusLabels: Record<string, string> = {
  needs_review: "Ellenorzesre var",
  verified: "Ellenorizve",
  rejected: "Elutasitva",
  corrected: "Javitva",
  new: "Uj"
};

const sourceValidationLabels: Record<string, string> = {
  source_valid: "Forras ervenyes",
  source_invalid: "Forras ervenytelen",
  pending_source_validation: "Forras ellenorzesre var"
};

const runStatusLabels: Record<string, string> = {
  running: "Folyamatban",
  succeeded: "Sikeres",
  failed: "Sikertelen",
  cancelled: "Megszakitva"
};

const validationStatusLabels: Record<string, string> = {
  passed: "Atment",
  failed: "Sikertelen",
  warning: "Figyelmeztetes"
};

const actionLabels: Record<string, string> = {
  verify: "Ellenorzes",
  reject: "Elutasitas",
  mark_needs_review: "Ellenorzesre jeloles",
  comment: "Megjegyzes"
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
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(5);
  const [analysisSourceMode, setAnalysisSourceMode] = useState<AnalysisSourceMode>("focused_query");
  const [analysisDocumentId, setAnalysisDocumentId] = useState("");
  const [maxChunks, setMaxChunks] = useState(50);
  const [batchSize, setBatchSize] = useState(5);
  const [claimReviewScope, setClaimReviewScope] = useState<ClaimReviewScope>("reviewable");
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
  const selectedAnalysisDocument = useMemo(
    () => documents.find((item) => item.id === analysisDocumentId) ?? null,
    [analysisDocumentId, documents]
  );
  const canUseBatchScope =
    moduleKey === "extract_claims" ||
    moduleKey === "extract_events" ||
    moduleKey === "extract_entities" ||
    moduleKey === "summarize_case" ||
    moduleKey === "detect_missing_items";
  const isContradictionModule = moduleKey === "detect_contradiction_candidates";
  const effectiveAnalysisSourceMode: AnalysisSourceMode = canUseBatchScope ? analysisSourceMode : "focused_query";
  const requiresFocusText = effectiveAnalysisSourceMode === "focused_query" && !isContradictionModule;
  const busyLabel = busy ? (busyLabels[busy] ?? busy) : "Keszenlet";
  const canRunAnalysis =
    Boolean(selectedCaseId) &&
    !busy &&
    (!requiresFocusText || query.trim().length > 0) &&
    (effectiveAnalysisSourceMode !== "document" || Boolean(analysisDocumentId));
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
    if (analysisDocumentId && !documents.some((item) => item.id === analysisDocumentId)) {
      setAnalysisDocumentId("");
    }
  }, [analysisDocumentId, documents]);

  useEffect(() => {
    if (!canUseBatchScope && analysisSourceMode !== "focused_query") {
      setAnalysisSourceMode("focused_query");
    }
  }, [analysisSourceMode, canUseBatchScope]);

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
      setLastActionSummary(`${documentsResponse.data.length} irat, ${runsResponse.data.length} elemzesi futas.`);
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
      setNotice("Ellenorzesi lista betoltve.");
      setLastActionSummary(`${summary}: ${reportResponse.items.length} elem.`);
    });
  }

  async function refreshExports() {
    if (!selectedCaseId) return;
    await perform("exports", async () => {
      const response = await listExports(selectedCaseId);
      setExports(response.data);
      setNotice("Export elozmenyek frissitve.");
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
      setLastActionSummary(`${document.original_filename}: ${pagesResponse.data.length} oldal, ${chunksResponse.data.length} szovegresz.`);
    });
  }

  async function handleDocumentOcr(document: DocumentRead) {
    if (!selectedCaseId) return;
    await perform("document-ocr", async () => {
      const response = await runDocumentOcr(selectedCaseId, document.id, "Felhasznaloi OCR inditas a feluletrol");
      const [documentsResponse, runsResponse, pagesResponse, chunksResponse] = await Promise.all([
        listDocuments(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listDocumentPages(selectedCaseId, document.id),
        listDocumentChunks(selectedCaseId, document.id)
      ]);
      const refreshedDocument = documentsResponse.data.find((item) => item.id === document.id) ?? response.document;
      setDocuments(documentsResponse.data);
      setAnalysisRuns(runsResponse.data);
      setSelectedDocument(refreshedDocument);
      setDocumentPages(pagesResponse.data);
      setDocumentChunks(chunksResponse.data);
      setNotice("OCR lefutott, az irat reszletei frissitve.");
      setLastActionSummary(
        `${document.original_filename}: ${labelRunStatus(response.analysis_run.status)}, ${response.analysis_run.validation_status ? labelValidationStatus(response.analysis_run.validation_status) : "nincs validacio"}`
      );
    });
  }

  async function handleAnalysisRunDetail(run: AnalysisRunRead) {
    if (!selectedCaseId) return;
    await perform("run-detail", async () => {
      const detail = await getAnalysisRun(selectedCaseId, run.id);
      setAnalysisRunDetail(detail);
      setNotice("Elemzesi futas reszletei betoltve.");
      setLastActionSummary(`${labelModule(run.run_type)}: ${detail.inputs.length} bemenet, ${detail.outputs.length} kimenet.`);
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
      const payload = {
        query: query.trim() ? query.trim() : null,
        limit,
        source_mode: effectiveAnalysisSourceMode,
        document_id: effectiveAnalysisSourceMode === "document" ? analysisDocumentId : null,
        max_chunks: maxChunks,
        batch_size: batchSize,
        claim_review_scope: claimReviewScope
      };
      const response = await runAnalysis(selectedCaseId, moduleKey, payload);
      setAnalysis(response);
      const [reportResponse, runsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        listAnalysisRuns(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setNotice("Elemzes lefutott, jelentés frissitve.");
      setLastActionSummary(
        `${labelModule(response.module_key)}: ${labelAnalysisSourceMode(effectiveAnalysisSourceMode)}, ${labelValidationStatus(response.validation_status)}, ${analysisSourceMetric(response)}, ${analysisOutputCount(response)} kimenet`
      );
    });
  }

  async function handleLoadReport() {
    if (!selectedCaseId) return;
    await perform("report", async () => {
      const reportResponse = await getReviewReport(selectedCaseId, reportFilters);
      setReport(reportResponse);
      setSelectedReportItem((current) => (current ? reportResponse.items.find((item) => item.object_id === current.object_id) ?? null : null));
      setNotice("Attekintesi jelentés frissitve.");
      setLastActionSummary(`Jelentes betoltve: ${reportResponse.items.length} elem.`);
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
      setNotice("Felulvizsgalat rogzítve, jelentes frissitve.");
      setLastActionSummary(`${labelObjectType(itemObjectType)}: ${labelAction(actionType)}`);
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
          <span><ShieldCheck size={16} /> helyi</span>
          <span><Database size={16} /> forrashivatkozott</span>
          <span><CheckCircle2 size={16} /> emberi ellenorzes</span>
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
                  <span>{document.document_type ?? "ismeretlen"} | {labelProcessingStatus(document.processing_status)} | {formatBytes(document.file_size_bytes)}</span>
                  <code>{document.sha256_hash}</code>
                  <div className="button-row">
                    <button onClick={() => handleDocumentDetail(document)} disabled={Boolean(busy)}>
                      Reszletek
                    </button>
                    {canRunOcr(document) && (
                      <button onClick={() => handleDocumentOcr(document)} disabled={Boolean(busy)}>
                        <Play size={18} /> OCR inditasa
                      </button>
                    )}
                  </div>
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
                  <span>{documentPages.length} oldal</span>
                  <span>{documentChunks.length} szovegresz</span>
                  <span>{labelProcessingStatus(selectedDocument.processing_status)}</span>
                </div>
                {canRunOcr(selectedDocument) && (
                  <button onClick={() => handleDocumentOcr(selectedDocument)} disabled={Boolean(busy)}>
                    <Play size={18} /> OCR inditasa
                  </button>
                )}
                <details open>
                  <summary>Oldalak</summary>
                  <div className="detail-list">
                    {documentPages.map((page) => (
                      <article key={page.id} className="text-sample">
                        <strong>{page.page_number}. oldal</strong>
                        <span>{labelTextSource(page.text_source)} | OCR {page.ocr_used ? "igen" : "nem"} | biztossag {formatConfidence(page.ocr_confidence)} | {page.text_char_count} karakter</span>
                        <pre>{page.extracted_text}</pre>
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Szovegreszek</summary>
                  <div className="detail-list">
                    {documentChunks.map((chunk) => (
                      <article key={chunk.id} className="text-sample">
                        <strong>{chunk.chunk_index}. szovegresz</strong>
                        <span>oldalak: {chunk.page_start}-{chunk.page_end} | karakterek: {formatRange(chunk.char_start, chunk.char_end)}</span>
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
                Irat fajl
                <input type="file" accept=".txt,.pdf,text/plain,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              </label>
            </div>
            <button onClick={handleImport} disabled={!selectedCaseId || !file || Boolean(busy)}>
              <FilePlus2 size={18} /> Importalas
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
                  {modules.map((item) => <option key={item} value={item}>{labelModule(item)}</option>)}
                </select>
              </label>
              <label>
                Limit
                <input type="number" min={1} max={20} value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
              </label>
            </div>
            <div className="form-row">
              <label>
                Forraskor
                <select
                  value={effectiveAnalysisSourceMode}
                  onChange={(event) => setAnalysisSourceMode(event.target.value as AnalysisSourceMode)}
                  disabled={!canUseBatchScope}
                >
                  {analysisSourceModes.map((item) => <option key={item} value={item}>{labelAnalysisSourceMode(item)}</option>)}
                </select>
              </label>
              <label>
                Irat
                <select
                  value={analysisDocumentId}
                  onChange={(event) => setAnalysisDocumentId(event.target.value)}
                  disabled={!canUseBatchScope || effectiveAnalysisSourceMode !== "document"}
                >
                  <option value="">Valassz iratot</option>
                  {documents.map((document) => (
                    <option key={document.id} value={document.id}>{document.original_filename}</option>
                  ))}
                </select>
              </label>
            </div>
            {canUseBatchScope && effectiveAnalysisSourceMode !== "focused_query" && (
              <div className="form-row">
                <label>
                  Szovegresz plafon
                  <input
                    type="number"
                    min={1}
                    max={200}
                    value={maxChunks}
                    onChange={(event) => setMaxChunks(clampNumberInput(event.target.value, 1, 200, 50))}
                  />
                </label>
                <label>
                  Batch meret
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={batchSize}
                    onChange={(event) => setBatchSize(clampNumberInput(event.target.value, 1, 10, 5))}
                  />
                </label>
              </div>
            )}
            {isContradictionModule && (
              <>
                <div className="form-row">
                  <label>
                    Allitaskor
                    <select value={claimReviewScope} onChange={(event) => setClaimReviewScope(event.target.value as ClaimReviewScope)}>
                      {claimReviewScopes.map((item) => <option key={item} value={item}>{labelClaimReviewScope(item)}</option>)}
                    </select>
                  </label>
                </div>
                <div className="module-note">
                  Claim-par alapu modul: a rendszer a mar kinyert, forrasolt allitasok kozott valaszt ellenorizendo parokat. Az alapertelmezett allitaskor nem veszi figyelembe az elutasitott allitasokat. A fokusz opcionális.
                </div>
              </>
            )}
            <label>
              {isContradictionModule ? "Fokusz (opcionalis)" : "Fokusz"}
              <textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                rows={3}
                placeholder={analysisFocusPlaceholder(moduleKey, isContradictionModule)}
              />
            </label>
            <button onClick={handleRunAnalysis} disabled={!canRunAnalysis}>
              <Play size={18} /> Futtatas
            </button>
            {analysis && (
              <div className="analysis-summary">
                <div className="metrics">
                  <span>{labelAnalysisSourceMode(effectiveAnalysisSourceMode)}</span>
                  {selectedAnalysisDocument && <span>{selectedAnalysisDocument.original_filename}</span>}
                  <span>{labelValidationStatus(analysis.validation_status)}</span>
                  <span>{analysisSourceMetric(analysis)}</span>
                  <span>{analysis.unsupported_items.length} nem tamogatott</span>
                  <span>{analysisOutputCount(analysis)} kimenet</span>
                </div>
                <code>{analysis.analysis_run_id}</code>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Elemzesi elozmenyek</h2>
              <Archive size={20} />
            </div>
            <div className="compact-list">
              {analysisRuns.length === 0 && <p className="muted">Nincs elemzesi futas.</p>}
              {analysisRuns.slice(0, 8).map((run) => (
                <article key={run.id} className="compact-item">
                  <strong>{labelModule(run.run_type)}</strong>
                  <span>{labelRunStatus(run.status)} | {run.validation_status ? labelValidationStatus(run.validation_status) : "nincs validacio"} | {run.model_name ?? "nincs modell"}</span>
                  <span>{new Date(run.started_at).toLocaleString()} {run.finished_at ? `-> ${new Date(run.finished_at).toLocaleTimeString()}` : ""}</span>
                  {run.error_message && <p className="error-text">{run.error_message}</p>}
                  <code>{run.id}</code>
                  <button onClick={() => handleAnalysisRunDetail(run)} disabled={Boolean(busy)}>
                    Reszletek
                  </button>
                </article>
              ))}
            </div>
          </section>

          <section className="panel detail-panel">
            <div className="section-heading">
              <h2>Elemzesi futas reszletei</h2>
              <Archive size={20} />
            </div>
            {!analysisRunDetail && <p className="muted">Valassz elemzesi futast a reszletekhez.</p>}
            {analysisRunDetail && (
              <div className="detail-stack">
                <strong>{labelModule(analysisRunDetail.run.run_type)}</strong>
                <div className="metrics">
                  <span>{labelRunStatus(analysisRunDetail.run.status)}</span>
                  <span>{analysisRunDetail.run.validation_status ? labelValidationStatus(analysisRunDetail.run.validation_status) : "nincs validacio"}</span>
                  <span>{analysisRunDetail.inputs.length} bemenet</span>
                  <span>{analysisRunDetail.outputs.length} kimenet</span>
                </div>
                <code>{analysisRunDetail.run.id}</code>
                {analysisRunDetail.run.error_message && <p className="error-text">{analysisRunDetail.run.error_message}</p>}
                <details open>
                  <summary>Bemenetek</summary>
                  <div className="detail-list">
                    {analysisRunDetail.inputs.map((input) => (
                      <article key={input.id} className="compact-item">
                        <strong>{input.sequence_no}. {labelAnalysisInputType(input.input_type)}</strong>
                        <span>{input.related_object_type ? labelObjectType(input.related_object_type) : "Forras"} {input.related_object_id ?? input.chunk_id ?? input.document_id ?? ""}</span>
                        {input.payload_json && renderAnalysisInputPayload(input.payload_json)}
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Kimenetek</summary>
                  <div className="detail-list">
                    {analysisRunDetail.outputs.map((output) => (
                      <article key={output.id} className="compact-item">
                        <strong>{output.output_position ?? 0}. {labelAnalysisOutputType(output.output_type)}</strong>
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
              <h2>Attekintesi jelentés</h2>
              <Archive size={20} />
            </div>
            <div className="form-row">
              <label>
                Objektum
                <select value={objectType} onChange={(event) => setObjectType(event.target.value)}>
                  {objectTypes.map((item) => <option key={item} value={item}>{item ? labelObjectType(item) : "Osszes"}</option>)}
                </select>
              </label>
              <label>
                Felulvizsgalat allapota
                <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>
                  {reviewStatuses.map((item) => <option key={item} value={item}>{item ? labelReviewStatus(item) : "Osszes"}</option>)}
                </select>
              </label>
              <label>
                Forras allapota
                <select value={sourceValidationStatus} onChange={(event) => setSourceValidationStatus(event.target.value)}>
                  {sourceValidationStatuses.map((item) => <option key={item} value={item}>{item ? labelSourceValidationStatus(item) : "Osszes"}</option>)}
                </select>
              </label>
              <button onClick={handleLoadReport} disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} /> Betoltes
              </button>
            </div>
            <div className="queue-row">
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({ reviewStatus: "needs_review", sourceValidationStatus: "source_valid" }, "Ellenorzesi lista")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Ellenorzesi lista
              </button>
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({ objectType: "missing_item_candidate", reviewStatus: "needs_review", sourceValidationStatus: "source_valid" }, "Hianyzo iratok")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Hianyzo iratok
              </button>
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({ objectType: "contradiction_candidate", reviewStatus: "needs_review", sourceValidationStatus: "source_valid" }, "Ellentmondasok")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Ellentmondasok
              </button>
              <button
                className="secondary-button"
                onClick={() => applyReviewQueue({}, "Osszes jelenteselem")}
                disabled={!selectedCaseId || Boolean(busy)}
              >
                Osszes
              </button>
            </div>
            {report && (
              <>
                <div className="metrics">
                  <span>{report.counts.total} osszesen</span>
                  <span>{report.counts.needs_review} ellenorzesre var</span>
                  <span>{report.counts.verified} ellenorizve</span>
                  <span>{report.counts.rejected} elutasitva</span>
                </div>
                <div className="item-list">
                  {report.items.map((item) => (
                    <article key={item.object_id} className="report-item">
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.body_text}</p>
                        {item.object_type === "contradiction_candidate" && (
                          <p className="review-note">Ellenorizendo jelolt: a rendszer nem tekinti bizonyitott ellentmondasnak.</p>
                        )}
                      </div>
                      <div className="tags">
                        <span>{labelObjectType(item.object_type)}</span>
                        <span>{labelSubtype(item.object_type, item.subtype)}</span>
                        <span>{labelReviewStatus(item.review_status)}</span>
                        <span>{labelSourceValidationStatus(item.source_validation_status)}</span>
                        <span>{item.reviews.length} felulvizsgalat</span>
                        <span>{item.sources.length} forras</span>
                      </div>
                      <button className="secondary-button" onClick={() => setSelectedReportItem(item)}>
                        Reszletek
                      </button>
                      <div className="source-list">
                        {item.sources.map((source, index) => (
                          <details key={source.source_reference_id} className="source-detail" open={index === 0}>
                            <summary>
                              {index + 1}. forras: {source.document_filename ?? "irat"} {source.page_number ? `${source.page_number}. oldal` : ""} {source.chunk_index !== null ? `${source.chunk_index}. szovegresz` : ""}
                            </summary>
                            <div className="source-meta">
                              <span>{labelSupportType(source.support_type)}</span>
                              <span>sorrend {source.relevance_rank ?? index}</span>
                              <span>{source.citation_label ?? "nincs hivatkozasi cimke"}</span>
                              <span>idezet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                              <span>reszlet {formatRange(source.source_text_excerpt_char_start, source.source_text_excerpt_char_end)}</span>
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
                              <strong>{labelAction(review.action_type)}</strong>
                              <span>{review.new_review_status ? labelReviewStatus(review.new_review_status) : "megjegyzes"}</span>
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
                          placeholder="Felulvizsgalati megjegyzes"
                          aria-label="Felulvizsgalati megjegyzes"
                        />
                        <button title="Ellenorizve" onClick={() => handleReview(item.object_type, item.object_id, "verify")} disabled={Boolean(busy)}>
                          <CheckCircle2 size={18} />
                        </button>
                        <button title="Elutasitas" onClick={() => handleReview(item.object_type, item.object_id, "reject")} disabled={Boolean(busy)}>
                          Elutasit
                        </button>
                        <button title="Ellenorzesre var" onClick={() => handleReview(item.object_type, item.object_id, "mark_needs_review")} disabled={Boolean(busy)}>
                          Ellenorzesre
                        </button>
                        <button title="Megjegyzes" onClick={() => handleReview(item.object_type, item.object_id, "comment")} disabled={Boolean(busy)}>
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
              <h2>Objektum reszletei</h2>
              <Search size={20} />
            </div>
            {!selectedReportItem && <p className="muted">Valassz jelenteselemet a reszletekhez.</p>}
            {selectedReportItem && (
              <div className="detail-stack">
                <strong>{selectedReportItem.title}</strong>
                <div className="metrics">
                  <span>{labelObjectType(selectedReportItem.object_type)}</span>
                  <span>{labelSubtype(selectedReportItem.object_type, selectedReportItem.subtype)}</span>
                  <span>{labelReviewStatus(selectedReportItem.review_status)}</span>
                  <span>{labelSourceValidationStatus(selectedReportItem.source_validation_status)}</span>
                </div>
                <code>{selectedReportItem.object_id}</code>
                {selectedReportItem.body_text && <p>{selectedReportItem.body_text}</p>}
                {selectedReportItem.object_type === "contradiction_candidate" && (
                  <p className="review-note">A jelolt ket forrasolt allitas parjat emeli ki emberi ellenorzesre. Onmagaban nem bizonyitott tenymegallapitas.</p>
                )}
                <div className="object-facts">
                  {objectDetailFacts(selectedReportItem).map((fact) => (
                    <div key={fact.label}>
                      <span>{fact.label}</span>
                      <strong>{fact.value}</strong>
                    </div>
                  ))}
                </div>
                <details open>
                  <summary>Forrasok</summary>
                  <div className="detail-list">
                    {selectedReportItem.sources.map((source, index) => (
                      <article key={source.source_reference_id} className="text-sample">
                        <strong>{index + 1}. {source.document_filename ?? "irat"}</strong>
                        <span>{source.citation_label ?? "nincs hivatkozas"} | idezet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                        <pre>{source.quote_text}</pre>
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Felulvizsgalati elozmenyek</summary>
                  <div className="detail-list">
                    {selectedReportItem.reviews.map((review) => (
                      <article key={review.id} className="compact-item">
                        <strong>{labelAction(review.action_type)}</strong>
                        <span>{review.new_review_status ? labelReviewStatus(review.new_review_status) : "megjegyzes"} | {new Date(review.performed_at).toLocaleString()}</span>
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
                <span>{lastExport.items.length} elem</span>
                <a href={`/api/v1/cases/${selectedCaseId}/exports/${lastExport.export.id}/download`}>Letoltes</a>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Export elozmenyek</h2>
              <button className="icon-button" onClick={refreshExports} title="Export elozmenyek frissitese" disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} />
              </button>
            </div>
            <div className="compact-list">
              {exports.length === 0 && <p className="muted">Nincs export.</p>}
              {exports.slice(0, 10).map((item) => (
                <article key={item.id} className="compact-item">
                  <strong>{item.export_type.toUpperCase()} {labelExportScope(item.export_scope)}</strong>
                  <span>{labelExportFilter(item.review_filter)} | {new Date(item.created_at).toLocaleString()}</span>
                  {item.sha256_hash && <code>{item.sha256_hash}</code>}
                  <a href={`/api/v1/cases/${selectedCaseId}/exports/${item.id}/download`}>Letoltes</a>
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

function analysisSourceMetric(response: AnalysisResponse) {
  if (response.module_key === "detect_contradiction_candidates") {
    return "claim-par alapu";
  }
  return `${response.selected_chunk_ids.length} szovegresz`;
}

function analysisFocusPlaceholder(moduleKey: string, isContradictionModule: boolean) {
  if (isContradictionModule) {
    return "Opcionális: nev, tema vagy idoszak. Uresen hagyva az ugy forrasolt allitasai kozott keres parokat.";
  }
  const placeholders: Record<string, string> = {
    extract_claims: "Add meg, milyen allitasokat keressen a forrasokban.",
    extract_events: "Add meg, milyen esemenyekre vagy idoszakra fokuszaljon.",
    extract_entities: "Add meg, milyen szemelyre, szervezetre, helyre vagy azonosítora fokuszaljon.",
    summarize_case: "Add meg, milyen temarol keszuljon forrashu osszefoglalo.",
    detect_missing_items: "Add meg, milyen hivatkozott iratot, mellekletet vagy bizonyitekfajtat keressen."
  };
  return placeholders[moduleKey] ?? "Add meg a fokuszt a forrasalapu elemzeshez.";
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

function formatConfidence(value: number | null) {
  if (value === null) {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}

function labelModule(value: string) {
  return moduleLabels[value] ?? value;
}

function labelAnalysisSourceMode(value: AnalysisSourceMode) {
  return analysisSourceModeLabels[value] ?? value;
}

function labelClaimReviewScope(value: ClaimReviewScope) {
  return claimReviewScopeLabels[value] ?? value;
}

function clampNumberInput(value: string, min: number, max: number, fallback: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

function labelObjectType(value: string) {
  return objectTypeLabels[value] ?? value;
}

function labelReviewStatus(value: string) {
  return reviewStatusLabels[value] ?? value;
}

function labelSourceValidationStatus(value: string) {
  return sourceValidationLabels[value] ?? value;
}

function labelRunStatus(value: string) {
  return runStatusLabels[value] ?? value;
}

function labelValidationStatus(value: string) {
  return validationStatusLabels[value] ?? value;
}

function labelAction(value: string) {
  return actionLabels[value] ?? value;
}

function labelProcessingStatus(value: string) {
  const labels: Record<string, string> = {
    imported: "Importalva",
    pending: "Varakozik",
    processing: "Feldolgozas alatt",
    processed: "Feldolgozva",
    review_required: "Ellenorzest igenyel",
    failed: "Sikertelen"
  };
  return labels[value] ?? value;
}

function labelTextSource(value: string) {
  const labels: Record<string, string> = {
    native: "Nativ szoveg",
    txt_import: "TXT import",
    ocr: "OCR",
    docling: "Docling",
    manual: "Kezi"
  };
  return labels[value] ?? value;
}

function canRunOcr(document: DocumentRead) {
  const needsOcrAction =
    document.processing_status === "review_required" ||
    document.processing_status === "failed" ||
    document.page_count === 0;
  return document.original_filename.toLowerCase().endsWith(".pdf") && document.processing_status !== "processing" && needsOcrAction;
}

function labelSupportType(value: string) {
  const labels: Record<string, string> = {
    direct: "Kozvetlen",
    indirect: "Kozvetett",
    context: "Kontekstus"
  };
  return labels[value] ?? value;
}

function labelAnalysisInputType(value: string) {
  const labels: Record<string, string> = {
    query_text: "Keresdes",
    filter: "Kivalasztasi szuro",
    chunk: "Szovegresz",
    claim: "Allitas",
    event: "Esemeny",
    source_reference: "Forrashivatkozas"
  };
  return labels[value] ?? value;
}

function renderAnalysisInputPayload(payload: Record<string, unknown>) {
  if (payload.input_kind === "claim_selection") {
    const selectedPairs = Array.isArray(payload.selected_pairs) ? payload.selected_pairs : [];
    return (
      <div className="payload-summary">
        <div className="metrics">
          <span>{formatUnknownNumber(payload.retrieved_claim_count)} lekert allitas</span>
          <span>{formatUnknownNumber(payload.selected_claim_count)} kivalasztott allitas</span>
          <span>{formatUnknownNumber(payload.selected_pair_count)} claim-par</span>
          <span>par limit {formatUnknownNumber(payload.pair_limit)}</span>
          <span>{labelPayloadClaimReviewScope(payload.claim_review_scope)}</span>
          <span>{payload.focus_filter_applied ? "fokuszszures aktiv" : "nincs fokuszszures"}</span>
        </div>
        {Array.isArray(payload.focus_terms) && payload.focus_terms.length > 0 && (
          <p className="muted">Fokusz: {payload.focus_terms.map(String).join(", ")}</p>
        )}
        {selectedPairs.length > 0 && (
          <div className="pair-list">
            {selectedPairs.slice(0, 10).map((pair, index) => renderSelectedPair(pair, index))}
            {selectedPairs.length > 10 && <span className="muted">Tovabbi {selectedPairs.length - 10} par nincs megjelenitve.</span>}
          </div>
        )}
      </div>
    );
  }

  if (Array.isArray(payload.claim_pair_labels) && payload.claim_pair_labels.length > 0) {
    return (
      <div className="payload-summary">
        <div className="metrics">
          <span>{String(payload.claim_label ?? "allitas")}</span>
          <span>{payload.claim_pair_labels.length} kivalasztott parban szerepel</span>
          <span>{String(payload.source_validation_status ?? "forras allapot ismeretlen")}</span>
        </div>
        <p className="muted">Parok: {payload.claim_pair_labels.map(String).join(", ")}</p>
      </div>
    );
  }

  return <pre>{JSON.stringify(payload, null, 2)}</pre>;
}

function labelPayloadClaimReviewScope(value: unknown) {
  if (value === "reviewable" || value === "verified" || value === "needs_review" || value === "all_source_valid") {
    return labelClaimReviewScope(value);
  }
  return "Ellenorizheto allitasok";
}

function renderSelectedPair(pair: unknown, index: number) {
  if (!isRecord(pair)) {
    return <span key={index} className="muted">Ismeretlen claim-par</span>;
  }
  return (
    <div key={`${String(pair.pair_label ?? index)}-${index}`} className="pair-item">
      <strong>{String(pair.pair_label ?? `pair_${index + 1}`)}</strong>
      <span>{String(pair.claim_label_a ?? "claim_a")} {"->"} {String(pair.claim_label_b ?? "claim_b")}</span>
      <code>{String(pair.claim_id_a ?? "")}</code>
      <code>{String(pair.claim_id_b ?? "")}</code>
    </div>
  );
}

function formatUnknownNumber(value: unknown) {
  return typeof value === "number" ? String(value) : "0";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function labelAnalysisOutputType(value: string) {
  const labels: Record<string, string> = {
    claim: "Allitas",
    event: "Esemeny",
    entity: "Entitas",
    mention: "Emlites",
    source_reference: "Forrashivatkozas",
    summary_item: "Osszefoglalo elem",
    contradiction_candidate: "Ellentmondasjelolt",
    missing_item_candidate: "Hianyzo irat jelolt"
  };
  return labels[value] ?? value;
}

function labelExportFilter(value: string | null) {
  const labels: Record<string, string> = {
    all: "Osszes",
    verified_only: "Csak ellenorzott",
    needs_review: "Ellenorzesre var",
    rejected: "Elutasitott"
  };
  return labels[value ?? "all"] ?? (value ?? "Osszes");
}

function labelExportScope(value: string) {
  const labels: Record<string, string> = {
    review_report: "attekintesi jelentés"
  };
  return labels[value] ?? value;
}

function objectDetailFacts(item: ReviewReportItem) {
  const base = [
    { label: "Forrasok", value: String(item.sources.length) },
    { label: "Felulvizsgalatok", value: String(item.reviews.length) }
  ];
  if (item.object_type === "contradiction_candidate") {
    return [...base, { label: "Jelolt tipusa", value: labelSubtype(item.object_type, item.subtype) }];
  }
  if (item.object_type === "missing_item_candidate") {
    return [...base, { label: "Hivatkozott irat", value: item.title }];
  }
  if (item.object_type === "summary_item") {
    return [...base, { label: "Osszefoglalo tipusa", value: item.subtype }];
  }
  if (item.object_type === "entity") {
    return [...base, { label: "Entitas tipusa", value: item.subtype }];
  }
  if (item.object_type === "event") {
    return [...base, { label: "Esemeny tipusa", value: item.subtype }];
  }
  return [...base, { label: "Allitas tipusa", value: item.subtype }];
}

function labelSubtype(objectType: string, subtype: string) {
  if (objectType === "contradiction_candidate") {
    const labels: Record<string, string> = {
      time_conflict: "Idobeli elteres",
      location_conflict: "Helyszini elteres",
      identity_conflict: "Szemelyi vagy azonossagi elteres",
      document_mismatch: "Iratosszeferhetetlenseg",
      amount_conflict: "Osszegbeli elteres",
      other: "Egyeb elteres"
    };
    return labels[subtype] ?? subtype;
  }
  return subtype;
}
