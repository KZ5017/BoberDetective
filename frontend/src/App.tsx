import { useEffect, useMemo, useRef, useState } from "react";
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
  ClaimRead,
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
  ResearchFindingRead,
  ReviewReport,
  ReviewReportFilterValues,
  ReviewReportItem,
  ReviewReportSource,
  RetrievalStrategy,
  attachDetachedSourceItem,
  bulkDeleteResearchFindings,
  convertResearchFinding,
  createCase,
  createDocumentChunks,
  createExport,
  createManualObject,
  createManualContradictionCandidate,
  createManualObjectFromDetachedSource,
  detachObjectSource,
  discardDocument,
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
  listClaims,
  listDocuments,
  listEntities,
  listEvents,
  listExports,
  listMissingItemCandidates,
  listResearchFindings,
  loadChatModel,
  loadEmbeddingModel,
  mergeClaim,
  mergeEvent,
  mergeEntity,
  mergeMissingItemCandidate,
  moveObjectSource,
  reviewObject,
  restoreResearchFinding,
  runAnalysis,
  runDocumentOcr,
  setAsideResearchFinding,
  startChunkIndexJob,
  updateDocumentLifecycle,
  updateDocumentTaxonomy
} from "./api";

const modules = ["search_findings", "detect_contradiction_candidates"];

const objectTypes = [
  "",
  "claim",
  "event",
  "entity",
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
  "document-exclude": "Irat kizárása",
  "document-archive": "Irat archiválása",
  "document-restore": "Irat visszaállítása",
  "document-discard": "Irat elvetése",
  "document-chunks": "Szovegreszek letrehozasa",
  "document-ocr": "OCR futtatasa",
  "run-detail": "Elemzesi futas reszleteinek betoltese",
  exports: "Export elozmenyek betoltese",
  import: "Irat importalasa",
  analysis: "Elemzes futtatasa",
  report: "Attekintesi jelentés betoltese",
  "export-json": "JSON export keszitese",
  "export-html": "HTML export keszitese",
  "review-verify": "Ellenőrzés rögzítése",
  "review-reject": "Ellenőrzés rögzítése",
  "review-mark_needs_review": "Ellenőrzés rögzítése",
  "review-comment": "Megjegyzes rogzítese",
  "entity-merge": "Entitások összevonása",
  "event-merge": "Események összevonása",
  "missing-item-merge": "Hiányzó iratjelöltek összevonása",
  "source-detach": "Forráshivatkozás leválasztása",
  "source-move": "Forráshivatkozás áthelyezése",
  "detached-source-attach": "Leválasztott forráshivatkozás csatolása",
  "detached-source-discard": "Leválasztott forráshivatkozás irrelevánsnak jelölése",
  "manual-object": "Kézi találat rögzítése",
  "manual-contradiction": "Kézi ellentmondásjelölt rögzítése",
  "finding-convert": "Kutatási találat átalakítása",
  "chunk-index": "Chunk indexeles",
  "llm-smoke": "LLM modell allapot",
  "chat-load": "Chat modell betoltese",
  "embedding-load": "Embedding modell betoltese"
};

const moduleLabels: Record<string, string> = {
  search_findings: "Kutatási találatok keresése",
  detect_contradiction_candidates: "Ellentmondásjelöltek keresése",
  retired_analysis_module: "Kivezetett elemzési futás",
  manual_entry: "Kézi rögzítés"
};

const analysisSourceModeLabels: Record<AnalysisSourceMode, string> = {
  document: "Kivalasztott irat",
  case: "Teljes ugy"
};

const claimReviewScopeLabels: Record<ClaimReviewScope, string> = {
  reviewable: "Ellenorizheto allitasok",
  verified: "Csak ellenorzott",
  needs_review: "Ellenőrzésre várók",
  all_source_valid: "Minden forráshivatkozás érvényes"
};

const retrievalStrategyLabels: Record<RetrievalStrategy, string> = {
  keyword: "Kulcsszavas",
  semantic: "Szemantikus",
  hybrid: "Hybrid"
};

const objectTypeLabels: Record<string, string> = {
  claim: "Állítás",
  event: "Esemény",
  entity: "Entitás",
  contradiction_candidate: "Ellentmondásjelölt",
  missing_item_candidate: "Hiányzó iratjelölt",
  export: "Export"
};

const manualObjectTypeLabels: Record<ManualObjectType, string> = {
  claim: "Állítás",
  entity: "Entitás",
  event: "Esemény",
  missing_item_candidate: "Hiányzó iratjelölt"
};

const researchFindingTypeLabels: Record<string, string> = {
  claim: "Állítás jellegű",
  event: "Esemény jellegű",
  entity: "Entitás jellegű",
  document_reference: "Iratra utaló",
  other: "Egyéb találat"
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
  needs_review: "Ellenőrzésre vár",
  verified: "Ellenőrizve",
  rejected: "Elutasítva",
  corrected: "Javítva",
  new: "Új"
};

const sourceValidationLabels: Record<string, string> = {
  source_valid: "Forráshivatkozás érvényes",
  source_invalid: "Nincs érvényes forráshivatkozás",
  pending_source_validation: "Forráshivatkozás ellenőrzésre vár"
};

