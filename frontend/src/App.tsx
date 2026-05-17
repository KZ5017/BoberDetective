import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  CheckCircle2,
  Database,
  Download,
  FilePlus2,
  FolderPlus,
  GitMerge,
  Loader2,
  MessageSquare,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Unlink
} from "lucide-react";
import {
  AnalysisResponse,
  AnalysisRunDetail,
  AnalysisRunRead,
  AnalysisSourceMode,
  CaseRead,
  ClaimReviewScope,
  ChunkIndexStatusResponse,
  DetachedSourceItemRead,
  DocumentChunkRead,
  DocumentPageRead,
  DocumentRead,
  DocumentTaxonomyGroupRead,
  EntityRead,
  EventRead,
  ExportDetail,
  ExportRead,
  LlmSmokeResponse,
  ManualObjectPayload,
  ManualObjectType,
  ManualObjectFromSourcePayload,
  ManualContradictionCandidatePayload,
  MissingItemCandidateRead,
  ReviewReport,
  ReviewReportFilterValues,
  ReviewReportItem,
  ReviewReportSource,
  RetrievalStrategy,
  attachDetachedSourceItem,
  createCase,
  createDocumentChunks,
  createExport,
  createManualObject,
  createManualContradictionCandidate,
  createManualObjectFromDetachedSource,
  detachObjectSource,
  discardDetachedSourceItem,
  getAnalysisRun,
  getChunkIndexStatus,
  getReviewReport,
  importDocument,
  getLlmSmoke,
  listDetachedSourceItems,
  listDocumentChunks,
  listDocumentPages,
  listDocumentTaxonomy,
  listAnalysisRuns,
  listCases,
  listDocuments,
  listEntities,
  listEvents,
  listExports,
  listMissingItemCandidates,
  loadChatModel,
  loadEmbeddingModel,
  mergeEvent,
  mergeEntity,
  mergeMissingItemCandidate,
  moveObjectSource,
  reviewObject,
  runAnalysis,
  runDocumentOcr,
  startChunkIndexJob,
  updateDocumentTaxonomy
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
const analysisSourceModes: AnalysisSourceMode[] = ["case", "document"];
const claimReviewScopes: ClaimReviewScope[] = ["reviewable", "verified", "needs_review", "all_source_valid"];
const retrievalStrategies: RetrievalStrategy[] = ["keyword", "semantic", "hybrid"];

const busyLabels: Record<string, string> = {
  cases: "Ugylista frissitese",
  "case-create": "Ugy letrehozasa",
  "case-data": "Ugyadatok betoltese",
  "document-detail": "Iratreszletek betoltese",
  "document-taxonomy": "Iratbesorolas mentese",
  "document-chunks": "Szovegreszek letrehozasa",
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
  "review-comment": "Megjegyzes rogzítese",
  "entity-merge": "Entitasok osszevonasa",
  "event-merge": "Esemenyek osszevonasa",
  "missing-item-merge": "Hianyzo irat jeloltek osszevonasa",
  "source-detach": "Forras levalasztasa",
  "source-move": "Forras athelyezese",
  "detached-source-attach": "Levalasztott forras csatolasa",
  "detached-source-discard": "Levalasztott forras irrelevansnak jelolese",
  "manual-object": "Kezi objektum rogzitese",
  "manual-contradiction": "Kezi ellentmondasjelolt rogzitese",
  "chunk-index": "Chunk indexeles",
  "llm-smoke": "LLM modell allapot",
  "chat-load": "Chat modell betoltese",
  "embedding-load": "Embedding modell betoltese"
};

const moduleLabels: Record<string, string> = {
  extract_claims: "Allitasok kinyerese",
  extract_events: "Esemenyek kinyerese",
  extract_entities: "Entitasok kinyerese",
  summarize_case: "Ugyosszefoglalo keszitese",
  detect_contradiction_candidates: "Ellentmondasjeloltek keresese",
  detect_missing_items: "Hianyzo iratok keresese",
  manual_entry: "Kezi rogzitese"
};

const analysisSourceModeLabels: Record<AnalysisSourceMode, string> = {
  document: "Kivalasztott irat",
  case: "Teljes ugy"
};

const claimReviewScopeLabels: Record<ClaimReviewScope, string> = {
  reviewable: "Ellenorizheto allitasok",
  verified: "Csak ellenorzott",
  needs_review: "Ellenorzesre varok",
  all_source_valid: "Minden forraservenyes"
};

const retrievalStrategyLabels: Record<RetrievalStrategy, string> = {
  keyword: "Kulcsszavas",
  semantic: "Szemantikus",
  hybrid: "Hybrid"
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

const manualObjectTypeLabels: Record<ManualObjectType, string> = {
  claim: "Allitas",
  entity: "Entitas",
  event: "Esemeny",
  missing_item_candidate: "Hianyzo irat jelolt"
};

const contradictionTypeLabels: Record<ManualContradictionCandidatePayload["contradiction_type"], string> = {
  time_conflict: "Idobeli elteres",
  location_conflict: "Helyszinbeli elteres",
  identity_conflict: "Azonossagi elteres",
  document_mismatch: "Iratbeli elteres",
  amount_conflict: "Osszegbeli elteres",
  other: "Egyeb elteres"
};

const severityHintLabels: Record<NonNullable<ManualContradictionCandidatePayload["severity_hint"]>, string> = {
  low: "Alacsony",
  medium: "Kozepes",
  high: "Magas"
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
  comment: "Megjegyzes",
  correct: "Javitas",
  attach_source: "Forras csatolasa",
  detach_source: "Forras levalasztasa"
};

function getManualContradictionClaims(caseId: string): Promise<ReviewReport> {
  return getReviewReport(caseId, { objectType: "claim", sourceValidationStatus: "source_valid" });
}

export function App() {
  const [cases, setCases] = useState<CaseRead[]>([]);
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [analysisRuns, setAnalysisRuns] = useState<AnalysisRunRead[]>([]);
  const [exports, setExports] = useState<ExportRead[]>([]);
  const [entities, setEntities] = useState<EntityRead[]>([]);
  const [events, setEvents] = useState<EventRead[]>([]);
  const [missingItemCandidates, setMissingItemCandidates] = useState<MissingItemCandidateRead[]>([]);
  const [detachedSourceItems, setDetachedSourceItems] = useState<DetachedSourceItemRead[]>([]);
  const [manualContradictionClaims, setManualContradictionClaims] = useState<ReviewReportItem[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentRead | null>(null);
  const [taxonomyEditGroupCode, setTaxonomyEditGroupCode] = useState("uncategorized");
  const [taxonomyEditTypeCode, setTaxonomyEditTypeCode] = useState("uncategorized");
  const [taxonomyEditComment, setTaxonomyEditComment] = useState("");
  const [documentPages, setDocumentPages] = useState<DocumentPageRead[]>([]);
  const [documentChunks, setDocumentChunks] = useState<DocumentChunkRead[]>([]);
  const [analysisRunDetail, setAnalysisRunDetail] = useState<AnalysisRunDetail | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [caseName, setCaseName] = useState("");
  const [caseReference, setCaseReference] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [documentTaxonomy, setDocumentTaxonomy] = useState<DocumentTaxonomyGroupRead[]>([]);
  const [documentGroupCode, setDocumentGroupCode] = useState("uncategorized");
  const [documentTypeCode, setDocumentTypeCode] = useState("uncategorized");
  const [documentListSearch, setDocumentListSearch] = useState("");
  const [moduleKey, setModuleKey] = useState("detect_missing_items");
  const [query, setQuery] = useState("");
  const [analysisSourceMode, setAnalysisSourceMode] = useState<AnalysisSourceMode>("case");
  const [analysisDocumentId, setAnalysisDocumentId] = useState("");
  const [analysisDocumentGroupCode, setAnalysisDocumentGroupCode] = useState("");
  const [analysisDocumentTypeCode, setAnalysisDocumentTypeCode] = useState("");
  const [analysisDocumentIds, setAnalysisDocumentIds] = useState<string[]>([]);
  const [analysisDocumentSearch, setAnalysisDocumentSearch] = useState("");
  const [analysisPageStart, setAnalysisPageStart] = useState("");
  const [analysisPageEnd, setAnalysisPageEnd] = useState("");
  const [maxChunks, setMaxChunks] = useState(20);
  const [batchSize, setBatchSize] = useState(5);
  const [claimReviewScope, setClaimReviewScope] = useState<ClaimReviewScope>("reviewable");
  const [contradictionCandidateLimit, setContradictionCandidateLimit] = useState(5);
  const [retrievalStrategy, setRetrievalStrategy] = useState<RetrievalStrategy>("keyword");
  const [forceReindex, setForceReindex] = useState(false);
  const [activeIndexJobId, setActiveIndexJobId] = useState<string | null>(null);
  const [llmSmoke, setLlmSmoke] = useState<LlmSmokeResponse | null>(null);
  const [chunkIndexStatus, setChunkIndexStatus] = useState<ChunkIndexStatusResponse | null>(null);
  const [objectType, setObjectType] = useState("");
  const [reviewStatus, setReviewStatus] = useState("needs_review");
  const [sourceValidationStatus, setSourceValidationStatus] = useState("source_valid");
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [selectedReportItem, setSelectedReportItem] = useState<ReviewReportItem | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [lastExport, setLastExport] = useState<ExportDetail | null>(null);
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});
  const [mergeTargets, setMergeTargets] = useState<Record<string, string>>({});
  const [sourceMoveTargets, setSourceMoveTargets] = useState<Record<string, string>>({});
  const [detachedSourceTargets, setDetachedSourceTargets] = useState<Record<string, string>>({});
  const [detachedManualTypes, setDetachedManualTypes] = useState<Record<string, ManualObjectType>>({});
  const [detachedManualFields, setDetachedManualFields] = useState<Record<string, Record<string, string>>>({});
  const [manualSource, setManualSource] = useState<{
    documentId: string;
    documentName: string;
    pageId: string | null;
    chunkId: string;
    chunkIndex: number;
    quoteText: string;
    quoteStart: number;
    quoteEnd: number;
    citationLabel: string;
  } | null>(null);
  const [manualObjectType, setManualObjectType] = useState<ManualObjectType>("claim");
  const [manualFields, setManualFields] = useState<Record<string, string>>({});
  const [manualContradiction, setManualContradiction] = useState<ManualContradictionCandidatePayload>({
    claim_id_a: "",
    claim_id_b: "",
    contradiction_type: "other",
    severity_hint: "low",
    description: ""
  });
  const [busy, setBusy] = useState("");
  const [busyStartedAt, setBusyStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastActionSummary, setLastActionSummary] = useState("");

  const selectedCase = useMemo(() => cases.find((item) => item.id === selectedCaseId), [cases, selectedCaseId]);
  const selectedImportGroup = useMemo(
    () => documentTaxonomy.find((group) => group.code === documentGroupCode) ?? null,
    [documentTaxonomy, documentGroupCode]
  );
  const selectedImportType = useMemo(
    () => selectedImportGroup?.types.find((documentType) => documentType.code === documentTypeCode) ?? null,
    [selectedImportGroup, documentTypeCode]
  );
  const selectedTaxonomyEditGroup = useMemo(
    () => documentTaxonomy.find((group) => group.code === taxonomyEditGroupCode) ?? null,
    [documentTaxonomy, taxonomyEditGroupCode]
  );
  const taxonomyEditChanged =
    Boolean(selectedDocument) &&
    (selectedDocument?.document_group_code !== taxonomyEditGroupCode ||
      selectedDocument?.document_type_code !== taxonomyEditTypeCode);
  const selectedAnalysisDocument = useMemo(
    () => documents.find((item) => item.id === analysisDocumentId) ?? null,
    [analysisDocumentId, documents]
  );
  const filteredDocuments = useMemo(
    () => filterDocumentsByName(documents, documentListSearch),
    [documents, documentListSearch]
  );
  const selectedAnalysisGroup = useMemo(
    () => documentTaxonomy.find((group) => group.code === analysisDocumentGroupCode) ?? null,
    [documentTaxonomy, analysisDocumentGroupCode]
  );
  const analysisTypeOptions = selectedAnalysisGroup?.types ?? [];
  const analysisDocumentFilterOptions = useMemo(
    () =>
      documents.filter((document) => {
        if (analysisDocumentGroupCode && document.document_group_code !== analysisDocumentGroupCode) return false;
        if (analysisDocumentTypeCode && document.document_type_code !== analysisDocumentTypeCode) return false;
        return true;
      }),
    [documents, analysisDocumentGroupCode, analysisDocumentTypeCode]
  );
  const filteredCaseAnalysisDocuments = useMemo(
    () => filterDocumentsByName(analysisDocumentFilterOptions, analysisDocumentSearch),
    [analysisDocumentFilterOptions, analysisDocumentSearch]
  );
  const filteredDocumentAnalysisDocuments = useMemo(
    () => filterDocumentsByName(documents, analysisDocumentSearch),
    [documents, analysisDocumentSearch]
  );
  const manualContradictionClaimOptions = useMemo(
    () =>
      manualContradictionClaims.filter(
        (item) => item.source_validation_status === "source_valid" && item.review_status !== "rejected"
      ),
    [manualContradictionClaims]
  );
  const selectedManualClaimA = useMemo(
    () => manualContradictionClaimOptions.find((item) => item.object_id === manualContradiction.claim_id_a) ?? null,
    [manualContradiction.claim_id_a, manualContradictionClaimOptions]
  );
  const selectedManualClaimB = useMemo(
    () => manualContradictionClaimOptions.find((item) => item.object_id === manualContradiction.claim_id_b) ?? null,
    [manualContradiction.claim_id_b, manualContradictionClaimOptions]
  );
  const canUseBatchScope =
    moduleKey === "extract_claims" ||
    moduleKey === "extract_events" ||
    moduleKey === "extract_entities" ||
    moduleKey === "summarize_case" ||
    moduleKey === "detect_missing_items";
  const isContradictionModule = moduleKey === "detect_contradiction_candidates";
  const effectiveAnalysisSourceMode: AnalysisSourceMode = canUseBatchScope ? analysisSourceMode : "case";
  const showStructuredAnalysisFilters = canUseBatchScope && effectiveAnalysisSourceMode === "case";
  const showAnalysisPageRange = canUseBatchScope && effectiveAnalysisSourceMode === "document" && Boolean(analysisDocumentId);
  const sourceScopeMaxPage = useMemo(() => {
    if (effectiveAnalysisSourceMode === "document") {
      return Math.max(1, selectedAnalysisDocument?.page_count ?? 1);
    }
    return Math.max(1, ...documents.map((item) => item.page_count ?? 0));
  }, [documents, effectiveAnalysisSourceMode, selectedAnalysisDocument]);
  const requiresFocusText = true;
  const usesSemanticIndex = canUseBatchScope && retrievalStrategy !== "keyword" && query.trim().length > 0;
  const semanticIndexReady = !usesSemanticIndex || Boolean(chunkIndexStatus?.is_ready);
  const parsedAnalysisPageStart = analysisPageStart.trim() ? Number(analysisPageStart) : null;
  const parsedAnalysisPageEnd = analysisPageEnd.trim() ? Number(analysisPageEnd) : null;
  const analysisPageRangeValid =
    (!showAnalysisPageRange || (
      parsedAnalysisPageStart !== null &&
      parsedAnalysisPageEnd !== null &&
      Number.isInteger(parsedAnalysisPageStart) &&
      Number.isInteger(parsedAnalysisPageEnd) &&
      parsedAnalysisPageStart >= 1 &&
      parsedAnalysisPageEnd >= 1 &&
      parsedAnalysisPageStart <= parsedAnalysisPageEnd &&
      parsedAnalysisPageEnd <= sourceScopeMaxPage
    ));
  const indexJobIsRunning = chunkIndexStatus?.latest_run_status === "running";
  const busyLabel = busy ? (busyLabels[busy] ?? busy) : "Keszenlet";
  const canRunAnalysis =
    Boolean(selectedCaseId) &&
    !busy &&
    (!requiresFocusText || query.trim().length > 0) &&
    (effectiveAnalysisSourceMode !== "document" || Boolean(analysisDocumentId)) &&
    semanticIndexReady &&
    analysisPageRangeValid;
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
    void refreshDocumentTaxonomy();
  }, []);

  useEffect(() => {
    if (documentTaxonomy.length === 0) return;
    const group = documentTaxonomy.find((item) => item.code === documentGroupCode) ?? documentTaxonomy[0];
    if (group.code !== documentGroupCode) {
      setDocumentGroupCode(group.code);
    }
    if (!group.types.some((documentType) => documentType.code === documentTypeCode)) {
      setDocumentTypeCode(group.types[0]?.code ?? "uncategorized");
    }
  }, [documentTaxonomy, documentGroupCode, documentTypeCode]);

  useEffect(() => {
    if (!selectedDocument) return;
    setTaxonomyEditGroupCode(selectedDocument.document_group_code);
    setTaxonomyEditTypeCode(selectedDocument.document_type_code);
    setTaxonomyEditComment("");
  }, [selectedDocument]);

  useEffect(() => {
    if (selectedCaseId) {
      void refreshCaseData(false);
    } else {
      setDocuments([]);
      setEntities([]);
      setEvents([]);
      setMissingItemCandidates([]);
      setDetachedSourceItems([]);
      setManualContradictionClaims([]);
      setAnalysisRuns([]);
      setExports([]);
      setSelectedDocument(null);
      setDocumentPages([]);
      setDocumentChunks([]);
      setManualSource(null);
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
    if (!analysisDocumentGroupCode) {
      if (analysisDocumentTypeCode) setAnalysisDocumentTypeCode("");
      return;
    }
    if (!selectedAnalysisGroup) {
      setAnalysisDocumentGroupCode("");
      setAnalysisDocumentTypeCode("");
      return;
    }
    if (analysisDocumentTypeCode && !selectedAnalysisGroup.types.some((documentType) => documentType.code === analysisDocumentTypeCode)) {
      setAnalysisDocumentTypeCode("");
    }
  }, [analysisDocumentGroupCode, analysisDocumentTypeCode, selectedAnalysisGroup]);

  useEffect(() => {
    const allowedIds = new Set(analysisDocumentFilterOptions.map((document) => document.id));
    setAnalysisDocumentIds((current) => current.filter((documentId) => allowedIds.has(documentId)));
  }, [analysisDocumentFilterOptions]);

  useEffect(() => {
    if (!showAnalysisPageRange) {
      return;
    }
    setAnalysisPageStart("1");
    setAnalysisPageEnd(String(sourceScopeMaxPage));
  }, [showAnalysisPageRange, analysisDocumentId, sourceScopeMaxPage]);

  useEffect(() => {
    if (!selectedCaseId || !canUseBatchScope) {
      setChunkIndexStatus(null);
      return;
    }
    if (effectiveAnalysisSourceMode === "document" && !analysisDocumentId) {
      setChunkIndexStatus(null);
      return;
    }
    void refreshChunkIndexStatus().catch(() => setChunkIndexStatus(null));
  }, [selectedCaseId, canUseBatchScope, effectiveAnalysisSourceMode, analysisDocumentId, analysisDocumentGroupCode, analysisDocumentTypeCode, analysisDocumentIds, retrievalStrategy, query]);

  useEffect(() => {
    if (!selectedCaseId || !activeIndexJobId) {
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await refreshChunkIndexStatus();
        const runsResponse = await listAnalysisRuns(selectedCaseId);
        if (cancelled) return;
        setAnalysisRuns(runsResponse.data);
        if (response?.latest_run_id === activeIndexJobId && response.latest_run_status && response.latest_run_status !== "running") {
          setActiveIndexJobId(null);
          setNotice(response.latest_run_status === "succeeded" ? "Szovegresz-indexeles befejezodott." : "Szovegresz-indexeles hibaval leallt.");
          setLastActionSummary(
            `Indexeles: ${labelRunStatus(response.latest_run_status)}, ${response.latest_run_output_count}/${response.latest_run_input_count} szovegresz`
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Indexelesi allapot lekerdezese sikertelen.");
        }
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selectedCaseId, activeIndexJobId, effectiveAnalysisSourceMode, analysisDocumentId, analysisDocumentGroupCode, analysisDocumentTypeCode, analysisDocumentIds]);

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

  async function refreshDocumentTaxonomy() {
    try {
      const response = await listDocumentTaxonomy();
      setDocumentTaxonomy(response.data);
      const uncategorized = response.data.find((group) => group.code === "uncategorized") ?? response.data[0];
      if (uncategorized) {
        setDocumentGroupCode(uncategorized.code);
        setDocumentTypeCode(uncategorized.types[0]?.code ?? "uncategorized");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Az irattaxonomia betoltese sikertelen.");
    }
  }

  async function refreshCaseData(showNotice = true) {
    if (!selectedCaseId) return;
    await perform("case-data", async () => {
      const [documentsResponse, runsResponse, exportsResponse, reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        listDocuments(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listExports(selectedCaseId),
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setDocuments(documentsResponse.data);
      setAnalysisRuns(runsResponse.data);
      setExports(exportsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setReport(reportResponse);
      if (showNotice) {
        setNotice("Ugyadatok frissitve.");
      }
      setLastActionSummary(`${documentsResponse.data.length} irat, ${runsResponse.data.length} elemzesi futas.`);
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
      setManualSource(null);
      setNotice("Irat reszletek betoltve.");
      setLastActionSummary(`${document.original_filename}: ${pagesResponse.data.length} oldal, ${chunksResponse.data.length} szovegresz.`);
    });
  }

  async function handleDocumentTaxonomySave() {
    if (!selectedCaseId || !selectedDocument) return;
    await perform("document-taxonomy", async () => {
      const response = await updateDocumentTaxonomy(selectedCaseId, selectedDocument.id, {
        document_group_code: taxonomyEditGroupCode,
        document_type_code: taxonomyEditTypeCode,
        comment: taxonomyEditComment.trim() || null
      });
      const documentsResponse = await listDocuments(selectedCaseId);
      const refreshedDocument = documentsResponse.data.find((item) => item.id === selectedDocument.id) ?? response;
      setDocuments(documentsResponse.data);
      setSelectedDocument(refreshedDocument);
      setTaxonomyEditComment("");
      setNotice("Iratbesorolas mentve.");
      setLastActionSummary(`${refreshedDocument.original_filename}: ${labelDocumentTaxonomy(refreshedDocument)}`);
    });
  }

  function handleManualSourceFromChunk(chunk: DocumentChunkRead, textarea: HTMLTextAreaElement) {
    if (!selectedDocument) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const quote = chunk.chunk_text.slice(start, end).trim();
    if (quote.length === 0 || end <= start) {
      setError("Jelolj ki egy konkret forrasreszletet a szovegreszbol.");
      return;
    }
    const quoteStart = chunk.chunk_text.indexOf(quote, start);
    const resolvedStart = quoteStart >= 0 ? quoteStart : start;
    const resolvedEnd = resolvedStart + quote.length;
    setManualSource({
      documentId: selectedDocument.id,
      documentName: selectedDocument.original_filename,
      pageId: null,
      chunkId: chunk.id,
      chunkIndex: chunk.chunk_index,
      quoteText: quote,
      quoteStart: resolvedStart,
      quoteEnd: resolvedEnd,
      citationLabel: `${selectedDocument.original_filename}, chunk ${chunk.chunk_index}`
    });
    setManualFields({});
    setNotice("Forras kijelolve kezi rogzitesehez.");
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

  async function handleCreateDocumentChunks(document: DocumentRead) {
    if (!selectedCaseId) return;
    await perform("document-chunks", async () => {
      const response = await createDocumentChunks(selectedCaseId, document.id, "Felhasznaloi jovahagyas utan szovegreszek letrehozasa");
      const [documentsResponse, runsResponse, chunksResponse] = await Promise.all([
        listDocuments(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listDocumentChunks(selectedCaseId, document.id)
      ]);
      const refreshedDocument = documentsResponse.data.find((item) => item.id === document.id) ?? response.document;
      setDocuments(documentsResponse.data);
      setAnalysisRuns(runsResponse.data);
      setSelectedDocument(refreshedDocument);
      setDocumentChunks(chunksResponse.data);
      setNotice("Szovegreszek letrehozva, az irat feldolgozasi alapja kesz.");
      setLastActionSummary(
        `${document.original_filename}: ${labelRunStatus(response.analysis_run.status)}, ${chunksResponse.data.length} szovegresz`
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
      await importDocument(selectedCaseId, file, documentGroupCode, documentTypeCode);
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
        source_mode: effectiveAnalysisSourceMode,
        document_id: effectiveAnalysisSourceMode === "document" ? analysisDocumentId : null,
        ...(showStructuredAnalysisFilters && analysisDocumentGroupCode ? { document_group_code: analysisDocumentGroupCode } : {}),
        ...(showStructuredAnalysisFilters && analysisDocumentTypeCode ? { document_type_code: analysisDocumentTypeCode } : {}),
        ...(showStructuredAnalysisFilters && analysisDocumentIds.length > 0 ? { document_ids: analysisDocumentIds } : {}),
        max_chunks: maxChunks,
        batch_size: batchSize,
        claim_review_scope: claimReviewScope,
        retrieval_strategy: retrievalStrategy,
        ...(showAnalysisPageRange ? { page_start: parsedAnalysisPageStart, page_end: parsedAnalysisPageEnd } : {}),
        ...(isContradictionModule ? { contradiction_candidate_limit: contradictionCandidateLimit } : {})
      };
      const response = await runAnalysis(selectedCaseId, moduleKey, payload);
      setAnalysis(response);
      const [reportResponse, manualClaimsResponse, runsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setNotice("Elemzes lefutott, jelentés frissitve.");
      setLastActionSummary(
        `${labelModule(response.module_key)}: ${analysisSourceSummaryLabel(effectiveAnalysisSourceMode, analysisDocumentIds.length)}, ${labelValidationStatus(response.validation_status)}, ${analysisSourceMetric(response)}, ${analysisOutputCount(response)} kimenet`
      );
    });
  }

  function toggleAnalysisDocumentFilter(documentId: string) {
    setAnalysisDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId]
    );
  }

  function chunkIndexScopePayload() {
    if (effectiveAnalysisSourceMode === "document") {
      return { document_id: analysisDocumentId || null };
    }
    return {
      document_id: null,
      ...(analysisDocumentGroupCode ? { document_group_code: analysisDocumentGroupCode } : {}),
      ...(analysisDocumentTypeCode ? { document_type_code: analysisDocumentTypeCode } : {}),
      ...(analysisDocumentIds.length > 0 ? { document_ids: analysisDocumentIds } : {})
    };
  }

  async function refreshChunkIndexStatus(documentIdOverride?: string | null): Promise<ChunkIndexStatusResponse | null> {
    if (!selectedCaseId) return null;
    const response = await getChunkIndexStatus(
      selectedCaseId,
      documentIdOverride !== undefined ? { document_id: documentIdOverride || null } : chunkIndexScopePayload()
    );
    setChunkIndexStatus(response);
    return response;
  }

  async function handleIndexChunks() {
    if (!selectedCaseId) return;
    await perform("chunk-index", async () => {
      const response = await startChunkIndexJob(selectedCaseId, {
        ...chunkIndexScopePayload(),
        limit: 1000,
        force_reindex: forceReindex
      });
      const [runsResponse, documentsResponse] = await Promise.all([
        listAnalysisRuns(selectedCaseId),
        listDocuments(selectedCaseId)
      ]);
      setAnalysisRuns(runsResponse.data);
      setDocuments(documentsResponse.data);
      await refreshChunkIndexStatus(effectiveAnalysisSourceMode === "document" ? analysisDocumentId : null);
      setActiveIndexJobId(response.analysis_run_id);
      setNotice("Szovegresz-indexeles elindult, az allapot automatikusan frissul.");
      setLastActionSummary(
        `Indexeles inditva: ${labelRunStatus(response.status)}, gyujtemeny: ${response.collection_name}`
      );
    });
  }

  async function handleLlmSmoke() {
    await perform("llm-smoke", async () => {
      const response = await getLlmSmoke();
      setLlmSmoke(response);
      setNotice("LLM modell allapot frissitve.");
      setLastActionSummary(`Chat: ${labelModelLoadState(response.configured_chat_model_loaded)}, embedding: ${labelModelLoadState(response.configured_embedding_model_loaded)}`);
    });
  }

  async function handleLoadChatModel() {
    await perform("chat-load", async () => {
      await loadChatModel();
      const response = await getLlmSmoke();
      setLlmSmoke(response);
      setNotice("Chat modell betoltve.");
      setLastActionSummary(`Betoltott chat modell: ${response.configured_chat_model}`);
    });
  }

  async function handleLoadEmbeddingModel() {
    await perform("embedding-load", async () => {
      await loadEmbeddingModel();
      const response = await getLlmSmoke();
      setLlmSmoke(response);
      setNotice("Embedding modell betoltve.");
      setLastActionSummary(`Betoltott embedding modell: ${response.configured_embedding_model}`);
    });
  }

  async function handleLoadReport() {
    if (!selectedCaseId) return;
    await perform("report", async () => {
      const [reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
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
      const [reportResponse, manualClaimsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId)
      ]);
      setReport(reportResponse);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === objectId) ?? null);
      setNotice("Felulvizsgalat rogzítve, jelentes frissitve.");
      setLastActionSummary(`${labelObjectType(itemObjectType)}: ${labelAction(actionType)}`);
    });
  }

  async function handleEntityMerge(sourceItem: ReviewReportItem) {
    if (!selectedCaseId || sourceItem.object_type !== "entity") return;
    const targetEntityId = mergeTargets[sourceItem.object_id];
    if (!targetEntityId) {
      setError("Valassz celentitast az osszevonashoz.");
      return;
    }
    const comment = reviewComments[sourceItem.object_id] ?? "";
    await perform("entity-merge", async () => {
      await mergeEntity(selectedCaseId, sourceItem.object_id, targetEntityId, comment);
      setReviewComments((current) => ({ ...current, [sourceItem.object_id]: "" }));
      setMergeTargets((current) => ({ ...current, [sourceItem.object_id]: "" }));
      const [reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetEntityId) ?? null);
      setNotice("Entitasok osszevonva, forrasok atkapcsolva.");
      setLastActionSummary(`Entitas osszevonva: ${sourceItem.title}`);
    });
  }

  async function handleEventMerge(sourceItem: ReviewReportItem) {
    if (!selectedCaseId || sourceItem.object_type !== "event") return;
    const targetEventId = mergeTargets[sourceItem.object_id];
    if (!targetEventId) {
      setError("Valassz celesemenyt az osszevonashoz.");
      return;
    }
    const comment = reviewComments[sourceItem.object_id] ?? "";
    await perform("event-merge", async () => {
      await mergeEvent(selectedCaseId, sourceItem.object_id, targetEventId, comment);
      setReviewComments((current) => ({ ...current, [sourceItem.object_id]: "" }));
      setMergeTargets((current) => ({ ...current, [sourceItem.object_id]: "" }));
      const [reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetEventId) ?? null);
      setNotice("Esemenyek osszevonva, forrasok atkapcsolva.");
      setLastActionSummary(`Esemeny osszevonva: ${sourceItem.title}`);
    });
  }

  async function handleMissingItemMerge(sourceItem: ReviewReportItem) {
    if (!selectedCaseId || sourceItem.object_type !== "missing_item_candidate") return;
    const targetCandidateId = mergeTargets[sourceItem.object_id];
    if (!targetCandidateId) {
      setError("Valassz celjeloltet az osszevonashoz.");
      return;
    }
    const comment = reviewComments[sourceItem.object_id] ?? "";
    await perform("missing-item-merge", async () => {
      await mergeMissingItemCandidate(selectedCaseId, sourceItem.object_id, targetCandidateId, comment);
      setReviewComments((current) => ({ ...current, [sourceItem.object_id]: "" }));
      setMergeTargets((current) => ({ ...current, [sourceItem.object_id]: "" }));
      const [reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetCandidateId) ?? null);
      setNotice("Hianyzo irat jeloltek osszevonva, forrasok atkapcsolva.");
      setLastActionSummary(`Hianyzo irat jelolt osszevonva: ${sourceItem.title}`);
    });
  }

  function canDetachSource(item: ReviewReportItem, source: ReviewReportSource) {
    return (
      Boolean(source.source_link_id) &&
      (item.object_type === "entity" || item.object_type === "event" || item.object_type === "missing_item_candidate")
    );
  }

  async function handleDetachSource(item: ReviewReportItem, source: ReviewReportSource) {
    if (!selectedCaseId || !source.source_link_id || !canDetachSource(item, source)) return;
    const comment = reviewComments[item.object_id] ?? "";
    await perform("source-detach", async () => {
      await detachObjectSource(selectedCaseId, item.object_type, item.object_id, source.source_link_id!, comment);
      setReviewComments((current) => ({ ...current, [item.object_id]: "" }));
      const [reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((reportItem) => reportItem.object_id === item.object_id) ?? null);
      setNotice("Forras levalasztva, jelentés frissitve.");
      setLastActionSummary(`${labelObjectType(item.object_type)}: forras levalasztva.`);
    });
  }

  function sourceMoveKey(item: ReviewReportItem, source: ReviewReportSource) {
    return `${item.object_id}:${source.source_link_id ?? source.source_reference_id}`;
  }

  function sourceMoveTargetOptions(item: ReviewReportItem) {
    if (item.object_type === "entity") {
      return entities
        .filter((entity) => entity.id !== item.object_id && entity.entity_type === item.subtype && entity.review_status !== "corrected")
        .map((entity) => ({ id: entity.id, label: `${entity.canonical_name} (${labelReviewStatus(entity.review_status)})` }));
    }
    if (item.object_type === "event") {
      return events
        .filter((event) => event.id !== item.object_id && event.event_type === item.subtype && event.review_status !== "corrected")
        .map((event) => ({ id: event.id, label: `${event.event_title} (${labelReviewStatus(event.review_status)})` }));
    }
    if (item.object_type === "missing_item_candidate") {
      return missingItemCandidates
        .filter((candidate) => candidate.id !== item.object_id && candidate.missing_item_type === item.subtype && candidate.review_status !== "corrected")
        .map((candidate) => ({ id: candidate.id, label: `${candidate.referenced_item_text} (${labelReviewStatus(candidate.review_status)})` }));
    }
    return [];
  }

  function detachedSourceTargetOptions(item: DetachedSourceItemRead) {
    if (item.detached_from_object_type === "entity") {
      return entities
        .filter((entity) => entity.entity_type === item.object_subtype_snapshot && entity.review_status !== "corrected")
        .map((entity) => ({ id: entity.id, label: `${entity.canonical_name} (${labelReviewStatus(entity.review_status)})` }));
    }
    if (item.detached_from_object_type === "event") {
      return events
        .filter((event) => event.event_type === item.object_subtype_snapshot && event.review_status !== "corrected")
        .map((event) => ({ id: event.id, label: `${event.event_title} (${labelReviewStatus(event.review_status)})` }));
    }
    if (item.detached_from_object_type === "missing_item_candidate") {
      return missingItemCandidates
        .filter((candidate) => candidate.missing_item_type === item.object_subtype_snapshot && candidate.review_status !== "corrected")
        .map((candidate) => ({ id: candidate.id, label: `${candidate.referenced_item_text} (${labelReviewStatus(candidate.review_status)})` }));
    }
    return [];
  }

  async function refreshReviewStateAfterSourceChange(selectedObjectId?: string | null) {
    if (!selectedCaseId) return;
    const [reportResponse, manualClaimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
      getReviewReport(selectedCaseId, reportFilters),
      getManualContradictionClaims(selectedCaseId),
      listEntities(selectedCaseId),
      listEvents(selectedCaseId),
      listMissingItemCandidates(selectedCaseId),
      listDetachedSourceItems(selectedCaseId)
    ]);
    setReport(reportResponse);
    setEntities(entitiesResponse.data);
    setEvents(eventsResponse.data);
    setMissingItemCandidates(missingItemsResponse.data);
    setDetachedSourceItems(detachedSourcesResponse.data);
    setManualContradictionClaims(manualClaimsResponse.items);
    setSelectedReportItem(selectedObjectId ? reportResponse.items.find((reportItem) => reportItem.object_id === selectedObjectId) ?? null : null);
  }

  async function handleMoveSource(item: ReviewReportItem, source: ReviewReportSource) {
    if (!selectedCaseId || !source.source_link_id || !canDetachSource(item, source)) return;
    const key = sourceMoveKey(item, source);
    const targetObjectId = sourceMoveTargets[key];
    if (!targetObjectId) {
      setError("Valassz celobjektumot a forras athelyezesehez.");
      return;
    }
    const comment = reviewComments[item.object_id] ?? "";
    await perform("source-move", async () => {
      await moveObjectSource(selectedCaseId, item.object_type, item.object_id, source.source_link_id!, targetObjectId, comment);
      setReviewComments((current) => ({ ...current, [item.object_id]: "" }));
      setSourceMoveTargets((current) => ({ ...current, [key]: "" }));
      await refreshReviewStateAfterSourceChange(targetObjectId);
      setNotice("Forras athelyezve, jelentés frissitve.");
      setLastActionSummary(`${labelObjectType(item.object_type)}: forras athelyezve.`);
    });
  }

  async function handleAttachDetachedSource(item: DetachedSourceItemRead) {
    if (!selectedCaseId) return;
    const targetObjectId = detachedSourceTargets[item.id];
    if (!targetObjectId) {
      setError("Valassz celobjektumot a levalasztott forras csatolasahoz.");
      return;
    }
    await perform("detached-source-attach", async () => {
      await attachDetachedSourceItem(selectedCaseId, item.id, targetObjectId, item.detach_comment ?? undefined);
      setDetachedSourceTargets((current) => ({ ...current, [item.id]: "" }));
      await refreshReviewStateAfterSourceChange(targetObjectId);
      setNotice("Levalasztott forras csatolva.");
      setLastActionSummary(`${labelObjectType(item.detached_from_object_type)}: levalasztott forras csatolva.`);
    });
  }

  async function handleDiscardDetachedSource(item: DetachedSourceItemRead) {
    if (!selectedCaseId) return;
    await perform("detached-source-discard", async () => {
      await discardDetachedSourceItem(selectedCaseId, item.id, item.detach_comment ?? undefined);
      await refreshReviewStateAfterSourceChange(null);
      setNotice("Levalasztott forras irrelevansnak jelolve.");
      setLastActionSummary("Levalasztott forras irrelevansnak jelolve.");
    });
  }

  function updateManualField(key: string, value: string) {
    setManualFields((current) => ({ ...current, [key]: value }));
  }

  function manualObjectFieldsPayload(type: ManualObjectType, fields: Record<string, string>): ManualObjectFromSourcePayload {
    return {
      object_type: type,
      claim_type: fields.claim_type || "document_fact",
      claim_text: fields.claim_text || null,
      entity_type: fields.entity_type || (type === "entity" ? "person" : null),
      canonical_name: fields.canonical_name || null,
      normalized_value: fields.normalized_value || null,
      description: fields.description || null,
      event_type: fields.event_type || (type === "event" ? "statement" : null),
      event_title: fields.event_title || null,
      event_description: fields.event_description || null,
      event_time_raw: fields.event_time_raw || null,
      time_precision: fields.time_precision || "unknown",
      location_text: fields.location_text || null,
      missing_item_type: fields.missing_item_type || (type === "missing_item_candidate" ? "document_reference" : null),
      referenced_item_text: fields.referenced_item_text || null,
      expected_document_type: fields.expected_document_type || null
    };
  }

  function manualObjectPayload(): ManualObjectPayload | null {
    if (!manualSource) return null;
    return {
      source_reference: {
        document_id: manualSource.documentId,
        page_id: manualSource.pageId,
        chunk_id: manualSource.chunkId,
        quote_text: manualSource.quoteText,
        quote_char_start: manualSource.quoteStart,
        quote_char_end: manualSource.quoteEnd,
        citation_label: manualSource.citationLabel,
        source_kind: "chunk_quote"
      },
      ...manualObjectFieldsPayload(manualObjectType, manualFields)
    };
  }

  async function handleCreateManualObject() {
    if (!selectedCaseId || !manualSource) return;
    const payload = manualObjectPayload();
    if (!payload) return;
    await perform("manual-object", async () => {
      const response = await createManualObject(selectedCaseId, payload);
      setManualSource(null);
      setManualFields({});
      const [reportResponse, manualClaimsResponse, runsResponse, entitiesResponse, eventsResponse, missingItemsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === response.object_id) ?? null);
      setNotice("Forrasbol rogzitett objektum letrehozva.");
      setLastActionSummary(`${labelObjectType(response.object_type)}: forrasbol rogzitve.`);
    });
  }

  function updateDetachedManualField(itemId: string, key: string, value: string) {
    setDetachedManualFields((current) => ({ ...current, [itemId]: { ...(current[itemId] ?? {}), [key]: value } }));
  }

  async function handleCreateManualObjectFromDetachedSource(item: DetachedSourceItemRead) {
    if (!selectedCaseId) return;
    const type = detachedManualTypes[item.id] ?? "claim";
    const fields = detachedManualFields[item.id] ?? {};
    await perform("manual-object", async () => {
      const response = await createManualObjectFromDetachedSource(selectedCaseId, item.id, manualObjectFieldsPayload(type, fields));
      setDetachedManualFields((current) => ({ ...current, [item.id]: {} }));
      setDetachedManualTypes((current) => ({ ...current, [item.id]: "claim" }));
      await refreshReviewStateAfterSourceChange(response.object_id);
      setNotice("Levalasztott forrasbol uj objektum letrehozva.");
      setLastActionSummary(`${labelObjectType(response.object_type)}: levalasztott forrasbol rogzitve.`);
    });
  }

  function updateManualContradictionField<K extends keyof ManualContradictionCandidatePayload>(
    key: K,
    value: ManualContradictionCandidatePayload[K]
  ) {
    setManualContradiction((current) => ({ ...current, [key]: value }));
  }

  async function handleCreateManualContradictionCandidate() {
    if (!selectedCaseId) return;
    if (!manualContradiction.claim_id_a || !manualContradiction.claim_id_b) {
      setError("Valassz ket allitast a kezi ellentmondasjelolthez.");
      return;
    }
    if (manualContradiction.claim_id_a === manualContradiction.claim_id_b) {
      setError("Ket kulonbozo allitast kell valasztani.");
      return;
    }
    if (!manualContradiction.description.trim()) {
      setError("Add meg roviden, hogy miert igenyel ellenorzest ez a par.");
      return;
    }
    await perform("manual-contradiction", async () => {
      await createManualContradictionCandidate(selectedCaseId, {
        ...manualContradiction,
        description: manualContradiction.description.trim()
      });
      setManualContradiction((current) => ({ ...current, claim_id_a: "", claim_id_b: "", description: "" }));
      const [reportResponse, manualClaimsResponse, runsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId)
      ]);
      setReport(reportResponse);
      setManualContradictionClaims(manualClaimsResponse.items);
      setAnalysisRuns(runsResponse.data);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_type === "contradiction_candidate") ?? null);
      setNotice("Kezi ellentmondasjelolt letrehozva.");
      setLastActionSummary("Kezi ellentmondasjelolt: ket allitas parositva.");
    });
  }

  function renderClaimPreview(item: ReviewReportItem | null, fallback: string) {
    if (!item) {
      return <p className="muted">{fallback}</p>;
    }
    return (
      <article className="text-sample">
        <strong>{item.title}</strong>
        <span>
          {labelReviewStatus(item.review_status)} | {item.sources.length} forras
        </span>
        <pre>{item.body_text ?? ""}</pre>
        <div className="source-list">
          {item.sources.slice(0, 3).map((source, index) => (
            <details key={source.source_link_id ?? source.source_reference_id} className="source-detail" open={index === 0}>
              <summary>
                {index + 1}. forras: {source.document_filename ?? "irat"} {source.page_number ? `${source.page_number}. oldal` : ""}{" "}
                {source.chunk_index !== null ? `${source.chunk_index}. szovegresz` : ""}
              </summary>
              <blockquote>{source.quote_text}</blockquote>
            </details>
          ))}
        </div>
      </article>
    );
  }

  function renderSourceDetachButton(item: ReviewReportItem, source: ReviewReportSource) {
    if (!canDetachSource(item, source)) return null;
    const key = sourceMoveKey(item, source);
    const targetOptions = sourceMoveTargetOptions(item);
    return (
      <div className="source-action-row">
        <button
          className="secondary-button source-action"
          title="Forras levalasztasa errol az objektumrol"
          onClick={() => handleDetachSource(item, source)}
          disabled={Boolean(busy)}
        >
          <Unlink size={16} /> Levalasztas
        </button>
        {targetOptions.length > 0 && (
          <>
            <select
              value={sourceMoveTargets[key] ?? ""}
              onChange={(event) => setSourceMoveTargets((current) => ({ ...current, [key]: event.target.value }))}
              aria-label="Forras athelyezes celja"
            >
              <option value="">Athelyezes celja</option>
              {targetOptions.map((target) => (
                <option key={target.id} value={target.id}>
                  {target.label}
                </option>
              ))}
            </select>
            <button className="secondary-button source-action" onClick={() => handleMoveSource(item, source)} disabled={Boolean(busy) || !sourceMoveTargets[key]}>
              Athelyezes
            </button>
          </>
        )}
      </div>
    );
  }

  function renderManualObjectFields() {
    return renderManualObjectFieldsFor(manualObjectType, manualFields, updateManualField);
  }

  function renderManualObjectFieldsFor(type: ManualObjectType, fields: Record<string, string>, updateField: (key: string, value: string) => void) {
    if (type === "claim") {
      return (
        <>
          <label>
            Allitas tipusa
            <select value={fields.claim_type ?? "document_fact"} onChange={(event) => updateField("claim_type", event.target.value)}>
              <option value="document_fact">Iratbeli teny</option>
              <option value="witness_statement">Tanui allitas</option>
              <option value="expert_opinion">Szakertoi velemeny</option>
              <option value="administrative_fact">Hivatalos teny</option>
              <option value="inference_candidate">Kovetkeztetesjelolt</option>
              <option value="unknown">Ismeretlen</option>
            </select>
          </label>
          <label>
            Allitas szovege
            <textarea value={fields.claim_text ?? ""} onChange={(event) => updateField("claim_text", event.target.value)} />
          </label>
        </>
      );
    }
    if (type === "entity") {
      return (
        <>
          <label>
            Entitas tipus
            <select value={fields.entity_type ?? "person"} onChange={(event) => updateField("entity_type", event.target.value)}>
              <option value="person">Szemely</option>
              <option value="organization">Szervezet</option>
              <option value="location">Hely</option>
              <option value="phone">Telefon</option>
              <option value="email">Email</option>
              <option value="license_plate">Rendszam</option>
              <option value="case_reference">Ugyhivatkozas</option>
              <option value="money_amount">Penzosszeg</option>
              <option value="document_reference">Irat hivatkozas</option>
              <option value="other">Egyeb</option>
            </select>
          </label>
          <label>
            Nev / ertek
            <input value={fields.canonical_name ?? ""} onChange={(event) => updateField("canonical_name", event.target.value)} />
          </label>
          <label>
            Leiras
            <textarea value={fields.description ?? ""} onChange={(event) => updateField("description", event.target.value)} />
          </label>
        </>
      );
    }
    if (type === "event") {
      return (
        <>
          <label>
            Esemeny tipus
            <select value={fields.event_type ?? "statement"} onChange={(event) => updateField("event_type", event.target.value)}>
              <option value="statement">Nyilatkozat</option>
              <option value="call">Hivas</option>
              <option value="meeting">Talalkozo</option>
              <option value="transfer">Atadas / utalas</option>
              <option value="search">Kutatas</option>
              <option value="seizure">Lefoglalas</option>
              <option value="document_created">Irat keletkezett</option>
              <option value="document_received">Irat erkezett</option>
              <option value="other">Egyeb</option>
            </select>
          </label>
          <label>
            Esemeny cime
            <input value={fields.event_title ?? ""} onChange={(event) => updateField("event_title", event.target.value)} />
          </label>
          <label>
            Leiras
            <textarea value={fields.event_description ?? ""} onChange={(event) => updateField("event_description", event.target.value)} />
          </label>
          <label>
            Ido szovegesen
            <input value={fields.event_time_raw ?? ""} onChange={(event) => updateField("event_time_raw", event.target.value)} />
          </label>
          <label>
            Hely
            <input value={fields.location_text ?? ""} onChange={(event) => updateField("location_text", event.target.value)} />
          </label>
        </>
      );
    }
    return (
      <>
        <label>
          Hianyzo irat tipus
          <select value={fields.missing_item_type ?? "document_reference"} onChange={(event) => updateField("missing_item_type", event.target.value)}>
            <option value="attachment">Melleklet</option>
            <option value="video">Video</option>
            <option value="expert_report">Szakertoi velemeny</option>
            <option value="protocol">Jegyzokonyv</option>
            <option value="image">Kep</option>
            <option value="document_reference">Irat hivatkozas</option>
            <option value="other">Egyeb</option>
          </select>
        </label>
        <label>
          Hivatkozott elem
          <input value={fields.referenced_item_text ?? ""} onChange={(event) => updateField("referenced_item_text", event.target.value)} />
        </label>
        <label>
          Leiras
          <textarea value={fields.description ?? ""} onChange={(event) => updateField("description", event.target.value)} />
        </label>
        <label>
          Varhato irattipus
          <input value={fields.expected_document_type ?? ""} onChange={(event) => updateField("expected_document_type", event.target.value)} />
        </label>
      </>
    );
  }

  function renderEntityMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "entity") return null;
    const targetOptions = entities.filter(
      (entity) =>
        entity.id !== item.object_id &&
        entity.entity_type === item.subtype &&
        entity.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          Osszevonas celja
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Valassz celentitast</option>
            {targetOptions.map((entity) => (
              <option key={entity.id} value={entity.id}>
                {entity.canonical_name} ({labelReviewStatus(entity.review_status)})
              </option>
            ))}
          </select>
          <span className="field-hint">Csak azonos tipusú, nem javitott entitasok valaszthatok celkent.</span>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleEntityMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Osszevonas
        </button>
      </div>
    );
  }

  function renderEventMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "event") return null;
    const targetOptions = events.filter(
      (event) =>
        event.id !== item.object_id &&
        event.event_type === item.subtype &&
        event.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          Osszevonas celja
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Valassz celesemenyt</option>
            {targetOptions.map((event) => (
              <option key={event.id} value={event.id}>
                {event.event_title} ({labelReviewStatus(event.review_status)})
              </option>
            ))}
          </select>
          <span className="field-hint">Csak azonos tipusú, nem javitott esemenyek valaszthatok celkent.</span>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleEventMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Osszevonas
        </button>
      </div>
    );
  }

  function renderMissingItemMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "missing_item_candidate") return null;
    const targetOptions = missingItemCandidates.filter(
      (candidate) =>
        candidate.id !== item.object_id &&
        candidate.missing_item_type === item.subtype &&
        candidate.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          Osszevonas celja
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Valassz celjeloltet</option>
            {targetOptions.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.referenced_item_text} ({labelReviewStatus(candidate.review_status)})
              </option>
            ))}
          </select>
          <span className="field-hint">Csak azonos tipusú, nem javitott hianyzo irat jeloltek valaszthatok celkent.</span>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleMissingItemMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Osszevonas
        </button>
      </div>
    );
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
        <section className="case-strip">
          <div className="section-heading">
            <h2>Ugyek</h2>
            <button className="icon-button" onClick={refreshCases} title="Frissites" disabled={Boolean(busy)}>
              <RefreshCw size={18} />
            </button>
          </div>
          <div className="case-strip-controls">
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
          </div>
        </section>

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

          <div className="workflow-column">
          <section className="panel documents-panel">
            <div className="section-heading">
              <h2>Iratok</h2>
              <Database size={20} />
            </div>
            <input
              className="panel-search-input"
              value={documentListSearch}
              onChange={(event) => setDocumentListSearch(event.target.value)}
              placeholder="Iratnev keresese"
              disabled={documents.length === 0}
            />
            <div className="compact-list">
              {documents.length === 0 && <p className="muted">Nincs importalt irat.</p>}
              {documents.length > 0 && filteredDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelo irat.</p>}
              {filteredDocuments.map((document) => (
                <article key={document.id} className="compact-item">
                  <strong>{document.original_filename}</strong>
                  <span>{labelDocumentTaxonomy(document)} | {labelProcessingStatus(document.processing_status)} | {formatBytes(document.file_size_bytes)}</span>
                  <code>{document.sha256_hash}</code>
                  <div className="button-row">
                    <button onClick={() => handleDocumentDetail(document)} disabled={Boolean(busy)}>
                      Reszletek
                    </button>
                    {canRunOcr(document) && (
                      <>
                        <button onClick={() => handleDocumentOcr(document)} disabled={Boolean(busy)}>
                          <Play size={18} /> {labelOcrAction(document)}
                        </button>
                        <span>{document.ocr_recommendation?.message}</span>
                      </>
                    )}
                    {canCreateChunks(document) && (
                      <button onClick={() => handleCreateDocumentChunks(document)} disabled={Boolean(busy)}>
                        Szovegreszek letrehozasa
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel detail-panel document-detail-panel">
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
                  <span>{labelDocumentTaxonomy(selectedDocument)}</span>
                  <span>{labelProcessingStatus(selectedDocument.processing_status)}</span>
                </div>
                <details>
                  <summary>Besorolas modositasa</summary>
                  <div className="manual-entry-panel">
                    <div className="form-row">
                      <label>
                        Iratcsoport
                        <select
                          value={taxonomyEditGroupCode}
                          onChange={(event) => {
                            const nextGroupCode = event.target.value;
                            const nextGroup = documentTaxonomy.find((group) => group.code === nextGroupCode);
                            setTaxonomyEditGroupCode(nextGroupCode);
                            setTaxonomyEditTypeCode(nextGroup?.types[0]?.code ?? "uncategorized");
                          }}
                          disabled={Boolean(busy) || documentTaxonomy.length === 0}
                        >
                          {documentTaxonomy.map((group) => (
                            <option key={group.code} value={group.code}>
                              {group.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Irattipus
                        <select
                          value={taxonomyEditTypeCode}
                          onChange={(event) => setTaxonomyEditTypeCode(event.target.value)}
                          disabled={Boolean(busy) || !selectedTaxonomyEditGroup}
                        >
                          {(selectedTaxonomyEditGroup?.types ?? []).map((documentType) => (
                            <option key={documentType.code} value={documentType.code}>
                              {documentType.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <label>
                      Megjegyzes
                      <textarea
                        value={taxonomyEditComment}
                        onChange={(event) => setTaxonomyEditComment(event.target.value)}
                        placeholder="Peldaul: teves importkori besorolas javitasa"
                        disabled={Boolean(busy)}
                      />
                    </label>
                    <p className="field-hint">
                      Csak az irat adminisztrativ besorolasa valtozik. Az oldalak, szovegreszek, forrashivatkozasok es elemzesi futasok nem modosulnak.
                    </p>
                    <div className="button-row">
                      <button
                        onClick={handleDocumentTaxonomySave}
                        disabled={Boolean(busy) || !selectedTaxonomyEditGroup || !taxonomyEditTypeCode || !taxonomyEditChanged}
                      >
                        Besorolas mentese
                      </button>
                      <button
                        className="secondary-button"
                        onClick={() => {
                          setTaxonomyEditGroupCode(selectedDocument.document_group_code);
                          setTaxonomyEditTypeCode(selectedDocument.document_type_code);
                          setTaxonomyEditComment("");
                        }}
                        disabled={Boolean(busy)}
                      >
                        Visszaallitas
                      </button>
                    </div>
                  </div>
                </details>
                {canRunOcr(selectedDocument) && (
                  <div className="ocr-action-box">
                    <button onClick={() => handleDocumentOcr(selectedDocument)} disabled={Boolean(busy)}>
                      <Play size={18} /> {labelOcrAction(selectedDocument)}
                    </button>
                    <p>{selectedDocument.ocr_recommendation?.message}</p>
                  </div>
                )}
                {canCreateChunks(selectedDocument) && (
                  <div className="ocr-action-box">
                    <button onClick={() => handleCreateDocumentChunks(selectedDocument)} disabled={Boolean(busy)}>
                      Szovegreszek letrehozasa
                    </button>
                    <p>Ellenorizd az oldalak szoveget, majd ezzel hozd letre a tovabbi kereseshez es elemzeshez szukseges szovegreszeket.</p>
                  </div>
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
                        <textarea
                          className="chunk-selector"
                          readOnly
                          defaultValue={chunk.chunk_text}
                          aria-label={`${chunk.chunk_index}. szovegresz kijelolheto szovege`}
                        />
                        <button
                          className="secondary-button"
                          onClick={(event) => {
                            const textarea = event.currentTarget.parentElement?.querySelector("textarea");
                            if (textarea) handleManualSourceFromChunk(chunk, textarea);
                          }}
                          disabled={Boolean(busy)}
                        >
                          Forras kijelolese
                        </button>
                      </article>
                    ))}
                  </div>
                </details>
                {manualSource && (
                  <details open>
                    <summary>Uj objektum forrasbol</summary>
                    <div className="manual-entry-panel">
                      <label>
                        Kijelolt forras
                        <textarea readOnly value={manualSource.quoteText} aria-label="Kijelolt forras readonly elonezet" />
                      </label>
                      <span className="field-hint">
                        {manualSource.citationLabel} | idezet {formatRange(manualSource.quoteStart, manualSource.quoteEnd)}
                      </span>
                      <label>
                        Objektum tipus
                        <select value={manualObjectType} onChange={(event) => setManualObjectType(event.target.value as ManualObjectType)}>
                          {(Object.keys(manualObjectTypeLabels) as ManualObjectType[]).map((type) => (
                            <option key={type} value={type}>
                              {manualObjectTypeLabels[type]}
                            </option>
                          ))}
                        </select>
                      </label>
                      {renderManualObjectFields()}
                      <div className="button-row">
                        <button onClick={handleCreateManualObject} disabled={Boolean(busy)}>
                          Rogzites forrasbol
                        </button>
                        <button className="secondary-button" onClick={() => setManualSource(null)} disabled={Boolean(busy)}>
                          Megse
                        </button>
                      </div>
                    </div>
                  </details>
                )}
              </div>
            )}
          </section>

          <section className="panel document-import-panel">
            <div className="section-heading">
              <h2>Irat import</h2>
              <FilePlus2 size={20} />
            </div>
            <div className="form-row">
              <label>
                Iratcsoport
                <select
                  value={documentGroupCode}
                  onChange={(event) => {
                    const nextGroupCode = event.target.value;
                    const nextGroup = documentTaxonomy.find((group) => group.code === nextGroupCode);
                    setDocumentGroupCode(nextGroupCode);
                    setDocumentTypeCode(nextGroup?.types[0]?.code ?? "uncategorized");
                  }}
                  disabled={documentTaxonomy.length === 0}
                >
                  {documentTaxonomy.map((group) => (
                    <option key={group.code} value={group.code}>
                      {group.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Irattipus
                <select
                  value={documentTypeCode}
                  onChange={(event) => setDocumentTypeCode(event.target.value)}
                  disabled={!selectedImportGroup}
                >
                  {(selectedImportGroup?.types ?? []).map((documentType) => (
                    <option key={documentType.code} value={documentType.code}>
                      {documentType.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {selectedImportGroup && selectedImportType && (
              <p className="field-hint">{selectedImportGroup.description} {selectedImportType.description}</p>
            )}
            <div className="form-row">
              <label>
                Irat fajl
                <input type="file" accept=".txt,.pdf,text/plain,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              </label>
            </div>
            <button onClick={handleImport} disabled={!selectedCaseId || !file || !selectedImportType || Boolean(busy)}>
              <FilePlus2 size={18} /> Importalas
            </button>
          </section>

          <section className="panel analysis-panel">
            <div className="section-heading">
              <h2>Elemzes</h2>
              <Search size={20} />
            </div>
            <div className="source-action-row">
              <button className="secondary-button" onClick={handleLlmSmoke} disabled={Boolean(busy)}>
                Modell allapot frissitese
              </button>
            </div>
            {llmSmoke && (
              <div className="model-status-panel">
                <div>
                  <strong>Lokalis modell allapot</strong>
                  <p>Provider: {llmSmoke.provider} | API: {llmSmoke.reachable ? "elerheto" : "nem erheto el"}</p>
                </div>
                <div className="model-status-grid">
                  <div className="model-status-card">
                    <strong>Chat modell</strong>
                    <code>{llmSmoke.configured_chat_model}</code>
                    <div className="metrics">
                      <span>{labelModelAvailability(llmSmoke.configured_chat_model_available)}</span>
                      <span>{labelModelLoadState(llmSmoke.configured_chat_model_loaded)}</span>
                    </div>
                    <button className="secondary-button" onClick={handleLoadChatModel} disabled={Boolean(busy)}>
                      Chat modell betoltese
                    </button>
                  </div>
                  <div className="model-status-card">
                    <strong>Embedding modell</strong>
                    <code>{llmSmoke.configured_embedding_model}</code>
                    <div className="metrics">
                      <span>{labelModelAvailability(llmSmoke.configured_embedding_model_available)}</span>
                      <span>{labelModelLoadState(llmSmoke.configured_embedding_model_loaded)}</span>
                    </div>
                    <button className="secondary-button" onClick={handleLoadEmbeddingModel} disabled={Boolean(busy)}>
                      Embedding modell betoltese
                    </button>
                  </div>
                </div>
                {llmSmoke.loaded_model_ids.length > 0 && (
                  <p className="field-hint">Betoltott instance-ek: {llmSmoke.loaded_model_ids.join(", ")}</p>
                )}
                {llmSmoke.error_message && <p className="error-text">{llmSmoke.error_message}</p>}
              </div>
            )}
            {canUseBatchScope && chunkIndexStatus && (
              <div className="model-status-panel">
                <div>
                  <strong>Szemantikus index allapot</strong>
                  <p>{labelChunkIndexScope(chunkIndexStatus)} | {chunkIndexStatus.embedding_model}</p>
                </div>
                <div className="metrics">
                  <span>{labelChunkIndexStatus(chunkIndexStatus)}</span>
                  <span>Indexelve: {chunkIndexStatus.indexed_chunk_count}/{chunkIndexStatus.current_chunk_count}</span>
                  <span>Hianyzik: {chunkIndexStatus.missing_chunk_count}</span>
                </div>
                <code>{chunkIndexStatus.collection_name}</code>
                {chunkIndexStatus.latest_run_id && (
                  <p className="field-hint">
                    Utolso indexeles: {chunkIndexStatus.latest_run_status ? labelRunStatus(chunkIndexStatus.latest_run_status) : "ismeretlen"}
                    {chunkIndexStatus.latest_run_finished_at ? ` | ${new Date(chunkIndexStatus.latest_run_finished_at).toLocaleString()}` : ""}
                  </p>
                )}
                {chunkIndexStatus.latest_run_input_count > 0 && (
                  <p className="field-hint">
                    Folyamat: {chunkIndexStatus.latest_run_output_count}/{chunkIndexStatus.latest_run_input_count} szovegresz
                    {chunkIndexStatus.latest_run_progress_percent !== null ? ` | ${chunkIndexStatus.latest_run_progress_percent}%` : ""}
                  </p>
                )}
                {indexJobIsRunning && (
                  <p className="field-hint">Indexeles folyamatban, az allapot automatikusan frissul.</p>
                )}
                {usesSemanticIndex && !chunkIndexStatus.is_ready && (
                  <p className="error-text">Szemantikus vagy hybrid futtatashoz elobb indexelni kell az aktualis forraskort.</p>
                )}
              </div>
            )}
            {canUseBatchScope && (
              <div className="source-action-row">
                <button
                  className="secondary-button"
                  onClick={handleIndexChunks}
                  disabled={!selectedCaseId || Boolean(busy) || indexJobIsRunning || (effectiveAnalysisSourceMode === "document" && !analysisDocumentId)}
                  title="Lokalis embedding es Qdrant index keszitese az aktualis forraskorhoz"
                >
                  {indexJobIsRunning ? "Indexeles folyamatban" : "Szovegreszek indexelese"}
                </button>
                <label className="checkbox-label">
                  <input type="checkbox" checked={forceReindex} onChange={(event) => setForceReindex(event.target.checked)} />
                  Ujraindexeles
                </label>
              </div>
            )}
            <div className="form-row">
              <label>
                Modul
                <select value={moduleKey} onChange={(event) => setModuleKey(event.target.value)}>
                  {modules.map((item) => <option key={item} value={item}>{labelModule(item)}</option>)}
                </select>
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
            </div>
            {showStructuredAnalysisFilters && (
              <div className="source-filter-panel">
                <div className="form-row">
                  <label>
                    Iratcsoport szuro
                    <select
                      value={analysisDocumentGroupCode}
                      onChange={(event) => {
                        setAnalysisDocumentGroupCode(event.target.value);
                        setAnalysisDocumentTypeCode("");
                      }}
                    >
                      <option value="">Minden iratcsoport</option>
                      {documentTaxonomy.map((group) => (
                        <option key={group.code} value={group.code}>
                          {group.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Irattipus szuro
                    <select
                      value={analysisDocumentTypeCode}
                      onChange={(event) => setAnalysisDocumentTypeCode(event.target.value)}
                      disabled={!analysisDocumentGroupCode}
                    >
                      <option value="">Minden irattipus</option>
                      {analysisTypeOptions.map((documentType) => (
                        <option key={documentType.code} value={documentType.code}>
                          {documentType.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <p className="field-hint">
                  A szurok csak a teljes ugy forraskorben ervenyesek. Ha nem jelolsz ki konkret iratot, a rendszer a valasztott csoport/tipus osszes aktualis irataban keres.
                </p>
                <div className="source-filter-list">
                  <div className="source-filter-list-heading">
                    <button
                      className="secondary-button"
                      onClick={() => setAnalysisDocumentIds([])}
                      disabled={analysisDocumentIds.length === 0 || Boolean(busy)}
                    >
                      Kijeloles torlese
                    </button>
                    <input
                      className="source-filter-search"
                      value={analysisDocumentSearch}
                      onChange={(event) => setAnalysisDocumentSearch(event.target.value)}
                      placeholder="Iratnev keresese"
                      disabled={analysisDocumentFilterOptions.length === 0}
                    />
                  </div>
                  {analysisDocumentFilterOptions.length === 0 && <p className="muted">Nincs a szuroknek megfelelo irat.</p>}
                  {analysisDocumentFilterOptions.length > 0 && filteredCaseAnalysisDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelo irat.</p>}
                  {filteredCaseAnalysisDocuments.map((document) => (
                    <label key={document.id} className="checkbox-label source-document-option">
                      <input
                        type="checkbox"
                        checked={analysisDocumentIds.includes(document.id)}
                        onChange={() => toggleAnalysisDocumentFilter(document.id)}
                      />
                      <span>
                        {document.original_filename}
                        <small>{labelDocumentTaxonomy(document)} | {labelProcessingStatus(document.processing_status)}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            {canUseBatchScope && effectiveAnalysisSourceMode === "document" && (
              <div className="source-filter-panel">
                <p className="field-hint">
                  Valassz ki egy iratot. Az oldaltartomany a kijeloles utan jelenik meg.
                </p>
                <div className="source-filter-list">
                  <div className="source-filter-list-heading">
                    <button
                      className="secondary-button"
                      onClick={() => setAnalysisDocumentId("")}
                      disabled={!analysisDocumentId || Boolean(busy)}
                    >
                      Kijeloles torlese
                    </button>
                    <input
                      className="source-filter-search"
                      value={analysisDocumentSearch}
                      onChange={(event) => setAnalysisDocumentSearch(event.target.value)}
                      placeholder="Iratnev keresese"
                      disabled={documents.length === 0}
                    />
                  </div>
                  {documents.length === 0 && <p className="muted">Nincs importalt irat.</p>}
                  {documents.length > 0 && filteredDocumentAnalysisDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelo irat.</p>}
                  {filteredDocumentAnalysisDocuments.map((document) => (
                    <label key={document.id} className="checkbox-label source-document-option">
                      <input
                        type="radio"
                        name="analysis-document-source"
                        checked={analysisDocumentId === document.id}
                        onChange={() => setAnalysisDocumentId(document.id)}
                      />
                      <span>
                        {document.original_filename}
                        <small>{labelDocumentTaxonomy(document)} | {labelProcessingStatus(document.processing_status)}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            {showAnalysisPageRange && (
              <div className="form-row">
                <label>
                  Oldaltol
                  <input
                    type="number"
                    min={1}
                    max={sourceScopeMaxPage}
                    value={analysisPageStart}
                    onChange={(event) => setAnalysisPageStart(event.target.value)}
                    onBlur={() => {
                      const value = clampNumberInput(analysisPageStart, 1, sourceScopeMaxPage, 1);
                      setAnalysisPageStart(String(value));
                      if (parsedAnalysisPageEnd !== null && value > parsedAnalysisPageEnd) {
                        setAnalysisPageEnd(String(value));
                      }
                    }}
                  />
                </label>
                <label>
                  Oldalig
                  <input
                    type="number"
                    min={1}
                    max={sourceScopeMaxPage}
                    value={analysisPageEnd}
                    onChange={(event) => setAnalysisPageEnd(event.target.value)}
                    onBlur={() => {
                      const value = clampNumberInput(analysisPageEnd, 1, sourceScopeMaxPage, sourceScopeMaxPage);
                      setAnalysisPageEnd(String(value));
                      if (parsedAnalysisPageStart !== null && parsedAnalysisPageStart > value) {
                        setAnalysisPageStart(String(value));
                      }
                    }}
                  />
                </label>
              </div>
            )}
            {canUseBatchScope && (
              <div className="form-row">
                <label>
                  Szovegresz plafon
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={maxChunks}
                    onChange={(event) => setMaxChunks(clampNumberInput(event.target.value, 1, 30, 20))}
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
            {showAnalysisPageRange && !analysisPageRangeValid && (
              <p className="error-text">Az oldaltartomany kotelezo, csak 1 es {sourceScopeMaxPage} kozotti egesz szam lehet, es az elso oldal nem lehet nagyobb az utolsonal.</p>
            )}
            {canUseBatchScope && (
              <>
                <div className="form-row">
                  <label>
                    Forraskereses
                    <select
                      value={retrievalStrategy}
                      onChange={(event) => setRetrievalStrategy(event.target.value as RetrievalStrategy)}
                    >
                      {retrievalStrategies.map((item) => <option key={item} value={item}>{labelRetrievalStrategy(item)}</option>)}
                    </select>
                    <span className="field-hint">A keresesi mod a fokusz alapjan valasztja ki a feldolgozando szovegreszeket. Szemantikus vagy hybrid modhoz elobb indexeld a szovegreszeket.</span>
                  </label>
                </div>
              </>
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
                  <label>
                    Ellentmondasjelolt plafon
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={contradictionCandidateLimit}
                      onChange={(event) => setContradictionCandidateLimit(clampNumberInput(event.target.value, 1, 10, 5))}
                    />
                  </label>
                </div>
                <div className="module-note">
                  Claim-par alapu modul: a rendszer a mar kinyert, forrasolt allitasok kozott valaszt ellenorizendo parokat. Az alapertelmezett allitaskor nem veszi figyelembe az elutasitott allitasokat. A fokusz kotelezo, es a claim szovegeben vagy forrasidezeteiben szur.
                </div>
              </>
            )}
            <label>
              Fokusz
              <textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                rows={3}
                placeholder={analysisFocusPlaceholder(moduleKey, isContradictionModule)}
              />
              <span className="field-hint">
                {isContradictionModule
                  ? "Kotelezo: ez szuri a mar kinyert allitasokat es forrasidezeteiket."
                  : "Kotelezo: ez valasztja ki a relevans szovegreszeket a megadott forraskorben."}
              </span>
            </label>
            {requiresFocusText && query.trim().length === 0 && (
              <p className="error-text">A feldolgozashoz adj meg fokuszt; enelkul nagy ugyeknel nem inditunk vak feldolgozast.</p>
            )}
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

          <section className="panel analysis-history-panel">
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

          <section className="panel detail-panel analysis-detail-panel">
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
                        {renderAnalysisSourceSummary(input.source_summary, input.payload_json)}
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
                        {renderAnalysisOutputSummary(output.output_summary)}
                        <code>{output.output_object_id}</code>
                      </article>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </section>

          </div>

          <div className="review-column">
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
                      {renderEntityMergeControls(item, true)}
                      {renderEventMergeControls(item, true)}
                      {renderMissingItemMergeControls(item, true)}
                      <div className="source-list">
                        {item.sources.map((source, index) => (
                          <details key={source.source_link_id ?? source.source_reference_id} className="source-detail" open={index === 0}>
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
                            {renderSourceDetachButton(item, source)}
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

          <section className="panel">
            <div className="section-heading">
              <h2>Kezi ellentmondasjelolt</h2>
              <GitMerge size={20} />
            </div>
            <div className="module-note">
              Ket forraservenyes, nem elutasitott allitasbol hoz letre ellenorzendo jeloltet. A rogzites nem bizonyitott ellentmondas, hanem emberi review-ra varo par.
            </div>
            {manualContradictionClaimOptions.length < 2 && (
              <p className="muted">Legalabb ket forraservenyes, nem elutasitott allitas kell a kezi jelolthez.</p>
            )}
            <div className="form-row">
              <label>
                1. allitas
                <select
                  value={manualContradiction.claim_id_a}
                  onChange={(event) => updateManualContradictionField("claim_id_a", event.target.value)}
                >
                  <option value="">Valassz allitast</option>
                  {manualContradictionClaimOptions.map((item) => (
                    <option key={item.object_id} value={item.object_id} disabled={item.object_id === manualContradiction.claim_id_b}>
                      {truncateText(item.title || item.body_text || item.object_id, 90)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                2. allitas
                <select
                  value={manualContradiction.claim_id_b}
                  onChange={(event) => updateManualContradictionField("claim_id_b", event.target.value)}
                >
                  <option value="">Valassz allitast</option>
                  {manualContradictionClaimOptions.map((item) => (
                    <option key={item.object_id} value={item.object_id} disabled={item.object_id === manualContradiction.claim_id_a}>
                      {truncateText(item.title || item.body_text || item.object_id, 90)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                Elteres tipusa
                <select
                  value={manualContradiction.contradiction_type}
                  onChange={(event) =>
                    updateManualContradictionField(
                      "contradiction_type",
                      event.target.value as ManualContradictionCandidatePayload["contradiction_type"]
                    )
                  }
                >
                  {(Object.keys(contradictionTypeLabels) as ManualContradictionCandidatePayload["contradiction_type"][]).map((type) => (
                    <option key={type} value={type}>
                      {contradictionTypeLabels[type]}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Sulyossagi jelzes
                <select
                  value={manualContradiction.severity_hint ?? "low"}
                  onChange={(event) =>
                    updateManualContradictionField(
                      "severity_hint",
                      event.target.value as NonNullable<ManualContradictionCandidatePayload["severity_hint"]>
                    )
                  }
                >
                  {(Object.keys(severityHintLabels) as NonNullable<ManualContradictionCandidatePayload["severity_hint"]>[]).map((severity) => (
                    <option key={severity} value={severity}>
                      {severityHintLabels[severity]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Ellenorzesi indoklas
              <textarea
                value={manualContradiction.description}
                onChange={(event) => updateManualContradictionField("description", event.target.value)}
                rows={3}
                placeholder="Roviden ird le, milyen konkret elteres miatt kell emberi ellenorzes."
              />
            </label>
            <div className="claim-preview-grid">
              {renderClaimPreview(selectedManualClaimA, "Valassz elso allitast az elonezethez.")}
              {renderClaimPreview(selectedManualClaimB, "Valassz masodik allitast az elonezethez.")}
            </div>
            <button
              onClick={handleCreateManualContradictionCandidate}
              disabled={
                Boolean(busy) ||
                !selectedCaseId ||
                manualContradictionClaimOptions.length < 2 ||
                !manualContradiction.claim_id_a ||
                !manualContradiction.claim_id_b ||
                manualContradiction.claim_id_a === manualContradiction.claim_id_b ||
                !manualContradiction.description.trim()
              }
            >
              <GitMerge size={18} /> Kezi jelolt letrehozasa
            </button>
          </section>

          <section className="panel detail-panel object-detail-panel">
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
                {renderEntityMergeControls(selectedReportItem)}
                {renderEventMergeControls(selectedReportItem)}
                {renderMissingItemMergeControls(selectedReportItem)}
                <details open>
                  <summary>Forrasok</summary>
                  <div className="detail-list">
                    {selectedReportItem.sources.map((source, index) => (
                      <article key={source.source_link_id ?? source.source_reference_id} className="text-sample">
                        <strong>{index + 1}. {source.document_filename ?? "irat"}</strong>
                        <span>{source.citation_label ?? "nincs hivatkozas"} | idezet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                        <pre>{source.quote_text}</pre>
                        {renderSourceDetachButton(selectedReportItem, source)}
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
              <h2>Levalasztott forrasok</h2>
              <Archive size={20} />
            </div>
            <div className="compact-list detached-source-list">
              {detachedSourceItems.length === 0 && <p className="muted">Nincs levalasztott forras.</p>}
              {detachedSourceItems.slice(0, 12).map((item) => (
                <article key={item.id} className="compact-item">
                  <strong>
                    {labelObjectType(item.detached_from_object_type)}: {item.object_title_snapshot}
                  </strong>
                  <span>
                    {labelDetachedHandlingStatus(item.handling_status)} | {new Date(item.detached_at).toLocaleString()}
                    {item.reattached_to_object_type && item.reattached_to_object_title_snapshot
                      ? ` | ${labelObjectType(item.reattached_to_object_type)}: ${item.reattached_to_object_title_snapshot}`
                      : ""}
                  </span>
                  <span>
                    Eredeti tipus: {item.object_subtype_snapshot ?? "ismeretlen"} | korabbi allapot:{" "}
                    {item.object_review_status_snapshot ? labelReviewStatus(item.object_review_status_snapshot) : "ismeretlen"}
                  </span>
                  {item.source_snapshot_json?.citation_label && <span>{item.source_snapshot_json.citation_label}</span>}
                  {item.source_snapshot_json?.quote_text && <blockquote>{item.source_snapshot_json.quote_text}</blockquote>}
                  {item.detach_comment && <p>{item.detach_comment}</p>}
                  {item.handling_status === "needs_review" && (
                    <>
                      <div className="source-action-row">
                        <select
                          value={detachedSourceTargets[item.id] ?? ""}
                          onChange={(event) => setDetachedSourceTargets((current) => ({ ...current, [item.id]: event.target.value }))}
                          aria-label="Levalasztott forras csatolasi celja"
                        >
                          <option value="">Csatolas celja</option>
                          {detachedSourceTargetOptions(item).map((target) => (
                            <option key={target.id} value={target.id}>
                              {target.label}
                            </option>
                          ))}
                        </select>
                        <button
                          className="secondary-button source-action"
                          onClick={() => handleAttachDetachedSource(item)}
                          disabled={Boolean(busy) || !detachedSourceTargets[item.id]}
                        >
                          Csatolas
                        </button>
                        <button className="secondary-button source-action" onClick={() => handleDiscardDetachedSource(item)} disabled={Boolean(busy)}>
                          Irrelevans
                        </button>
                      </div>
                      <details>
                        <summary>Uj objektum ebből a forrasbol</summary>
                        <div className="manual-entry-panel">
                          <textarea readOnly value={item.source_snapshot_json?.quote_text ?? ""} aria-label="Levalasztott forras readonly elonezet" />
                          <label>
                            Objektum tipus
                            <select
                              value={detachedManualTypes[item.id] ?? "claim"}
                              onChange={(event) => setDetachedManualTypes((current) => ({ ...current, [item.id]: event.target.value as ManualObjectType }))}
                            >
                              {(Object.keys(manualObjectTypeLabels) as ManualObjectType[]).map((type) => (
                                <option key={type} value={type}>
                                  {manualObjectTypeLabels[type]}
                                </option>
                              ))}
                            </select>
                          </label>
                          {renderManualObjectFieldsFor(
                            detachedManualTypes[item.id] ?? "claim",
                            detachedManualFields[item.id] ?? {},
                            (key, value) => updateDetachedManualField(item.id, key, value)
                          )}
                          <button onClick={() => handleCreateManualObjectFromDetachedSource(item)} disabled={Boolean(busy)}>
                            Uj objektum letrehozasa
                          </button>
                        </div>
                      </details>
                    </>
                  )}
                </article>
              ))}
            </div>
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

          </div>

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
    return "Add meg, milyen temaju allitasok kozott keressen ellentmondasjelolteket.";
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

function analysisSourceSummaryLabel(value: AnalysisSourceMode, selectedDocumentCount: number) {
  if (value === "case" && selectedDocumentCount > 0) {
    return `Teljes ugy, ${selectedDocumentCount} kijelolt irat`;
  }
  return labelAnalysisSourceMode(value);
}

function labelClaimReviewScope(value: ClaimReviewScope) {
  return claimReviewScopeLabels[value] ?? value;
}

function labelRetrievalStrategy(value: RetrievalStrategy) {
  return retrievalStrategyLabels[value] ?? value;
}

function labelModelAvailability(value: boolean | null) {
  if (value === null) return "nem ellenorizheto";
  return value ? "elerheto" : "nem latszik";
}

function labelModelLoadState(value: boolean | null) {
  if (value === null) return "nem ellenorizheto";
  return value ? "betoltve" : "nincs betoltve";
}

function labelChunkIndexStatus(value: ChunkIndexStatusResponse) {
  if (value.current_chunk_count === 0) return "nincs chunk";
  if (value.is_ready) return "index kesz";
  if (value.indexed_chunk_count > 0) return "reszben indexelve";
  return "indexeles szukseges";
}

function labelChunkIndexScope(value: ChunkIndexStatusResponse) {
  if (value.document_id) return "Kivalasztott irat";
  if (value.document_ids.length > 0) return `Teljes ugy, ${value.document_ids.length} kijelolt irat`;
  if (value.document_group_code && value.document_type_code) return "Teljes ugy, iratcsoport es irattipus szerint szurve";
  if (value.document_group_code) return "Teljes ugy, iratcsoport szerint szurve";
  return "Teljes ugy";
}

function labelDocumentTaxonomy(document: DocumentRead) {
  const groupLabel = document.document_group_label ?? document.document_group_code;
  const typeLabel = document.document_type_label ?? document.document_type_code;
  if (groupLabel === typeLabel) {
    return typeLabel;
  }
  return `${groupLabel} / ${typeLabel}`;
}

function filterDocumentsByName(documents: DocumentRead[], searchText: string) {
  const needle = searchText.trim().toLocaleLowerCase("hu-HU");
  if (!needle) return documents;
  return documents.filter((document) => document.original_filename.toLocaleLowerCase("hu-HU").includes(needle));
}

function clampNumberInput(value: string, min: number, max: number, fallback: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
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

function labelDetachedHandlingStatus(value: string) {
  const labels: Record<string, string> = {
    needs_review: "Ellenorzesre var",
    reattached: "Ujra csatolva",
    discarded: "Irrelevansnak jelolve"
  };
  return labels[value] ?? value;
}

function labelProcessingStatus(value: string) {
  const labels: Record<string, string> = {
    imported: "Importalva",
    pending: "Varakozik",
    processing: "Feldolgozas alatt",
    processed: "Feldolgozva",
    text_review_required: "Szoveg ellenorzesre var",
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
  return document.ocr_recommendation?.action === "recommended" || document.ocr_recommendation?.action === "optional";
}

function canCreateChunks(document: DocumentRead) {
  return document.processing_status === "text_review_required";
}

function labelOcrAction(document: DocumentRead) {
  if (document.ocr_recommendation?.action === "optional") {
    return "OCR futtatasa ellenorzeskent";
  }
  return "OCR inditasa";
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

function renderAnalysisSourceSummary(
  summary: AnalysisRunDetail["inputs"][number]["source_summary"],
  payload: Record<string, unknown> | null
) {
  if (!summary) return null;
  const pageLabel =
    summary.page_start && summary.page_end && summary.page_start !== summary.page_end
      ? `${summary.page_start}-${summary.page_end}. oldal`
      : summary.page_start
        ? `${summary.page_start}. oldal`
        : "oldal ismeretlen";
  return (
    <div className="analysis-readable-card">
      <strong>{summary.document_filename ?? "Ismeretlen irat"}</strong>
      <div className="source-meta">
        <span>{pageLabel}</span>
        {summary.chunk_index !== null && <span>{summary.chunk_index}. szovegresz</span>}
        {payload?.source_label !== undefined && payload.source_label !== null && (
          <span>{formatAnalysisSourceLabel(payload.source_label)}</span>
        )}
        {payload?.retrieval_match_type !== undefined && payload.retrieval_match_type !== null && (
          <span>{labelRetrievalMatchType(payload.retrieval_match_type)}</span>
        )}
        {payload?.retrieval_score !== undefined && payload.retrieval_score !== null && (
          <span>relevancia {formatScore(payload.retrieval_score)}</span>
        )}
        {payload?.batch_index !== undefined && payload.batch_index !== null && payload?.batch_count !== undefined && payload.batch_count !== null && (
          <span>batch {String(payload.batch_index)} / {String(payload.batch_count)}</span>
        )}
        {(summary.char_start !== null || summary.char_end !== null) && (
          <span>karakter {formatRange(summary.char_start, summary.char_end)}</span>
        )}
      </div>
      {summary.text_preview && <p className="analysis-source-preview">{summary.text_preview}</p>}
    </div>
  );
}

function renderAnalysisOutputSummary(summary: AnalysisRunDetail["outputs"][number]["output_summary"]) {
  if (!summary) return null;
  return (
    <div className="analysis-readable-card">
      {summary.title && <strong>{summary.title}</strong>}
      <div className="source-meta">
        {summary.review_status && <span>{labelReviewStatus(summary.review_status)}</span>}
        {summary.source_validation_status && <span>{labelSourceValidationStatus(summary.source_validation_status)}</span>}
        {summary.source_count !== null && summary.source_count !== undefined && <span>{summary.source_count} forras</span>}
      </div>
      {summary.body_text && <p className="analysis-source-preview">{summary.body_text}</p>}
    </div>
  );
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

function labelRetrievalMatchType(value: unknown) {
  const labels: Record<string, string> = {
    keyword: "kulcsszavas talalat",
    semantic: "szemantikus talalat",
    hybrid: "hybrid talalat"
  };
  return labels[String(value)] ?? String(value);
}

function formatAnalysisSourceLabel(value: unknown) {
  const rawValue = String(value);
  const match = rawValue.match(/^chunk_(\d+)$/);
  if (match) {
    return `elemzesi forras: ${match[1]}`;
  }
  return `elemzesi forras: ${rawValue}`;
}

function formatScore(value: unknown) {
  const numberValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numberValue)) return String(value);
  return numberValue.toFixed(3);
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
