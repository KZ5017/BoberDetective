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
  CaseRead,
  ExportDetail,
  ReviewReport,
  createCase,
  createExport,
  getReviewReport,
  importDocument,
  listCases,
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

export function App() {
  const [cases, setCases] = useState<CaseRead[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [caseName, setCaseName] = useState("");
  const [caseReference, setCaseReference] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("jegyzokonyv");
  const [moduleKey, setModuleKey] = useState("detect_missing_items");
  const [query, setQuery] = useState("Keress hivatkozott mellekletet.");
  const [limit, setLimit] = useState(5);
  const [objectType, setObjectType] = useState("");
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [lastExport, setLastExport] = useState<ExportDetail | null>(null);
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const selectedCase = useMemo(() => cases.find((item) => item.id === selectedCaseId), [cases, selectedCaseId]);

  useEffect(() => {
    void refreshCases();
  }, []);

  async function perform(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ismeretlen hiba");
    } finally {
      setBusy("");
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
    });
  }

  async function handleImport() {
    if (!selectedCaseId || !file) return;
    await perform("import", async () => {
      await importDocument(selectedCaseId, file, documentType);
      setFile(null);
    });
  }

  async function handleRunAnalysis() {
    if (!selectedCaseId) return;
    await perform("analysis", async () => {
      const response = await runAnalysis(selectedCaseId, moduleKey, query, limit);
      setAnalysis(response);
      const reportResponse = await getReviewReport(selectedCaseId, objectType || undefined);
      setReport(reportResponse);
    });
  }

  async function handleLoadReport() {
    if (!selectedCaseId) return;
    await perform("report", async () => {
      setReport(await getReviewReport(selectedCaseId, objectType || undefined));
    });
  }

  async function handleExport(exportType: "json" | "html") {
    if (!selectedCaseId) return;
    await perform(`export-${exportType}`, async () => {
      setLastExport(await createExport(selectedCaseId, exportType, objectType || undefined));
    });
  }

  async function handleReview(itemObjectType: string, objectId: string, actionType: "verify" | "reject" | "mark_needs_review" | "comment") {
    if (!selectedCaseId) return;
    const comment = reviewComments[objectId] ?? "";
    await perform(`review-${actionType}`, async () => {
      await reviewObject(selectedCaseId, itemObjectType, objectId, actionType, comment);
      setReviewComments((current) => ({ ...current, [objectId]: "" }));
      setReport(await getReviewReport(selectedCaseId, objectType || undefined));
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
        </aside>

        <section className="main-grid">
          <section className="panel hero-panel">
            <div>
              <h2>{selectedCase?.case_name ?? "Nincs aktiv ugy"}</h2>
              <p>{selectedCase?.case_reference ?? selectedCase?.status ?? "Valassz vagy hozz letre ugyet"}</p>
            </div>
            <span className="run-state">{busy ? <Loader2 className="spin" size={18} /> : <CheckCircle2 size={18} />} {busy || "keszenlet"}</span>
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
              <div className="metrics">
                <span>{analysis.validation_status}</span>
                <span>{analysis.selected_chunk_ids.length} chunk</span>
                <span>{analysis.unsupported_items.length} unsupported</span>
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
              <button onClick={handleLoadReport} disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} /> Betoltes
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
                      </div>
                      {item.sources[0] && <blockquote>{item.sources[0].quote_text}</blockquote>}
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
        </section>
      </section>
    </main>
  );
}