const llmSupportLabels: Record<string, string> = {
  confirmed: "LLM megerősített",
  unconfirmed: "LLM nem megerősített"
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
  verify: "Ellenőrzés",
  reject: "Elutasitas",
  mark_needs_review: "Ellenőrzésre jelölés",
  comment: "Megjegyzes",
  correct: "Javitas",
  attach_source: "Forráshivatkozás csatolása",
  detach_source: "Forráshivatkozás leválasztása"
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
  const [claims, setClaims] = useState<ClaimRead[]>([]);
  const [events, setEvents] = useState<EventRead[]>([]);
  const [missingItemCandidates, setMissingItemCandidates] = useState<MissingItemCandidateRead[]>([]);
  const [researchFindings, setResearchFindings] = useState<ResearchFindingRead[]>([]);
  const [detachedSourceItems, setDetachedSourceItems] = useState<DetachedSourceItemRead[]>([]);
  const [manualContradictionClaims, setManualContradictionClaims] = useState<ReviewReportItem[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentRead | null>(null);
  const [taxonomyEditGroupCode, setTaxonomyEditGroupCode] = useState("uncategorized");
  const [taxonomyEditTypeCode, setTaxonomyEditTypeCode] = useState("uncategorized");
  const [taxonomyEditComment, setTaxonomyEditComment] = useState("");
  const [documentLifecycleReason, setDocumentLifecycleReason] = useState("");
  const [documentPages, setDocumentPages] = useState<DocumentPageRead[]>([]);
  const [documentChunks, setDocumentChunks] = useState<DocumentChunkRead[]>([]);
  const [analysisRunDetail, setAnalysisRunDetail] = useState<AnalysisRunDetail | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [caseName, setCaseName] = useState("");
  const [caseReference, setCaseReference] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const [documentTaxonomy, setDocumentTaxonomy] = useState<DocumentTaxonomyGroupRead[]>([]);
  const [documentGroupCode, setDocumentGroupCode] = useState("uncategorized");
  const [documentTypeCode, setDocumentTypeCode] = useState("uncategorized");
  const [documentListSearch, setDocumentListSearch] = useState("");
  const [moduleKey, setModuleKey] = useState("search_findings");
  const [query, setQuery] = useState("");
  const [analysisSourceMode, setAnalysisSourceMode] = useState<AnalysisSourceMode>("case");
  const [analysisDocumentId, setAnalysisDocumentId] = useState("");
  const [analysisDocumentGroupCode, setAnalysisDocumentGroupCode] = useState("");
  const [analysisDocumentTypeCode, setAnalysisDocumentTypeCode] = useState("");
  const [analysisDocumentIds, setAnalysisDocumentIds] = useState<string[]>([]);
  const [analysisDocumentSearch, setAnalysisDocumentSearch] = useState("");
  const [analysisPageStart, setAnalysisPageStart] = useState("");
  const [analysisPageEnd, setAnalysisPageEnd] = useState("");
  const [maxChunks, setMaxChunks] = useState(30);
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
  const [reportSearch, setReportSearch] = useState("");
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [selectedReportItem, setSelectedReportItem] = useState<ReviewReportItem | null>(null);
  const objectDetailPanelRef = useRef<HTMLElement | null>(null);
  const researchFindingsPanelRef = useRef<HTMLElement | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [lastExport, setLastExport] = useState<ExportDetail | null>(null);
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});
  const [mergeTargets, setMergeTargets] = useState<Record<string, string>>({});
  const [sourceMoveTargets, setSourceMoveTargets] = useState<Record<string, string>>({});
  const [detachedSourceTargets, setDetachedSourceTargets] = useState<Record<string, string>>({});
  const [detachedManualTypes, setDetachedManualTypes] = useState<Record<string, ManualObjectType>>({});
  const [detachedManualFields, setDetachedManualFields] = useState<Record<string, Record<string, string>>>({});
  const [researchFindingManualTypes, setResearchFindingManualTypes] = useState<Record<string, ManualObjectType>>({});
  const [researchFindingManualFields, setResearchFindingManualFields] = useState<Record<string, Record<string, string>>>({});
  const [showSetAsideResearchFindings, setShowSetAsideResearchFindings] = useState(false);
  const [researchFindingsMarkedForDeletion, setResearchFindingsMarkedForDeletion] = useState<string[]>([]);
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
  const manualSourcePanelRef = useRef<HTMLDetailsElement | null>(null);
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
  const activeDocuments = useMemo(
    () => documents.filter((document) => document.lifecycle_status === "active"),
    [documents]
  );
  const selectedAnalysisDocument = useMemo(
    () => activeDocuments.find((item) => item.id === analysisDocumentId) ?? null,
    [activeDocuments, analysisDocumentId]
  );
  const selectedDocumentIsActive = selectedDocument?.lifecycle_status === "active";
  const canAttemptSelectedDocumentDiscard = Boolean(selectedDocumentIsActive && documentChunks.length === 0);
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
      activeDocuments.filter((document) => {
        if (analysisDocumentGroupCode && document.document_group_code !== analysisDocumentGroupCode) return false;
        if (analysisDocumentTypeCode && document.document_type_code !== analysisDocumentTypeCode) return false;
        return true;
      }),
    [activeDocuments, analysisDocumentGroupCode, analysisDocumentTypeCode]
  );
  const filteredCaseAnalysisDocuments = useMemo(
    () => filterDocumentsByName(analysisDocumentFilterOptions, analysisDocumentSearch),
    [analysisDocumentFilterOptions, analysisDocumentSearch]
  );
  const filteredDocumentAnalysisDocuments = useMemo(
    () => filterDocumentsByName(activeDocuments, analysisDocumentSearch),
    [activeDocuments, analysisDocumentSearch]
  );
  const manualContradictionClaimOptions = useMemo(
    () =>
      manualContradictionClaims.filter(
        (item) => item.source_validation_status === "source_valid" && item.review_status !== "rejected" && reportItemSourcesAreActive(item)
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
  const canUseBatchScope = moduleKey === "search_findings";
  const isContradictionModule = moduleKey === "detect_contradiction_candidates";
  const effectiveAnalysisSourceMode: AnalysisSourceMode = canUseBatchScope ? analysisSourceMode : "case";
  const showStructuredAnalysisFilters = canUseBatchScope && effectiveAnalysisSourceMode === "case";
  const showAnalysisPageRange = canUseBatchScope && effectiveAnalysisSourceMode === "document" && Boolean(analysisDocumentId);
  const sourceScopeMaxPage = useMemo(() => {
    if (effectiveAnalysisSourceMode === "document") {
      return Math.max(1, selectedAnalysisDocument?.page_count ?? 1);
    }
    return Math.max(1, ...activeDocuments.map((item) => item.page_count ?? 0));
  }, [activeDocuments, effectiveAnalysisSourceMode, selectedAnalysisDocument]);
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
  const visibleReportItems = useMemo(() => {
    if (!report) return [];
    const queryText = reportSearch.trim().toLocaleLowerCase("hu-HU");
    if (!queryText) return report.items;
    return report.items.filter((item) => reportItemMatchesSearch(item, queryText));
  }, [report, reportSearch]);
  const setAsideResearchFindingCount = useMemo(
    () => researchFindings.filter((finding) => finding.conversion_status === "ignored").length,
    [researchFindings]
  );
  const visibleResearchFindings = useMemo(
    () =>
      researchFindings.filter(
        (finding) => showSetAsideResearchFindings || finding.conversion_status !== "ignored"
      ),
    [researchFindings, showSetAsideResearchFindings]
  );
  const markedResearchFindingCount = researchFindingsMarkedForDeletion.length;

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
      setClaims([]);
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
    if (analysisDocumentId && !activeDocuments.some((item) => item.id === analysisDocumentId)) {
      setAnalysisDocumentId("");
    }
  }, [activeDocuments, analysisDocumentId]);

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
    const deletableIds = new Set(
      researchFindings
        .filter((finding) => finding.conversion_status !== "converted")
        .map((finding) => finding.id)
    );
    setResearchFindingsMarkedForDeletion((current) => current.filter((findingId) => deletableIds.has(findingId)));
  }, [researchFindings]);

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
      const [
        documentsResponse,
        runsResponse,
        exportsResponse,
        reportResponse,
        manualClaimsResponse,
        claimsResponse,
        entitiesResponse,
        eventsResponse,
        missingItemsResponse,
        researchFindingsResponse,
        detachedSourcesResponse
      ] = await Promise.all([
        listDocuments(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listExports(selectedCaseId),
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listResearchFindings(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setDocuments(documentsResponse.data);
      setAnalysisRuns(runsResponse.data);
      setExports(exportsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setResearchFindings(researchFindingsResponse.data);
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
      setDocumentLifecycleReason("");
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

  async function refreshDocumentsAfterLifecycleChange(documentId: string, fallback?: DocumentRead | null) {
    if (!selectedCaseId) return;
    const documentsResponse = await listDocuments(selectedCaseId);
    const refreshedDocument = documentsResponse.data.find((item) => item.id === documentId) ?? fallback ?? null;
    setDocuments(documentsResponse.data);
    setSelectedDocument(refreshedDocument);
    if (refreshedDocument) {
      setTaxonomyEditGroupCode(refreshedDocument.document_group_code);
      setTaxonomyEditTypeCode(refreshedDocument.document_type_code);
      if (refreshedDocument.lifecycle_status !== "active") {
        setManualSource(null);
      }
    } else {
      setDocumentPages([]);
      setDocumentChunks([]);
      setManualSource(null);
    }
    if (!documentsResponse.data.some((item) => item.id === analysisDocumentId && item.lifecycle_status === "active")) {
      setAnalysisDocumentId("");
      setAnalysisDocumentIds([]);
    }
    setMergeTargets({});
    setSourceMoveTargets({});
    setDetachedSourceTargets({});
    setManualContradiction((current) => ({ ...current, claim_id_a: "", claim_id_b: "" }));
    await refreshReviewStateAfterSourceChange(selectedReportItem?.object_id ?? null);
  }

  async function handleDocumentLifecycleAction(action: "exclude" | "archive" | "restore") {
    if (!selectedCaseId || !selectedDocument) return;
    await perform(`document-${action}`, async () => {
      const response = await updateDocumentLifecycle(selectedCaseId, selectedDocument.id, action, documentLifecycleReason.trim() || undefined);
      await refreshDocumentsAfterLifecycleChange(selectedDocument.id, response);
      setDocumentLifecycleReason("");
      setNotice(`Irat állapota frissítve: ${labelDocumentLifecycleStatus(response.lifecycle_status)}.`);
      setLastActionSummary(`${response.original_filename}: ${labelDocumentLifecycleStatus(response.lifecycle_status)}`);
    });
  }

  async function handleDocumentDiscard() {
    if (!selectedCaseId || !selectedDocument) return;
    if (!canAttemptSelectedDocumentDiscard) {
      setError("Az irat jelenlegi állapotában nem vethető el végleges törléssel.");
      return;
    }
    const confirmed = window.confirm("Biztosan végleg elveted ezt az iratot? Ez csak korai, elemzési alapként még nem használt iratnál engedélyezett.");
    if (!confirmed) return;
    const documentId = selectedDocument.id;
    const filename = selectedDocument.original_filename;
    await perform("document-discard", async () => {
      await discardDocument(selectedCaseId, documentId, documentLifecycleReason.trim() || undefined);
      await refreshDocumentsAfterLifecycleChange(documentId, null);
      setDocumentLifecycleReason("");
      setNotice("Irat elvetve és törölve.");
      setLastActionSummary(`${filename}: elvetve`);
    });
  }

  function handleManualSourceFromChunk(chunk: DocumentChunkRead, textarea: HTMLTextAreaElement) {
    if (!selectedDocument) return;
    if (selectedDocument.lifecycle_status !== "active") {
      setError("Kézi forráshivatkozás csak aktív iratból hozható létre.");
      return;
    }
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const quote = chunk.chunk_text.slice(start, end).trim();
    if (quote.length === 0 || end <= start) {
      setError("Jelölj ki egy konkrét forráshivatkozási idézetet a szövegrészből.");
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
    setNotice("Forráshivatkozás kijelölve kézi rögzítéshez.");
    window.setTimeout(() => {
      manualSourcePanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
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
      if (importFileInputRef.current) {
        importFileInputRef.current.value = "";
      }
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
      const [
        reportResponse,
        manualClaimsResponse,
        runsResponse,
        claimsResponse,
        entitiesResponse,
        eventsResponse,
        missingItemsResponse,
        researchFindingsResponse,
        detachedSourcesResponse
      ] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listResearchFindings(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setResearchFindings(researchFindingsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      if (response.module_key === "search_findings") {
        setTimeout(() => {
          researchFindingsPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
      }
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
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
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
      setNotice("Ellenőrzés rögzítve, jelentés frissítve.");
      setLastActionSummary(`${labelObjectType(itemObjectType)}: ${labelAction(actionType)}`);
    });
  }

  function reviewActionDisabled(item: ReviewReportItem, actionType: "verify" | "reject" | "mark_needs_review" | "comment") {
    if (busy) return true;
    if (actionType === "verify") return item.review_status === "verified";
    if (actionType === "reject") return item.review_status === "rejected";
    if (actionType === "mark_needs_review") return item.review_status === "needs_review";
    return false;
  }

  async function handleClaimMerge(sourceItem: ReviewReportItem) {
    if (!selectedCaseId || sourceItem.object_type !== "claim") return;
    const targetClaimId = mergeTargets[sourceItem.object_id];
    if (!targetClaimId) {
      setError("Válassz célállítást az összevonáshoz.");
      return;
    }
    const comment = reviewComments[sourceItem.object_id] ?? "";
    await perform("claim-merge", async () => {
      await mergeClaim(selectedCaseId, sourceItem.object_id, targetClaimId, comment);
      setReviewComments((current) => ({ ...current, [sourceItem.object_id]: "" }));
      setMergeTargets((current) => ({ ...current, [sourceItem.object_id]: "" }));
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetClaimId) ?? null);
      setNotice("Állítások összevonva, forráshivatkozások átkapcsolva.");
      setLastActionSummary(`Állítás összevonva: ${sourceItem.title}`);
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
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetEntityId) ?? null);
      setNotice("Entitások összevonva, forráshivatkozások átkapcsolva.");
      setLastActionSummary(`Entitás összevonva: ${sourceItem.title}`);
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
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetEventId) ?? null);
      setNotice("Események összevonva, forráshivatkozások átkapcsolva.");
      setLastActionSummary(`Esemény összevonva: ${sourceItem.title}`);
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
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === targetCandidateId) ?? null);
      setNotice("Hiányzó iratjelöltek összevonva, forráshivatkozások átkapcsolva.");
      setLastActionSummary(`Hiányzó iratjelölt összevonva: ${sourceItem.title}`);
    });
  }

  function canDetachSource(item: ReviewReportItem, source: ReviewReportSource) {
    return (
      Boolean(source.source_link_id) &&
      reportSourceIsActive(source) &&
      (item.object_type === "claim" || item.object_type === "entity" || item.object_type === "event" || item.object_type === "missing_item_candidate")
    );
  }

  async function handleDetachSource(item: ReviewReportItem, source: ReviewReportSource) {
    if (!selectedCaseId || !source.source_link_id || !canDetachSource(item, source)) return;
    const comment = reviewComments[item.object_id] ?? "";
    await perform("source-detach", async () => {
      await detachObjectSource(selectedCaseId, item.object_type, item.object_id, source.source_link_id!, comment);
      setReviewComments((current) => ({ ...current, [item.object_id]: "" }));
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((reportItem) => reportItem.object_id === item.object_id) ?? null);
      setNotice("Forráshivatkozás leválasztva, jelentés frissítve.");
      setLastActionSummary(`${labelObjectType(item.object_type)}: forráshivatkozás leválasztva.`);
    });
  }

  function sourceMoveKey(item: ReviewReportItem, source: ReviewReportSource) {
    return `${item.object_id}:${source.source_link_id ?? source.source_reference_id}`;
  }

  function sourceMoveTargetOptions(item: ReviewReportItem) {
    const sourceTargetLabel = (title: string, reviewStatus: string) =>
      `${title} (${labelReviewStatus(reviewStatus)}${reviewStatus === "corrected" ? ", újranyitás" : ""})`;
    if (item.object_type === "claim") {
      return claims
        .filter((claim) => claim.id !== item.object_id)
        .map((claim) => ({ id: claim.id, label: sourceTargetLabel(claim.claim_title, claim.review_status) }));
    }
    if (item.object_type === "entity") {
      return entities
        .filter((entity) => entity.id !== item.object_id)
        .map((entity) => ({ id: entity.id, label: sourceTargetLabel(entity.canonical_name, entity.review_status) }));
    }
    if (item.object_type === "event") {
      return events
        .filter((event) => event.id !== item.object_id)
        .map((event) => ({ id: event.id, label: sourceTargetLabel(event.event_title, event.review_status) }));
    }
    if (item.object_type === "missing_item_candidate") {
      return missingItemCandidates
        .filter((candidate) => candidate.id !== item.object_id)
        .map((candidate) => ({ id: candidate.id, label: sourceTargetLabel(candidate.referenced_item_text, candidate.review_status) }));
    }
    return [];
  }

  function detachedSourceTargetOptions(item: DetachedSourceItemRead) {
    const sourceTargetLabel = (title: string, reviewStatus: string) =>
      `${title} (${labelReviewStatus(reviewStatus)}${reviewStatus === "corrected" ? ", újranyitás" : ""})`;
    if (item.detached_from_object_type === "claim") {
      return claims.map((claim) => ({ id: claim.id, label: sourceTargetLabel(claim.claim_title, claim.review_status) }));
    }
    if (item.detached_from_object_type === "entity") {
      return entities.map((entity) => ({ id: entity.id, label: sourceTargetLabel(entity.canonical_name, entity.review_status) }));
    }
    if (item.detached_from_object_type === "event") {
      return events.map((event) => ({ id: event.id, label: sourceTargetLabel(event.event_title, event.review_status) }));
    }
    if (item.detached_from_object_type === "missing_item_candidate") {
      return missingItemCandidates.map((candidate) => ({ id: candidate.id, label: sourceTargetLabel(candidate.referenced_item_text, candidate.review_status) }));
    }
    return [];
  }

  async function refreshReviewStateAfterSourceChange(selectedObjectId?: string | null) {
    if (!selectedCaseId) return;
    const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
      getReviewReport(selectedCaseId, reportFilters),
      getManualContradictionClaims(selectedCaseId),
      listClaims(selectedCaseId),
      listEntities(selectedCaseId),
      listEvents(selectedCaseId),
      listMissingItemCandidates(selectedCaseId),
      listDetachedSourceItems(selectedCaseId)
    ]);
    setReport(reportResponse);
    setClaims(claimsResponse.data);
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
      setError("Válassz céltalálatot a forráshivatkozás áthelyezéséhez.");
      return;
    }
    const comment = reviewComments[item.object_id] ?? "";
    await perform("source-move", async () => {
      await moveObjectSource(selectedCaseId, item.object_type, item.object_id, source.source_link_id!, targetObjectId, comment);
      setReviewComments((current) => ({ ...current, [item.object_id]: "" }));
      setSourceMoveTargets((current) => ({ ...current, [key]: "" }));
      await refreshReviewStateAfterSourceChange(targetObjectId);
      setNotice("Forráshivatkozás áthelyezve, jelentés frissítve.");
      setLastActionSummary(`${labelObjectType(item.object_type)}: forráshivatkozás áthelyezve.`);
    });
  }

  async function handleAttachDetachedSource(item: DetachedSourceItemRead) {
    if (!selectedCaseId) return;
    const targetObjectId = detachedSourceTargets[item.id];
    if (!targetObjectId) {
      setError("Válassz céltalálatot a leválasztott forráshivatkozás csatolásához.");
      return;
    }
    await perform("detached-source-attach", async () => {
      await attachDetachedSourceItem(selectedCaseId, item.id, targetObjectId, item.detach_comment ?? undefined);
      setDetachedSourceTargets((current) => ({ ...current, [item.id]: "" }));
      await refreshReviewStateAfterSourceChange(targetObjectId);
      setNotice("Leválasztott forráshivatkozás csatolva.");
      setLastActionSummary(`${labelObjectType(item.detached_from_object_type)}: leválasztott forráshivatkozás csatolva.`);
    });
  }

  async function handleDiscardDetachedSource(item: DetachedSourceItemRead) {
    if (!selectedCaseId) return;
    await perform("detached-source-discard", async () => {
      await discardDetachedSourceItem(selectedCaseId, item.id, item.detach_comment ?? undefined);
      await refreshReviewStateAfterSourceChange(null);
      setNotice("Leválasztott forráshivatkozás irrelevánsnak jelölve.");
      setLastActionSummary("Leválasztott forráshivatkozás irrelevánsnak jelölve.");
    });
  }

  function updateManualField(key: string, value: string) {
    setManualFields((current) => ({ ...current, [key]: value }));
  }

  function manualObjectFieldsPayload(type: ManualObjectType, fields: Record<string, string>): ManualObjectFromSourcePayload {
    return {
      object_type: type,
      claim_type: fields.claim_type || "document_fact",
      claim_title: fields.claim_title || null,
      claim_text: fields.claim_text || null,
      entity_type: fields.entity_type || (type === "entity" ? "person" : null),
      canonical_name: fields.canonical_name || null,
      normalized_value: fields.normalized_value || null,
      description: fields.description || null,
      event_type: fields.event_type || (type === "event" ? "statement" : null),
      event_title: fields.event_title || null,
      event_description: fields.event_description || null,
      event_time_start: eventTimeStartPayload(fields),
      time_precision: fields.time_precision || "unknown",
      missing_item_type: fields.missing_item_type || (type === "missing_item_candidate" ? "document_reference" : null),
      referenced_item_text: fields.referenced_item_text || null
    };
  }

  function eventTimeStartPayload(fields: Record<string, string>): string | null {
    const precision = fields.time_precision || "unknown";
    if (precision === "unknown") return null;
    const year = Number(fields.event_year);
    if (!Number.isInteger(year) || year < 1 || year > 9999) return null;
    const month = precision === "year" ? 1 : Number(fields.event_month);
    const day = precision === "year" || precision === "month" ? 1 : Number(fields.event_day);
    const hour = precision === "hour" || precision === "minute" ? Number(fields.event_hour) : 0;
    const minute = precision === "minute" ? Number(fields.event_minute) : 0;
    if (!Number.isInteger(month) || month < 1 || month > 12) return null;
    if (!Number.isInteger(day) || day < 1 || day > 31) return null;
    if (!Number.isInteger(hour) || hour < 0 || hour > 23) return null;
    if (!Number.isInteger(minute) || minute < 0 || minute > 59) return null;
    return new Date(year, month - 1, day, hour, minute, 0, 0).toISOString();
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
      const [reportResponse, manualClaimsResponse, runsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === response.object_id) ?? null);
      setNotice("Forráshivatkozásból rögzített találat létrehozva.");
      setLastActionSummary(`${labelObjectType(response.object_type)}: forráshivatkozásból rögzítve.`);
    });
  }

  function updateDetachedManualField(itemId: string, key: string, value: string) {
    setDetachedManualFields((current) => ({ ...current, [itemId]: { ...(current[itemId] ?? {}), [key]: value } }));
  }

  function updateResearchFindingManualField(findingId: string, key: string, value: string) {
    setResearchFindingManualFields((current) => ({ ...current, [findingId]: { ...(current[findingId] ?? {}), [key]: value } }));
  }

  function fillResearchFindingManualFields(finding: ResearchFindingRead, type: ManualObjectType) {
    const descriptionParts = [
      finding.finding_text,
      `Relevancia: ${finding.relevance_reason}`,
      finding.suggested_type_reason ? `Típusjavaslat oka: ${finding.suggested_type_reason}` : ""
    ].filter((part) => part.trim() !== "");
    const description = descriptionParts.join("\n");
    setResearchFindingManualFields((current) => {
      const fields = { ...(current[finding.id] ?? {}) };
      if (type === "claim") {
        fields.claim_title = finding.title;
        fields.claim_text = description;
      } else if (type === "entity") {
        fields.canonical_name = finding.title;
        fields.description = description;
      } else if (type === "event") {
        fields.event_title = finding.title;
        fields.event_description = description;
      } else {
        fields.referenced_item_text = finding.title;
        fields.description = description;
      }
      return { ...current, [finding.id]: fields };
    });
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
      setNotice("Leválasztott forráshivatkozásból új találat létrehozva.");
      setLastActionSummary(`${labelObjectType(response.object_type)}: leválasztott forráshivatkozásból rögzítve.`);
    });
  }

  async function handleConvertResearchFinding(finding: ResearchFindingRead) {
    if (!selectedCaseId || finding.conversion_status === "converted") return;
    const type = researchFindingManualTypes[finding.id] ?? suggestedResearchFindingManualType(finding);
    const fields = researchFindingManualFields[finding.id] ?? {};
    await perform("finding-convert", async () => {
      const response = await convertResearchFinding(selectedCaseId, finding.id, manualObjectFieldsPayload(type, fields));
      setResearchFindingManualFields((current) => ({ ...current, [finding.id]: {} }));
      setResearchFindingManualTypes((current) => ({ ...current, [finding.id]: suggestedResearchFindingManualType(finding) }));
      const [findingsResponse, reportResponse, manualClaimsResponse, runsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse] = await Promise.all([
        listResearchFindings(selectedCaseId),
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId)
      ]);
      setResearchFindings(findingsResponse.data);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === response.object_id) ?? null);
      setNotice("Kutatási találat strukturált objektummá alakítva.");
      setLastActionSummary(`${labelObjectType(response.object_type)}: kutatási találatból létrehozva.`);
    });
  }

  async function handleSetAsideResearchFinding(finding: ResearchFindingRead) {
    if (!selectedCaseId || finding.conversion_status === "converted") return;
    await perform("finding-set-aside", async () => {
      const response = await setAsideResearchFinding(selectedCaseId, finding.id);
      setResearchFindings((current) => current.map((item) => (item.id === finding.id ? response.finding : item)));
      setNotice("Kutatási találat félretéve.");
      setLastActionSummary(`${response.finding.title}: félretéve.`);
    });
  }

  async function handleRestoreResearchFinding(finding: ResearchFindingRead) {
    if (!selectedCaseId || finding.conversion_status === "converted") return;
    await perform("finding-restore", async () => {
      const response = await restoreResearchFinding(selectedCaseId, finding.id);
      setResearchFindings((current) => current.map((item) => (item.id === finding.id ? response.finding : item)));
      setNotice("Kutatási találat visszakerült az aktív listába.");
      setLastActionSummary(`${response.finding.title}: újra aktív.`);
    });
  }

  function toggleResearchFindingDeletionMark(finding: ResearchFindingRead) {
    if (finding.conversion_status === "converted") return;
    setResearchFindingsMarkedForDeletion((current) =>
      current.includes(finding.id)
        ? current.filter((findingId) => findingId !== finding.id)
        : [...current, finding.id]
    );
  }

  async function handleBulkDeleteResearchFindings() {
    if (!selectedCaseId || researchFindingsMarkedForDeletion.length === 0) return;
    const count = researchFindingsMarkedForDeletion.length;
    if (!window.confirm(`Törlöd a kijelölt kutatási találatokat?\n\nKijelölt elemek száma: ${count}`)) return;
    await perform("finding-delete", async () => {
      const response = await bulkDeleteResearchFindings(selectedCaseId, researchFindingsMarkedForDeletion);
      setResearchFindings((current) => current.filter((item) => !researchFindingsMarkedForDeletion.includes(item.id)));
      setResearchFindingsMarkedForDeletion([]);
      setNotice("Kijelölt kutatási találatok törölve a munkalistából.");
      setLastActionSummary(`${response.deleted_count} kutatási találat törölve.`);
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
      setNotice("Kézi ellentmondásjelölt létrehozva.");
      setLastActionSummary("Kézi ellentmondásjelölt: két állítás párosítva.");
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
          {labelReviewStatus(item.review_status)} | {formatSourceReferenceCount(item.sources.length)}
        </span>
        <pre>{item.body_text ?? ""}</pre>
        <div className="source-list">
          {item.sources.slice(0, 3).map((source, index) => (
            <details key={source.source_link_id ?? source.source_reference_id} className="source-detail">
              <summary>
                {index + 1}. forráshivatkozás: {source.document_filename ?? "irat"} {source.page_number ? `${source.page_number}. oldal` : ""}{" "}
                {source.chunk_index !== null ? `${source.chunk_index}. szövegrész` : ""}
              </summary>
              <blockquote>{source.quote_text}</blockquote>
            </details>
          ))}
        </div>
      </article>
    );
  }

  function renderResearchFindingSource(finding: ResearchFindingRead, sourceDocument: DocumentRead | undefined) {
    const source = finding.source_reference;
    if (!source) return null;
    return (
      <details className="source-detail research-finding-source">
        <summary>
          Forráshivatkozás: {sourceDocument?.original_filename ?? "irat"} {source.page_number ? `${source.page_number}. oldal` : ""}
        </summary>
        <div className="source-meta">
          <span>{labelSourceKind(source.source_kind)}</span>
          <span>{source.citation_label ?? "nincs hivatkozási címke"}</span>
          {sourceDocument?.lifecycle_status && sourceDocument.lifecycle_status !== "active" && (
            <span>forrás irat állapota: {labelDocumentLifecycleStatus(sourceDocument.lifecycle_status)}</span>
          )}
          <span>idézet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
          <span>szövegkörnyezet {formatRange(source.source_text_excerpt_char_start, source.source_text_excerpt_char_end)}</span>
        </div>
        <blockquote>{source.quote_text}</blockquote>
        {source.source_text_excerpt && <p className="excerpt">{source.source_text_excerpt}</p>}
        <code className="hash">{source.id}</code>
      </details>
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
          title="Forráshivatkozás leválasztása erről a találatról"
          onClick={() => handleDetachSource(item, source)}
          disabled={Boolean(busy)}
        >
          <Unlink size={16} /> Leválasztás
        </button>
        {targetOptions.length > 0 && (
          <>
            <select
              value={sourceMoveTargets[key] ?? ""}
              onChange={(event) => setSourceMoveTargets((current) => ({ ...current, [key]: event.target.value }))}
              aria-label="Forráshivatkozás áthelyezési célja"
            >
              <option value="">Áthelyezés célja</option>
              {targetOptions.map((target) => (
                <option key={target.id} value={target.id}>
                  {target.label}
                </option>
              ))}
            </select>
            <button className="secondary-button source-action" onClick={() => handleMoveSource(item, source)} disabled={Boolean(busy) || !sourceMoveTargets[key]}>
              Áthelyezés
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
    return (
      <>
        {renderManualObjectSubtypeFieldFor(type, fields, updateField)}
        {renderManualObjectDetailFieldsFor(type, fields, updateField)}
      </>
    );
  }

  function renderManualObjectSubtypeFieldFor(
    type: ManualObjectType,
    fields: Record<string, string>,
    updateField: (key: string, value: string) => void
  ) {
    if (type === "claim") {
      return (
        <label>
          Állítás típusa
          <select value={fields.claim_type ?? "document_fact"} onChange={(event) => updateField("claim_type", event.target.value)}>
            <option value="document_fact">Iratbeli tény</option>
            <option value="witness_statement">Tanúi állítás</option>
            <option value="expert_opinion">Szakértői vélemény</option>
            <option value="administrative_fact">Hivatalos tény</option>
            <option value="inference_candidate">Következtetésjelölt</option>
            <option value="unknown">Ismeretlen</option>
          </select>
        </label>
      );
    }
    if (type === "entity") {
      return (
        <label>
          Entitás típusa
          <select value={fields.entity_type ?? "person"} onChange={(event) => updateField("entity_type", event.target.value)}>
            <option value="person">Személy</option>
            <option value="organization">Szervezet</option>
            <option value="location">Hely</option>
            <option value="phone">Telefon</option>
            <option value="email">Email</option>
            <option value="license_plate">Rendszám</option>
            <option value="case_reference">Ügyhivatkozás</option>
            <option value="money_amount">Pénzösszeg</option>
            <option value="document_reference">Irat hivatkozás</option>
            <option value="other">Egyéb</option>
          </select>
        </label>
      );
    }
    if (type === "event") {
      return (
        <label>
          Esemény típusa
          <select value={fields.event_type ?? "statement"} onChange={(event) => updateField("event_type", event.target.value)}>
            <option value="statement">Nyilatkozat</option>
            <option value="call">Hívás</option>
            <option value="meeting">Találkozó</option>
            <option value="transfer">Átadás / utalás</option>
            <option value="search">Kutatás</option>
            <option value="seizure">Lefoglalás</option>
            <option value="document_created">Irat keletkezett</option>
            <option value="document_received">Irat érkezett</option>
            <option value="other">Egyéb</option>
          </select>
        </label>
      );
    }
    return (
      <label>
        Hiányzó irat típusa
        <select value={fields.missing_item_type ?? "document_reference"} onChange={(event) => updateField("missing_item_type", event.target.value)}>
          <option value="attachment">Melléklet</option>
          <option value="video">Video</option>
          <option value="expert_report">Szakértői vélemény</option>
          <option value="protocol">Jegyzőkönyv</option>
          <option value="image">Kép</option>
          <option value="document_reference">Irat hivatkozás</option>
          <option value="other">Egyéb</option>
        </select>
      </label>
    );
  }

  function renderManualObjectDetailFieldsFor(
    type: ManualObjectType,
    fields: Record<string, string>,
    updateField: (key: string, value: string) => void
  ) {
    if (type === "claim") {
      return (
        <>
          <label>
            Cím
            <input value={fields.claim_title ?? ""} onChange={(event) => updateField("claim_title", event.target.value)} />
          </label>
          <label>
            Leírás
            <textarea value={fields.claim_text ?? ""} onChange={(event) => updateField("claim_text", event.target.value)} />
          </label>
        </>
      );
    }
    if (type === "entity") {
      return (
        <>
          <label>
            Cím
            <input value={fields.canonical_name ?? ""} onChange={(event) => updateField("canonical_name", event.target.value)} />
          </label>
          <label>
            Leírás
            <textarea value={fields.description ?? ""} onChange={(event) => updateField("description", event.target.value)} />
          </label>
        </>
      );
    }
    if (type === "event") {
      return (
        <>
          <label>
            Cím
            <input value={fields.event_title ?? ""} onChange={(event) => updateField("event_title", event.target.value)} />
          </label>
          <label>
            Leírás
            <textarea value={fields.event_description ?? ""} onChange={(event) => updateField("event_description", event.target.value)} />
          </label>
          <label>
            Idő pontossága
            <select value={fields.time_precision ?? "unknown"} onChange={(event) => updateField("time_precision", event.target.value)}>
              <option value="unknown">Ismeretlen</option>
              <option value="year">Év</option>
              <option value="month">Hónap</option>
              <option value="day">Nap</option>
              <option value="hour">Óra</option>
              <option value="minute">Perc</option>
            </select>
          </label>
          {renderEventTimeFields(fields, updateField)}
        </>
      );
    }
    return (
      <>
        <label>
          Cím
          <input value={fields.referenced_item_text ?? ""} onChange={(event) => updateField("referenced_item_text", event.target.value)} />
        </label>
        <label>
          Leírás
          <textarea value={fields.description ?? ""} onChange={(event) => updateField("description", event.target.value)} />
        </label>
      </>
    );
  }

  function renderEventTimeFields(fields: Record<string, string>, updateField: (key: string, value: string) => void) {
    const precision = fields.time_precision || "unknown";
    if (precision === "unknown") return null;
    const showMonth = ["month", "day", "hour", "minute"].includes(precision);
    const showDay = ["day", "hour", "minute"].includes(precision);
    const showHour = ["hour", "minute"].includes(precision);
    const showMinute = precision === "minute";
    return (
      <div className="event-time-grid">
        <label>
          Év
          <input
            type="number"
            min="1"
            max="9999"
            value={fields.event_year ?? ""}
            onChange={(event) => updateField("event_year", event.target.value)}
          />
        </label>
        {showMonth && (
          <label>
            Hónap
            <select value={fields.event_month ?? "1"} onChange={(event) => updateField("event_month", event.target.value)}>
              {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                <option key={month} value={month}>
                  {month}
                </option>
              ))}
            </select>
          </label>
        )}
        {showDay && (
          <label>
            Nap
            <select value={fields.event_day ?? "1"} onChange={(event) => updateField("event_day", event.target.value)}>
              {Array.from({ length: 31 }, (_, index) => index + 1).map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
          </label>
        )}
        {showHour && (
          <label>
            Óra
            <select value={fields.event_hour ?? "0"} onChange={(event) => updateField("event_hour", event.target.value)}>
              {Array.from({ length: 24 }, (_, index) => index).map((hour) => (
                <option key={hour} value={hour}>
                  {hour}
                </option>
              ))}
            </select>
          </label>
        )}
        {showMinute && (
          <label>
            Perc
            <select value={fields.event_minute ?? "0"} onChange={(event) => updateField("event_minute", event.target.value)}>
              {Array.from({ length: 60 }, (_, index) => index).map((minute) => (
                <option key={minute} value={minute}>
                  {minute}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    );
  }

  function renderClaimMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "claim") return null;
    if (item.source_validation_status === "source_invalid") return null;
    if (!reportItemSourcesAreActive(item)) return null;
    const targetOptions = claims.filter(
      (claim) =>
        claim.id !== item.object_id &&
        claim.source_validation_status !== "source_invalid" &&
        claim.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          <span className="merge-label-line">
            Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású állítások választhatók célként.)</span>
          </span>
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Válassz célállítást</option>
            {targetOptions.map((claim) => (
              <option key={claim.id} value={claim.id}>
                {claim.claim_title} ({labelReviewStatus(claim.review_status)})
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleClaimMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Összevonás
        </button>
      </div>
    );
  }

  function renderEntityMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "entity") return null;
    if (item.source_validation_status === "source_invalid") return null;
    if (!reportItemSourcesAreActive(item)) return null;
    const targetOptions = entities.filter(
      (entity) =>
        entity.id !== item.object_id &&
        entity.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          <span className="merge-label-line">
            Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású entitások választhatók célként.)</span>
          </span>
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Válassz célentitást</option>
            {targetOptions.map((entity) => (
              <option key={entity.id} value={entity.id}>
                {entity.canonical_name} ({labelReviewStatus(entity.review_status)})
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleEntityMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Összevonás
        </button>
      </div>
    );
  }

  function renderEventMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "event") return null;
    if (item.source_validation_status === "source_invalid") return null;
    if (!reportItemSourcesAreActive(item)) return null;
    const targetOptions = events.filter(
      (event) =>
        event.id !== item.object_id &&
        event.source_validation_status !== "source_invalid" &&
        event.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          <span className="merge-label-line">
            Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású események választhatók célként.)</span>
          </span>
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Válassz céleseményt</option>
            {targetOptions.map((event) => (
              <option key={event.id} value={event.id}>
                {event.event_title} ({labelReviewStatus(event.review_status)})
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleEventMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Összevonás
        </button>
      </div>
    );
  }

  function renderMissingItemMergeControls(item: ReviewReportItem, compact = false) {
    if (item.object_type !== "missing_item_candidate") return null;
    if (item.source_validation_status === "source_invalid") return null;
    if (!reportItemSourcesAreActive(item)) return null;
    const targetOptions = missingItemCandidates.filter(
      (candidate) =>
        candidate.id !== item.object_id &&
        candidate.source_validation_status !== "source_invalid" &&
        candidate.review_status !== "corrected"
    );
    if (targetOptions.length === 0) return null;
    return (
      <div className={compact ? "merge-panel compact-merge" : "merge-panel"}>
        <label>
          <span className="merge-label-line">
            Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású hiányzó iratjelöltek választhatók célként.)</span>
          </span>
          <select
            value={mergeTargets[item.object_id] ?? ""}
            onChange={(event) => setMergeTargets((current) => ({ ...current, [item.object_id]: event.target.value }))}
          >
            <option value="">Válassz céljelöltet</option>
            {targetOptions.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.referenced_item_text} ({labelReviewStatus(candidate.review_status)})
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary-button"
          onClick={() => handleMissingItemMerge(item)}
          disabled={Boolean(busy) || !mergeTargets[item.object_id]}
        >
          <GitMerge size={18} /> Összevonás
        </button>
      </div>
    );
  }

  function handleSelectReportItem(item: ReviewReportItem) {
    setSelectedReportItem(item);
    window.setTimeout(() => {
      objectDetailPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
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
          <span><Database size={16} /> forráshivatkozott</span>
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
                <article key={document.id} className="compact-item document-list-item">
                  <div className="document-list-main">
                    <strong>{document.original_filename}</strong>
                    <span>
                      {labelDocumentTaxonomy(document)} | {labelProcessingStatus(document.processing_status)} | {labelDocumentLifecycleStatus(document.lifecycle_status)} | {formatBytes(document.file_size_bytes)}
                    </span>
                    <code>{document.sha256_hash}</code>
                    {(canRunOcr(document) || canCreateChunks(document)) && (
                      <div className="button-row document-list-extra-actions">
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
                    )}
                  </div>
                  <button className="document-detail-button" onClick={() => handleDocumentDetail(document)} disabled={Boolean(busy)}>
                    Reszletek
                  </button>
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
                  <span>{labelDocumentLifecycleStatus(selectedDocument.lifecycle_status)}</span>
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
                      Csak az irat adminisztratív besorolása változik. Az oldalak, szövegrészek, forráshivatkozások és elemzési futások nem módosulnak.
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
                <details>
                  <summary>Irat állapota</summary>
                  <div className="manual-entry-panel">
                    <div className="metrics">
                      <span>{labelDocumentLifecycleStatus(selectedDocument.lifecycle_status)}</span>
                      {selectedDocument.lifecycle_status_changed_at && (
                        <span>{formatDateTime(selectedDocument.lifecycle_status_changed_at)}</span>
                      )}
                    </div>
                    {selectedDocument.lifecycle_status_reason && (
                      <p className="field-hint">Utolsó indoklás: {selectedDocument.lifecycle_status_reason}</p>
                    )}
                    <label>
                      Megjegyzés / indoklás
                      <textarea
                        value={documentLifecycleReason}
                        onChange={(event) => setDocumentLifecycleReason(event.target.value)}
                        placeholder="Opcionális indoklás az állapotváltozáshoz"
                        disabled={Boolean(busy)}
                      />
                    </label>
                    <p className="field-hint">
                      Az aktív iratok vesznek részt új keresésben, indexelésben és elemzésben. A kizárt vagy archivált iratok történeti forrásként továbbra is visszakereshetők.
                    </p>
                    <div className="button-row">
                      {!selectedDocumentIsActive && (
                        <button onClick={() => handleDocumentLifecycleAction("restore")} disabled={Boolean(busy)}>
                          Visszaállítás aktívra
                        </button>
                      )}
                      {selectedDocumentIsActive && (
                        <button onClick={() => handleDocumentLifecycleAction("exclude")} disabled={Boolean(busy)}>
                          Kizárás elemzésből
                        </button>
                      )}
                      {selectedDocumentIsActive && (
                        <button onClick={() => handleDocumentLifecycleAction("archive")} disabled={Boolean(busy)}>
                          Archiválás
                        </button>
                      )}
                      {selectedDocument.lifecycle_status === "excluded" && (
                        <button onClick={() => handleDocumentLifecycleAction("archive")} disabled={Boolean(busy)}>
                          Archiválás
                        </button>
                      )}
                      {selectedDocument.lifecycle_status === "archived" && (
                        <button onClick={() => handleDocumentLifecycleAction("exclude")} disabled={Boolean(busy)}>
                          Kizárás elemzésből
                        </button>
                      )}
                      {canAttemptSelectedDocumentDiscard && (
                        <button className="secondary-button" onClick={handleDocumentDiscard} disabled={Boolean(busy)}>
                          Elvetés / törlés
                        </button>
                      )}
                    </div>
                    {selectedDocumentIsActive && documentChunks.length > 0 && (
                      <p className="field-hint">
                        Az irat már szövegrészekre lett bontva, ezért nem vethető el végleges törléssel. Kizárással vagy archiválással parkolópályára tehető.
                      </p>
                    )}
                    {!selectedDocumentIsActive && (
                      <p className="field-hint">
                        Nem aktív iratból nem indítható új OCR, szövegrész-létrehozás, indexelés, elemzés vagy kézi forráshivatkozás.
                      </p>
                    )}
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
                <details>
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
                    {!selectedDocumentIsActive && documentChunks.length > 0 && (
                      <p className="field-hint">Ez az irat nem aktív, ezért a meglévő szövegrészek csak megtekinthetők.</p>
                    )}
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
                        {selectedDocumentIsActive && (
                          <button
                            className="secondary-button"
                            onClick={(event) => {
                              const textarea = event.currentTarget.parentElement?.querySelector("textarea");
                              if (textarea) handleManualSourceFromChunk(chunk, textarea);
                            }}
                            disabled={Boolean(busy)}
                          >
                            Forráshivatkozás kijelölése
                          </button>
                        )}
                      </article>
                    ))}
                  </div>
                </details>
                {manualSource && (
                  <section className="manual-source-panel" ref={manualSourcePanelRef}>
                    <h3>Új találat forráshivatkozásból</h3>
                    <div className="manual-entry-panel">
                      <label>
                        Kijelölt forráshivatkozás
                        <textarea
                          className="manual-source-preview"
                          readOnly
                          rows={6}
                          value={manualSource.quoteText}
                          aria-label="Kijelölt forráshivatkozás readonly előnézet"
                        />
                      </label>
                      <span className="field-hint">
                        {manualSource.citationLabel} | idézet {formatRange(manualSource.quoteStart, manualSource.quoteEnd)}
                      </span>
                      <label>
                        Találat típusa
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
                          Rögzítés forráshivatkozásból
                        </button>
                        <button className="secondary-button" onClick={() => setManualSource(null)} disabled={Boolean(busy)}>
                          Mégse
                        </button>
                      </div>
                    </div>
                  </section>
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
                <input
                  ref={importFileInputRef}
                  type="file"
                  accept=".txt,.pdf,text/plain,application/pdf"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
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
                  <p className="error-text">Szemantikus vagy hybrid futtatáshoz előbb indexelni kell az aktuális forráskört.</p>
                )}
              </div>
            )}
            {canUseBatchScope && (
              <div className="source-action-row">
                <button
                  className="secondary-button"
                  onClick={handleIndexChunks}
                  disabled={!selectedCaseId || Boolean(busy) || indexJobIsRunning || (effectiveAnalysisSourceMode === "document" && !analysisDocumentId)}
                  title="Lokális embedding és Qdrant index készítése az aktuális forráskörhöz"
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
              <label>
                Forráskör
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
                  A szűrők csak a teljes ügy forráskörben érvényesek. Ha nem jelölsz ki konkrét iratot, a rendszer a választott csoport/típus összes aktuális iratában keres.
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
                      disabled={activeDocuments.length === 0}
                    />
                  </div>
                  {activeDocuments.length === 0 && <p className="muted">Nincs aktív irat.</p>}
                  {activeDocuments.length > 0 && filteredDocumentAnalysisDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelo aktív irat.</p>}
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
                    max={50}
                    value={maxChunks}
                    onChange={(event) => setMaxChunks(clampNumberInput(event.target.value, 1, 50, 30))}
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
                    Forráskeresés
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
                    Állításkör
                    <select value={claimReviewScope} onChange={(event) => setClaimReviewScope(event.target.value as ClaimReviewScope)}>
                      {claimReviewScopes.map((item) => <option key={item} value={item}>{labelClaimReviewScope(item)}</option>)}
                    </select>
                  </label>
                  <label>
                    Ellentmondásjelölt plafon
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
                  Állításpár alapú modul: a rendszer a már kinyert, forráshivatkozott állítások között választ ellenőrizendő párokat. Az alapértelmezett állításkör nem veszi figyelembe az elutasított állításokat. A fókusz kötelező, és az állítás szövegében vagy forráshivatkozási idézeteiben szűr.
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
                  ? "Kötelező: ez szűri a már kinyert állításokat és forráshivatkozási idézeteiket."
                  : "Kötelező: ez választja ki a releváns szövegrészeket a megadott forráskörben."}
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
                {analysis.module_key === "search_findings" && (
                  <button
                    className="secondary-button"
                    onClick={() => researchFindingsPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  >
                    Ugrás a kutatási találatokhoz
                  </button>
                )}
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
                <article key={run.id} className="compact-item analysis-run-list-item">
                  <div className="analysis-run-list-main">
                    <strong>{labelModule(run.run_type)}</strong>
                    <span>{labelRunStatus(run.status)} | {run.validation_status ? labelValidationStatus(run.validation_status) : "nincs validacio"} | {run.model_name ?? "nincs modell"}</span>
                    <span>{new Date(run.started_at).toLocaleString()} {run.finished_at ? `-> ${new Date(run.finished_at).toLocaleTimeString()}` : ""}</span>
                    {run.error_message && <p className="error-text">{run.error_message}</p>}
                    <code>{run.id}</code>
                  </div>
                  <button className="analysis-run-detail-button" onClick={() => handleAnalysisRunDetail(run)} disabled={Boolean(busy)}>
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
                <details>
                  <summary>Bemenetek</summary>
                  <div className="detail-list">
                    {analysisRunDetail.inputs.map((input) => (
                      <article key={input.id} className="compact-item">
                        <strong>{input.sequence_no}. {labelAnalysisInputType(input.input_type)}</strong>
                        <span>{input.related_object_type ? labelObjectType(input.related_object_type) : "Forráshivatkozás"} {input.related_object_id ?? input.chunk_id ?? input.document_id ?? ""}</span>
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
          <section className="panel research-findings-panel" ref={researchFindingsPanelRef}>
            <div className="section-heading">
              <h2>Kutatási találatok</h2>
              <Search size={20} />
            </div>
            <p className="module-note">
              A találatok forráshivatkozáshoz kötött keresési munkadarabok. Végleges, ellenőrizhető objektummá az átalakítás után válnak.
            </p>
            <div className="finding-toolbar">
              <button
                type="button"
                onClick={() => setShowSetAsideResearchFindings((current) => !current)}
                disabled={setAsideResearchFindingCount === 0}
              >
                {showSetAsideResearchFindings ? "Félretettek elrejtése" : `Félretettek mutatása (${setAsideResearchFindingCount})`}
              </button>
              <button
                type="button"
                onClick={handleBulkDeleteResearchFindings}
                disabled={Boolean(busy) || markedResearchFindingCount === 0}
              >
                Jelöltek törlése ({markedResearchFindingCount})
              </button>
            </div>
            {visibleResearchFindings.length > 0 && (
              <div className="research-finding-list">
                {visibleResearchFindings.map((finding) => {
                  const sourceDocument = documents.find((document) => document.id === finding.source_reference?.document_id);
                  const conversionType = researchFindingManualTypes[finding.id] ?? suggestedResearchFindingManualType(finding);
                  const conversionFields = researchFindingManualFields[finding.id] ?? {};
                  const isMarkedForDeletion = researchFindingsMarkedForDeletion.includes(finding.id);
                  return (
                    <article
                      key={finding.id}
                      className={`research-finding-card ${finding.conversion_status === "ignored" ? "is-set-aside" : ""} ${
                        isMarkedForDeletion ? "is-marked-delete" : ""
                      }`}
                    >
                      <div className="research-finding-header">
                        <div>
                          <h3>{finding.title}</h3>
                          <p>{finding.finding_text}</p>
                        </div>
                        <span className="status-pill">{labelResearchFindingType(finding.suggested_type)}</span>
                      </div>
                      <div className="tags">
                        <span>{labelLlmSupportStatus(finding.llm_support_status)}</span>
                        <span>{labelSourceValidationStatus(finding.source_validation_status)}</span>
                        <span>{labelResearchFindingConversionStatus(finding.conversion_status)}</span>
                      </div>
                      <p className="field-hint">Relevancia: {finding.relevance_reason}</p>
                      {finding.suggested_type_reason && <p className="field-hint">Típusjavaslat oka: {finding.suggested_type_reason}</p>}
                      <div className="finding-actions">
                        {finding.conversion_status === "ignored" ? (
                          <button type="button" onClick={() => handleRestoreResearchFinding(finding)} disabled={Boolean(busy)}>
                            Vissza az aktív listába
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleSetAsideResearchFinding(finding)}
                            disabled={Boolean(busy) || finding.conversion_status === "converted"}
                          >
                            Félreteszem
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => toggleResearchFindingDeletionMark(finding)}
                          disabled={Boolean(busy)}
                        >
                          {isMarkedForDeletion ? "Törlésre jelölve" : "Törlésre jelölés"}
                        </button>
                        {finding.conversion_status !== "converted" && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => fillResearchFindingManualFields(finding, conversionType)}
                            disabled={Boolean(busy)}
                          >
                            Cím és leírás automatikus kitöltése
                          </button>
                        )}
                      </div>
                      {renderResearchFindingSource(finding, sourceDocument)}
                      {finding.conversion_status !== "converted" && (
                        <div className="finding-conversion-panel">
                          <div className="finding-conversion-heading">
                            <h4>Átalakítás strukturált találattá</h4>
                            <span>A forráshivatkozásból ellenőrizhető objektum készül.</span>
                          </div>
                          <div className="finding-conversion-type-row">
                            <label>
                              Cél típusa
                              <select
                                value={conversionType}
                                onChange={(event) =>
                                  setResearchFindingManualTypes((current) => ({
                                    ...current,
                                    [finding.id]: event.target.value as ManualObjectType
                                  }))
                                }
                              >
                                {(Object.keys(manualObjectTypeLabels) as ManualObjectType[]).map((type) => (
                                  <option key={type} value={type}>
                                    {manualObjectTypeLabels[type]}
                                  </option>
                                ))}
                              </select>
                            </label>
                            {renderManualObjectSubtypeFieldFor(
                              conversionType,
                              conversionFields,
                              (key, value) => updateResearchFindingManualField(finding.id, key, value)
                            )}
                          </div>
                          {renderManualObjectDetailFieldsFor(
                            conversionType,
                            conversionFields,
                            (key, value) => updateResearchFindingManualField(finding.id, key, value)
                          )}
                          <button onClick={() => handleConvertResearchFinding(finding)} disabled={Boolean(busy)}>
                            Strukturált találat létrehozása
                          </button>
                        </div>
                      )}
                      {finding.conversion_status === "converted" && finding.target_object_type && finding.target_object_id && (
                        <p className="field-hint">
                          Átalakítva: {labelObjectType(finding.target_object_type)} | {finding.target_object_id}
                        </p>
                      )}
                      <code>{finding.id}</code>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <section className="panel report-panel">
            <div className="section-heading">
              <h2>Áttekintési jelentés</h2>
              <Archive size={20} />
            </div>
            <div className="form-row">
              <label>
                Találat típusa
                <select value={objectType} onChange={(event) => setObjectType(event.target.value)}>
                  {objectTypes.map((item) => <option key={item} value={item}>{item ? labelObjectType(item) : "Összes találat"}</option>)}
                </select>
              </label>
              <label>
                Ellenőrzési állapot
                <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>
                  {reviewStatuses.map((item) => <option key={item} value={item}>{item ? labelReviewStatus(item) : "Összes"}</option>)}
                </select>
              </label>
              <label>
                Forráshivatkozás állapota
                <select value={sourceValidationStatus} onChange={(event) => setSourceValidationStatus(event.target.value)}>
                  {sourceValidationStatuses.map((item) => <option key={item} value={item}>{item ? labelSourceValidationStatus(item) : "Összes"}</option>)}
                </select>
              </label>
              <button onClick={handleLoadReport} disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} /> Betöltés
              </button>
            </div>
            {report && (
              <>
                <div className="form-row">
                  <label>
                    Keresés a találatokban
                    <input
                      value={reportSearch}
                      onChange={(event) => setReportSearch(event.target.value)}
                      placeholder="Találat neve, leírása vagy idézete"
                    />
                  </label>
                </div>
                <div className="metrics">
                  <span>{report.counts.total} találat</span>
                  <span>{visibleReportItems.length} megjelenítve</span>
                  <span>{report.counts.needs_review} ellenőrzésre vár</span>
                  <span>{report.counts.verified} ellenőrizve</span>
                  <span>{report.counts.rejected} elutasítva</span>
                </div>
                <div className="item-list">
                  {visibleReportItems.length === 0 && <p className="muted">Nincs a keresésnek megfelelő találat.</p>}
                  {visibleReportItems.map((item) => (
                    <article key={item.object_id} className="report-item">
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.body_text}</p>
                        {item.object_type === "contradiction_candidate" && (
                          <p className="review-note">Ellenőrizendő jelölt: a rendszer nem tekinti bizonyított ellentmondásnak.</p>
                        )}
                      </div>
                      <div className="tags">
                        <span>{labelObjectType(item.object_type)}</span>
                        <span>{labelSubtype(item.object_type, item.subtype)}</span>
                        {item.object_type === "event" && <span>Idő: {formatEventTime(item.event_time_start, item.time_precision)}</span>}
                        <span>{labelReviewStatus(item.review_status)}</span>
                        <span>{labelSourceValidationStatus(item.source_validation_status)}</span>
                        <span>{item.reviews.length} ellenőrzés</span>
                        <span>{formatSourceReferenceCount(item.sources.length)}</span>
                      </div>
                      <button className="secondary-button" onClick={() => handleSelectReportItem(item)}>
                        Részletek
                      </button>
                      <div className="source-list">
                        {item.sources.map((source, index) => (
                          <details key={source.source_link_id ?? source.source_reference_id} className="source-detail">
                            <summary>
                              {index + 1}. forráshivatkozás: {source.document_filename ?? "irat"} {source.page_number ? `${source.page_number}. oldal` : ""} {source.chunk_index !== null ? `${source.chunk_index}. szövegrész` : ""}
                            </summary>
                            <div className="source-meta">
                              <span>{labelSupportType(source.support_type)}</span>
                              <span>sorrend {source.relevance_rank ?? index}</span>
                              <span>{source.citation_label ?? "nincs hivatkozási címke"}</span>
                              {source.document_lifecycle_status && source.document_lifecycle_status !== "active" && (
                                <span>forrás irat állapota: {labelDocumentLifecycleStatus(source.document_lifecycle_status)}</span>
                              )}
                              <span>idézet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                              <span>szövegkörnyezet {formatRange(source.source_text_excerpt_char_start, source.source_text_excerpt_char_end)}</span>
                            </div>
                            <blockquote>{source.quote_text}</blockquote>
                            {source.source_text_excerpt && <p className="excerpt">{source.source_text_excerpt}</p>}
                            {source.document_sha256_hash && <code className="hash">{source.document_sha256_hash}</code>}
                            {renderSourceDetachButton(item, source)}
                          </details>
                        ))}
                      </div>
                      {renderClaimMergeControls(item, true)}
                      {renderEntityMergeControls(item, true)}
                      {renderEventMergeControls(item, true)}
                      {renderMissingItemMergeControls(item, true)}
                      <div className="review-row">
                        <input
                          value={reviewComments[item.object_id] ?? ""}
                          onChange={(event) => setReviewComments((current) => ({ ...current, [item.object_id]: event.target.value }))}
                          placeholder="Ellenőrzési megjegyzés"
                          aria-label="Ellenőrzési megjegyzés"
                        />
                        <button title="Ellenőrizve" onClick={() => handleReview(item.object_type, item.object_id, "verify")} disabled={reviewActionDisabled(item, "verify")}>
                          <CheckCircle2 size={18} />
                        </button>
                        <button title="Elutasítás" onClick={() => handleReview(item.object_type, item.object_id, "reject")} disabled={reviewActionDisabled(item, "reject")}>
                          Elutasít
                        </button>
                        <button title="Ellenőrzésre vár" onClick={() => handleReview(item.object_type, item.object_id, "mark_needs_review")} disabled={reviewActionDisabled(item, "mark_needs_review")}>
                          Ellenőrzésre
                        </button>
                        <button title="Megjegyzés" onClick={() => handleReview(item.object_type, item.object_id, "comment")} disabled={reviewActionDisabled(item, "comment")}>
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
              <h2>Kézi ellentmondásjelölt</h2>
              <GitMerge size={20} />
            </div>
            <div className="module-note">
              Két érvényes forráshivatkozású, nem elutasított állításból hoz létre ellenőrizendő jelöltet. A rögzítés nem bizonyított ellentmondás, hanem emberi ellenőrzésre váró pár.
            </div>
            {manualContradictionClaimOptions.length < 2 && (
              <p className="muted">Legalább két érvényes forráshivatkozású, nem elutasított állítás kell a kézi jelölthez.</p>
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
              Ellenőrzési indoklás
              <textarea
                value={manualContradiction.description}
                onChange={(event) => updateManualContradictionField("description", event.target.value)}
                rows={3}
                placeholder="Roviden ird le, milyen konkret elteres miatt kell emberi ellenorzes."
              />
            </label>
            <div className="claim-preview-grid">
              {selectedManualClaimA && renderClaimPreview(selectedManualClaimA, "")}
              {selectedManualClaimB && renderClaimPreview(selectedManualClaimB, "")}
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

          <section className="panel detail-panel object-detail-panel" ref={objectDetailPanelRef}>
            <div className="section-heading">
              <h2>Találat részletei</h2>
              <Search size={20} />
            </div>
            {!selectedReportItem && <p className="muted">Válassz találatot a részletekhez.</p>}
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
                  <p className="review-note">A jelölt két forráshivatkozott állítás párját emeli ki emberi ellenőrzésre. Önmagában nem bizonyított ténymegállapítás.</p>
                )}
                <div className="object-facts">
                  {objectDetailFacts(selectedReportItem).map((fact) => (
                    <div key={fact.label}>
                      <span>{fact.label}</span>
                      <strong>{fact.value}</strong>
                    </div>
                  ))}
                </div>
                {renderClaimMergeControls(selectedReportItem)}
                {renderEntityMergeControls(selectedReportItem)}
                {renderEventMergeControls(selectedReportItem)}
                {renderMissingItemMergeControls(selectedReportItem)}
                <details>
                  <summary>Forráshivatkozások</summary>
                  <div className="detail-list">
                    {selectedReportItem.sources.map((source, index) => (
                      <article key={source.source_link_id ?? source.source_reference_id} className="text-sample">
                        <strong>{index + 1}. {source.document_filename ?? "irat"}</strong>
                        <div className="source-meta">
                          <span>{labelSupportType(source.support_type)}</span>
                          <span>sorrend {source.relevance_rank ?? index}</span>
                          <span>{source.citation_label ?? "nincs hivatkozási címke"}</span>
                          {source.document_lifecycle_status && source.document_lifecycle_status !== "active" && (
                            <span>forrás irat állapota: {labelDocumentLifecycleStatus(source.document_lifecycle_status)}</span>
                          )}
                          <span>idézet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
                          <span>szövegkörnyezet {formatRange(source.source_text_excerpt_char_start, source.source_text_excerpt_char_end)}</span>
                        </div>
                        <blockquote>{source.quote_text}</blockquote>
                        {source.source_text_excerpt && <p className="excerpt">{source.source_text_excerpt}</p>}
                        {source.document_sha256_hash && <code className="hash">{source.document_sha256_hash}</code>}
                        {renderSourceDetachButton(selectedReportItem, source)}
                      </article>
                    ))}
                  </div>
                </details>
                <details>
                  <summary>Ellenőrzési előzmények</summary>
                  <div className="detail-list">
                    {selectedReportItem.reviews.map((review) => (
                      <article key={review.id} className="review-history-item">
                        <strong>{labelAction(review.action_type)}</strong>
                        <span>{review.new_review_status ? labelReviewStatus(review.new_review_status) : "megjegyzés"} | {new Date(review.performed_at).toLocaleString()}</span>
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
              <h2>Leválasztott forráshivatkozások</h2>
              <Archive size={20} />
            </div>
            <div className="compact-list detached-source-list">
              {detachedSourceItems.length === 0 && <p className="muted">Nincs leválasztott forráshivatkozás.</p>}
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
                    Eredeti típus: {item.object_subtype_snapshot ?? "ismeretlen"} | korábbi állapot:{" "}
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
                          aria-label="Leválasztott forráshivatkozás csatolási célja"
                        >
                          <option value="">Visszacsatolás célja</option>
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
                          Csatolás
                        </button>
                        <button className="secondary-button source-action" onClick={() => handleDiscardDetachedSource(item)} disabled={Boolean(busy)}>
                          Irreleváns
                        </button>
                      </div>
                      <details className="detached-source-create-details">
                        <summary>Új találat ebből a forráshivatkozásból</summary>
                        <div className="manual-entry-panel">
                          <textarea
                            className="detached-source-preview"
                            readOnly
                            value={item.source_snapshot_json?.quote_text ?? ""}
                            aria-label="Leválasztott forráshivatkozás readonly előnézet"
                          />
                          <label>
                            Találat típusa
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
                            Új találat létrehozása
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
  return response.contradiction_candidates.length + response.research_findings.length;
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
    search_findings: "Add meg, milyen forráshű kutatási találatokat keressen."
  };
  return placeholders[moduleKey] ?? "Add meg a fókuszt a forráshivatkozott elemzéshez.";
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("hu-HU", {
    dateStyle: "medium",
    timeStyle: "medium"
  }).format(new Date(value));
}

function formatEventTime(value: string | null, precision: string | null) {
  if (!value || precision === "unknown") return "ismeretlen";
  const date = new Date(value);
  if (precision === "year") {
    return new Intl.DateTimeFormat("hu-HU", { year: "numeric" }).format(date);
  }
  if (precision === "month") {
    return new Intl.DateTimeFormat("hu-HU", { year: "numeric", month: "2-digit" }).format(date);
  }
  if (precision === "day") {
    return new Intl.DateTimeFormat("hu-HU", { dateStyle: "medium" }).format(date);
  }
  if (precision === "hour") {
    return new Intl.DateTimeFormat("hu-HU", { dateStyle: "medium", hour: "2-digit" }).format(date);
  }
  return new Intl.DateTimeFormat("hu-HU", { dateStyle: "medium", timeStyle: "short" }).format(date);
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

function labelLlmSupportStatus(value: string) {
  return llmSupportLabels[value] ?? value;
}

function labelResearchFindingType(value: string) {
  return researchFindingTypeLabels[value] ?? value;
}

function labelResearchFindingConversionStatus(value: string) {
  const labels: Record<string, string> = {
    not_converted: "Aktív munkalista-elem",
    converted: "Átalakítva",
    ignored: "Félretéve"
  };
  return labels[value] ?? value;
}

function suggestedResearchFindingManualType(finding: ResearchFindingRead): ManualObjectType {
  if (finding.suggested_type === "entity") return "entity";
  if (finding.suggested_type === "event") return "event";
  if (finding.suggested_type === "document_reference") return "missing_item_candidate";
  return "claim";
}

function reportItemMatchesSearch(item: ReviewReportItem, queryText: string) {
  const haystack = [
    item.title,
    item.body_text ?? "",
    labelObjectType(item.object_type),
    labelSubtype(item.object_type, item.subtype),
    ...item.sources.flatMap((source) => [
      source.document_filename ?? "",
      source.citation_label ?? "",
      source.quote_text,
      source.source_text_excerpt ?? ""
    ])
  ]
    .join(" ")
    .toLocaleLowerCase("hu-HU");
  return haystack.includes(queryText);
}

function formatSourceReferenceCount(count: number) {
  return `${count} forráshivatkozás`;
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
    needs_review: "Ellenőrzésre vár",
    reattached: "Újra csatolva",
    discarded: "Irrelevánsnak jelölve"
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
    review_required: "Ellenőrzést igényel",
    failed: "Sikertelen"
  };
  return labels[value] ?? value;
}

function labelDocumentLifecycleStatus(value: string) {
  const labels: Record<string, string> = {
    active: "Aktív",
    excluded: "Kizárt",
    archived: "Archivált"
  };
  return labels[value] ?? value;
}

function reportSourceIsActive(source: ReviewReportSource) {
  return !source.document_lifecycle_status || source.document_lifecycle_status === "active";
}

function reportItemSourcesAreActive(item: ReviewReportItem) {
  return item.sources.length > 0 && item.sources.every(reportSourceIsActive);
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
  return document.lifecycle_status === "active" && (document.ocr_recommendation?.action === "recommended" || document.ocr_recommendation?.action === "optional");
}

function canCreateChunks(document: DocumentRead) {
  return document.lifecycle_status === "active" && document.processing_status === "text_review_required";
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

function labelSourceKind(value: string) {
  const labels: Record<string, string> = {
    chunk_quote: "Szövegrész-idézet",
    page_quote: "Oldalidézet",
    manual: "Kézi forráshivatkozás"
  };
  return labels[value] ?? value;
}

function labelAnalysisInputType(value: string) {
  const labels: Record<string, string> = {
    query_text: "Kérdés",
    filter: "Kiválasztási szűrő",
    chunk: "Szövegrész",
    claim: "Állítás",
    event: "Esemény",
    source_reference: "Forráshivatkozás"
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
        {summary.source_count !== null && summary.source_count !== undefined && <span>{formatSourceReferenceCount(summary.source_count)}</span>}
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
          <span>{String(payload.source_validation_status ?? "forráshivatkozás állapota ismeretlen")}</span>
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
    return `elemzési szövegrész: ${match[1]}`;
  }
  return `elemzési forrás: ${rawValue}`;
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
    claim: "Állítás",
    event: "Esemény",
    entity: "Entitás",
    mention: "Említés",
    source_reference: "Forráshivatkozás",
    research_finding: "Kutatási találat",
    contradiction_candidate: "Ellentmondásjelölt",
    missing_item_candidate: "Hiányzó iratjelölt"
  };
  return labels[value] ?? value;
}

function labelExportFilter(value: string | null) {
  const labels: Record<string, string> = {
    all: "Összes",
    verified_only: "Csak ellenorzott",
    needs_review: "Ellenőrzésre vár",
    rejected: "Elutasitott"
  };
  return labels[value ?? "all"] ?? (value ?? "Összes");
}

function labelExportScope(value: string) {
  const labels: Record<string, string> = {
    review_report: "attekintesi jelentés"
  };
  return labels[value] ?? value;
}

function objectDetailFacts(item: ReviewReportItem) {
  const base = [
    { label: "Forráshivatkozások", value: String(item.sources.length) },
    { label: "Ellenőrzések", value: String(item.reviews.length) }
  ];
  if (item.object_type === "contradiction_candidate") {
    return [...base, { label: "Jelölt típusa", value: labelSubtype(item.object_type, item.subtype) }];
  }
  if (item.object_type === "missing_item_candidate") {
    return [...base, { label: "Hivatkozott irat", value: item.title }];
  }
  if (item.object_type === "entity") {
    return [...base, { label: "Entitás típusa", value: item.subtype }];
  }
  if (item.object_type === "event") {
    return [
      ...base,
      { label: "Esemény típusa", value: item.subtype },
      { label: "Idő", value: formatEventTime(item.event_time_start, item.time_precision) }
    ];
  }
  return [...base, { label: "Állítás típusa", value: item.subtype }];
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
