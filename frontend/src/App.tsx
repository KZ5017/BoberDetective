import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Archive,
  Brain,
  CheckCircle2,
  Copy,
  Database,
  Download,
  FilePlus2,
  FolderPlus,
  GitMerge,
  Loader2,
  MessageSquare,
  Moon,
  MoreVertical,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sun,
  Trash2,
  Unlink
} from "lucide-react";
import {
  AnalysisResponse,
  AssistantChatDetail,
  AssistantChatListItem,
  AssistantMessageRead,
  AnalysisRunDetail,
  AnalysisRunRead,
  ApiError,
  AnalysisSourceMode,
  CaseRead,
  ClaimRead,
  ClaimReviewScope,
  ChunkIndexStatusResponse,
  DetachedSourceItemRead,
  DocumentCollectionRead,
  DocumentCollectionScopeResolveResponse,
  DocumentProcessingItemRead,
  DocumentChunkRead,
  DocumentPageRead,
  DocumentRead,
  EntityRead,
  EventRead,
  ExportDetail,
  ExportRead,
  FullDocumentProcessingProfileRead,
  FullDocumentAnswerRead,
  LlmSmokeResponse,
  ManualObjectPayload,
  ManualObjectType,
  ManualObjectFromSourcePayload,
  ManualContradictionCandidatePayload,
  MissingItemCandidateRead,
  RagLatestRunSummary,
  RagAnswerMode,
  RagQueryResponse,
  RagSavedAnswerDetail,
  RagSavedAnswerListItem,
  RagSourceMode,
  RagUsedSource,
  KnowledgeChunkDetail,
  KnowledgeDocumentRead,
  KnowledgeBatchImportDecision,
  KnowledgeBatchImportResponse,
  KnowledgeBatchPreviewItem,
  KnowledgeBatchPreviewResponse,
  KnowledgeIndexStatusResponse,
  KnowledgeQueryResponse,
  KnowledgeUsedSource,
  RelationshipGraph,
  RelationshipGraphEdge,
  RelationshipGraphFocusObject,
  RelationshipGraphNode,
  ResearchFindingLatestRunSummary,
  ResearchFindingRead,
  ReviewReport,
  ReviewReportFilterValues,
  ReviewReportItem,
  ReviewReportSource,
  RetrievalStrategy,
  addDocumentsToCollection,
  archiveKnowledgeDocument,
  attachDetachedSourceItem,
  attachManualSourceToExistingObject,
  bulkDeleteDocumentProcessingItems,
  bulkDeleteResearchFindings,
  convertResearchFinding,
  createAssistantChat,
  createCase,
  createDocumentChunks,
  createDocumentCollection,
  createExport,
  createManualObject,
  createManualContradictionCandidate,
  createManualObjectFromDetachedSource,
  deleteAssistantChat,
  deleteCase,
  deleteDocumentCollection,
  deleteKnowledgeDocument,
  deleteFullDocumentAnswer,
  deleteRagAnswer,
  detachObjectSource,
  detachContradictionCandidateClaim,
  discardDocument,
  deleteDetachedSourceItem,
  deleteReviewReportItem,
  getAnalysisRun,
  getAssistantChat,
  getChunkIndexStatus,
  getLatestResearchFindingRunSummary,
  getLatestRagRunSummary,
  getRelationshipGraphForObjects,
  getRagAnswer,
  getReviewReport,
  importDocument,
  importKnowledgeDocumentBatch,
  indexKnowledgeDocuments,
  getLlmSmoke,
  getKnowledgeDocumentChunk,
  getKnowledgeIndexStatus,
  listDetachedSourceItems,
  listDocumentCollectionDocuments,
  listDocumentCollections,
  listDocumentChunks,
  listDocumentPages,
  listAnalysisRuns,
  listAssistantChats,
  listCases,
  listClaims,
  listDocuments,
  listDocumentProcessingItems,
  listEntities,
  listEvents,
  listExports,
  listFullDocumentProcessingProfiles,
  listFullDocumentAnswers,
  listKnowledgeDocuments,
  listMissingItemCandidates,
  listRagAnswers,
  listResearchFindings,
  previewKnowledgeDocumentBatch,
  regenerateLastAssistantMessage,
  loadChatModel,
  loadEmbeddingModel,
  mergeClaim,
  mergeEvent,
  mergeEntity,
  mergeMissingItemCandidate,
  moveObjectSource,
  reviewObject,
  removeDocumentsFromCollection,
  restoreResearchFinding,
  resolveDocumentCollectionScope,
  runAnalysis,
  runFullDocumentProcessing,
  runKnowledgeQuery,
  runDocumentOcr,
  runRagQuery,
  saveRagAnswer,
  sendAssistantMessage,
  setAsideResearchFinding,
  startChunkIndexJob,
  unloadChatModel,
  unloadEmbeddingModel,
  updateAssistantChat,
  updateDocumentLifecycle,
  updateDocumentProcessingItemStatus,
  updateReviewReportItemText
} from "./api";

const RelationshipFlowCanvas = lazy(() => import("./RelationshipFlowCanvas"));

const modules = ["search_findings", "detect_contradiction_candidates"];

const objectTypes = [
  "",
  "claim",
  "event",
  "entity",
  "contradiction_candidate",
  "missing_item_candidate"
];

const reviewStatuses = ["", "needs_review", "verified", "rejected", "corrected"];
const sourceValidationStatuses = ["", "source_valid", "source_invalid", "pending_source_validation"];
const analysisSourceModes: AnalysisSourceMode[] = ["case", "document", "collection"];
const claimReviewScopes: ClaimReviewScope[] = ["reviewable", "verified", "needs_review", "all_source_valid"];
const retrievalStrategies: RetrievalStrategy[] = ["keyword", "semantic", "hybrid"];
const ragAnswerModes: RagAnswerMode[] = ["short", "detailed"];
const workSurfaces = ["document_organizer", "case_workbench", "relationship_map", "full_document_processing", "general_rag", "knowledge_base", "ai_assistant", "audit_log"] as const;

type WorkSurface = (typeof workSurfaces)[number];
type ThemeMode = "light" | "dark";

type AppDialogMode = "confirm" | "text_confirm";

type AppDialogState = {
  mode: AppDialogMode;
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  inputLabel?: string;
  expectedValue?: string;
};

type AppDialogResult = boolean | string | null;


type DocumentProcessingUnconfirmedDetail = {
  validation_status: "unconfirmed";
  validation_message?: string;
  llm_source_label?: string;
};

function MarkdownAnswer({ children }: { children: string }) {
  return (
    <div className="rag-answer-text markdown-answer">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
        {children}
      </ReactMarkdown>
    </div>
  );
}

const workSurfaceLabels: Record<WorkSurface, string> = {
  document_organizer: "Irat rendező",
  case_workbench: "Ügy munkapad",
  relationship_map: "Kapcsolati térkép",
  full_document_processing: "Teljes iratfeldolgozás",
  general_rag: "Általános iratkérdező",
  knowledge_base: "Tudásbázis",
  ai_assistant: "AI-asszisztens",
  audit_log: "Audit napló"
};

type SearchableSelectOption = {
  id: string;
  label: string;
  searchText?: string;
  disabled?: boolean;
};

type RelationshipGraphLayerKey = "document_node" | "page_node" | "source_chunk" | "source_reference" | "related_objects" | "contradictions";

type RelationshipGraphLayerState = Record<RelationshipGraphLayerKey, boolean>;

const relationshipGraphLayerLabels: Record<RelationshipGraphLayerKey, string> = {
  document_node: "Irat",
  page_node: "Oldal",
  source_chunk: "Szövegrész",
  source_reference: "Forráshivatkozás",
  related_objects: "Kapcsolódó objektumok",
  contradictions: "Ellentmondások"
};

const defaultRelationshipGraphLayers: RelationshipGraphLayerState = {
  document_node: true,
  page_node: false,
  source_chunk: false,
  source_reference: true,
  related_objects: false,
  contradictions: false
};

const maxRelationshipFocusObjects = 20;

type AiOperationStatus = {
  label: string;
  status: "succeeded" | "failed";
  durationSeconds: number;
};

const busyLabels: Record<string, string> = {
  cases: "Ugylista frissitese",
  "case-create": "Ugy letrehozasa",
  "case-data": "Ugyadatok betoltese",
  "document-detail": "Iratreszletek betoltese",
  "document-exclude": "Irat kizárása",
  "document-archive": "Irat archiválása",
  "document-restore": "Irat visszaállítása",
  "document-discard": "Irat elvetése",
  "document-chunks": "Szovegreszek letrehozasa",
  "document-ocr": "OCR futtatasa",
  "document-collections": "Iratgyűjtemények betöltése",
  "document-collection-create": "Iratgyűjtemény létrehozása",
  "document-collection-delete": "Iratgyűjtemény törlése",
  "document-collection-membership": "Iratgyűjtemény tagság módosítása",
  "document-collection-scope": "Forráskör előnézet",
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
  "detached-source-delete": "Leválasztott forráshivatkozás végleges törlése",
  "review-item-delete": "Találat végleges törlése",
  "review-item-text": "Találat szövegének módosítása",
  "manual-object": "Kézi találat rögzítése",
  "manual-source-attach": "Kézi forráshivatkozás csatolása",
  "manual-contradiction": "Kézi ellentmondásjelölt rögzítése",
  "finding-convert": "Kutatási találat átalakítása",
  "rag-query": "Általános iratkérdező futtatása",
  "rag-save": "Iratkérdező válasz mentése",
  "rag-answers": "Mentett iratkérdező válaszok betöltése",
  "rag-answer-delete": "Mentett iratkérdező válasz törlése",
  "knowledge-documents": "Tudásbázis dokumentumok betöltése",
  "knowledge-import": "Markdown tudásanyag importálása",
  "knowledge-batch-preview": "Markdown batch import előnézet",
  "knowledge-batch-import": "Markdown batch import",
  "knowledge-index-status": "Tudásbázis indexállapot",
  "knowledge-index": "Tudásbázis indexelés",
  "knowledge-query": "Tudásbázis kérdezés",
  "knowledge-archive": "Tudásbázis dokumentum archiválása",
  "knowledge-restore": "Tudásbázis dokumentum visszaállítása",
  "knowledge-delete": "Tudásbázis dokumentum törlése",
  "assistant-chats": "AI-asszisztens beszélgetések betöltése",
  "assistant-chat-create": "AI-asszisztens beszélgetés létrehozása",
  "assistant-chat-load": "AI-asszisztens beszélgetés megnyitása",
  "assistant-chat-delete": "AI-asszisztens beszélgetés törlése",
  "assistant-message": "AI-asszisztens válasz generálása",
  "relationship-graph": "Kapcsolati térkép betöltése",
  "full-document-profiles": "Teljes iratfeldolgozási profilok betöltése",
  "full-document-items": "Teljes iratfeldolgozási munkalista betöltése",
  "full-document-answers": "Iratválaszok betöltése",
  "full-document-answer-delete": "Iratválasz törlése",
  "full-document-run": "Teljes iratfeldolgozás futtatása",
  "full-document-status": "Teljes iratfeldolgozási elem állapota",
  "chunk-index": "Chunk indexeles",
  "llm-smoke": "LLM modell allapot",
  "chat-load": "Chat modell betoltese",
  "chat-unload": "Chat modell leválasztása",
  "embedding-load": "Embedding modell betoltese",
  "embedding-unload": "Embedding modell leválasztása"
};

const aiOperationLabels = new Set([
  "analysis",
  "full-document-run",
  "rag-query",
  "knowledge-query",
  "knowledge-index",
  "assistant-message",
  "chunk-index",
  "chat-load",
  "embedding-load",
]);

const moduleLabels: Record<string, string> = {
  search_findings: "Kutatási találatok keresése",
  detect_contradiction_candidates: "Ellentmondásjelöltek keresése",
  retired_analysis_module: "Kivezetett elemzési futás",
  manual_entry: "Kézi rögzítés"
};

const analysisSourceModeLabels: Record<AnalysisSourceMode, string> = {
  document: "Kivalasztott irat",
  collection: "Iratgyűjtemény",
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

const ragAnswerModeLabels: Record<RagAnswerMode, string> = {
  short: "Rövid válasz",
  detailed: "Részletes válasz"
};

const objectTypeLabels: Record<string, string> = {
  claim: "Állítás",
  event: "Esemény",
  entity: "Entitás",
  contradiction_candidate: "Ellentmondásjelölt",
  missing_item_candidate: "Hiányzó iratjelölt",
  source_reference: "Forráshivatkozás",
  document: "Irat",
  page: "Oldal",
  chunk: "Szövegrész",
  analysis_run: "Elemzési futás",
  research_finding: "Kutatási találat",
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
  corrected: "Korrekcióval kizárt"
};

const sourceValidationLabels: Record<string, string> = {
  source_valid: "Forráshivatkozás érvényes",
  source_invalid: "Nincs érvényes forráshivatkozás",
  pending_source_validation: "Forráshivatkozás ellenőrzésre vár"
};

const runStatusLabels: Record<string, string> = {
  running: "Folyamatban",
  succeeded: "Sikeres",
  failed: "Sikertelen",
  cancelled: "Megszakitva"
};

const validationStatusLabels: Record<string, string> = {
  passed: "Sikeres",
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
  detach_source: "Forráshivatkozás leválasztása",
  edit_text: "Cím/leírás módosítása",
  delete_object: "Végleges törlés"
};

function getManualContradictionClaims(caseId: string): Promise<ReviewReport> {
  return getReviewReport(caseId, { objectType: "claim", sourceValidationStatus: "source_valid" });
}

export function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") {
      return "light";
    }
    return window.localStorage.getItem("boberdetective-theme") === "dark" ? "dark" : "light";
  });
  const [cases, setCases] = useState<CaseRead[]>([]);
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [documentCollections, setDocumentCollections] = useState<DocumentCollectionRead[]>([]);
  const [selectedDocumentCollectionId, setSelectedDocumentCollectionId] = useState("");
  const [selectedDocumentCollectionDocuments, setSelectedDocumentCollectionDocuments] = useState<DocumentRead[]>([]);
  const [selectedDocumentCollectionMarkedDocumentIds, setSelectedDocumentCollectionMarkedDocumentIds] = useState<string[]>([]);
  const [documentCollectionContentSearch, setDocumentCollectionContentSearch] = useState("");
  const [documentCollectionTargetId, setDocumentCollectionTargetId] = useState("");
  const [documentCollectionTargetDocuments, setDocumentCollectionTargetDocuments] = useState<DocumentRead[]>([]);
  const [documentCollectionMarkedDocumentIds, setDocumentCollectionMarkedDocumentIds] = useState<string[]>([]);
  const [newDocumentCollectionName, setNewDocumentCollectionName] = useState("");
  const [newDocumentCollectionDescription, setNewDocumentCollectionDescription] = useState("");
  const [documentCollectionScopePreview, setDocumentCollectionScopePreview] = useState<DocumentCollectionScopeResolveResponse | null>(null);
  const [analysisRuns, setAnalysisRuns] = useState<AnalysisRunRead[]>([]);
  const [analysisHistoryKind, setAnalysisHistoryKind] = useState<"search_findings" | "manual_entry">("search_findings");
  const [exports, setExports] = useState<ExportRead[]>([]);
  const [entities, setEntities] = useState<EntityRead[]>([]);
  const [claims, setClaims] = useState<ClaimRead[]>([]);
  const [events, setEvents] = useState<EventRead[]>([]);
  const [missingItemCandidates, setMissingItemCandidates] = useState<MissingItemCandidateRead[]>([]);
  const [researchFindings, setResearchFindings] = useState<ResearchFindingRead[]>([]);
  const [detachedSourceItems, setDetachedSourceItems] = useState<DetachedSourceItemRead[]>([]);
  const [manualContradictionClaims, setManualContradictionClaims] = useState<ReviewReportItem[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentRead | null>(null);
  const [documentLifecycleReason, setDocumentLifecycleReason] = useState("");
  const [documentPages, setDocumentPages] = useState<DocumentPageRead[]>([]);
  const [documentChunks, setDocumentChunks] = useState<DocumentChunkRead[]>([]);
  const [analysisRunDetail, setAnalysisRunDetail] = useState<AnalysisRunDetail | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [caseName, setCaseName] = useState("");
  const [caseReference, setCaseReference] = useState("");
  const [importFiles, setImportFiles] = useState<File[]>([]);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const [documentListSearch, setDocumentListSearch] = useState("");
  const [activeSurface, setActiveSurface] = useState<WorkSurface>("document_organizer");
  const [assistantChats, setAssistantChats] = useState<AssistantChatListItem[]>([]);
  const [assistantActiveChatId, setAssistantActiveChatId] = useState("");
  const [assistantActiveChat, setAssistantActiveChat] = useState<AssistantChatDetail | null>(null);
  const [assistantDraft, setAssistantDraft] = useState("");
  const [assistantMenu, setAssistantMenu] = useState<{ chatId: string; left: number; top: number } | null>(null);
  const [assistantRenameDialog, setAssistantRenameDialog] = useState<{ chatId: string; currentTitle: string } | null>(null);
  const [assistantRenameDraft, setAssistantRenameDraft] = useState("");
  const [assistantPendingMessage, setAssistantPendingMessage] = useState<{ chatId: string; content: string } | null>(null);
  const [assistantRegeneratingChatId, setAssistantRegeneratingChatId] = useState("");
  const [assistantReasoningEnabled, setAssistantReasoningEnabled] = useState(false);
  const assistantMessageInFlightRef = useRef(false);
  const assistantMessageListRef = useRef<HTMLDivElement | null>(null);
  const assistantDraftRef = useRef<HTMLTextAreaElement | null>(null);
  const assistantRenameInputRef = useRef<HTMLInputElement | null>(null);
  const [fullDocumentId, setFullDocumentId] = useState("");
  const [fullDocumentProfile, setFullDocumentProfile] = useState("person_search_seeds");
  const [fullDocumentProfiles, setFullDocumentProfiles] = useState<FullDocumentProcessingProfileRead[]>([]);
  const [documentProcessingItems, setDocumentProcessingItems] = useState<DocumentProcessingItemRead[]>([]);
  const [fullDocumentAnswers, setFullDocumentAnswers] = useState<FullDocumentAnswerRead[]>([]);
  const [fullDocumentCurrentAnswer, setFullDocumentCurrentAnswer] = useState<FullDocumentAnswerRead | null>(null);
  const [fullDocumentQuestion, setFullDocumentQuestion] = useState("");
  const [fullDocumentWorkStatus, setFullDocumentWorkStatus] = useState<"active" | "set_aside">("active");
  const [documentProcessingItemSearch, setDocumentProcessingItemSearch] = useState("");
  const [documentProcessingItemsMarkedForDeletion, setDocumentProcessingItemsMarkedForDeletion] = useState<string[]>([]);
  const [lastFullDocumentRun, setLastFullDocumentRun] = useState<{
    validation_status: string;
    created_item_count: number;
    unsupported_count: number;
    unsupported_items: string[];
  } | null>(null);
  const [lastResearchFindingRun, setLastResearchFindingRun] = useState<ResearchFindingLatestRunSummary | null>(null);
  const [fullDocumentPageStart, setFullDocumentPageStart] = useState("1");
  const [fullDocumentPageEnd, setFullDocumentPageEnd] = useState("1");
  const [moduleKey, setModuleKey] = useState("search_findings");
  const [query, setQuery] = useState("");
  const [ragQuestion, setRagQuestion] = useState("");
  const [ragSourceMode, setRagSourceMode] = useState<RagSourceMode>("case");
  const [ragDocumentId, setRagDocumentId] = useState("");
  const [ragDocumentIds, setRagDocumentIds] = useState<string[]>([]);
  const [ragDocumentSearch, setRagDocumentSearch] = useState("");
  const [ragCollectionId, setRagCollectionId] = useState("");
  const [ragAnswerMode, setRagAnswerMode] = useState<RagAnswerMode>("detailed");
  const [ragRetrievalStrategy, setRagRetrievalStrategy] = useState<RetrievalStrategy>("hybrid");
  const [ragMaxChunks, setRagMaxChunks] = useState(45);
  const [ragCurrentResponse, setRagCurrentResponse] = useState<RagQueryResponse | null>(null);
  const [lastRagRun, setLastRagRun] = useState<RagLatestRunSummary | null>(null);
  const [ragSaveTitle, setRagSaveTitle] = useState("");
  const [ragSaveNote, setRagSaveNote] = useState("");
  const [ragSavedAnswers, setRagSavedAnswers] = useState<RagSavedAnswerListItem[]>([]);
  const [selectedRagAnswerId, setSelectedRagAnswerId] = useState("");
  const [selectedRagAnswer, setSelectedRagAnswer] = useState<RagSavedAnswerDetail | null>(null);
  const [ragForceReindex, setRagForceReindex] = useState(false);
  const [ragActiveIndexJobId, setRagActiveIndexJobId] = useState<string | null>(null);
  const [ragChunkIndexStatus, setRagChunkIndexStatus] = useState<ChunkIndexStatusResponse | null>(null);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocumentRead[]>([]);
  const knowledgeBatchInputRef = useRef<HTMLInputElement | null>(null);
  const [knowledgeBatchFiles, setKnowledgeBatchFiles] = useState<File[]>([]);
  const [knowledgeBatchRelativePath, setKnowledgeBatchRelativePath] = useState("");
  const [knowledgeBatchPreview, setKnowledgeBatchPreview] = useState<KnowledgeBatchPreviewResponse | null>(null);
  const [knowledgeBatchDecisions, setKnowledgeBatchDecisions] = useState<Record<string, KnowledgeBatchImportDecision>>({});
  const [knowledgeBatchImportResult, setKnowledgeBatchImportResult] = useState<KnowledgeBatchImportResponse | null>(null);
  const [knowledgeDocumentSearch, setKnowledgeDocumentSearch] = useState("");
  const [knowledgeQuestion, setKnowledgeQuestion] = useState("");
  const [knowledgeDocumentIds, setKnowledgeDocumentIds] = useState<string[]>([]);
  const [knowledgeAnswerMode, setKnowledgeAnswerMode] = useState<RagAnswerMode>("detailed");
  const [knowledgeRetrievalStrategy, setKnowledgeRetrievalStrategy] = useState<RetrievalStrategy>("hybrid");
  const [knowledgeMaxChunks, setKnowledgeMaxChunks] = useState(30);
  const [knowledgeForceReindex, setKnowledgeForceReindex] = useState(false);
  const [knowledgeIndexStatus, setKnowledgeIndexStatus] = useState<KnowledgeIndexStatusResponse | null>(null);
  const [knowledgeCurrentResponse, setKnowledgeCurrentResponse] = useState<KnowledgeQueryResponse | null>(null);
  const [knowledgeSourcesPanelOpen, setKnowledgeSourcesPanelOpen] = useState(false);
  const [knowledgeSourceSearch, setKnowledgeSourceSearch] = useState("");
  const [expandedKnowledgeSourceKeys, setExpandedKnowledgeSourceKeys] = useState<string[]>([]);
  const [knowledgeSourceDetails, setKnowledgeSourceDetails] = useState<Record<string, KnowledgeChunkDetail>>({});
  const [knowledgeSourceLoadingKeys, setKnowledgeSourceLoadingKeys] = useState<string[]>([]);
  const [knowledgeSourceErrors, setKnowledgeSourceErrors] = useState<Record<string, string>>({});
  const [relationshipGraphObjectType, setRelationshipGraphObjectType] = useState("");
  const [relationshipGraphFocusKeys, setRelationshipGraphFocusKeys] = useState<string[]>([]);
  const [relationshipGraphObjectSearch, setRelationshipGraphObjectSearch] = useState("");
  const [relationshipGraph, setRelationshipGraph] = useState<RelationshipGraph | null>(null);
  const [relationshipGraphLayers, setRelationshipGraphLayers] = useState<RelationshipGraphLayerState>(defaultRelationshipGraphLayers);
  const [selectedRelationshipEdgeId, setSelectedRelationshipEdgeId] = useState<string | null>(null);
  const [selectedRelationshipNodeId, setSelectedRelationshipNodeId] = useState<string | null>(null);
  const [analysisSourceMode, setAnalysisSourceMode] = useState<AnalysisSourceMode>("case");
  const [analysisDocumentId, setAnalysisDocumentId] = useState("");
  const [analysisDocumentIds, setAnalysisDocumentIds] = useState<string[]>([]);
  const [analysisCollectionId, setAnalysisCollectionId] = useState("");
  const [analysisDocumentSearch, setAnalysisDocumentSearch] = useState("");
  const [maxChunks, setMaxChunks] = useState(45);
  const [batchSize, setBatchSize] = useState(3);
  const [claimReviewScope, setClaimReviewScope] = useState<ClaimReviewScope>("reviewable");
  const [contradictionCandidateLimit, setContradictionCandidateLimit] = useState(5);
  const [retrievalStrategy, setRetrievalStrategy] = useState<RetrievalStrategy>("hybrid");
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
  const analysisPanelRef = useRef<HTMLElement | null>(null);
  const researchFindingsPanelRef = useRef<HTMLElement | null>(null);
  const ragSavedDetailPanelRef = useRef<HTMLElement | null>(null);
  const ragCurrentAnswerCardRef = useRef<HTMLElement | null>(null);
  const [ragCurrentAnswerHeight, setRagCurrentAnswerHeight] = useState(0);
  const [lastExport, setLastExport] = useState<ExportDetail | null>(null);
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});
  const [objectTextEdit, setObjectTextEdit] = useState({ title: "", description: "" });
  const [mergeTargets, setMergeTargets] = useState<Record<string, string>>({});
  const [sourceMoveTargets, setSourceMoveTargets] = useState<Record<string, string>>({});
  const [searchableSelectQueries, setSearchableSelectQueries] = useState<Record<string, string>>({});
  const [activeSearchableSelectKey, setActiveSearchableSelectKey] = useState("");
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
  const [manualSourceAttachType, setManualSourceAttachType] = useState<ManualObjectType>("claim");
  const [manualSourceAttachTargetId, setManualSourceAttachTargetId] = useState("");
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
  const [, setLastActionSummary] = useState("");
  const [lastAiOperation, setLastAiOperation] = useState<AiOperationStatus | null>(null);
  const [appDialog, setAppDialog] = useState<AppDialogState | null>(null);
  const [appDialogInput, setAppDialogInput] = useState("");
  const appDialogInputRef = useRef<HTMLInputElement | null>(null);
  const appDialogResolveRef = useRef<((value: AppDialogResult) => void) | null>(null);

  useEffect(() => {
    if (appDialog?.mode !== "text_confirm") return;
    window.requestAnimationFrame(() => {
      appDialogInputRef.current?.focus();
      appDialogInputRef.current?.select();
    });
  }, [appDialog]);

  useEffect(() => {
    if (!appDialog) return;

    function closeAppDialogWithKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        resolveAppDialog(null);
      }
    }

    window.addEventListener("keydown", closeAppDialogWithKeyboard);
    return () => window.removeEventListener("keydown", closeAppDialogWithKeyboard);
  }, [appDialog]);

  function openAppDialog(dialog: AppDialogState): Promise<AppDialogResult> {
    setAppDialogInput("");
    setAppDialog(dialog);
    return new Promise((resolve) => {
      appDialogResolveRef.current = resolve;
    });
  }

  async function requestAppConfirmation(dialog: Omit<AppDialogState, "mode">) {
    const result = await openAppDialog({ ...dialog, mode: "confirm" });
    return result === true;
  }

  async function requestAppTextConfirmation(dialog: Omit<AppDialogState, "mode">) {
    const result = await openAppDialog({ ...dialog, mode: "text_confirm" });
    return typeof result === "string" ? result : null;
  }

  function resolveAppDialog(result: AppDialogResult) {
    const resolver = appDialogResolveRef.current;
    appDialogResolveRef.current = null;
    setAppDialog(null);
    setAppDialogInput("");
    resolver?.(result);
  }

  function submitAppDialog() {
    if (!appDialog) return;
    if (appDialog.mode === "text_confirm") {
      resolveAppDialog(appDialogInput);
      return;
    }
    resolveAppDialog(true);
  }

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode;
    window.localStorage.setItem("boberdetective-theme", themeMode);
  }, [themeMode]);

  function toggleThemeMode() {
    setThemeMode((current) => (current === "dark" ? "light" : "dark"));
  }

  function handleSurfaceNavClick(surface: WorkSurface) {
    setActiveSurface(surface);
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  const selectedCase = useMemo(() => cases.find((item) => item.id === selectedCaseId), [cases, selectedCaseId]);
  const activeDocuments = useMemo(
    () => documents.filter((document) => document.lifecycle_status === "active"),
    [documents]
  );
  const analysisReadyDocuments = useMemo(
    () => activeDocuments.filter((document) => document.current_chunk_count > 0),
    [activeDocuments]
  );
  const selectedDocumentCollection = useMemo(
    () => documentCollections.find((collection) => collection.id === selectedDocumentCollectionId) ?? null,
    [documentCollections, selectedDocumentCollectionId]
  );
  const targetDocumentCollection = useMemo(
    () => documentCollections.find((collection) => collection.id === documentCollectionTargetId) ?? null,
    [documentCollections, documentCollectionTargetId]
  );
  const analysisDocumentCollection = useMemo(
    () => documentCollections.find((collection) => collection.id === analysisCollectionId) ?? null,
    [documentCollections, analysisCollectionId]
  );
  const ragDocument = useMemo(
    () => analysisReadyDocuments.find((document) => document.id === ragDocumentId) ?? null,
    [analysisReadyDocuments, ragDocumentId]
  );
  const ragCollection = useMemo(
    () => documentCollections.find((collection) => collection.id === ragCollectionId) ?? null,
    [documentCollections, ragCollectionId]
  );
  const filteredRagCaseDocuments = useMemo(
    () => filterDocumentsByName(analysisReadyDocuments, ragDocumentSearch),
    [analysisReadyDocuments, ragDocumentSearch]
  );
  const filteredKnowledgeDocuments = useMemo(
    () => filterKnowledgeDocuments(knowledgeDocuments, knowledgeDocumentSearch),
    [knowledgeDocuments, knowledgeDocumentSearch]
  );
  const targetCollectionDocumentIds = useMemo(
    () => new Set(documentCollectionTargetDocuments.map((document) => document.id)),
    [documentCollectionTargetDocuments]
  );
  const documentCollectionTargetOptions = useMemo(
    () =>
      documentCollections.map((collection) => ({
        id: collection.id,
        label: `${collection.name} (${collection.active_document_count}/${collection.document_count})`,
        searchText: `${collection.name} ${collection.description ?? ""}`
      })),
    [documentCollections]
  );
  const filteredSelectedDocumentCollectionDocuments = useMemo(
    () => filterDocumentsByName(selectedDocumentCollectionDocuments, documentCollectionContentSearch),
    [selectedDocumentCollectionDocuments, documentCollectionContentSearch]
  );
  const fullDocumentOptions = useMemo(
    () =>
      activeDocuments.map((document) => ({
        id: document.id,
        label: `${document.original_filename} (${document.page_count ?? 0} oldal, ${labelProcessingStatus(document.processing_status)})`,
        searchText: `${document.original_filename} ${document.sha256_hash}`
      })),
    [activeDocuments]
  );
  const selectedFullDocument = useMemo(
    () => activeDocuments.find((document) => document.id === fullDocumentId) ?? null,
    [activeDocuments, fullDocumentId]
  );
  const selectedFullDocumentProfile = useMemo(
    () => fullDocumentProfiles.find((profile) => profile.key === fullDocumentProfile) ?? null,
    [fullDocumentProfiles, fullDocumentProfile]
  );
  const fullDocumentProfileIsFreeQuestion = fullDocumentProfile === "free_document_question";
  const fullDocumentMaxPage = Math.max(1, selectedFullDocument?.page_count ?? 1);
  const fullDocumentPageStartNumber = Number(fullDocumentPageStart);
  const fullDocumentPageEndNumber = Number(fullDocumentPageEnd);
  const fullDocumentPageRangeValid =
    Number.isInteger(fullDocumentPageStartNumber) &&
    Number.isInteger(fullDocumentPageEndNumber) &&
    fullDocumentPageStartNumber >= 1 &&
    fullDocumentPageEndNumber >= 1 &&
    fullDocumentPageStartNumber <= fullDocumentPageEndNumber &&
    fullDocumentPageEndNumber <= fullDocumentMaxPage;
  const selectedAnalysisDocument = useMemo(
    () => analysisReadyDocuments.find((item) => item.id === analysisDocumentId) ?? null,
    [analysisReadyDocuments, analysisDocumentId]
  );
  const selectedDocumentIsActive = selectedDocument?.lifecycle_status === "active";
  const canAttemptSelectedDocumentDiscard = Boolean(selectedDocumentIsActive && documentChunks.length === 0);
  const filteredDocuments = useMemo(
    () => filterDocumentsByName(documents, documentListSearch),
    [documents, documentListSearch]
  );
  const visibleDocumentIds = useMemo(() => filteredDocuments.map((document) => document.id), [filteredDocuments]);
  const visibleMarkedDocumentIds = useMemo(
    () => visibleDocumentIds.filter((documentId) => documentCollectionMarkedDocumentIds.includes(documentId)),
    [visibleDocumentIds, documentCollectionMarkedDocumentIds]
  );
  const allVisibleDocumentsMarked =
    visibleDocumentIds.length > 0 &&
    visibleDocumentIds.every((documentId) => documentCollectionMarkedDocumentIds.includes(documentId));
  const selectedCollectionVisibleDocumentIds = useMemo(
    () => filteredSelectedDocumentCollectionDocuments.map((document) => document.id),
    [filteredSelectedDocumentCollectionDocuments]
  );
  const selectedCollectionVisibleMarkedDocumentIds = useMemo(
    () => selectedCollectionVisibleDocumentIds.filter((documentId) => selectedDocumentCollectionMarkedDocumentIds.includes(documentId)),
    [selectedCollectionVisibleDocumentIds, selectedDocumentCollectionMarkedDocumentIds]
  );
  const filteredCaseAnalysisDocuments = useMemo(
    () => filterDocumentsByName(analysisReadyDocuments, analysisDocumentSearch),
    [analysisReadyDocuments, analysisDocumentSearch]
  );
  const filteredDocumentAnalysisDocuments = useMemo(
    () => filterDocumentsByName(analysisReadyDocuments, analysisDocumentSearch),
    [analysisReadyDocuments, analysisDocumentSearch]
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
  const showCaseDocumentFilters = canUseBatchScope && effectiveAnalysisSourceMode === "case";
  const requiresFocusText = true;
  const usesSemanticIndex = canUseBatchScope && retrievalStrategy !== "keyword" && query.trim().length > 0;
  const semanticIndexReady = !usesSemanticIndex || Boolean(chunkIndexStatus?.is_ready);
  const indexJobIsRunning = chunkIndexStatus?.latest_run_status === "running";
  const hasAnalysisSource =
    effectiveAnalysisSourceMode === "document"
      ? Boolean(analysisDocumentId)
      : effectiveAnalysisSourceMode === "collection"
        ? Boolean(analysisCollectionId) && Boolean(analysisDocumentCollection?.active_document_count)
        : analysisReadyDocuments.length > 0;
  const busyLabel = busy ? (busyLabels[busy] ?? busy) : "Keszenlet";
  const canRunAnalysis =
    Boolean(selectedCaseId) &&
    !busy &&
    (!requiresFocusText || query.trim().length > 0) &&
    hasAnalysisSource &&
    semanticIndexReady;
  const ragHasSource =
    ragSourceMode === "document"
      ? Boolean(ragDocumentId)
      : ragSourceMode === "collection"
        ? Boolean(ragCollectionId) && Boolean(ragCollection?.active_document_count)
        : analysisReadyDocuments.length > 0;
  const ragUsesSemanticIndex = ragRetrievalStrategy !== "keyword" && ragQuestion.trim().length > 0;
  const ragIndexJobIsRunning = ragChunkIndexStatus?.latest_run_status === "running";
  const canRunRagQuery = Boolean(selectedCaseId) && !busy && ragQuestion.trim().length > 0 && ragHasSource;
  const activeKnowledgeDocuments = useMemo(
    () => knowledgeDocuments.filter((document) => document.processing_status !== "archived"),
    [knowledgeDocuments]
  );
  const selectedKnowledgeDocuments = useMemo(
    () => knowledgeDocuments.filter((document) => knowledgeDocumentIds.includes(document.id)),
    [knowledgeDocuments, knowledgeDocumentIds]
  );
  const selectedActiveKnowledgeDocuments = useMemo(
    () => selectedKnowledgeDocuments.filter((document) => document.processing_status !== "archived"),
    [selectedKnowledgeDocuments]
  );
  const canRunKnowledgeQuery =
    !busy &&
    knowledgeQuestion.trim().length > 0 &&
    activeKnowledgeDocuments.length > 0 &&
    (knowledgeRetrievalStrategy === "keyword" || Boolean(knowledgeIndexStatus?.is_ready));
  const showKnowledgeIndexMissingError =
    knowledgeQuestion.trim().length > 0 &&
    knowledgeRetrievalStrategy !== "keyword" &&
    Boolean(knowledgeIndexStatus) &&
    !knowledgeIndexStatus?.is_ready;
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
  const relationshipObjectCandidates = useMemo(() => {
    if (!report) return [];
    const queryText = relationshipGraphObjectSearch.trim().toLocaleLowerCase("hu-HU");
    return report.items.filter((item) => {
      if (relationshipGraphObjectType && item.object_type !== relationshipGraphObjectType) return false;
      if (item.source_validation_status !== "source_valid") return false;
      return !queryText || reportItemMatchesSearch(item, queryText);
    });
  }, [relationshipGraphObjectSearch, relationshipGraphObjectType, report]);
  const relationshipVisibleCandidateKeys = useMemo(
    () => relationshipObjectCandidates.map((item) => relationshipFocusKey(item.object_type, item.object_id)),
    [relationshipObjectCandidates]
  );
  const selectedRelationshipFocusObjects = useMemo<RelationshipGraphFocusObject[]>(() => {
    if (!report) return [];
    const selectedKeys = new Set(relationshipGraphFocusKeys);
    return report.items
      .filter((item) => selectedKeys.has(relationshipFocusKey(item.object_type, item.object_id)))
      .filter((item) => item.source_validation_status === "source_valid")
      .map((item) => ({ object_type: item.object_type, object_id: item.object_id }));
  }, [relationshipGraphFocusKeys, report]);
  const selectedRelationshipFocusCount = selectedRelationshipFocusObjects.length;
  const relationshipFocusLimitReached = selectedRelationshipFocusCount >= maxRelationshipFocusObjects;
  const selectedRelationshipFocusLabels = useMemo(
    () =>
      selectedRelationshipFocusObjects
        .map((focus) => labelObjectType(focus.object_type))
        .reduce<Record<string, number>>((accumulator, label) => {
          accumulator[label] = (accumulator[label] ?? 0) + 1;
          return accumulator;
        }, {}),
    [selectedRelationshipFocusObjects]
  );
  const selectedVisibleRelationshipFocusCount = useMemo(() => {
    const selectedKeys = new Set(relationshipGraphFocusKeys);
    return relationshipVisibleCandidateKeys.filter((key) => selectedKeys.has(key)).length;
  }, [relationshipGraphFocusKeys, relationshipVisibleCandidateKeys]);
  const visibleRelationshipGraph = useMemo(
    () => filterRelationshipGraphByLayers(relationshipGraph, relationshipGraphLayers),
    [relationshipGraph, relationshipGraphLayers]
  );
  const analysisHistoryCounts = useMemo(
    () => ({
      search_findings: analysisRuns.filter((run) => run.run_type === "search_findings").length,
      manual_entry: analysisRuns.filter((run) => run.run_type === "manual_entry").length
    }),
    [analysisRuns]
  );
  const visibleAnalysisRuns = useMemo(
    () => analysisRuns.filter((run) => run.run_type === analysisHistoryKind),
    [analysisRuns, analysisHistoryKind]
  );
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
  const markableResearchFindingIds = useMemo(
    () => visibleResearchFindings.filter((finding) => finding.conversion_status !== "converted").map((finding) => finding.id),
    [visibleResearchFindings]
  );
  const allVisibleResearchFindingsMarked =
    markableResearchFindingIds.length > 0 &&
    markableResearchFindingIds.every((findingId) => researchFindingsMarkedForDeletion.includes(findingId));
  const visibleDocumentProcessingItems = useMemo(
    () => filterDocumentProcessingItemsByName(documentProcessingItems, documentProcessingItemSearch),
    [documentProcessingItems, documentProcessingItemSearch]
  );
  const markedDocumentProcessingItemCount = documentProcessingItemsMarkedForDeletion.length;
  const markableDocumentProcessingItemIds = useMemo(
    () => visibleDocumentProcessingItems.filter((item) => item.work_status !== "converted").map((item) => item.id),
    [visibleDocumentProcessingItems]
  );
  const allVisibleDocumentProcessingItemsMarked =
    markableDocumentProcessingItemIds.length > 0 &&
    markableDocumentProcessingItemIds.every((itemId) => documentProcessingItemsMarkedForDeletion.includes(itemId));

  useEffect(() => {
    void refreshCases();
    void refreshFullDocumentProfiles();
    void refreshLlmSmoke(false);
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      void refreshCaseData(false);
    } else {
      setDocuments([]);
      setDocumentCollections([]);
      setSelectedDocumentCollectionId("");
      setSelectedDocumentCollectionDocuments([]);
      setSelectedDocumentCollectionMarkedDocumentIds([]);
      setDocumentCollectionContentSearch("");
      setAnalysisCollectionId("");
      setDocumentCollectionTargetId("");
      setDocumentCollectionTargetDocuments([]);
      setDocumentCollectionMarkedDocumentIds([]);
      setDocumentCollectionScopePreview(null);
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
      setDocumentProcessingItems([]);
      setDocumentProcessingItemsMarkedForDeletion([]);
      setLastFullDocumentRun(null);
      setLastResearchFindingRun(null);
      setRagCurrentResponse(null);
      setRagSavedAnswers([]);
      setSelectedRagAnswerId("");
      setSelectedRagAnswer(null);
      setRagSaveTitle("");
      setRagSaveNote("");
    }
  }, [selectedCaseId]);

  useEffect(() => {
    if (documentCollections.length === 0) {
      setSelectedDocumentCollectionId("");
      setSelectedDocumentCollectionDocuments([]);
      setSelectedDocumentCollectionMarkedDocumentIds([]);
      setDocumentCollectionContentSearch("");
      setAnalysisCollectionId("");
      setDocumentCollectionTargetId("");
      setDocumentCollectionTargetDocuments([]);
      setDocumentCollectionMarkedDocumentIds([]);
      setDocumentCollectionScopePreview(null);
      return;
    }
    if (selectedDocumentCollectionId && !documentCollections.some((collection) => collection.id === selectedDocumentCollectionId)) {
      setSelectedDocumentCollectionId("");
      setSelectedDocumentCollectionDocuments([]);
      setSelectedDocumentCollectionMarkedDocumentIds([]);
      setDocumentCollectionScopePreview(null);
    }
  }, [documentCollections, selectedDocumentCollectionId]);

  useEffect(() => {
    if (!selectedCaseId || !selectedDocumentCollectionId) {
      setSelectedDocumentCollectionDocuments([]);
      setSelectedDocumentCollectionMarkedDocumentIds([]);
      return;
    }
    void refreshSelectedDocumentCollectionDocuments(false);
  }, [selectedCaseId, selectedDocumentCollectionId]);

  useEffect(() => {
    if (analysisCollectionId && !documentCollections.some((collection) => collection.id === analysisCollectionId)) {
      setAnalysisCollectionId("");
    }
  }, [analysisCollectionId, documentCollections]);

  useEffect(() => {
    if (documentCollectionTargetId && !documentCollections.some((collection) => collection.id === documentCollectionTargetId)) {
      setDocumentCollectionTargetId("");
      setDocumentCollectionTargetDocuments([]);
    }
  }, [documentCollections, documentCollectionTargetId]);

  useEffect(() => {
    if (!selectedCaseId || !documentCollectionTargetId) {
      setDocumentCollectionTargetDocuments([]);
      return;
    }
    void refreshDocumentCollectionTargetDocuments(false);
  }, [selectedCaseId, documentCollectionTargetId]);

  useEffect(() => {
    const documentIds = new Set(documents.map((document) => document.id));
    setDocumentCollectionMarkedDocumentIds((current) => current.filter((documentId) => documentIds.has(documentId)));
    setSelectedDocumentCollectionMarkedDocumentIds((current) => current.filter((documentId) => documentIds.has(documentId)));
  }, [documents]);

  useEffect(() => {
    if (fullDocumentProfiles.length === 0) return;
    if (!fullDocumentProfiles.some((profile) => profile.key === fullDocumentProfile)) {
      setFullDocumentProfile(fullDocumentProfiles[0].key);
    }
  }, [fullDocumentProfiles, fullDocumentProfile]);

  useEffect(() => {
    if (fullDocumentId && !activeDocuments.some((document) => document.id === fullDocumentId)) {
      setFullDocumentId("");
      setDocumentProcessingItems([]);
      setDocumentProcessingItemsMarkedForDeletion([]);
      setFullDocumentAnswers([]);
      setFullDocumentCurrentAnswer(null);
    }
  }, [activeDocuments, fullDocumentId]);

  useEffect(() => {
    if (!selectedFullDocument) {
      setFullDocumentPageStart("1");
      setFullDocumentPageEnd("1");
      return;
    }
    setFullDocumentPageStart("1");
    setFullDocumentPageEnd(String(Math.max(1, selectedFullDocument.page_count ?? 1)));
  }, [selectedFullDocument?.id, selectedFullDocument?.page_count]);

  useEffect(() => {
    if (!selectedCaseId || !fullDocumentId) {
      setDocumentProcessingItems([]);
      setDocumentProcessingItemsMarkedForDeletion([]);
      setFullDocumentAnswers([]);
      setFullDocumentCurrentAnswer(null);
      return;
    }
    if (fullDocumentProfileIsFreeQuestion) {
      setDocumentProcessingItems([]);
      setDocumentProcessingItemsMarkedForDeletion([]);
      void refreshFullDocumentAnswers(false);
      return;
    }
    setFullDocumentAnswers([]);
    setFullDocumentCurrentAnswer(null);
    void refreshFullDocumentItems(false);
  }, [selectedCaseId, fullDocumentId, fullDocumentProfile, fullDocumentWorkStatus, fullDocumentProfileIsFreeQuestion]);

  useEffect(() => {
    const visibleIds = new Set(documentProcessingItems.map((item) => item.id));
    setDocumentProcessingItemsMarkedForDeletion((current) => current.filter((itemId) => visibleIds.has(itemId)));
  }, [documentProcessingItems]);

  useEffect(() => {
    setObjectTextEdit({
      title: selectedReportItem?.title ?? "",
      description: selectedReportItem?.body_text ?? "",
    });
  }, [selectedReportItem?.object_id, selectedReportItem?.title, selectedReportItem?.body_text]);

  useEffect(() => {
    if (analysisDocumentId && !analysisReadyDocuments.some((item) => item.id === analysisDocumentId)) {
      setAnalysisDocumentId("");
    }
  }, [analysisReadyDocuments, analysisDocumentId]);

  useEffect(() => {
    if (ragDocumentId && !analysisReadyDocuments.some((item) => item.id === ragDocumentId)) {
      setRagDocumentId("");
    }
    const validDocumentIds = new Set(analysisReadyDocuments.map((item) => item.id));
    setRagDocumentIds((current) => current.filter((documentId) => validDocumentIds.has(documentId)));
  }, [analysisReadyDocuments, ragDocumentId]);

  useEffect(() => {
    if (ragCollectionId && !documentCollections.some((item) => item.id === ragCollectionId)) {
      setRagCollectionId("");
    }
  }, [documentCollections, ragCollectionId]);

  useEffect(() => {
    if (selectedRagAnswerId && !ragSavedAnswers.some((item) => item.id === selectedRagAnswerId)) {
      setSelectedRagAnswerId("");
      setSelectedRagAnswer(null);
    }
  }, [ragSavedAnswers, selectedRagAnswerId]);

  useEffect(() => {
    if (activeSurface !== "knowledge_base") return;
    void refreshKnowledgeDocuments(false);
    void refreshKnowledgeIndexStatus(false);
  }, [activeSurface]);

  useEffect(() => {
    if (activeSurface !== "ai_assistant") return;
    void refreshAssistantChats(false);
  }, [activeSurface]);

  useEffect(() => {
    if (!assistantMenu) return;

    function closeAssistantMenu(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest(".assistant-history-menu-popover") || target.closest(".assistant-history-menu-button")) return;
      setAssistantMenu(null);
    }

    function closeAssistantMenuWithKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setAssistantMenu(null);
      }
    }

    window.addEventListener("pointerdown", closeAssistantMenu);
    window.addEventListener("keydown", closeAssistantMenuWithKeyboard);
    return () => {
      window.removeEventListener("pointerdown", closeAssistantMenu);
      window.removeEventListener("keydown", closeAssistantMenuWithKeyboard);
    };
  }, [assistantMenu]);


  useEffect(() => {
    if (!assistantRenameDialog) return;
    window.requestAnimationFrame(() => {
      assistantRenameInputRef.current?.focus();
      assistantRenameInputRef.current?.select();
    });
  }, [assistantRenameDialog]);

  useEffect(() => {
    if (!assistantRenameDialog) return;

    function closeAssistantRenameWithKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setAssistantRenameDialog(null);
        setAssistantRenameDraft("");
      }
    }

    window.addEventListener("keydown", closeAssistantRenameWithKeyboard);
    return () => window.removeEventListener("keydown", closeAssistantRenameWithKeyboard);
  }, [assistantRenameDialog]);


  useEffect(() => {
    const element = assistantMessageListRef.current;
    if (!element) return;
    window.requestAnimationFrame(() => {
      element.scrollTop = element.scrollHeight;
    });
  }, [assistantActiveChat?.id, assistantActiveChat?.messages.length, assistantPendingMessage?.content]);

  useEffect(() => {
    const element = assistantDraftRef.current;
    if (!element) return;
    const minHeight = 38;
    const maxHeight = 176;
    element.style.height = "auto";
    const nextHeight = Math.min(Math.max(element.scrollHeight, minHeight), maxHeight);
    element.style.height = nextHeight + "px";
    element.style.overflowY = element.scrollHeight > maxHeight + 1 ? "auto" : "hidden";
  }, [activeSurface, assistantDraft]);

  useEffect(() => {
    const validIds = new Set(knowledgeDocuments.map((document) => document.id));
    setKnowledgeDocumentIds((current) => current.filter((documentId) => validIds.has(documentId)));
  }, [knowledgeDocuments]);

  useEffect(() => {
    const allowedIds = new Set(analysisReadyDocuments.map((document) => document.id));
    setAnalysisDocumentIds((current) => current.filter((documentId) => allowedIds.has(documentId)));
  }, [analysisReadyDocuments]);

  useEffect(() => {
    const deletableIds = new Set(
      researchFindings
        .filter((finding) => finding.conversion_status !== "converted")
        .map((finding) => finding.id)
    );
    setResearchFindingsMarkedForDeletion((current) => current.filter((findingId) => deletableIds.has(findingId)));
  }, [researchFindings]);

  useEffect(() => {
    if (!selectedCaseId || !canUseBatchScope) {
      setChunkIndexStatus(null);
      return;
    }
    if (effectiveAnalysisSourceMode === "document" && !analysisDocumentId) {
      setChunkIndexStatus(null);
      return;
    }
    if (effectiveAnalysisSourceMode === "collection" && !analysisCollectionId) {
      setChunkIndexStatus(null);
      return;
    }
    void refreshChunkIndexStatus().catch(() => setChunkIndexStatus(null));
  }, [selectedCaseId, canUseBatchScope, effectiveAnalysisSourceMode, analysisDocumentId, analysisDocumentIds, analysisCollectionId, retrievalStrategy, query]);

  useEffect(() => {
    if (!selectedCaseId) {
      setRagChunkIndexStatus(null);
      return;
    }
    if (ragSourceMode === "document" && !ragDocumentId) {
      setRagChunkIndexStatus(null);
      return;
    }
    if (ragSourceMode === "collection" && !ragCollectionId) {
      setRagChunkIndexStatus(null);
      return;
    }
    void refreshRagChunkIndexStatus().catch(() => setRagChunkIndexStatus(null));
  }, [selectedCaseId, ragSourceMode, ragDocumentId, ragDocumentIds, ragCollectionId]);

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
  }, [selectedCaseId, activeIndexJobId, effectiveAnalysisSourceMode, analysisDocumentId, analysisDocumentIds, analysisCollectionId]);

  useEffect(() => {
    if (!selectedCaseId || !ragActiveIndexJobId) {
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await refreshRagChunkIndexStatus();
        const runsResponse = await listAnalysisRuns(selectedCaseId);
        if (cancelled) return;
        setAnalysisRuns(runsResponse.data);
        if (response?.latest_run_id === ragActiveIndexJobId && response.latest_run_status && response.latest_run_status !== "running") {
          setRagActiveIndexJobId(null);
          setNotice(response.latest_run_status === "succeeded" ? "Iratkérdező indexelés befejeződött." : "Iratkérdező indexelés hibával leállt.");
          setLastActionSummary(
            `Iratkerdezo indexeles: ${labelRunStatus(response.latest_run_status)}, ${response.latest_run_output_count}/${response.latest_run_input_count} szovegresz`
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Iratkérdező indexállapot lekérdezése sikertelen.");
        }
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selectedCaseId, ragActiveIndexJobId, ragSourceMode, ragDocumentId, ragCollectionId]);

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

  useEffect(() => {
    if (!ragCurrentResponse || !ragCurrentAnswerCardRef.current) {
      setRagCurrentAnswerHeight(0);
      return;
    }
    const element = ragCurrentAnswerCardRef.current;
    const updateHeight = () => setRagCurrentAnswerHeight(element.getBoundingClientRect().height);
    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ragCurrentResponse]);


  async function perform(label: string, action: () => Promise<void>) {
    const startedAt = Date.now();
    const tracksAiOperation = aiOperationLabels.has(label);
    setBusy(label);
    setBusyStartedAt(startedAt);
    setError("");
    setNotice("");
    try {
      await action();
      if (tracksAiOperation) {
        setLastAiOperation({
          label: busyLabels[label] ?? label,
          status: "succeeded",
          durationSeconds: Math.max(0, Math.round((Date.now() - startedAt) / 1000))
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ismeretlen hiba");
      if (tracksAiOperation) {
        setLastAiOperation({
          label: busyLabels[label] ?? label,
          status: "failed",
          durationSeconds: Math.max(0, Math.round((Date.now() - startedAt) / 1000))
        });
      }
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

  async function refreshFullDocumentProfiles() {
    try {
      const response = await listFullDocumentProcessingProfiles();
      setFullDocumentProfiles(response.data);
      if (response.data[0] && !response.data.some((profile) => profile.key === fullDocumentProfile)) {
        setFullDocumentProfile(response.data[0].key);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Teljes iratfeldolgozási profilok betöltése sikertelen.");
    }
  }

  async function refreshAssistantChats(showNotice = false) {
    const action = async () => {
      const response = await listAssistantChats();
      setAssistantChats(response.data);
      if (showNotice) {
        setNotice("AI-asszisztens beszélgetések frissítve.");
        setLastActionSummary(String(response.data.length) + " beszélgetés.");
      }
      return response.data;
    };
    if (showNotice) {
      let data: AssistantChatListItem[] = [];
      await perform("assistant-chats", async () => {
        data = await action();
      });
      return data;
    }
    try {
      return await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI-asszisztens beszélgetések betöltése sikertelen.");
      return [];
    }
  }

  async function handleCreateAssistantChat() {
    await perform("assistant-chat-create", async () => {
      const chat = await createAssistantChat({});
      setAssistantActiveChat(chat);
      setAssistantActiveChatId(chat.id);
      setAssistantDraft("");
      setAssistantMenu(null);
      await refreshAssistantChats(false);
      setNotice("Új AI-asszisztens beszélgetés létrehozva.");
    });
  }

  async function handleLoadAssistantChat(chatId: string) {
    await perform("assistant-chat-load", async () => {
      const chat = await getAssistantChat(chatId);
      setAssistantActiveChat(chat);
      setAssistantActiveChatId(chat.id);
      setAssistantMenu(null);
    });
  }

  async function handleDeleteAssistantChat(chat: AssistantChatListItem) {
    const confirmed = await requestAppConfirmation({
      title: "Beszélgetés törlése",
      message: "Törlöd ezt a beszélgetést?",
      detail: chat.title,
      confirmLabel: "Törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("assistant-chat-delete", async () => {
      setAssistantMenu(null);
      await deleteAssistantChat(chat.id);
      const remainingChats = await refreshAssistantChats(false);
      if (assistantActiveChatId === chat.id) {
        setAssistantDraft("");
        setAssistantPendingMessage(null);
        setAssistantRegeneratingChatId("");
        const nextChat = remainingChats[0];
        if (nextChat) {
          const nextChatDetail = await getAssistantChat(nextChat.id);
          setAssistantActiveChat(nextChatDetail);
          setAssistantActiveChatId(nextChatDetail.id);
        } else {
          setAssistantActiveChat(null);
          setAssistantActiveChatId("");
        }
      }
      setNotice("AI-asszisztens beszélgetés törölve.");
    });
  }

  function openAssistantRenameDialog(chat: AssistantChatListItem) {
    setAssistantMenu(null);
    setAssistantRenameDialog({ chatId: chat.id, currentTitle: chat.title });
    setAssistantRenameDraft(chat.title);
  }

  function closeAssistantRenameDialog() {
    setAssistantRenameDialog(null);
    setAssistantRenameDraft("");
  }

  async function handleRenameAssistantChat() {
    if (!assistantRenameDialog) return;
    const title = assistantRenameDraft.trim();
    if (!title || title === assistantRenameDialog.currentTitle) {
      closeAssistantRenameDialog();
      return;
    }
    const chatId = assistantRenameDialog.chatId;
    await perform("assistant-chat-load", async () => {
      const updatedChat = await updateAssistantChat(chatId, { title });
      if (assistantActiveChatId === chatId) {
        setAssistantActiveChat(updatedChat);
        setAssistantActiveChatId(updatedChat.id);
      }
      await refreshAssistantChats(false);
      closeAssistantRenameDialog();
      setNotice("Beszélgetés címe mentve.");
    });
  }

  async function handleCopyAssistantMessage(message: AssistantMessageRead) {
    try {
      await navigator.clipboard.writeText(message.content);
      setNotice("AI-asszisztens válasz másolva.");
    } catch {
      setError("A válasz másolása nem sikerült.");
    }
  }

  async function handleRegenerateLastAssistantMessage() {
    if (!assistantActiveChatId || assistantMessageInFlightRef.current) return;
    const currentChat = assistantActiveChat;
    const messages = currentChat?.messages ?? [];
    const lastMessage = messages[messages.length - 1];
    if (!currentChat || lastMessage?.role !== "assistant") return;
    assistantMessageInFlightRef.current = true;
    setAssistantRegeneratingChatId(currentChat.id);
    setAssistantActiveChat({ ...currentChat, messages: messages.slice(0, -1) });
    try {
      await perform("assistant-message", async () => {
        try {
          const response = await regenerateLastAssistantMessage(currentChat.id, {
            reasoning_mode: assistantReasoningEnabled ? "model_default" : "normal"
          });
          setAssistantActiveChat(response.chat);
          setAssistantActiveChatId(response.chat.id);
          await refreshAssistantChats(false);
          setNotice("AI-asszisztens válasz újragenerálva.");
          setLastActionSummary(response.chat.title);
        } catch (err) {
          setAssistantActiveChat(currentChat);
          throw err;
        } finally {
          setAssistantRegeneratingChatId("");
        }
      });
    } finally {
      assistantMessageInFlightRef.current = false;
    }
  }

  async function handleSendAssistantMessage() {
    const content = assistantDraft.trim();
    if (!content || assistantMessageInFlightRef.current) return;
    assistantMessageInFlightRef.current = true;
    setAssistantDraft("");
    try {
      await perform("assistant-message", async () => {
        let chat = assistantActiveChat;
        if (!chat) {
          chat = await createAssistantChat({});
          setAssistantActiveChat(chat);
          setAssistantActiveChatId(chat.id);
        }
        setAssistantPendingMessage({ chatId: chat.id, content });
        try {
          const response = await sendAssistantMessage(chat.id, {
            content,
            reasoning_mode: assistantReasoningEnabled ? "model_default" : "normal"
          });
          setAssistantActiveChat(response.chat);
          setAssistantActiveChatId(response.chat.id);
          await refreshAssistantChats(false);
          setNotice("AI-asszisztens válasz elkészült.");
        } finally {
          setAssistantPendingMessage(null);
        }
      });
    } finally {
      assistantMessageInFlightRef.current = false;
    }
  }

  async function refreshRagAnswers(showNotice = false) {
    if (!selectedCaseId) return;
    const action = async () => {
      const response = await listRagAnswers(selectedCaseId);
      setRagSavedAnswers(response.data);
      if (showNotice) {
        setNotice("Mentett iratkérdező válaszok frissítve.");
        setLastActionSummary(`${response.data.length} mentett válasz.`);
      }
    };
    if (showNotice) {
      await perform("rag-answers", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Mentett iratkérdező válaszok betöltése sikertelen.");
      }
    }
  }

  async function refreshKnowledgeDocuments(showNotice = false) {
    const action = async () => {
      const response = await listKnowledgeDocuments();
      setKnowledgeDocuments(response.data);
      if (showNotice) {
        setNotice("Tudásbázis dokumentumok frissítve.");
        setLastActionSummary(`${response.data.length} tudásbázis dokumentum.`);
      }
    };
    if (showNotice) {
      await perform("knowledge-documents", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Tudásbázis dokumentumok betöltése sikertelen.");
      }
    }
  }

  async function refreshKnowledgeIndexStatus(showNotice = false): Promise<KnowledgeIndexStatusResponse | null> {
    const action = async () => {
      const response = await getKnowledgeIndexStatus();
      setKnowledgeIndexStatus(response);
      if (showNotice) {
        setNotice("Tudásbázis indexállapot frissítve.");
        setLastActionSummary(`Indexelve: ${response.indexed_chunk_count}/${response.chunk_count} tudásbázis szövegrész.`);
      }
      return response;
    };
    if (showNotice) {
      let response: KnowledgeIndexStatusResponse | null = null;
      await perform("knowledge-index-status", async () => {
        response = await action();
      });
      return response;
    }
    try {
      return await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tudásbázis indexállapot lekérdezése sikertelen.");
      return null;
    }
  }

  function knowledgeSourceKey(source: KnowledgeUsedSource) {
    return `${source.knowledge_document_id}:${source.chunk_id}`;
  }

  async function toggleKnowledgeSource(source: KnowledgeUsedSource) {
    const key = knowledgeSourceKey(source);
    if (expandedKnowledgeSourceKeys.includes(key)) {
      setExpandedKnowledgeSourceKeys((current) => current.filter((item) => item !== key));
      return;
    }
    setExpandedKnowledgeSourceKeys((current) => (current.includes(key) ? current : [...current, key]));
    if (knowledgeSourceDetails[key] || knowledgeSourceLoadingKeys.includes(key)) {
      return;
    }
    setKnowledgeSourceLoadingKeys((current) => (current.includes(key) ? current : [...current, key]));
    setKnowledgeSourceErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    try {
      const detail = await getKnowledgeDocumentChunk(source.knowledge_document_id, source.chunk_id);
      setKnowledgeSourceDetails((current) => ({ ...current, [key]: detail }));
    } catch (err) {
      setKnowledgeSourceErrors((current) => ({
        ...current,
        [key]: err instanceof Error ? err.message : "A Markdown forrásszövegrész betöltése sikertelen."
      }));
    } finally {
      setKnowledgeSourceLoadingKeys((current) => current.filter((item) => item !== key));
    }
  }

  async function refreshDocumentCollections(showNotice = false) {
    if (!selectedCaseId) return;
    const action = async () => {
      const response = await listDocumentCollections(selectedCaseId);
      setDocumentCollections(response.data);
      if (showNotice) {
        setNotice("Iratgyűjtemények frissítve.");
        setLastActionSummary(`${response.data.length} iratgyűjtemény.`);
      }
    };
    if (showNotice) {
      await perform("document-collections", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Iratgyűjtemények betöltése sikertelen.");
      }
    }
  }

  async function refreshSelectedDocumentCollectionDocuments(showNotice = false) {
    if (!selectedCaseId || !selectedDocumentCollectionId) return;
    const action = async () => {
      const response = await listDocumentCollectionDocuments(selectedCaseId, selectedDocumentCollectionId);
      setSelectedDocumentCollectionDocuments(response.data);
      setSelectedDocumentCollectionMarkedDocumentIds((current) =>
        current.filter((documentId) => response.data.some((document) => document.id === documentId))
      );
      if (showNotice) {
        setNotice("Gyűjtemény tartalma frissítve.");
        setLastActionSummary(`${response.data.length} irat a kiválasztott gyűjteményben.`);
      }
    };
    if (showNotice) {
      await perform("document-collections", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Gyűjtemény tartalmának betöltése sikertelen.");
      }
    }
  }

  async function refreshDocumentCollectionTargetDocuments(showNotice = false) {
    if (!selectedCaseId || !documentCollectionTargetId) return;
    const action = async () => {
      const response = await listDocumentCollectionDocuments(selectedCaseId, documentCollectionTargetId);
      setDocumentCollectionTargetDocuments(response.data);
      if (showNotice) {
        setNotice("Célgyűjtemény tartalma frissítve.");
        setLastActionSummary(`${response.data.length} irat a célgyűjteményben.`);
      }
    };
    if (showNotice) {
      await perform("document-collections", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Célgyűjtemény tartalmának betöltése sikertelen.");
      }
    }
  }

  async function handleCreateDocumentCollection() {
    if (!selectedCaseId) return;
    const name = newDocumentCollectionName.trim();
    if (!name) {
      setError("Adj nevet az iratgyűjteménynek.");
      return;
    }
    await perform("document-collection-create", async () => {
      const collection = await createDocumentCollection(selectedCaseId, {
        name,
        description: newDocumentCollectionDescription.trim() || null
      });
      const response = await listDocumentCollections(selectedCaseId);
      setDocumentCollections(response.data);
      setSelectedDocumentCollectionId(collection.id);
      setDocumentCollectionTargetId(collection.id);
      setNewDocumentCollectionName("");
      setNewDocumentCollectionDescription("");
      setNotice("Iratgyűjtemény létrehozva.");
      setLastActionSummary(collection.name);
    });
  }

  async function handleDeleteDocumentCollection() {
    if (!selectedCaseId || !selectedDocumentCollection) return;
    const confirmed = await requestAppConfirmation({
      title: "Iratgyűjtemény törlése",
      message: "Törlöd ezt az iratgyűjteményt?",
      detail: `${selectedDocumentCollection.name}
Az iratok nem törlődnek.`,
      confirmLabel: "Törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("document-collection-delete", async () => {
      await deleteDocumentCollection(selectedCaseId, selectedDocumentCollection.id);
      const response = await listDocumentCollections(selectedCaseId);
      setDocumentCollections(response.data);
      setSelectedDocumentCollectionId(response.data[0]?.id ?? "");
      if (documentCollectionTargetId === selectedDocumentCollection.id) {
        setDocumentCollectionTargetId("");
        setDocumentCollectionTargetDocuments([]);
      }
      setDocumentCollectionScopePreview(null);
      setNotice("Iratgyűjtemény törölve.");
      setLastActionSummary(`${selectedDocumentCollection.name}: törölve.`);
    });
  }

  async function handleAddDocumentToTargetCollection(document: DocumentRead) {
    if (!selectedCaseId || !documentCollectionTargetId) return;
    if (targetCollectionDocumentIds.has(document.id)) return;
    await perform("document-collection-membership", async () => {
      const result = await addDocumentsToCollection(selectedCaseId, documentCollectionTargetId, [document.id]);
      const [collectionsResponse, documentsResponse] = await Promise.all([
        listDocumentCollections(selectedCaseId),
        listDocumentCollectionDocuments(selectedCaseId, documentCollectionTargetId)
      ]);
      setDocumentCollections(collectionsResponse.data);
      setDocumentCollectionTargetDocuments(documentsResponse.data);
      setDocumentCollectionScopePreview(null);
      setNotice("Irat hozzáadva a célgyűjteményhez.");
      setLastActionSummary(
        `${result.total_document_count} irat, ${result.active_document_count} aktív a kiválasztott gyűjteményben.`
      );
    });
  }

  function toggleDocumentCollectionDocumentMark(documentId: string) {
    setDocumentCollectionMarkedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId]
    );
  }

  function markAllVisibleDocumentsForCollection() {
    setDocumentCollectionMarkedDocumentIds((current) => Array.from(new Set([...current, ...visibleDocumentIds])));
  }

  function clearDocumentCollectionDocumentMarks() {
    setDocumentCollectionMarkedDocumentIds([]);
  }

  async function handleAddMarkedDocumentsToTargetCollection() {
    if (!selectedCaseId || !documentCollectionTargetId || documentCollectionMarkedDocumentIds.length === 0) return;
    await perform("document-collection-membership", async () => {
      const result = await addDocumentsToCollection(selectedCaseId, documentCollectionTargetId, documentCollectionMarkedDocumentIds);
      const [collectionsResponse, documentsResponse] = await Promise.all([
        listDocumentCollections(selectedCaseId),
        listDocumentCollectionDocuments(selectedCaseId, documentCollectionTargetId)
      ]);
      setDocumentCollections(collectionsResponse.data);
      setDocumentCollectionTargetDocuments(documentsResponse.data);
      setDocumentCollectionScopePreview(null);
      setNotice("Kijelölt iratok hozzáadva a célgyűjteményhez.");
      setLastActionSummary(
        `${result.added_count} új, ${result.already_present_count} már benne volt, ${result.skipped_count} kihagyva.`
      );
    });
  }

  async function handleRemoveDocumentFromSelectedCollection(document: DocumentRead) {
    if (!selectedCaseId || !selectedDocumentCollectionId) return;
    await perform("document-collection-membership", async () => {
      const result = await removeDocumentsFromCollection(selectedCaseId, selectedDocumentCollectionId, [document.id]);
      const [collectionsResponse, documentsResponse] = await Promise.all([
        listDocumentCollections(selectedCaseId),
        listDocumentCollectionDocuments(selectedCaseId, selectedDocumentCollectionId)
      ]);
      setDocumentCollections(collectionsResponse.data);
      setSelectedDocumentCollectionDocuments(documentsResponse.data);
      setSelectedDocumentCollectionMarkedDocumentIds((current) => current.filter((documentId) => documentId !== document.id));
      if (documentCollectionTargetId === selectedDocumentCollectionId) {
        setDocumentCollectionTargetDocuments(documentsResponse.data);
      }
      setDocumentCollectionScopePreview(null);
      setNotice("Irat kivéve a gyűjteményből.");
      setLastActionSummary(
        `${result.removed_count} eltávolítva, ${result.not_present_count} nem volt a gyűjteményben, ${result.skipped_count} kihagyva.`
      );
    });
  }

  function toggleSelectedDocumentCollectionDocumentMark(documentId: string) {
    setSelectedDocumentCollectionMarkedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId]
    );
  }

  function markAllVisibleSelectedCollectionDocuments() {
    setSelectedDocumentCollectionMarkedDocumentIds((current) => Array.from(new Set([...current, ...selectedCollectionVisibleDocumentIds])));
  }

  function clearSelectedDocumentCollectionDocumentMarks() {
    setSelectedDocumentCollectionMarkedDocumentIds([]);
  }

  async function handleRemoveMarkedDocumentsFromSelectedCollection() {
    if (!selectedCaseId || !selectedDocumentCollectionId || selectedDocumentCollectionMarkedDocumentIds.length === 0) return;
    await perform("document-collection-membership", async () => {
      const result = await removeDocumentsFromCollection(
        selectedCaseId,
        selectedDocumentCollectionId,
        selectedDocumentCollectionMarkedDocumentIds
      );
      const [collectionsResponse, documentsResponse] = await Promise.all([
        listDocumentCollections(selectedCaseId),
        listDocumentCollectionDocuments(selectedCaseId, selectedDocumentCollectionId)
      ]);
      setDocumentCollections(collectionsResponse.data);
      setSelectedDocumentCollectionDocuments(documentsResponse.data);
      setSelectedDocumentCollectionMarkedDocumentIds([]);
      if (documentCollectionTargetId === selectedDocumentCollectionId) {
        setDocumentCollectionTargetDocuments(documentsResponse.data);
      }
      setDocumentCollectionScopePreview(null);
      setNotice("Kijelölt iratok kivéve a gyűjteményből.");
      setLastActionSummary(
        `${result.removed_count} eltávolítva, ${result.not_present_count} nem volt a gyűjteményben, ${result.skipped_count} kihagyva.`
      );
    });
  }

  async function handleResolveDocumentCollectionScope() {
    if (!selectedCaseId || !selectedDocumentCollectionId) return;
    await perform("document-collection-scope", async () => {
      const response = await resolveDocumentCollectionScope(selectedCaseId, [selectedDocumentCollectionId]);
      setDocumentCollectionScopePreview(response);
      setNotice("Forráskör előnézet elkészült.");
      setLastActionSummary(`${response.active_document_count} egyedi aktív irat a forráskörben.`);
    });
  }

  async function refreshFullDocumentItems(showNotice = true) {
    if (!selectedCaseId || !fullDocumentId) return;
    const action = async () => {
      const response = await listDocumentProcessingItems(selectedCaseId, fullDocumentId, {
        profile_key: fullDocumentProfile,
        work_status: fullDocumentWorkStatus
      });
      setDocumentProcessingItems(response.data);
      setDocumentProcessingItemsMarkedForDeletion([]);
      if (showNotice) {
        setNotice("Teljes iratfeldolgozási munkalista frissítve.");
      }
      setLastActionSummary(
        `${response.data.length} ${
          fullDocumentWorkStatus === "active" ? "aktív" : "félretett"
        } teljes iratfeldolgozási elem.`
      );
    };
    if (showNotice) {
      await perform("full-document-items", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Teljes iratfeldolgozási munkalista betöltése sikertelen.");
      }
    }
  }

  async function refreshFullDocumentAnswers(showNotice = true) {
    if (!selectedCaseId || !fullDocumentId) return;
    const action = async () => {
      const response = await listFullDocumentAnswers(selectedCaseId, fullDocumentId, { answer_status: "active" });
      setFullDocumentAnswers(response.data);
      setFullDocumentCurrentAnswer((current) => {
        if (current && response.data.some((answer) => answer.id === current.id)) {
          return current;
        }
        return response.data[0] ?? null;
      });
      if (showNotice) {
        setNotice("Iratválaszok frissítve.");
      }
      setLastActionSummary(`${response.data.length} aktív iratválasz.`);
    };
    if (showNotice) {
      await perform("full-document-answers", action);
    } else {
      try {
        await action();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Iratválaszok betöltése sikertelen.");
      }
    }
  }

  async function refreshCaseData(showNotice = true) {
    if (!selectedCaseId) return;
    await perform("case-data", async () => {
      const [
        documentsResponse,
        documentCollectionsResponse,
        runsResponse,
        exportsResponse,
        reportResponse,
        manualClaimsResponse,
        claimsResponse,
        entitiesResponse,
        eventsResponse,
        missingItemsResponse,
        researchFindingsResponse,
        researchFindingRunSummaryResponse,
        ragAnswersResponse,
        ragLatestRunResponse,
        detachedSourcesResponse
      ] = await Promise.all([
        listDocuments(selectedCaseId),
        listDocumentCollections(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listExports(selectedCaseId),
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listResearchFindings(selectedCaseId),
        getLatestResearchFindingRunSummary(selectedCaseId),
        listRagAnswers(selectedCaseId),
        getLatestRagRunSummary(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setDocuments(documentsResponse.data);
      setDocumentCollections(documentCollectionsResponse.data);
      setAnalysisRuns(runsResponse.data);
      setExports(exportsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setResearchFindings(researchFindingsResponse.data);
      setLastResearchFindingRun(researchFindingRunSummaryResponse.latest_run);
      setRagSavedAnswers(ragAnswersResponse.data);
      setLastRagRun(ragLatestRunResponse.latest_run);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setReport(reportResponse);
      if (showNotice) {
        setNotice("Ugyadatok frissitve.");
      }
      setLastActionSummary(`${documentsResponse.data.length} irat, ${runsResponse.data.length} elemzesi futas.`);
    });
  }

  async function handleRunFullDocumentProcessing() {
    if (!selectedCaseId || !fullDocumentId || !fullDocumentProfile) return;
    await perform("full-document-run", async () => {
      const response = await runFullDocumentProcessing(selectedCaseId, fullDocumentId, {
        profile_key: fullDocumentProfile,
        page_start: fullDocumentPageStartNumber,
        page_end: fullDocumentPageEndNumber,
        question_text: fullDocumentProfileIsFreeQuestion ? fullDocumentQuestion.trim() : null
      });
      setFullDocumentWorkStatus("active");
      if (response.answer) {
        setFullDocumentCurrentAnswer(response.answer);
        setFullDocumentAnswers((current) => [response.answer!, ...current.filter((answer) => answer.id !== response.answer!.id)]);
        setDocumentProcessingItems([]);
        setDocumentProcessingItemsMarkedForDeletion([]);
      } else {
        setDocumentProcessingItems(response.items);
        setDocumentProcessingItemsMarkedForDeletion([]);
        setFullDocumentCurrentAnswer(null);
      }
      setLastFullDocumentRun({
        validation_status: response.validation_status,
        created_item_count: response.created_item_count,
        unsupported_count: response.unsupported_count,
        unsupported_items: response.unsupported_items
      });
      const runsResponse = await listAnalysisRuns(selectedCaseId);
      setAnalysisRuns(runsResponse.data);
      setNotice("Teljes iratfeldolgozás lefutott.");
      setLastActionSummary(
        response.answer
          ? `Szabad iratkérdés: ${labelValidationStatus(response.validation_status)}, iratválasz létrejött.`
          : `Teljes iratfeldolgozás: ${labelValidationStatus(response.validation_status)}, ${response.created_item_count} elem, ${response.unsupported_count} nem megerősített jelölt.`
      );
    });
  }

  async function handleDeleteFullDocumentAnswer(answerId: string) {
    if (!selectedCaseId || !fullDocumentId) return;
    await perform("full-document-answer-delete", async () => {
      await deleteFullDocumentAnswer(selectedCaseId, answerId);
      const response = await listFullDocumentAnswers(selectedCaseId, fullDocumentId, { answer_status: "active" });
      setFullDocumentAnswers(response.data);
      setFullDocumentCurrentAnswer(response.data[0] ?? null);
      setNotice("Iratválasz törölve.");
      setLastActionSummary(String(response.data.length) + " aktív iratválasz.");
    });
  }

  async function handleDocumentProcessingItemStatus(itemId: string, workStatus: "active" | "set_aside" | "deleted") {
    if (!selectedCaseId) return;
    await perform("full-document-status", async () => {
      const response = await updateDocumentProcessingItemStatus(selectedCaseId, itemId, workStatus);
      setDocumentProcessingItems((current) => {
        if (workStatus !== fullDocumentWorkStatus) {
          return current.filter((item) => item.id !== itemId);
        }
        return current.map((item) => (item.id === itemId ? response.item : item));
      });
      setDocumentProcessingItemsMarkedForDeletion((current) => current.filter((markedId) => markedId !== itemId));
      setNotice(workStatus === "deleted" ? "Munkalista-elem törölve." : "Munkalista-elem állapota módosítva.");
      setLastActionSummary(labelDocumentProcessingWorkStatus(workStatus));
    });
  }

  function toggleDocumentProcessingItemDeletionMark(item: DocumentProcessingItemRead) {
    if (item.work_status === "converted") return;
    setDocumentProcessingItemsMarkedForDeletion((current) =>
      current.includes(item.id)
        ? current.filter((itemId) => itemId !== item.id)
        : [...current, item.id]
    );
  }

  function markAllVisibleDocumentProcessingItemsForDeletion() {
    setDocumentProcessingItemsMarkedForDeletion((current) =>
      Array.from(new Set([...current, ...markableDocumentProcessingItemIds]))
    );
  }

  async function handleBulkDeleteDocumentProcessingItems() {
    if (!selectedCaseId || documentProcessingItemsMarkedForDeletion.length === 0) return;
    const count = documentProcessingItemsMarkedForDeletion.length;
    const confirmed = await requestAppConfirmation({
      title: "Kijelölt elemek törlése",
      message: "Törlöd a kijelölt teljes iratfeldolgozási elemeket?",
      detail: `Kijelölt elemek száma: ${count}`,
      confirmLabel: "Törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("full-document-status", async () => {
      const response = await bulkDeleteDocumentProcessingItems(selectedCaseId, documentProcessingItemsMarkedForDeletion);
      setDocumentProcessingItems((current) =>
        current.filter((item) => !documentProcessingItemsMarkedForDeletion.includes(item.id))
      );
      setDocumentProcessingItemsMarkedForDeletion([]);
      setNotice("Kijelölt teljes iratfeldolgozási elemek törölve.");
      setLastActionSummary(`${response.deleted_count} teljes iratfeldolgozási elem törölve.`);
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

  async function refreshDocumentsAfterLifecycleChange(documentId: string, fallback?: DocumentRead | null) {
    if (!selectedCaseId) return;
    const documentsResponse = await listDocuments(selectedCaseId);
    const refreshedDocument = documentsResponse.data.find((item) => item.id === documentId) ?? fallback ?? null;
    setDocuments(documentsResponse.data);
    setSelectedDocument(refreshedDocument);
    if (refreshedDocument) {
      if (refreshedDocument.lifecycle_status !== "active") {
        setManualSource(null);
      }
    } else {
      setDocumentPages([]);
      setDocumentChunks([]);
      setManualSource(null);
    }
    if (!documentsResponse.data.some((item) => item.id === analysisDocumentId && item.lifecycle_status === "active" && item.current_chunk_count > 0)) {
      setAnalysisDocumentId("");
      setAnalysisDocumentIds([]);
    }
    setMergeTargets({});
    setSourceMoveTargets({});
    setDetachedSourceTargets({});
    setManualContradiction((current) => ({ ...current, claim_id_a: "", claim_id_b: "" }));
    await refreshDocumentCollections(false);
    if (selectedDocumentCollectionId) {
      await refreshSelectedDocumentCollectionDocuments(false);
    }
    if (documentCollectionTargetId) {
      await refreshDocumentCollectionTargetDocuments(false);
    }
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
    const confirmed = await requestAppConfirmation({
      title: "Irat végleges elvetése",
      message: "Biztosan végleg elveted ezt az iratot?",
      detail: "Ez csak korai, elemzési alapként még nem használt iratnál engedélyezett.",
      confirmLabel: "Elvetés",
      danger: true
    });
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

  async function handleDeleteSelectedCase() {
    if (!selectedCase) return;
    const typedName = await requestAppTextConfirmation({
      title: "Ügy végleges törlése",
      message: "Ez véglegesen törli a teljes ügyet és minden hozzá tartozó munkatartalmat.",
      detail: selectedCase.case_name,
      inputLabel: "A megerősítéshez írd be pontosan az ügy nevét",
      expectedValue: selectedCase.case_name,
      confirmLabel: "Végleges törlés",
      danger: true
    });
    if (typedName !== selectedCase.case_name) {
      if (typedName !== null) {
        setError("Az ügy törlése megszakadt: a beírt név nem egyezik.");
      }
      return;
    }
    const deletedCaseId = selectedCase.id;
    const deletedCaseName = selectedCase.case_name;
    await perform("case-delete", async () => {
      const result = await deleteCase(deletedCaseId);
      const response = await listCases();
      setCases(response.data);
      setSelectedCaseId(response.data[0]?.id ?? "");
      setNotice("Ügy véglegesen törölve.");
      setLastActionSummary(`${deletedCaseName}: törölve, ${result.deleted_counts.documents ?? 0} irat.`);
    });
  }

  async function handleImport() {
    if (!selectedCaseId || importFiles.length === 0) return;
    await perform("import", async () => {
      const filesToImport = [...importFiles];
      for (const selectedFile of filesToImport) {
        await importDocument(selectedCaseId, selectedFile);
      }
      setImportFiles([]);
      if (importFileInputRef.current) {
        importFileInputRef.current.value = "";
      }
      const documentsResponse = await listDocuments(selectedCaseId);
      setDocuments(documentsResponse.data);
      setNotice(filesToImport.length === 1 ? "Irat import kesz." : "Iratok importja kesz.");
      setLastActionSummary(
        filesToImport.length === 1
          ? `Import kesz: ${filesToImport[0].name}`
          : `Import kesz: ${filesToImport.length} irat`
      );
    });
  }

  async function handleRunAnalysis() {
    if (!selectedCaseId) return;
    await perform("analysis", async () => {
      const payload = {
        query: query.trim() ? query.trim() : null,
        source_mode: effectiveAnalysisSourceMode,
        document_id: effectiveAnalysisSourceMode === "document" ? analysisDocumentId : null,
        collection_id: effectiveAnalysisSourceMode === "collection" ? analysisCollectionId : null,
        ...(showCaseDocumentFilters && analysisDocumentIds.length > 0 ? { document_ids: analysisDocumentIds } : {}),
        max_chunks: maxChunks,
        batch_size: batchSize,
        claim_review_scope: claimReviewScope,
        retrieval_strategy: retrievalStrategy,
        ...(isContradictionModule ? { contradiction_candidate_limit: contradictionCandidateLimit } : {})
      };
      const response = await runAnalysis(selectedCaseId, moduleKey, payload);
      const [
        reportResponse,
        manualClaimsResponse,
        runsResponse,
        claimsResponse,
        entitiesResponse,
        eventsResponse,
        missingItemsResponse,
        researchFindingsResponse,
        researchFindingRunSummaryResponse,
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
        getLatestResearchFindingRunSummary(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setResearchFindings(researchFindingsResponse.data);
      setLastResearchFindingRun(researchFindingRunSummaryResponse.latest_run);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      if (response.module_key === "search_findings") {
        setTimeout(() => {
          researchFindingsPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
      }
      setNotice("Elemzes lefutott, jelentés frissitve.");
      setLastActionSummary(
        `${labelModule(response.module_key)}: ${analysisSourceSummaryLabel(
          effectiveAnalysisSourceMode,
          analysisDocumentIds.length,
          analysisDocumentCollection?.name
        )}, ${labelValidationStatus(response.validation_status)}, ${analysisSourceMetric(response)}, ${analysisOutputCount(response)} kimenet`
      );
    });
  }

  async function handleRunRagQuery() {
    if (!selectedCaseId) return;
    await perform("rag-query", async () => {
      const response = await runRagQuery(selectedCaseId, {
        question: ragQuestion.trim(),
        source_mode: ragSourceMode,
        document_id: ragSourceMode === "document" ? ragDocumentId : null,
        document_ids: ragSourceMode === "case" ? ragDocumentIds : [],
        collection_id: ragSourceMode === "collection" ? ragCollectionId : null,
        answer_mode: ragAnswerMode,
        retrieval_strategy: ragRetrievalStrategy,
        max_chunks: ragMaxChunks,
        include_sources: true
      });
      const [runsResponse, latestRagResponse] = await Promise.all([
        listAnalysisRuns(selectedCaseId),
        getLatestRagRunSummary(selectedCaseId)
      ]);
      setAnalysisRuns(runsResponse.data);
      setLastRagRun(latestRagResponse.latest_run);
      setRagCurrentResponse(response);
      setRagSaveTitle(ragQuestion.trim().slice(0, 120));
      setRagSaveNote("");
      setNotice("Iratkérdező válasz elkészült.");
      setLastActionSummary(
        `${labelRagAnswerMode(response.answer.answer_mode)} | ${response.used_sources.length} forrás | ${response.source_scope.resolved_document_count} irat`
      );
    });
  }

  async function handleSaveRagAnswer() {
    if (!selectedCaseId || !ragCurrentResponse?.can_save) return;
    await perform("rag-save", async () => {
      const saved = await saveRagAnswer(selectedCaseId, ragCurrentResponse.run_id, {
        title: ragSaveTitle.trim() || null,
        note: ragSaveNote.trim() || null
      });
      const [answersResponse, detail, latestRagResponse] = await Promise.all([
        listRagAnswers(selectedCaseId),
        getRagAnswer(selectedCaseId, saved.answer_id),
        getLatestRagRunSummary(selectedCaseId)
      ]);
      setRagSavedAnswers(answersResponse.data);
      setLastRagRun(latestRagResponse.latest_run);
      setSelectedRagAnswerId(saved.answer_id);
      setSelectedRagAnswer(detail);
      setRagCurrentResponse((current) => current ? { ...current, can_save: false } : current);
      setNotice("Iratkérdező válasz mentve.");
      setLastActionSummary(detail.title || detail.question);
      scrollToRagSavedDetailPanel();
    });
  }

  async function handleLoadRagAnswer(answerId: string) {
    if (!selectedCaseId) return;
    await perform("rag-answers", async () => {
      const detail = await getRagAnswer(selectedCaseId, answerId);
      setSelectedRagAnswerId(answerId);
      setSelectedRagAnswer(detail);
      setNotice("Mentett iratkérdező válasz betöltve.");
      setLastActionSummary(detail.title || detail.question);
      scrollToRagSavedDetailPanel();
    });
  }

  async function handleDeleteRagAnswer(answer: RagSavedAnswerListItem) {
    if (!selectedCaseId) return;
    const confirmed = await requestAppConfirmation({
      title: "Mentett válasz törlése",
      message: "Törlöd ezt a mentett iratkérdező választ?",
      detail: answer.title || answer.question,
      confirmLabel: "Törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("rag-answer-delete", async () => {
      await deleteRagAnswer(selectedCaseId, answer.id);
      const response = await listRagAnswers(selectedCaseId);
      setRagSavedAnswers(response.data);
      if (selectedRagAnswerId === answer.id) {
        setSelectedRagAnswerId("");
        setSelectedRagAnswer(null);
      }
      setNotice("Mentett iratkérdező válasz törölve.");
      setLastActionSummary(answer.title || answer.question);
    });
  }

  function knowledgeBatchClientIds(files: File[]) {
    return files.map((file, index) => `${index + 1}:${file.name}`);
  }

  function knowledgeBatchRelativeDirectories(files: File[]) {
    return files.map((file) => buildKnowledgeBatchRelativeDirectory(file, knowledgeBatchRelativePath));
  }

  function hasKnowledgeBatchRelativePath() {
    return !validateKnowledgeBatchRelativeDirectory(knowledgeBatchRelativePath);
  }

  function defaultKnowledgeBatchDecision(item: KnowledgeBatchPreviewItem): KnowledgeBatchImportDecision {
    if (item.status === "ready") return "import";
    if (item.status === "same_relative_path") return "replace";
    return "skip";
  }

  function effectiveKnowledgeBatchDecision(item: KnowledgeBatchPreviewItem): KnowledgeBatchImportDecision {
    if (item.status !== "same_relative_path") return defaultKnowledgeBatchDecision(item);
    return knowledgeBatchDecisions[item.client_file_id] ?? "replace";
  }

  function effectiveKnowledgeBatchDecisionsForFiles(files: File[], preview: KnowledgeBatchPreviewResponse): KnowledgeBatchImportDecision[] {
    const previewItemsByClientId = new Map(preview.items.map((item) => [item.client_file_id, item]));
    return knowledgeBatchClientIds(files).map((clientFileId) => {
      const previewItem = previewItemsByClientId.get(clientFileId);
      if (!previewItem) return "import";
      return effectiveKnowledgeBatchDecision(previewItem);
    });
  }

  function resetKnowledgeBatchState(keepFiles = false) {
    if (!keepFiles) {
      setKnowledgeBatchFiles([]);
      setKnowledgeBatchRelativePath("");
      if (knowledgeBatchInputRef.current) {
        knowledgeBatchInputRef.current.value = "";
      }
    }
    setKnowledgeBatchPreview(null);
    setKnowledgeBatchDecisions({});
    setKnowledgeBatchImportResult(null);
  }

  async function handlePreviewKnowledgeBatch() {
    if (knowledgeBatchFiles.length === 0 || !hasKnowledgeBatchRelativePath()) return;
    await perform("knowledge-batch-preview", async () => {
      const result = await previewKnowledgeDocumentBatch(
        knowledgeBatchFiles,
        knowledgeBatchRelativeDirectories(knowledgeBatchFiles),
        knowledgeBatchClientIds(knowledgeBatchFiles)
      );
      const decisions: Record<string, KnowledgeBatchImportDecision> = {};
      result.items.forEach((item) => {
        decisions[item.client_file_id] = defaultKnowledgeBatchDecision(item);
      });
      setKnowledgeBatchPreview(result);
      setKnowledgeBatchDecisions(decisions);
      setKnowledgeBatchImportResult(null);
      setNotice("Batch import előnézet elkészült.");
      setLastActionSummary(`${result.summary.total} fájl, ${result.summary.ready} importálható, ${result.summary.same_relative_path + result.summary.same_hash} ütközés.`);
    });
  }

  async function handleImportKnowledgeBatch() {
    if (knowledgeBatchFiles.length === 0 || !knowledgeBatchPreview || !hasKnowledgeBatchRelativePath()) return;
    await perform("knowledge-batch-import", async () => {
      const clientIds = knowledgeBatchClientIds(knowledgeBatchFiles);
      const result = await importKnowledgeDocumentBatch(
        knowledgeBatchFiles,
        knowledgeBatchRelativeDirectories(knowledgeBatchFiles),
        clientIds,
        effectiveKnowledgeBatchDecisionsForFiles(knowledgeBatchFiles, knowledgeBatchPreview)
      );
      setKnowledgeBatchImportResult(result);
      const [documentsResponse, indexStatusResponse] = await Promise.all([
        listKnowledgeDocuments(),
        getKnowledgeIndexStatus()
      ]);
      setKnowledgeDocuments(documentsResponse.data);
      setKnowledgeIndexStatus(indexStatusResponse);
      setKnowledgeBatchFiles([]);
      setKnowledgeBatchRelativePath("");
      setKnowledgeBatchPreview(null);
      setKnowledgeBatchDecisions({});
      if (knowledgeBatchInputRef.current) {
        knowledgeBatchInputRef.current.value = "";
      }
      setNotice("Batch import lefutott.");
      setLastActionSummary(
        `${result.summary.imported} importált, ${result.summary.replaced} cserélt, ${result.summary.skipped} kihagyott, ${result.summary.failed} hibás.`
      );
    });
  }

  async function refreshKnowledgeAfterLifecycleChange() {
    const [documentsResponse, indexStatusResponse] = await Promise.all([
      listKnowledgeDocuments(),
      getKnowledgeIndexStatus()
    ]);
    setKnowledgeDocuments(documentsResponse.data);
    setKnowledgeIndexStatus(indexStatusResponse);
    setKnowledgeDocumentIds((current) => {
      const activeIds = new Set(
        documentsResponse.data
          .filter((document) => document.processing_status !== "archived")
          .map((document) => document.id)
      );
      return current.filter((id) => activeIds.has(id));
    });
  }

  async function handleArchiveSelectedKnowledgeDocuments() {
    if (selectedActiveKnowledgeDocuments.length === 0) return;
    await perform("knowledge-archive-selected", async () => {
      for (const document of selectedActiveKnowledgeDocuments) {
        await archiveKnowledgeDocument(document.id);
      }
      await refreshKnowledgeAfterLifecycleChange();
      setNotice("Kijelölt tudásbázis dokumentumok archiválva.");
      setLastActionSummary(`${selectedActiveKnowledgeDocuments.length} dokumentum archiválva.`);
    });
  }

  async function handleDeleteSelectedKnowledgeDocuments() {
    if (selectedKnowledgeDocuments.length === 0) return;
    const confirmed = await requestAppConfirmation({
      title: "Tudásbázis dokumentumok törlése",
      message: "Végleg törlöd a kijelölt tudásbázis dokumentumokat?",
      detail: `${selectedKnowledgeDocuments.length} dokumentum`,
      confirmLabel: "Végleges törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("knowledge-delete-selected", async () => {
      for (const document of selectedKnowledgeDocuments) {
        await deleteKnowledgeDocument(document.id);
      }
      await refreshKnowledgeAfterLifecycleChange();
      setNotice("Kijelölt tudásbázis dokumentumok végleg törölve.");
      setLastActionSummary(`${selectedKnowledgeDocuments.length} dokumentum törölve.`);
    });
  }

  async function handleIndexKnowledgeDocuments() {
    await perform("knowledge-index", async () => {
      const result = await indexKnowledgeDocuments({
        document_ids: knowledgeDocumentIds,
        force_reindex: knowledgeForceReindex,
        limit: 1000
      });
      const [documentsResponse, indexStatusResponse] = await Promise.all([
        listKnowledgeDocuments(),
        getKnowledgeIndexStatus()
      ]);
      setKnowledgeDocuments(documentsResponse.data);
      setKnowledgeIndexStatus(indexStatusResponse);
      setNotice("Tudásbázis indexelés kész.");
      setLastActionSummary(
        `${result.indexed_document_count} dokumentum, ${result.indexed_chunk_count} szövegrész indexelve.`
      );
    });
  }

  async function handleRunKnowledgeQuery() {
    await perform("knowledge-query", async () => {
      const response = await runKnowledgeQuery({
        question: knowledgeQuestion.trim(),
        document_ids: knowledgeDocumentIds,
        answer_mode: knowledgeAnswerMode,
        retrieval_strategy: knowledgeRetrievalStrategy,
        max_chunks: knowledgeMaxChunks
      });
      setKnowledgeSourcesPanelOpen(false);
      setKnowledgeSourceSearch("");
      setExpandedKnowledgeSourceKeys([]);
      setKnowledgeSourceDetails({});
      setKnowledgeSourceLoadingKeys([]);
      setKnowledgeSourceErrors({});
      setKnowledgeCurrentResponse(response);
      setNotice("Tudásbázis válasz elkészült.");
      setLastActionSummary(
        `${labelRagAnswerMode(response.answer.answer_mode)} | ${response.used_sources.length} forrás | ${response.retrieval_metadata.selected_chunk_count} szövegrész`
      );
    });
  }

  async function loadRelationshipGraphForObjects(focusObjects: RelationshipGraphFocusObject[], options: { switchSurface?: boolean } = {}) {
    if (!selectedCaseId || focusObjects.length === 0) return;
    if (options.switchSurface) {
      setActiveSurface("relationship_map");
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }
    await perform("relationship-graph", async () => {
      const graph = await getRelationshipGraphForObjects(
        selectedCaseId,
        {
          focus_objects: focusObjects,
          include_shared_sources: true,
          max_nodes: 150,
          max_edges: 250
        }
      );
      setRelationshipGraph(graph);
      setSelectedRelationshipEdgeId(null);
      setSelectedRelationshipNodeId(graph.focus_node_id);
      setNotice("Kapcsolati térkép betöltve.");
      setLastActionSummary(`${graph.focus_node_ids.length} fókusz | ${graph.limits.node_count} elem | ${graph.limits.edge_count} kapcsolat`);
    });
  }

  async function loadRelationshipGraphFor(objectType: string, objectId: string, options: { switchSurface?: boolean } = {}) {
    if (!objectType || !objectId.trim()) return;
    setRelationshipGraphObjectType(objectType);
    setRelationshipGraphFocusKeys([relationshipFocusKey(objectType, objectId.trim())]);
    await loadRelationshipGraphForObjects([{ object_type: objectType, object_id: objectId.trim() }], options);
  }

  async function handleLoadRelationshipGraph() {
    if (selectedRelationshipFocusObjects.length === 0) {
      setRelationshipGraph(null);
      setSelectedRelationshipEdgeId(null);
      setSelectedRelationshipNodeId(null);
      setNotice("Kapcsolati térkép kiürítve.");
      setLastActionSummary("Nincs megjelenített kapcsolati térkép");
      return;
    }
    await loadRelationshipGraphForObjects(selectedRelationshipFocusObjects);
  }

  function toggleKnowledgeDocumentFilter(documentId: string) {
    setKnowledgeDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId]
    );
  }

  function selectAllFilteredKnowledgeDocuments() {
    setKnowledgeDocumentIds(
      filteredKnowledgeDocuments.map((document) => document.id)
    );
  }

  function scrollToRagSavedDetailPanel() {
    window.setTimeout(() => {
      ragSavedDetailPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }

  function scrollToAnalysisPanel() {
    window.setTimeout(() => {
      analysisPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
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
    if (effectiveAnalysisSourceMode === "collection") {
      return { document_id: null, collection_id: analysisCollectionId || null };
    }
    return {
      document_id: null,
      ...(analysisDocumentIds.length > 0 ? { document_ids: analysisDocumentIds } : {})
    };
  }

  function ragChunkIndexScopePayload() {
    if (ragSourceMode === "document") {
      return { document_id: ragDocumentId || null };
    }
    if (ragSourceMode === "collection") {
      return { document_id: null, collection_id: ragCollectionId || null };
    }
    return {
      document_id: null,
      ...(ragDocumentIds.length > 0 ? { document_ids: ragDocumentIds } : {})
    };
  }

  function toggleRagDocumentFilter(documentId: string) {
    setRagDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId]
    );
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

  async function refreshRagChunkIndexStatus(): Promise<ChunkIndexStatusResponse | null> {
    if (!selectedCaseId) return null;
    const response = await getChunkIndexStatus(selectedCaseId, ragChunkIndexScopePayload());
    setRagChunkIndexStatus(response);
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
      await refreshChunkIndexStatus();
      setActiveIndexJobId(response.analysis_run_id);
      setNotice("Szovegresz-indexeles elindult, az allapot automatikusan frissul.");
      setLastActionSummary(
        `Indexeles inditva: ${labelRunStatus(response.status)}, gyujtemeny: ${response.collection_name}`
      );
    });
  }

  async function handleIndexRagChunks() {
    if (!selectedCaseId) return;
    await perform("chunk-index", async () => {
      const response = await startChunkIndexJob(selectedCaseId, {
        ...ragChunkIndexScopePayload(),
        limit: 1000,
        force_reindex: ragForceReindex
      });
      const [runsResponse, documentsResponse] = await Promise.all([
        listAnalysisRuns(selectedCaseId),
        listDocuments(selectedCaseId)
      ]);
      setAnalysisRuns(runsResponse.data);
      setDocuments(documentsResponse.data);
      await refreshRagChunkIndexStatus();
      setRagActiveIndexJobId(response.analysis_run_id);
      setNotice("Iratkérdező indexelés elindult, az állapot automatikusan frissül.");
      setLastActionSummary(
        `Iratkerdezo indexeles inditva: ${labelRunStatus(response.status)}, gyujtemeny: ${response.collection_name}`
      );
    });
  }

  async function refreshLlmSmoke(showNotice = true) {
    const action = async () => {
      const response = await getLlmSmoke();
      setLlmSmoke(response);
      if (showNotice) {
        setNotice("LLM modell allapot frissitve.");
        setLastActionSummary(
          `Chat: ${labelModelLoadState(response.configured_chat_model_loaded)}, embedding: ${labelModelLoadState(response.configured_embedding_model_loaded)}`
        );
      }
    };
    if (showNotice) {
      await perform("llm-smoke", action);
      return;
    }
    try {
      await action();
    } catch (err) {
      setLlmSmoke(null);
    }
  }

  async function handleLlmSmoke() {
    await refreshLlmSmoke(true);
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

  async function handleUnloadChatModel() {
    await perform("chat-unload", async () => {
      await unloadChatModel();
      const response = await getLlmSmoke();
      setLlmSmoke(response);
      setNotice("Chat modell leválasztva.");
      setLastActionSummary(`Leválasztott chat modell: ${response.configured_chat_model}`);
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

  async function handleUnloadEmbeddingModel() {
    await perform("embedding-unload", async () => {
      await unloadEmbeddingModel();
      const response = await getLlmSmoke();
      setLlmSmoke(response);
      setNotice("Embedding modell leválasztva.");
      setLastActionSummary(`Leválasztott embedding modell: ${response.configured_embedding_model}`);
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

  function reviewItemCanBeDeleted(item: ReviewReportItem) {
    return item.review_status === "corrected" || item.source_validation_status === "source_invalid";
  }

  function reviewItemTextCanBeEdited(item: ReviewReportItem) {
    return item.review_status !== "corrected" && item.source_validation_status === "source_valid";
  }

  function reviewItemCanOpenRelationshipGraph(item: ReviewReportItem) {
    return objectTypes.includes(item.object_type) && item.object_type !== "" && item.source_validation_status === "source_valid";
  }

  async function handleOpenRelationshipGraphFromReportItem(item: ReviewReportItem) {
    if (!reviewItemCanOpenRelationshipGraph(item)) return;
    await loadRelationshipGraphFor(item.object_type, item.object_id, { switchSurface: true });
  }

  function objectTextEditUnchanged(item: ReviewReportItem) {
    return objectTextEdit.title.trim() === item.title.trim() && objectTextEdit.description.trim() === (item.body_text ?? "").trim();
  }

  async function handleUpdateReviewReportItemText(item: ReviewReportItem) {
    if (!selectedCaseId || !reviewItemTextCanBeEdited(item)) return;
    const title = objectTextEdit.title.trim();
    const description = objectTextEdit.description.trim();
    if (!title || !description || objectTextEditUnchanged(item)) return;
    await perform("review-item-text", async () => {
      await updateReviewReportItemText(selectedCaseId, item.object_type, item.object_id, title, description);
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((reportItem) => reportItem.object_id === item.object_id) ?? null);
      setNotice("Találat címe/leírása módosítva.");
      setLastActionSummary(`${labelObjectType(item.object_type)}: cím/leírás módosítva.`);
    });
  }

  async function handleDeleteReviewReportItem(item: ReviewReportItem) {
    if (!selectedCaseId || !reviewItemCanBeDeleted(item)) return;
    const confirmed = await requestAppConfirmation({
      title: "Találat végleges törlése",
      message: "Biztosan véglegesen törlöd ezt a találatot az áttekintési jelentésből?",
      detail: item.title,
      confirmLabel: "Végleges törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("review-item-delete", async () => {
      await deleteReviewReportItem(selectedCaseId, item.object_type, item.object_id);
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
      setSelectedReportItem(null);
      setNotice("Találat véglegesen törölve.");
      setLastActionSummary(`${labelObjectType(item.object_type)}: véglegesen törölve.`);
    });
  }

  async function handleDetachContradictionCandidateClaim(item: ReviewReportItem, side: "a" | "b") {
    if (!selectedCaseId || item.object_type !== "contradiction_candidate") return;
    const claimId = side === "a" ? item.claim_id_a : item.claim_id_b;
    if (!claimId) return;
    const confirmed = await requestAppConfirmation({
      title: "Állítás leválasztása",
      message: `Biztosan leválasztod a(z) ${side.toUpperCase()} állítást erről az ellentmondásjelöltről?`,
      detail: item.title,
      confirmLabel: "Leválasztás",
      danger: true
    });
    if (!confirmed) return;
    const reviewComment = reviewComments[item.object_id] ?? "";
    await perform("contradiction-claim-detach", async () => {
      await detachContradictionCandidateClaim(selectedCaseId, item.object_id, side, reviewComment);
      const [reportResponse, manualClaimsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId)
      ]);
      setReport(reportResponse);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((reportItem) => reportItem.object_id === item.object_id) ?? null);
      setNotice(`${side.toUpperCase()} állítás leválasztva. Az ellentmondásjelölt korrekcióval kizárt állapotba került.`);
      setLastActionSummary(`Ellentmondásjelölt: ${side.toUpperCase()} állítás leválasztva.`);
    });
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
      return claims.map((claim) => ({ id: claim.id, label: sourceTargetLabel(claim.claim_title, claim.review_status), searchText: claim.claim_text }));
    }
    if (item.detached_from_object_type === "entity") {
      return entities.map((entity) => ({ id: entity.id, label: sourceTargetLabel(entity.canonical_name, entity.review_status), searchText: entity.description ?? "" }));
    }
    if (item.detached_from_object_type === "event") {
      return events.map((event) => ({ id: event.id, label: sourceTargetLabel(event.event_title, event.review_status), searchText: event.event_description ?? "" }));
    }
    if (item.detached_from_object_type === "missing_item_candidate") {
      return missingItemCandidates.map((candidate) => ({ id: candidate.id, label: sourceTargetLabel(candidate.referenced_item_text, candidate.review_status), searchText: candidate.description }));
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

  async function handleDeleteDetachedSource(item: DetachedSourceItemRead) {
    if (!selectedCaseId) return;
    const confirmed = await requestAppConfirmation({
      title: "Leválasztott forráshivatkozás törlése",
      message: "Biztosan véglegesen törlöd ezt a leválasztott forráshivatkozást a munkalistából?",
      confirmLabel: "Végleges törlés",
      danger: true
    });
    if (!confirmed) return;
    await perform("detached-source-delete", async () => {
      await deleteDetachedSourceItem(selectedCaseId, item.id);
      await refreshReviewStateAfterSourceChange(null);
      setNotice("Leválasztott forráshivatkozás véglegesen törölve.");
      setLastActionSummary("Leválasztott forráshivatkozás véglegesen törölve.");
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
      source_reference: manualSourceReferencePayload(),
      ...manualObjectFieldsPayload(manualObjectType, manualFields)
    };
  }

  function manualSourceReferencePayload(): ManualObjectPayload["source_reference"] {
    if (!manualSource) {
      throw new Error("Manual source is not selected");
    }
    return {
        document_id: manualSource.documentId,
        page_id: manualSource.pageId,
        chunk_id: manualSource.chunkId,
        quote_text: manualSource.quoteText,
        quote_char_start: manualSource.quoteStart,
        quote_char_end: manualSource.quoteEnd,
        citation_label: manualSource.citationLabel,
        source_kind: "chunk_quote"
    };
  }

  function manualSourceAttachTargetOptions(type: ManualObjectType): SearchableSelectOption[] {
    if (type === "claim") {
      return claims.map((claim) => ({
        id: claim.id,
        label: `${claim.claim_title} (${labelReviewStatus(claim.review_status)})`,
        searchText: claim.claim_text
      }));
    }
    if (type === "entity") {
      return entities.map((entity) => ({
        id: entity.id,
        label: `${entity.canonical_name} (${labelReviewStatus(entity.review_status)})`,
        searchText: entity.description ?? ""
      }));
    }
    if (type === "event") {
      return events.map((event) => ({
        id: event.id,
        label: `${event.event_title} (${labelReviewStatus(event.review_status)})`,
        searchText: event.event_description ?? ""
      }));
    }
    return missingItemCandidates.map((candidate) => ({
      id: candidate.id,
      label: `${candidate.referenced_item_text} (${labelReviewStatus(candidate.review_status)})`,
      searchText: candidate.description
    }));
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

  async function handleAttachManualSourceToExistingObject() {
    if (!selectedCaseId || !manualSource || !manualSourceAttachTargetId) return;
    await perform("manual-source-attach", async () => {
      const response = await attachManualSourceToExistingObject(selectedCaseId, {
        source_reference: manualSourceReferencePayload(),
        target_object_type: manualSourceAttachType,
        target_object_id: manualSourceAttachTargetId
      });
      setManualSource(null);
      setManualFields({});
      setManualSourceAttachTargetId("");
      const [reportResponse, manualClaimsResponse, runsResponse, claimsResponse, entitiesResponse, eventsResponse, missingItemsResponse, detachedSourcesResponse] = await Promise.all([
        getReviewReport(selectedCaseId, reportFilters),
        getManualContradictionClaims(selectedCaseId),
        listAnalysisRuns(selectedCaseId),
        listClaims(selectedCaseId),
        listEntities(selectedCaseId),
        listEvents(selectedCaseId),
        listMissingItemCandidates(selectedCaseId),
        listDetachedSourceItems(selectedCaseId)
      ]);
      setReport(reportResponse);
      setAnalysisRuns(runsResponse.data);
      setClaims(claimsResponse.data);
      setEntities(entitiesResponse.data);
      setEvents(eventsResponse.data);
      setMissingItemCandidates(missingItemsResponse.data);
      setDetachedSourceItems(detachedSourcesResponse.data);
      setManualContradictionClaims(manualClaimsResponse.items);
      setSelectedReportItem(reportResponse.items.find((item) => item.object_id === response.target_object_id) ?? null);
      const suffix = response.skipped_duplicate_source ? " A forrás már szerepelt a célon, ezért nem duplikáltuk." : "";
      setNotice(`Forráshivatkozás meglévő találathoz csatolva.${suffix}`);
      setLastActionSummary(`${labelObjectType(response.target_object_type)}: kézi forráshivatkozás csatolva.`);
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

  function markAllVisibleResearchFindingsForDeletion() {
    setResearchFindingsMarkedForDeletion((current) =>
      Array.from(new Set([...current, ...markableResearchFindingIds]))
    );
  }

  async function handleBulkDeleteResearchFindings() {
    if (!selectedCaseId || researchFindingsMarkedForDeletion.length === 0) return;
    const count = researchFindingsMarkedForDeletion.length;
    const confirmed = await requestAppConfirmation({
      title: "Kutatási találatok törlése",
      message: "Törlöd a kijelölt kutatási találatokat?",
      detail: `Kijelölt elemek száma: ${count}`,
      confirmLabel: "Törlés",
      danger: true
    });
    if (!confirmed) return;
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
          <span>{labelSourceExcerpt(source.source_kind)} {formatRange(source.source_text_excerpt_char_start, source.source_text_excerpt_char_end)}</span>
        </div>
        <blockquote>{source.quote_text}</blockquote>
        {source.source_text_excerpt && <p className="excerpt">{highlightedSourceExcerpt(source.source_text_excerpt, source.quote_text)}</p>}
        <code className="hash">{source.id}</code>
      </details>
    );
  }

  function reportSourceTextUnitKey(source: ReviewReportSource) {
    if (source.chunk_id) {
      return `chunk:${source.document_id}:${source.chunk_id}`;
    }
    if (source.page_id) {
      return `page:${source.document_id}:${source.page_id}`;
    }
    return `source:${source.source_reference_id}`;
  }

  function groupedReportSources(sources: ReviewReportSource[]) {
    const groups: { key: string; sources: { source: ReviewReportSource; originalIndex: number }[] }[] = [];
    const groupIndexes = new Map<string, number>();
    sources.forEach((source, originalIndex) => {
      const key = reportSourceTextUnitKey(source);
      const existingIndex = groupIndexes.get(key);
      if (existingIndex === undefined) {
        groupIndexes.set(key, groups.length);
        groups.push({ key, sources: [{ source, originalIndex }] });
        return;
      }
      groups[existingIndex].sources.push({ source, originalIndex });
    });
    return groups;
  }

  function reportSourceUnitSummary(source: ReviewReportSource, sourceCount: number, groupIndex: number) {
    const prefix = sourceCount > 1 ? `${sourceCount} forráshivatkozás` : `${groupIndex + 1}. forráshivatkozás`;
    const pageLabel = source.page_number ? `${source.page_number}. oldal` : "";
    const chunkLabel = source.chunk_index !== null ? `${source.chunk_index}. szövegrész` : "";
    return `${prefix}: ${source.document_filename ?? "irat"} ${pageLabel} ${chunkLabel}`.trim();
  }

  function renderReportSourceQuote(item: ReviewReportItem, source: ReviewReportSource, originalIndex: number, showOrdinal: boolean) {
    return (
      <article key={source.source_link_id ?? source.source_reference_id} className="source-quote-item">
        {showOrdinal && <strong>{originalIndex + 1}. idézet</strong>}
        <div className="source-meta">
          <span>{labelSupportType(source.support_type)}</span>
          <span>sorrend {source.relevance_rank ?? originalIndex}</span>
          <span>{source.citation_label ?? "nincs hivatkozási címke"}</span>
          {source.document_lifecycle_status && source.document_lifecycle_status !== "active" && (
            <span>forrás irat állapota: {labelDocumentLifecycleStatus(source.document_lifecycle_status)}</span>
          )}
          <span>idézet {formatRange(source.quote_char_start, source.quote_char_end)}</span>
        </div>
        <blockquote>{source.quote_text}</blockquote>
        {renderSourceDetachButton(item, source)}
      </article>
    );
  }

  function renderReportSourceGroups(item: ReviewReportItem, mode: "card" | "detail") {
    const groups = groupedReportSources(item.sources);
    return (
      <div className={mode === "card" ? "source-list" : "detail-list"}>
        {groups.map((group, groupIndex) => {
          const firstSource = group.sources[0].source;
          return (
            <details key={group.key} className="source-detail">
              <summary>{reportSourceUnitSummary(firstSource, group.sources.length, groupIndex)}</summary>
              <div className="source-quote-list">
                {group.sources.map(({ source, originalIndex }) =>
                  renderReportSourceQuote(item, source, originalIndex, group.sources.length > 1)
                )}
              </div>
              {firstSource.source_text_excerpt && (
                <div className="source-shared-text">
                  <div className="source-meta">
                    <span>
                      {labelSourceExcerpt(firstSource.source_kind)}{" "}
                      {formatRange(firstSource.source_text_excerpt_char_start, firstSource.source_text_excerpt_char_end)}
                    </span>
                  </div>
                  <p className="excerpt">
                    {highlightedSourceExcerpt(
                      firstSource.source_text_excerpt,
                      firstExactQuoteInExcerpt(
                        firstSource.source_text_excerpt,
                        group.sources.map(({ source }) => source.quote_text)
                      )
                    )}
                  </p>
                </div>
              )}
              {firstSource.document_sha256_hash && <code className="hash">{firstSource.document_sha256_hash}</code>}
            </details>
          );
        })}
      </div>
    );
  }

  function renderSearchableSelect(params: {
    queryKey: string;
    value: string;
    onChange: (value: string) => void;
    options: SearchableSelectOption[];
    placeholder: string;
    searchPlaceholder?: string;
    ariaLabel: string;
    action?: ReactNode;
  }) {
    const selectedOption = params.options.find((option) => option.id === params.value);
    const inputValue = searchableSelectQueries[params.queryKey] ?? selectedOption?.label ?? "";
    const normalizedFilter = normalizeComboboxText(inputValue);
    const isActive = activeSearchableSelectKey === params.queryKey;
    const visibleOptions = params.options
      .filter((option) => {
        if (!normalizedFilter) return true;
        return normalizeComboboxText(`${option.label} ${option.searchText ?? ""}`).includes(normalizedFilter);
      })
      .slice(0, 30);
    return (
      <div
        className="searchable-select"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setActiveSearchableSelectKey("");
          }
        }}
      >
        <div className="searchable-select-row">
          <input
            value={inputValue}
            onFocus={() => setActiveSearchableSelectKey(params.queryKey)}
            onChange={(event) => {
              params.onChange("");
              setActiveSearchableSelectKey(params.queryKey);
              setSearchableSelectQueries((current) => ({ ...current, [params.queryKey]: event.target.value }));
            }}
            placeholder={params.searchPlaceholder ?? params.placeholder}
            aria-label={params.ariaLabel}
          />
          {(params.value || inputValue) && (
            <button
              type="button"
              className="secondary-button compact-clear-button"
              onClick={() => {
                params.onChange("");
                setSearchableSelectQueries((current) => ({ ...current, [params.queryKey]: "" }));
              }}
            >
              Törlés
            </button>
          )}
          {params.action}
        </div>
        {isActive && (
          <div className="searchable-select-options" role="listbox" aria-label={`${params.ariaLabel} találatok`}>
            {visibleOptions.length === 0 && <span className="field-hint">Nincs találat.</span>}
            {visibleOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={option.id === params.value ? "searchable-option selected" : "searchable-option"}
                disabled={option.disabled}
                onMouseDown={(event) => {
                  event.preventDefault();
                  params.onChange(option.id);
                  setSearchableSelectQueries((current) => ({ ...current, [params.queryKey]: option.label }));
                  setActiveSearchableSelectKey("");
                }}
                role="option"
                aria-selected={option.id === params.value}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
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
            {renderSearchableSelect({
              queryKey: `source-move:${key}`,
              value: sourceMoveTargets[key] ?? "",
              onChange: (value) => setSourceMoveTargets((current) => ({ ...current, [key]: value })),
              options: targetOptions,
              placeholder: "Áthelyezés célja",
              searchPlaceholder: "Keresés a célok között",
              ariaLabel: "Forráshivatkozás áthelyezési célja"
            })}
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
        <span className="merge-label-line">
          Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású állítások választhatók célként.)</span>
        </span>
        {renderSearchableSelect({
          queryKey: `claim-merge:${item.object_id}`,
          value: mergeTargets[item.object_id] ?? "",
          onChange: (value) => setMergeTargets((current) => ({ ...current, [item.object_id]: value })),
          options: targetOptions.map((claim) => ({
            id: claim.id,
            label: `${claim.claim_title} (${labelReviewStatus(claim.review_status)})`,
            searchText: claim.claim_text
          })),
          placeholder: "Válassz célállítást",
          searchPlaceholder: "Keresés célállításra",
          ariaLabel: "Állítás összevonási célja",
          action: (
            <button
              className="secondary-button"
              onClick={() => handleClaimMerge(item)}
              disabled={Boolean(busy) || !mergeTargets[item.object_id]}
            >
              <GitMerge size={18} /> Összevonás
            </button>
          )
        })}
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
        <span className="merge-label-line">
          Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású entitások választhatók célként.)</span>
        </span>
        {renderSearchableSelect({
          queryKey: `entity-merge:${item.object_id}`,
          value: mergeTargets[item.object_id] ?? "",
          onChange: (value) => setMergeTargets((current) => ({ ...current, [item.object_id]: value })),
          options: targetOptions.map((entity) => ({
            id: entity.id,
            label: `${entity.canonical_name} (${labelReviewStatus(entity.review_status)})`,
            searchText: entity.description ?? "",
          })),
          placeholder: "Válassz célentitást",
          searchPlaceholder: "Keresés célentitásra",
          ariaLabel: "Entitás összevonási célja",
          action: (
            <button
              className="secondary-button"
              onClick={() => handleEntityMerge(item)}
              disabled={Boolean(busy) || !mergeTargets[item.object_id]}
            >
              <GitMerge size={18} /> Összevonás
            </button>
          )
        })}
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
        <span className="merge-label-line">
          Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású események választhatók célként.)</span>
        </span>
        {renderSearchableSelect({
          queryKey: `event-merge:${item.object_id}`,
          value: mergeTargets[item.object_id] ?? "",
          onChange: (value) => setMergeTargets((current) => ({ ...current, [item.object_id]: value })),
          options: targetOptions.map((event) => ({
            id: event.id,
            label: `${event.event_title} (${labelReviewStatus(event.review_status)})`,
            searchText: event.event_description ?? "",
          })),
          placeholder: "Válassz céleseményt",
          searchPlaceholder: "Keresés céleseményre",
          ariaLabel: "Esemény összevonási célja",
          action: (
            <button
              className="secondary-button"
              onClick={() => handleEventMerge(item)}
              disabled={Boolean(busy) || !mergeTargets[item.object_id]}
            >
              <GitMerge size={18} /> Összevonás
            </button>
          )
        })}
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
        <span className="merge-label-line">
          Összevonás célja: <span className="field-hint">(Csak nem javított, érvényes forráshivatkozású hiányzó iratjelöltek választhatók célként.)</span>
        </span>
        {renderSearchableSelect({
          queryKey: `missing-merge:${item.object_id}`,
          value: mergeTargets[item.object_id] ?? "",
          onChange: (value) => setMergeTargets((current) => ({ ...current, [item.object_id]: value })),
          options: targetOptions.map((candidate) => ({
            id: candidate.id,
            label: `${candidate.referenced_item_text} (${labelReviewStatus(candidate.review_status)})`,
            searchText: candidate.description
          })),
          placeholder: "Válassz céljelöltet",
          searchPlaceholder: "Keresés céljelöltre",
          ariaLabel: "Hiányzó iratjelölt összevonási célja",
          action: (
            <button
              className="secondary-button"
              onClick={() => handleMissingItemMerge(item)}
              disabled={Boolean(busy) || !mergeTargets[item.object_id]}
            >
              <GitMerge size={18} /> Összevonás
            </button>
          )
        })}
      </div>
    );
  }

  function handleSelectReportItem(item: ReviewReportItem) {
    setSelectedReportItem(item);
    window.setTimeout(() => {
      objectDetailPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  }

  function renderModelStatusBar() {
    const chatLoaded = llmSmoke?.configured_chat_model_loaded === true;
    const embeddingLoaded = llmSmoke?.configured_embedding_model_loaded === true;
    const reachable = llmSmoke?.reachable === true;
    const statusLabel = !llmSmoke
      ? "Modellek állapota ismeretlen"
      : !reachable
        ? "LM Studio nem elérhető"
        : chatLoaded && embeddingLoaded
          ? "Modellek készen állnak"
          : "Modellek betöltése szükséges";
    return (
      <section className={`model-status-bar ${llmSmoke && !reachable ? "has-error" : ""}`}>
        <div className="model-status-summary">
          <strong>{statusLabel}</strong>
          <span>{llmSmoke ? `${llmSmoke.provider} | ${llmSmoke.base_url}` : "Állapot lekérése folyamatban."}</span>
        </div>
        <div className="model-status-models">
          <div className="model-status-model-card">
            <div className="model-status-model-main">
              <span>Chat modell</span>
              <code>{llmSmoke?.configured_chat_model ?? "ismeretlen"}</code>
              <em>{labelModelLoadState(llmSmoke?.configured_chat_model_loaded ?? null)}</em>
            </div>
            <div className="model-status-model-actions">
              <button
                className="secondary-button"
                onClick={handleLoadChatModel}
                disabled={Boolean(busy) || !llmSmoke || chatLoaded}
              >
                Betöltés
              </button>
              <button
                className="secondary-button"
                onClick={handleUnloadChatModel}
                disabled={Boolean(busy) || !chatLoaded}
              >
                Leválasztás
              </button>
            </div>
          </div>
          <div className="model-status-model-card">
            <div className="model-status-model-main">
              <span>Embedding modell</span>
              <code>{llmSmoke?.configured_embedding_model ?? "ismeretlen"}</code>
              <em>{labelModelLoadState(llmSmoke?.configured_embedding_model_loaded ?? null)}</em>
            </div>
            <div className="model-status-model-actions">
              <button
                className="secondary-button"
                onClick={handleLoadEmbeddingModel}
                disabled={Boolean(busy) || !llmSmoke || embeddingLoaded}
              >
                Betöltés
              </button>
              <button
                className="secondary-button"
                onClick={handleUnloadEmbeddingModel}
                disabled={Boolean(busy) || !embeddingLoaded}
              >
                Leválasztás
              </button>
            </div>
          </div>
        </div>
        <div className="model-status-refresh">
          <button
            onClick={handleLlmSmoke}
            title="Modellállapot frissítése"
            disabled={Boolean(busy)}
          >
            <RefreshCw size={18} /> Állapot frissítése
          </button>
        </div>
        {llmSmoke?.error_message && <p className="model-status-error">{llmSmoke.error_message}</p>}
      </section>
    );
  }

  function currentAiOperationLabel() {
    return aiOperationLabels.has(busy) ? (busyLabels[busy] ?? busy) : "Készenlét";
  }

  function lastAiOperationStatusLabel() {
    if (!lastAiOperation) return "Még nincs AI művelet";
    return lastAiOperation.status === "succeeded" ? "Sikeres" : "Hibával zárult";
  }

  function surfaceContextLabel() {
    if (!selectedCase) return "Nincs aktív ügy";
    return `${selectedCase.case_name}${selectedCase.case_reference ? ` | ${selectedCase.case_reference}` : ""}`;
  }

  function renderSurfaceHeader(surface: WorkSurface) {
    const currentAiOperation = aiOperationLabels.has(busy) ? (busyLabels[busy] ?? busy) : "Nincs futó AI művelet";
    const isRunning = aiOperationLabels.has(busy);
    const durationLabel = isRunning
      ? formatDuration(elapsedSeconds)
      : lastAiOperation
        ? formatDuration(lastAiOperation.durationSeconds)
        : "-";
    const feedbackMessage = error || notice || "Nincs friss visszajelzés";
    return (
      <section className="panel hero-panel">
        <div>
          <h2>{workSurfaceLabels[surface]}</h2>
          <p>{surfaceContextLabel()}</p>
        </div>
        <div className={`surface-operation-card ${isRunning ? "is-running" : ""}`}>
          <span className="run-state">{isRunning ? <Loader2 className="spin" size={18} /> : <CheckCircle2 size={18} />} {currentAiOperationLabel()}</span>
          <div>
            <span>Utolsó AI művelet</span>
            <strong>{lastAiOperation?.label ?? "Még nincs AI művelet"}</strong>
          </div>
          <div>
            <span>Eredmény</span>
            <strong>{lastAiOperationStatusLabel()}</strong>
          </div>
          <div>
            <span>Időtartam</span>
            <strong>{durationLabel}</strong>
          </div>
          <div className={`surface-feedback ${error ? "has-error" : notice ? "has-notice" : ""}`}>
            <span>Visszajelzés</span>
            <strong>{feedbackMessage}</strong>
          </div>
        </div>
      </section>
    );
  }

  function renderAnalysisReadinessStrip() {
    const hasIndexStatus = canUseBatchScope && Boolean(chunkIndexStatus);
    return (
      <section className={`analysis-readiness-strip ${hasIndexStatus ? "" : "is-empty"}`}>
        <div className="analysis-readiness-main">
          <div>
            <strong>Szemantikus index állapot</strong>
            {chunkIndexStatus ? (
              <span>
                {[labelChunkIndexScope(chunkIndexStatus), chunkIndexStatus.embedding_model, chunkIndexStatus.collection_name]
                  .filter(Boolean)
                  .join(" | ")}
              </span>
            ) : (
              <span>Az aktuális elemzési forráskör indexelési készültsége itt jelenik meg.</span>
            )}
          </div>
          {chunkIndexStatus ? (
            <div className="metrics">
              <span>{labelChunkIndexStatus(chunkIndexStatus)}</span>
              <span>Indexelve: {chunkIndexStatus.indexed_chunk_count}/{chunkIndexStatus.current_chunk_count}</span>
              <span>Hiányzik: {chunkIndexStatus.missing_chunk_count}</span>
              {chunkIndexStatus.latest_run_id && (
                <span>
                  Utolsó: {chunkIndexStatus.latest_run_status ? labelRunStatus(chunkIndexStatus.latest_run_status) : "ismeretlen"}
                  {chunkIndexStatus.latest_run_finished_at ? ` | ${new Date(chunkIndexStatus.latest_run_finished_at).toLocaleString()}` : ""}
                </span>
              )}
              {chunkIndexStatus.latest_run_input_count > 0 && (
                <span>
                  Folyamat: {chunkIndexStatus.latest_run_output_count}/{chunkIndexStatus.latest_run_input_count}
                  {chunkIndexStatus.latest_run_progress_percent !== null ? ` | ${chunkIndexStatus.latest_run_progress_percent}%` : ""}
                </span>
              )}
            </div>
          ) : (
            <div className="metrics">
              <span>Nincs betöltött indexállapot</span>
              <span>Forráskör váltásakor vagy frissítéskor töltődik</span>
            </div>
          )}
          {indexJobIsRunning && <p className="field-hint">Indexeles folyamatban, az allapot automatikusan frissul.</p>}
          {usesSemanticIndex && chunkIndexStatus && !chunkIndexStatus.is_ready && (
            <p className="error-text">Szemantikus vagy hybrid futtatáshoz előbb indexelni kell az aktuális forráskört.</p>
          )}
        </div>
        {canUseBatchScope && (
          <div className="analysis-readiness-actions">
            <button
              className="secondary-button"
              onClick={handleIndexChunks}
              disabled={!selectedCaseId || Boolean(busy) || indexJobIsRunning || !hasAnalysisSource}
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
      </section>
    );
  }

  function renderResearchRunSummaryStrip() {
    if (!lastResearchFindingRun) {
      return (
        <section className="research-run-summary is-empty">
          <div className="research-run-summary-heading">
            <div>
              <span>Utolsó kutatási keresés</span>
              <strong>Még nincs kutatási találatkeresési futás ebben az ügyben.</strong>
            </div>
          </div>
          <div className="metrics">
            <span>A legutóbbi keresési fókusz és eredmény itt jelenik meg</span>
          </div>
        </section>
      );
    }
    return (
      <section className="research-run-summary">
        <div className="research-run-summary-heading">
          <div>
            <strong>Utolsó kutatási keresés - {lastResearchFindingRun.query || "Nincs megadott fókusz"}</strong>
          </div>
          <span className={`status-pill ${lastResearchFindingRun.status === "failed" || lastResearchFindingRun.validation_status === "warning" ? "is-warning" : ""}`}>
            {labelResearchFindingRunOutcome(lastResearchFindingRun)}
          </span>
        </div>
        <div className="metrics">
          <span>{labelAnalysisSourceMode((lastResearchFindingRun.source_mode ?? "case") as AnalysisSourceMode)}</span>
          <span>{lastResearchFindingRun.selected_chunk_count} szövegrész</span>
          {lastResearchFindingRun.retrieval_strategy && <span>{labelRetrievalStrategy(lastResearchFindingRun.retrieval_strategy as RetrievalStrategy)}</span>}
          {lastResearchFindingRun.max_chunks !== null && <span>Plafon: {lastResearchFindingRun.max_chunks}</span>}
          {lastResearchFindingRun.batch_size !== null && <span>Max. batch: {lastResearchFindingRun.batch_size}</span>}
          <span>{formatDateTime(lastResearchFindingRun.started_at)}</span>
        </div>
        <div className="metrics">
          <span>{lastResearchFindingRun.created_finding_count} mentett</span>
          <span>{lastResearchFindingRun.corrected_finding_count} javított</span>
          <span>{lastResearchFindingRun.unconfirmed_finding_count} nem megerősített</span>
          <span>{lastResearchFindingRun.unsupported_count} elutasított</span>
        </div>
        {lastResearchFindingRun.created_finding_count === 0 && (
          <p className="error-text">Nem jött létre mentett kutatási találat. Az okok az alábbi validációs üzenetekben láthatók.</p>
        )}
        {lastResearchFindingRun.error_message && <p className="error-text">{lastResearchFindingRun.error_message}</p>}
        {lastResearchFindingRun.unsupported_items.length > 0 && (
          <div className="module-note module-note-warning research-run-validation">
            <strong>Backend validációval elutasított jelöltek / feldolgozási okok</strong>
            <ul>
              {lastResearchFindingRun.unsupported_items.slice(0, 5).map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </section>
    );
  }

  function renderRagIndexStatusStrip() {
    const hasIndexStatus = Boolean(ragChunkIndexStatus);
    return (
      <section className={`analysis-readiness-strip ${hasIndexStatus ? "" : "is-empty"}`}>
        <div className="analysis-readiness-main">
          <div>
            <strong>Szemantikus index állapot</strong>
            {ragChunkIndexStatus ? (
              <span>
                {[labelChunkIndexScope(ragChunkIndexStatus), ragChunkIndexStatus.embedding_model, ragChunkIndexStatus.collection_name]
                  .filter(Boolean)
                  .join(" | ")}
              </span>
            ) : (
              <span>Az iratkérdező aktuális forráskörének indexelési készültsége itt jelenik meg.</span>
            )}
          </div>
          {ragChunkIndexStatus ? (
            <div className="metrics">
              <span>{labelChunkIndexStatus(ragChunkIndexStatus)}</span>
              <span>Indexelve: {ragChunkIndexStatus.indexed_chunk_count}/{ragChunkIndexStatus.current_chunk_count}</span>
              <span>Hiányzik: {ragChunkIndexStatus.missing_chunk_count}</span>
              {ragChunkIndexStatus.latest_run_id && (
                <span>
                  Utolsó: {ragChunkIndexStatus.latest_run_status ? labelRunStatus(ragChunkIndexStatus.latest_run_status) : "ismeretlen"}
                  {ragChunkIndexStatus.latest_run_finished_at ? ` | ${new Date(ragChunkIndexStatus.latest_run_finished_at).toLocaleString()}` : ""}
                </span>
              )}
              {ragChunkIndexStatus.latest_run_input_count > 0 && (
                <span>
                  Folyamat: {ragChunkIndexStatus.latest_run_output_count}/{ragChunkIndexStatus.latest_run_input_count}
                  {ragChunkIndexStatus.latest_run_progress_percent !== null ? ` | ${ragChunkIndexStatus.latest_run_progress_percent}%` : ""}
                </span>
              )}
            </div>
          ) : (
            <div className="metrics">
              <span>Nincs betöltött indexállapot</span>
              <span>Forráskör váltásakor vagy frissítéskor töltődik</span>
            </div>
          )}
          {ragIndexJobIsRunning && <p className="field-hint">Indexeles folyamatban, az allapot automatikusan frissul.</p>}
          {ragUsesSemanticIndex && ragChunkIndexStatus && !ragChunkIndexStatus.is_ready && (
            <p className="error-text">Szemantikus vagy hybrid kérdezéshez előbb indexelni kell az aktuális forráskört.</p>
          )}
        </div>
        <div className="analysis-readiness-actions">
          <button
            className="secondary-button"
            onClick={handleIndexRagChunks}
            disabled={!selectedCaseId || Boolean(busy) || ragIndexJobIsRunning || !ragHasSource}
            title="Lokális embedding és Qdrant index készítése az iratkérdező aktuális forrásköréhez"
          >
            {ragIndexJobIsRunning ? "Indexeles folyamatban" : "Szovegreszek indexelese"}
          </button>
          <label className="checkbox-label">
            <input type="checkbox" checked={ragForceReindex} onChange={(event) => setRagForceReindex(event.target.checked)} />
            Ujraindexeles
          </label>
        </div>
      </section>
    );
  }

  function renderRagRunSummaryStrip() {
    if (!lastRagRun) {
      return (
        <section className="research-run-summary is-empty">
          <div className="research-run-summary-heading">
            <div>
              <span>Utolsó iratkérdező keresés</span>
              <strong>Még nincs iratkérdező futás ebben az ügyben.</strong>
            </div>
          </div>
          <div className="metrics">
            <span>A legutóbbi kérdés és válaszállapot itt jelenik meg</span>
          </div>
        </section>
      );
    }
    return (
      <section className="research-run-summary">
        <div className="research-run-summary-heading">
          <div>
            <strong>Utolsó iratkérdező keresés - {lastRagRun.question || "Nincs megadott kérdés"}</strong>
          </div>
          <span className={`status-pill ${lastRagRun.status === "failed" || lastRagRun.insufficient_source ? "is-warning" : ""}`}>
            {labelRagRunOutcome(lastRagRun)}
          </span>
        </div>
        <div className="metrics">
          <span>{labelRagSourceMode((lastRagRun.source_mode ?? "case") as RagSourceMode)}</span>
          <span>{lastRagRun.selected_chunk_count} szövegrész</span>
          {lastRagRun.retrieval_strategy && <span>{labelRetrievalStrategy(lastRagRun.retrieval_strategy)}</span>}
          {lastRagRun.max_chunks !== null && <span>Plafon: {lastRagRun.max_chunks}</span>}
          <span>{formatDateTime(lastRagRun.started_at)}</span>
        </div>
        <div className="metrics">
          {lastRagRun.answer_mode && <span>{labelRagAnswerMode(lastRagRun.answer_mode)}</span>}
          {lastRagRun.document_answer_count > 1 && <span>{lastRagRun.document_answer_count} részválasz</span>}
          <span>{lastRagRun.used_source_count} forrás</span>
          <span>{lastRagRun.saved_answer_id ? "Mentve" : "Nincs mentve"}</span>
        </div>
        {lastRagRun.error_message && <p className="error-text">{lastRagRun.error_message}</p>}
      </section>
    );
  }

  function renderRagUsedSources(sources: RagUsedSource[]) {
    if (sources.length === 0) {
      return <p className="muted">A válaszhoz nem tartozik megjeleníthető forrásszövegrész.</p>;
    }
    return (
      <div className="rag-source-list">
        {sources.map((source, index) => (
          <article key={`${source.chunk_id}-${index}`} className="compact-item rag-source-card">
            <div className="item-card-header">
              <div>
                <strong>{source.document_filename}</strong>
                <div className="metrics">
                  <span>{source.page_number ? `${source.page_number}. oldal` : "oldal nélkül"}</span>
                  <span>{source.chunk_index}. szövegrész</span>
                  {source.retrieval_match_type && <span>{labelRetrievalMatchType(source.retrieval_match_type)}</span>}
                  {source.retrieval_score !== null && <span>relevancia {source.retrieval_score.toFixed(3)}</span>}
                </div>
              </div>
            </div>
            <blockquote>{source.quote_preview}</blockquote>
          </article>
        ))}
      </div>
    );
  }

  function renderKnowledgeIndexStatusStrip() {
    const hasIndexStatus = Boolean(knowledgeIndexStatus);
    return (
      <section className={`analysis-readiness-strip ${hasIndexStatus ? "" : "is-empty"}`}>
        <div className="analysis-readiness-main">
          <div>
            <strong>Tudásbázis index állapot</strong>
            {knowledgeIndexStatus ? (
              <span>{[knowledgeIndexStatus.embedding_model, knowledgeIndexStatus.collection_name].filter(Boolean).join(" | ")}</span>
            ) : (
              <span>A Markdown tudásbázis indexelési készültsége itt jelenik meg.</span>
            )}
          </div>
          {knowledgeIndexStatus ? (
            <div className="metrics">
              <span>{knowledgeIndexStatus.is_ready ? "index kész" : knowledgeIndexStatus.needs_indexing ? "indexelés szükséges" : "nincs indexelhető tartalom"}</span>
              <span>Dokumentum: {knowledgeIndexStatus.indexed_document_count}/{knowledgeIndexStatus.document_count}</span>
              <span>Szövegrész: {knowledgeIndexStatus.indexed_chunk_count}/{knowledgeIndexStatus.chunk_count}</span>
              <span>Hiányzik: {knowledgeIndexStatus.missing_chunk_count}</span>
            </div>
          ) : (
            <div className="metrics">
              <span>Nincs betöltött indexállapot</span>
              <span>A Tudásbázis megnyitásakor frissül</span>
            </div>
          )}
          {knowledgeRetrievalStrategy !== "keyword" && knowledgeIndexStatus && !knowledgeIndexStatus.is_ready && (
            <p className="error-text">Szemantikus vagy hybrid tudásbázis kérdezéshez előbb indexelni kell a Markdown szövegrészeket.</p>
          )}
        </div>
        <div className="analysis-readiness-actions">
          <button
            className="secondary-button"
            onClick={handleIndexKnowledgeDocuments}
            disabled={Boolean(busy) || knowledgeDocuments.length === 0}
            title="Lokális embedding és Qdrant index készítése a tudásbázis dokumentumaihoz"
          >
            Tudásbázis indexelése
          </button>
          <label className="checkbox-label">
            <input type="checkbox" checked={knowledgeForceReindex} onChange={(event) => setKnowledgeForceReindex(event.target.checked)} />
            Újraindexelés
          </label>
        </div>
      </section>
    );
  }

  function renderKnowledgeUsedSources(sources: KnowledgeUsedSource[]) {
    if (sources.length === 0) {
      return <p className="muted">A válaszhoz nem tartozik megjeleníthető tudásbázis-forrás.</p>;
    }
    const normalizedSearch = knowledgeSourceSearch.trim().toLocaleLowerCase("hu-HU");
    const visibleSources = normalizedSearch
      ? sources.filter((source) => {
          const key = knowledgeSourceKey(source);
          const detail = knowledgeSourceDetails[key];
          const searchableText = [
            source.relative_path,
            source.original_filename,
            source.heading_path,
            `${source.chunk_index}. szövegrész`,
            source.retrieval_match_type ? labelRetrievalMatchType(source.retrieval_match_type) : "",
            source.retrieval_score !== null ? source.retrieval_score.toFixed(3) : "",
            source.contains_code_block ? "kódblokk" : "",
            ...(detail?.code_languages ?? []),
            detail?.text ?? ""
          ]
            .filter(Boolean)
            .join(" ")
            .toLocaleLowerCase("hu-HU");
          return searchableText.includes(normalizedSearch);
        })
      : sources;
    return (
      <>
        <div className="knowledge-source-toolbar">
          <input
            type="search"
            value={knowledgeSourceSearch}
            onChange={(event) => setKnowledgeSourceSearch(event.target.value)}
            placeholder="Keresés a felhasznált forrásokban"
          />
          <span className="metrics">
            <span>{visibleSources.length}/{sources.length} megjelenítve</span>
          </span>
        </div>
        {visibleSources.length === 0 ? (
          <div className="rag-empty-state">
            <strong>Nincs megjeleníthető forrás</strong>
            <span>A keresés nem talált egyezést a felhasznált Markdown források között.</span>
          </div>
        ) : (
          <div className="rag-source-list knowledge-source-list">
            {visibleSources.map((source, index) => (
              <article key={`${source.chunk_id}-${index}`} className="compact-item rag-source-card knowledge-source-card">
                <div className="item-card-header">
                  <div>
                    <strong>{source.relative_path ?? source.original_filename}</strong>
                    <div className="metrics">
                      {source.relative_path && <span>{source.original_filename}</span>}
                      {source.heading_path && <span>{source.heading_path}</span>}
                      <span>{source.chunk_index}. szövegrész</span>
                      {source.retrieval_match_type && <span>{labelRetrievalMatchType(source.retrieval_match_type)}</span>}
                      {source.retrieval_score !== null && <span>relevancia {source.retrieval_score.toFixed(3)}</span>}
                      {source.contains_code_block && <span>kódblokk</span>}
                    </div>
                  </div>
                </div>
                {renderKnowledgeSourceDetail(source)}
              </article>
            ))}
          </div>
        )}
      </>
    );
  }

  function renderKnowledgeSourceDetail(source: KnowledgeUsedSource) {
    const key = knowledgeSourceKey(source);
    const isOpen = expandedKnowledgeSourceKeys.includes(key);
    const isLoading = knowledgeSourceLoadingKeys.includes(key);
    const detail = knowledgeSourceDetails[key];
    const error = knowledgeSourceErrors[key];
    return (
      <div className="knowledge-source-detail">
        <button className="secondary-button" onClick={() => toggleKnowledgeSource(source)} disabled={isLoading}>
          {isOpen ? "Szövegrész bezárása" : "Szövegrész megnyitása"}
        </button>
        {isOpen && (
          <div className="knowledge-source-expanded">
            {isLoading && <p className="muted">Szövegrész betöltése...</p>}
            {error && <p className="error-text">{error}</p>}
            {detail && (
              <>
                <div className="metrics">
                  <span>{detail.text.length} karakter</span>
                  {detail.contains_code_block && <span>kódblokk</span>}
                  {detail.code_languages.map((language) => <span key={language}>{language}</span>)}
                </div>
                <div className="knowledge-source-full-text markdown-source-text">
                  <MarkdownAnswer>{detail.text}</MarkdownAnswer>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  function renderRelationshipGraphNode(node: RelationshipGraphNode) {
    const relationshipFocusIds = relationshipGraph
      ? relationshipGraph.focus_node_ids.length > 0
        ? relationshipGraph.focus_node_ids
        : [relationshipGraph.focus_node_id]
      : [];
    const isFocus = relationshipFocusIds.includes(node.id);
    const metadataEntries = Object.entries(node.metadata ?? {}).filter(([, value]) =>
      value !== null && value !== undefined && typeof value !== "object"
    );
    return (
      <article key={node.id} className="compact-item graph-node-card">
        <div className="item-card-header">
          <div>
            <strong>{node.label}</strong>
            <div className="metrics">
              <span>{labelObjectType(node.type)}</span>
              {isFocus && <span>fókusz</span>}
              {node.status.review_status && <span>{labelReviewStatus(node.status.review_status)}</span>}
              {node.status.source_validation_status && <span>{labelSourceValidationStatus(node.status.source_validation_status)}</span>}
            </div>
          </div>
        </div>
        {node.subtitle && <div className="graph-node-detail-text">{node.subtitle}</div>}
        {metadataEntries.length > 0 && (
          <div className="metrics">
            {metadataEntries.map(([key, value]) => (
              <span key={`${node.id}-${key}`}>{key}: {String(value)}</span>
            ))}
          </div>
        )}
      </article>
    );
  }

  function renderRelationshipGraphEdge(edge: RelationshipGraphEdge, graph: RelationshipGraph | null = relationshipGraph) {
    const sourceNode = graph?.nodes.find((node) => node.id === edge.source);
    const targetNode = graph?.nodes.find((node) => node.id === edge.target);
    return (
      <article key={edge.id} className="compact-item graph-edge-card">
        <div className="item-card-header">
          <div>
            <strong>{edge.label}</strong>
            <div className="metrics">
              <span>{edge.type}</span>
            </div>
          </div>
        </div>
        <p className="field-hint">
          {sourceNode?.label ?? edge.source} → {targetNode?.label ?? edge.target}
        </p>
      </article>
    );
  }

  function renderRelationshipSelectedNode(node: RelationshipGraphNode | null, graph: RelationshipGraph | null) {
    if (!graph) {
      return (
        <div className="research-empty-state relationship-inspector-empty">
          <strong>Nincs betöltött térkép</strong>
          <p>Nyiss meg egy objektumot a kapcsolati nézethez.</p>
        </div>
      );
    }
    if (!node) {
      return (
        <div className="research-empty-state relationship-inspector-empty">
          <strong>Nincs kijelölt elem</strong>
          <p>Kattints egy elemre a térképen.</p>
        </div>
      );
    }
    return (
      <div className="relationship-inspector-content">
        {renderRelationshipGraphNode(node)}
      </div>
    );
  }

  function renderRelationshipSelectedEdge(edge: RelationshipGraphEdge | null, selectedNode: RelationshipGraphNode | null, graph: RelationshipGraph | null) {
    if (!graph) {
      return (
        <div className="research-empty-state relationship-inspector-empty">
          <strong>Nincs betöltött kapcsolat</strong>
          <p>A kapcsolatok a térkép megnyitása után vizsgálhatók.</p>
        </div>
      );
    }
    if (edge) {
      return (
        <div className="relationship-inspector-content">
          {renderRelationshipGraphEdge(edge)}
        </div>
      );
    }
    const relatedEdges = selectedNode
      ? graph.edges.filter((item) => item.source === selectedNode.id || item.target === selectedNode.id)
      : [];
    if (relatedEdges.length === 0) {
      return (
        <div className="research-empty-state relationship-inspector-empty">
          <strong>Nincs kijelölt kapcsolat</strong>
          <p>Kattints egy kapcsolatra a térképen, vagy válassz olyan elemet, amelyhez tartozik kapcsolat.</p>
        </div>
      );
    }
    return (
      <div className="compact-list relationship-inspector-list">
        {relatedEdges.map((item) => renderRelationshipGraphEdge(item, graph))}
      </div>
    );
  }

  function toggleRelationshipFocusObject(item: ReviewReportItem) {
    const key = relationshipFocusKey(item.object_type, item.object_id);
    setRelationshipGraphFocusKeys((current) => {
      if (current.includes(key)) {
        return current.filter((value) => value !== key);
      }
      if (current.length >= maxRelationshipFocusObjects) {
        setNotice(`Legfeljebb ${maxRelationshipFocusObjects} objektum jelölhető ki egyszerre.`);
        return current;
      }
      return [...current, key];
    });
  }

  function selectVisibleRelationshipFocusObjects() {
    if (relationshipVisibleCandidateKeys.length === 0) return;
    setRelationshipGraphFocusKeys((current) => {
      const next = [...current];
      for (const key of relationshipVisibleCandidateKeys) {
        if (next.includes(key)) continue;
        if (next.length >= maxRelationshipFocusObjects) {
          setNotice(`Legfeljebb ${maxRelationshipFocusObjects} objektum jelölhető ki egyszerre.`);
          break;
        }
        next.push(key);
      }
      return next;
    });
  }

  function removeVisibleRelationshipFocusObjects() {
    if (relationshipVisibleCandidateKeys.length === 0) return;
    const visibleKeys = new Set(relationshipVisibleCandidateKeys);
    setRelationshipGraphFocusKeys((current) => current.filter((key) => !visibleKeys.has(key)));
  }

  function clearRelationshipGraphAndSelection() {
    setRelationshipGraphFocusKeys([]);
    setRelationshipGraph(null);
    setSelectedRelationshipEdgeId(null);
    setSelectedRelationshipNodeId(null);
    setNotice("Kapcsolati térkép kiürítve.");
    setLastActionSummary("Nincs megjelenített kapcsolati térkép");
  }

  function renderRelationshipObjectOption(item: ReviewReportItem) {
    const focusKey = relationshipFocusKey(item.object_type, item.object_id);
    const isSelected = relationshipGraphFocusKeys.includes(focusKey);
    const disabled = !isSelected && relationshipFocusLimitReached;
    return (
      <label key={item.object_id} className={`checkbox-label source-document-option relationship-object-option ${isSelected ? "is-selected" : ""}`}>
        <input
          type="checkbox"
          checked={isSelected}
          disabled={disabled}
          onChange={() => toggleRelationshipFocusObject(item)}
        />
        <span>
          <strong>{truncateText(item.title, 86)}</strong>
          <small>{truncateText(item.body_text ?? "Nincs rövid leírás.", 120)}</small>
        </span>
      </label>
    );
  }

  function renderRelationshipMapSurface() {
    const canApplyGraphSelection = Boolean(selectedCaseId && (selectedRelationshipFocusCount > 0 || relationshipGraph));
    const canSelectVisibleRelationshipObjects =
      relationshipObjectCandidates.length > 0 &&
      selectedRelationshipFocusCount < maxRelationshipFocusObjects &&
      selectedVisibleRelationshipFocusCount < relationshipObjectCandidates.length;
    const canRemoveVisibleRelationshipObjects = selectedVisibleRelationshipFocusCount > 0;
    const selectedRelationshipNode = visibleRelationshipGraph?.nodes.find((node) => node.id === selectedRelationshipNodeId) ?? null;
    const selectedRelationshipEdge = visibleRelationshipGraph?.edges.find((edge) => edge.id === selectedRelationshipEdgeId) ?? null;
    const selectedRelationshipFocusSummary = Object.entries(selectedRelationshipFocusLabels)
      .map(([label, count]) => `${label}: ${count}`)
      .join(" | ");
    return (
      <section className="surface-placeholder relationship-map-surface">
        {renderSurfaceHeader("relationship_map")}

        <section className="relationship-map-layout">
          <section className="relationship-top-row">
          <section className="panel relationship-focus-panel">
            <div className="section-heading">
              <h2>Megjelenítendő objektum</h2>
              <GitMerge size={20} />
            </div>
            <div className="surface-form">
              <div className="form-row relationship-focus-row">
                <label>
                  Objektumtípus
                  <select
                    value={relationshipGraphObjectType}
                    onChange={(event) => setRelationshipGraphObjectType(event.target.value)}
                  >
                    <option value="">Összes</option>
                    {objectTypes.filter(Boolean).map((item) => (
                      <option key={item} value={item}>{labelObjectType(item)}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Keresés
                  <input
                    value={relationshipGraphObjectSearch}
                    onChange={(event) => setRelationshipGraphObjectSearch(event.target.value)}
                    placeholder="Cím, leírás vagy forrásrészlet"
                  />
                </label>
              </div>
              <div className="button-row relationship-selection-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={selectVisibleRelationshipFocusObjects}
                  disabled={!canSelectVisibleRelationshipObjects || Boolean(busy)}
                >
                  Láthatók kijelölése
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={removeVisibleRelationshipFocusObjects}
                  disabled={!canRemoveVisibleRelationshipObjects || Boolean(busy)}
                >
                  Láthatók levétele
                </button>
              </div>
              <div className="source-filter-list relationship-object-list">
                {!report && (
                  <div className="research-empty-state relationship-object-empty">
                    <strong>Nincs betöltött áttekintési jelentés</strong>
                    <p>Az objektumválasztó az aktuális ügy áttekintési jelentéséből dolgozik.</p>
                  </div>
                )}
                {report && relationshipObjectCandidates.length === 0 && (
                  <div className="research-empty-state relationship-object-empty">
                    <strong>Nincs választható objektum</strong>
                    <p>Ehhez a típushoz nincs érvényes forráshivatkozású találat, vagy a keresés nem adott eredményt.</p>
                  </div>
                )}
                {relationshipObjectCandidates.map(renderRelationshipObjectOption)}
              </div>
              <div className="metrics relationship-focus-summary">
                <span>{selectedRelationshipFocusCount} kijelölve / {maxRelationshipFocusObjects}</span>
                {selectedRelationshipFocusSummary && <span>{selectedRelationshipFocusSummary}</span>}
              </div>
              <div className="button-row">
                <button onClick={handleLoadRelationshipGraph} disabled={!canApplyGraphSelection || Boolean(busy)}>
                  <GitMerge size={18} /> Térkép frissítése kijelölésből
                </button>
                <button
                  className="secondary-button"
                  onClick={clearRelationshipGraphAndSelection}
                  disabled={(!relationshipGraph && relationshipGraphFocusKeys.length === 0) || Boolean(busy)}
                >
                  Térkép ürítése
                </button>
              </div>
            </div>
          </section>

            <section className="panel relationship-inspector-panel">
              <div className="section-heading">
                <h2>Kijelölt csomópont tartalma</h2>
                <GitMerge size={20} />
              </div>
              {renderRelationshipSelectedNode(selectedRelationshipNode, visibleRelationshipGraph)}
            </section>

            <section className="panel relationship-inspector-panel">
              <div className="section-heading">
                <h2>Kapcsolatok</h2>
                <GitMerge size={20} />
              </div>
              {renderRelationshipSelectedEdge(selectedRelationshipEdge, selectedRelationshipNode, visibleRelationshipGraph)}
            </section>
          </section>

          <section className="panel relationship-graph-panel">
            <div className="section-heading">
              <h2>Kapcsolati térkép</h2>
              <GitMerge size={20} />
            </div>
            {!relationshipGraph || !visibleRelationshipGraph ? (
              <div className="research-empty-state relationship-empty-state">
                <strong>Nincs megjelenített kapcsolati térkép</strong>
                <p>Válassz egy érvényes forráshivatkozású objektumot, majd nyisd meg a térképet.</p>
              </div>
            ) : (
              <div className="relationship-graph-preview">
                <div className="metrics">
                  <span>{relationshipGraph.focus_node_ids.length} fókuszobjektum</span>
                  <span>{visibleRelationshipGraph.limits.node_count} / {relationshipGraph.limits.node_count} elem</span>
                  <span>{visibleRelationshipGraph.limits.edge_count} / {relationshipGraph.limits.edge_count} kapcsolat</span>
                  {relationshipGraph.limits.truncated && <span>rövidítve</span>}
                </div>
                <div className="relationship-layer-toggles">
                  {(Object.keys(relationshipGraphLayerLabels) as RelationshipGraphLayerKey[]).map((layerKey) => (
                    <label key={layerKey} className="checkbox-label relationship-layer-toggle">
                      <input
                        type="checkbox"
                        checked={relationshipGraphLayers[layerKey]}
                        onChange={(event) =>
                          setRelationshipGraphLayers((current) => ({
                            ...current,
                            [layerKey]: event.target.checked
                          }))
                        }
                      />
                      <span>{relationshipGraphLayerLabels[layerKey]}</span>
                    </label>
                  ))}
                </div>
                {relationshipGraph.warnings.length > 0 && (
                  <div className="module-note module-note-warning">
                    {relationshipGraph.warnings.map((warning) => (
                      <p key={warning.code}>{warning.message}</p>
                    ))}
                  </div>
                )}
                <Suspense
                  fallback={
                    <div className="relationship-flow-canvas relationship-flow-loading">
                      <span>Kapcsolati térkép vászon betöltése...</span>
                    </div>
                  }
                >
                  <RelationshipFlowCanvas
                    graph={visibleRelationshipGraph}
                    labelObjectType={labelObjectType}
                    labelSourceValidationStatus={labelSourceValidationStatus}
                    selectedEdgeId={selectedRelationshipEdgeId}
                    selectedNodeId={selectedRelationshipNodeId}
                    onEdgeSelect={(edgeId) => {
                      const edge = visibleRelationshipGraph.edges.find((item) => item.id === edgeId);
                      setSelectedRelationshipEdgeId(edgeId);
                      setSelectedRelationshipNodeId(edge?.target ?? null);
                    }}
                    onNodeSelect={(nodeId) => {
                      setSelectedRelationshipNodeId(nodeId);
                      setSelectedRelationshipEdgeId(null);
                    }}
                  />
                </Suspense>
              </div>
            )}
          </section>
        </section>
      </section>
    );
  }

  function isLastAssistantMessage(message: AssistantMessageRead) {
    const messages = assistantActiveChat?.messages ?? [];
    const lastMessage = messages[messages.length - 1];
    return message.role === "assistant" && lastMessage?.id === message.id;
  }

  function renderAssistantMessage(message: AssistantMessageRead) {
    const isUser = message.role === "user";
    return (
      <article key={message.id} className={"assistant-message " + (isUser ? "is-user" : "is-assistant")}>
        <div className="assistant-message-meta">
          <span>{isUser ? "Te" : "AI-asszisztens"}</span>
          <span>{new Date(message.created_at).toLocaleString()}</span>
        </div>
        {isUser ? (
          <p className="assistant-user-text">{message.content}</p>
        ) : (
          <>
            <MarkdownAnswer>{message.content}</MarkdownAnswer>
            <div className="assistant-message-actions">
              <button type="button" onClick={() => void handleCopyAssistantMessage(message)} disabled={Boolean(busy)} title="Válasz másolása" aria-label="Válasz másolása">
                <Copy size={15} />
              </button>
              {isLastAssistantMessage(message) && (
                <button type="button" onClick={() => void handleRegenerateLastAssistantMessage()} disabled={Boolean(busy)} title="Utolsó válasz újragenerálása" aria-label="Utolsó válasz újragenerálása">
                  <RotateCcw size={15} />
                </button>
              )}
            </div>
          </>
        )}
        {message.error_message && <p className="field-hint">{message.error_message}</p>}
      </article>
    );
  }

  function renderAssistantPendingUser(content: string) {
    return (
      <article className="assistant-message is-user is-pending">
        <div className="assistant-message-meta">
          <span>Te</span>
          <span>küldés alatt</span>
        </div>
        <p className="assistant-user-text">{content}</p>
      </article>
    );
  }

  function renderAssistantTyping() {
    return (
      <article className="assistant-message is-assistant is-typing" aria-label="AI-asszisztens válaszol">
        <div className="assistant-typing-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </article>
    );
  }

  function renderAssistantSurface() {
    const messages = assistantActiveChat?.messages ?? [];
    const pendingMessage = assistantPendingMessage?.chatId === assistantActiveChatId ? assistantPendingMessage : null;
    const isRegeneratingAssistantMessage = Boolean(assistantActiveChatId) && assistantRegeneratingChatId === assistantActiveChatId;
    const hasConversationContent = messages.length > 0 || Boolean(pendingMessage) || isRegeneratingAssistantMessage;
    const canSend = assistantDraft.trim().length > 0 && !busy;
    const assistantMenuChat = assistantMenu ? assistantChats.find((chat) => chat.id === assistantMenu.chatId) : null;
    return (
      <section className="assistant-surface">
        <section className="assistant-shell">
          <aside className="assistant-history-rail" aria-label="AI-asszisztens beszélgetések">
            <div className="assistant-rail-actions">
              <button onClick={handleCreateAssistantChat} disabled={Boolean(busy)}>
                <FilePlus2 size={18} /> Új chat
              </button>
              <button className="secondary-button" onClick={() => void refreshAssistantChats(true)} disabled={Boolean(busy)} title="Beszélgetések frissítése">
                <RefreshCw size={18} />
              </button>
            </div>
            <div className="assistant-history-list">
              {assistantChats.length === 0 && <p className="muted">Nincs mentett beszélgetés.</p>}
              {assistantChats.map((chat) => (
                <div key={chat.id} className={"assistant-history-item " + (assistantActiveChatId === chat.id ? "is-active" : "")}>
                  <button
                    type="button"
                    className="assistant-history-title"
                    onClick={() => void handleLoadAssistantChat(chat.id)}
                    disabled={Boolean(busy)}
                    title={chat.title}
                  >
                    <span>{chat.title}</span>
                    <small>{new Date(chat.updated_at).toLocaleString()}</small>
                  </button>
                  <button
                    type="button"
                    className="assistant-history-menu-button"
                    onClick={(event) => {
                      event.stopPropagation();
                      const rect = event.currentTarget.getBoundingClientRect();
                      const menuWidth = 150;
                      setAssistantMenu((current) => current?.chatId === chat.id ? null : {
                        chatId: chat.id,
                        left: Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8)),
                        top: Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - 96))
                      });
                    }}
                    disabled={Boolean(busy)}
                    aria-label="Beszélgetés műveletei"
                    title="Beszélgetés műveletei"
                  >
                    <MoreVertical size={16} />
                  </button>
                </div>
              ))}
            </div>
          </aside>

          <section className={"assistant-chat-canvas " + (hasConversationContent ? "has-messages" : "is-empty")}>

            <div className="assistant-thread" ref={assistantMessageListRef}>
              {!hasConversationContent && (
                <div className="assistant-start-state">
                  <h2>Miben segíthetek?</h2>
                </div>
              )}
              {messages.map(renderAssistantMessage)}
              {pendingMessage && renderAssistantPendingUser(pendingMessage.content)}
              {(pendingMessage || isRegeneratingAssistantMessage) && renderAssistantTyping()}
            </div>

            <div className="assistant-composer-shell">
              <div className="assistant-composer">
                <div className="assistant-composer-input">
                  <textarea
                    ref={assistantDraftRef}
                    value={assistantDraft}
                    onChange={(event) => setAssistantDraft(event.target.value)}
                    placeholder="Kérdezz bármit"
                    rows={1}
                    disabled={Boolean(busy)}
                  />
                </div>
                <button
                  type="button"
                  className={"assistant-reasoning-toggle " + (assistantReasoningEnabled ? "is-active" : "")}
                  onClick={() => setAssistantReasoningEnabled((current) => !current)}
                  disabled={Boolean(busy)}
                  title="Gondolkodó mód"
                  aria-pressed={assistantReasoningEnabled}
                >
                  <Brain size={16} />
                  <span>Gondolkodó</span>
                </button>
                <button onClick={handleSendAssistantMessage} disabled={!canSend} title="Küldés" aria-label="Üzenet küldése">
                  <Send size={18} />
                </button>
              </div>
            </div>
          </section>
        </section>
        {assistantMenu && assistantMenuChat && (
          <div
            className="assistant-history-menu-popover"
            style={{ left: assistantMenu.left, top: assistantMenu.top }}
          >
            <button type="button" onClick={() => openAssistantRenameDialog(assistantMenuChat)} disabled={Boolean(busy)}>
              Átnevezés
            </button>
            <button type="button" className="danger-action" onClick={() => void handleDeleteAssistantChat(assistantMenuChat)} disabled={Boolean(busy)}>
              <Trash2 size={15} /> Törlés
            </button>
          </div>
        )}
        {assistantRenameDialog && (
          <div className="assistant-rename-backdrop" onMouseDown={closeAssistantRenameDialog} role="presentation">
            <form
              className="assistant-rename-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="assistant-rename-title"
              onMouseDown={(event) => event.stopPropagation()}
              onSubmit={(event) => {
                event.preventDefault();
                void handleRenameAssistantChat();
              }}
            >
              <div className="assistant-rename-heading">
                <strong id="assistant-rename-title">Beszélgetés átnevezése</strong>
                <span className="field-hint">A név a bal oldali beszélgetéslistában jelenik meg.</span>
              </div>
              <label>
                <span>Új név</span>
                <input
                  ref={assistantRenameInputRef}
                  value={assistantRenameDraft}
                  onChange={(event) => setAssistantRenameDraft(event.target.value)}
                  maxLength={160}
                  disabled={Boolean(busy)}
                />
              </label>
              <div className="assistant-rename-actions">
                <button type="button" className="secondary-button" onClick={closeAssistantRenameDialog} disabled={Boolean(busy)}>
                  Mégse
                </button>
                <button type="submit" disabled={Boolean(busy) || assistantRenameDraft.trim().length === 0}>
                  Mentés
                </button>
              </div>
            </form>
          </div>
        )}
      </section>
    );
  }

  function renderKnowledgeBaseSurface() {
    return (
      <section className="surface-placeholder general-rag-surface knowledge-surface">
        {renderSurfaceHeader("knowledge_base")}
        <section className="workbench-status-row rag-status-row">
          {renderKnowledgeIndexStatusStrip()}
          <section className="research-run-summary">
            <div className="research-run-summary-heading">
              <div>
                <strong>Tudásbázis állomány</strong>
              </div>
              <span className={`status-pill ${knowledgeDocuments.length === 0 ? "is-warning" : ""}`}>
                {knowledgeDocuments.length === 0 ? "üres" : "használható"}
              </span>
            </div>
            <div className="metrics">
              <span>{knowledgeDocuments.length} dokumentum</span>
              <span>{activeKnowledgeDocuments.length} aktív</span>
              <span>{activeKnowledgeDocuments.reduce((sum, document) => sum + document.chunk_count, 0)} szövegrész</span>
              <span>{knowledgeDocuments.filter((document) => document.processing_status === "indexed").length} indexelt</span>
              <span>{knowledgeDocumentIds.length > 0 ? `${knowledgeDocumentIds.length} kijelölve` : "teljes tudásbázis"}</span>
            </div>
          </section>
        </section>

        <section className="knowledge-workspace-grid">
          <div className="knowledge-left-column">
            <section className="panel rag-query-panel knowledge-query-panel">
              <div className="section-heading">
                <h2>Kérdés a tudásbázishoz</h2>
                <MessageSquare size={20} />
              </div>
              <div className="surface-form">
                <div className="form-row knowledge-query-settings-row">
                  <label>
                    Válasz típusa
                    <select value={knowledgeAnswerMode} onChange={(event) => setKnowledgeAnswerMode(event.target.value as RagAnswerMode)}>
                      {ragAnswerModes.map((mode) => (
                        <option key={mode} value={mode}>{ragAnswerModeLabels[mode]}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Forráskeresés
                    <select value={knowledgeRetrievalStrategy} onChange={(event) => setKnowledgeRetrievalStrategy(event.target.value as RetrievalStrategy)}>
                      {retrievalStrategies.map((item) => <option key={item} value={item}>{labelRetrievalStrategy(item)}</option>)}
                    </select>
                  </label>
                  <label>
                    Szövegrész plafon
                    <input
                      type="number"
                      min={1}
                      max={60}
                      value={knowledgeMaxChunks}
                      onChange={(event) => setKnowledgeMaxChunks(clampNumberInput(event.target.value, 1, 60, 30))}
                    />
                  </label>
                </div>
                <label>
                  Kérdés
                  <textarea
                    value={knowledgeQuestion}
                    onChange={(event) => setKnowledgeQuestion(event.target.value)}
                    rows={6}
                    placeholder="Írd be, mire szeretnél választ kapni kizárólag az importált Markdown tudásbázis alapján."
                  />
                </label>
                {knowledgeQuestion.trim().length > 0 && activeKnowledgeDocuments.length === 0 && (
                  <p className="error-text">Nincs aktív tudásbázis dokumentum.</p>
                )}
                {showKnowledgeIndexMissingError && (
                  <p className="error-text">A kijelölt tudásbázis-forrásokhoz hiányzik az aktuális index.</p>
                )}
                <button onClick={handleRunKnowledgeQuery} disabled={!canRunKnowledgeQuery}>
                  <Play size={18} /> Kérdezés indítása
                </button>
              </div>
            </section>

            <section className="panel rag-query-panel knowledge-import-panel">
              <div className="section-heading">
                <h2>Tudásanyag importálás</h2>
                <FilePlus2 size={20} />
              </div>
              <div className="surface-form">
                <label>
                  Markdown fájlok
                  <input
                    ref={knowledgeBatchInputRef}
                    type="file"
                    accept=".md,text/markdown,text/plain"
                    multiple
                    onChange={(event) => {
                      setKnowledgeBatchFiles(Array.from(event.target.files ?? []));
                      resetKnowledgeBatchState(true);
                    }}
                  />
                </label>
                <label>
                  Közös relatív mappaútvonal
                  <input
                    value={knowledgeBatchRelativePath}
                    onChange={(event) => {
                      setKnowledgeBatchRelativePath(event.target.value);
                      setKnowledgeBatchPreview(null);
                      setKnowledgeBatchImportResult(null);
                    }}
                    placeholder="pl. notes/linux"
                  />
                </label>
                <div className="button-row">
                  <button onClick={handlePreviewKnowledgeBatch} disabled={Boolean(busy) || knowledgeBatchFiles.length === 0 || !hasKnowledgeBatchRelativePath()}>
                    <Search size={18} /> Import előnézet
                  </button>
                  <button className="secondary-button" onClick={handleImportKnowledgeBatch} disabled={Boolean(busy) || !knowledgeBatchPreview || knowledgeBatchFiles.length === 0 || !hasKnowledgeBatchRelativePath()}>
                    <FilePlus2 size={18} /> Batch import indítása
                  </button>
                  <button className="secondary-button" onClick={() => resetKnowledgeBatchState()} disabled={Boolean(busy) || knowledgeBatchFiles.length === 0}>
                    Kijelölés törlése
                  </button>
                </div>
                {knowledgeBatchFiles.length > 0 && (
                  <div className="metrics">
                    <span>{knowledgeBatchFiles.length} kijelölt fájl</span>
                    {knowledgeBatchPreview && <span>{knowledgeBatchPreview.summary.ready} új fájl</span>}
                    {knowledgeBatchPreview && <span>{knowledgeBatchPreview.summary.same_hash} azonos tartalom</span>}
                    {knowledgeBatchPreview && <span>{knowledgeBatchPreview.summary.same_relative_path} döntést igényel</span>}
                    {knowledgeBatchPreview && <span>{knowledgeBatchPreview.summary.invalid} hibás</span>}
                  </div>
                )}
                {knowledgeBatchPreview && (
                  <div className="compact-list knowledge-batch-preview-list">
                    {knowledgeBatchPreview.items.filter((item) => item.status !== "ready").length === 0 && (
                      <div className="research-empty-state compact-empty-state knowledge-import-empty-state">
                        <strong>Nincs importütközés</strong>
                        <span>Az összes kijelölt fájl automatikusan importálható.</span>
                      </div>
                    )}
                    {knowledgeBatchPreview.items.filter((item) => item.status !== "ready").map((item) => (
                      <article key={item.client_file_id} className={`compact-item ${item.status === "invalid" ? "is-muted" : ""}`}>
                        <div className="item-card-header">
                          <div className="knowledge-conflict-paths">
                            <strong>{item.resolved_relative_path ?? item.original_filename ?? item.client_file_id}</strong>
                            {item.existing_relative_path && (
                              <small>
                                <span>meglévő: </span>
                                <span>{item.existing_relative_path}</span>
                              </small>
                            )}
                          </div>
                          <span className="status-pill is-warning">{labelKnowledgeBatchPreviewStatus(item.status)}</span>
                        </div>
                        <div className="metrics">
                          {item.error && <span>{item.error}</span>}
                        </div>
                        {item.status === "same_relative_path" && (
                          <div className="inline-control-row">
                            <select
                              value={knowledgeBatchDecisions[item.client_file_id] ?? "replace"}
                              onChange={(event) =>
                                setKnowledgeBatchDecisions((current) => ({
                                  ...current,
                                  [item.client_file_id]: event.target.value as KnowledgeBatchImportDecision
                                }))
                              }
                            >
                              <option value="keep_existing">Meglévő megtartása</option>
                              <option value="replace">Csere az új fájlra</option>
                            </select>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                )}
                {knowledgeBatchImportResult && (
                  <div className="module-note">
                    <strong>Import összegzés</strong>
                    <div className="metrics">
                      <span>{knowledgeBatchImportResult.summary.imported} importált</span>
                      <span>{knowledgeBatchImportResult.summary.replaced} cserélt</span>
                      <span>{knowledgeBatchImportResult.summary.skipped} kihagyott</span>
                      <span>{knowledgeBatchImportResult.summary.failed} hibás</span>
                    </div>
                  </div>
                )}
              </div>
            </section>

            <section className="panel rag-query-panel knowledge-documents-panel">
              <div className="section-heading">
                <h2>Markdown tudásanyag</h2>
                <Database size={20} />
              </div>
              <div className="knowledge-document-toolbar">
                <button
                  className="secondary-button"
                  onClick={selectAllFilteredKnowledgeDocuments}
                  disabled={filteredKnowledgeDocuments.length === 0 || Boolean(busy)}
                >
                  Láthatók kijelölése
                </button>
                <button
                  className="secondary-button"
                  onClick={() => setKnowledgeDocumentIds([])}
                  disabled={knowledgeDocumentIds.length === 0 || Boolean(busy)}
                >
                  Kijelölés törlése
                </button>
                <button
                  className="secondary-button"
                  onClick={handleArchiveSelectedKnowledgeDocuments}
                  disabled={selectedActiveKnowledgeDocuments.length === 0 || Boolean(busy)}
                >
                  <Archive size={18} /> Archiválás
                </button>
                <button
                  className="danger-button"
                  onClick={handleDeleteSelectedKnowledgeDocuments}
                  disabled={selectedKnowledgeDocuments.length === 0 || Boolean(busy)}
                >
                  <Trash2 size={18} /> Végleges törlés
                </button>
              </div>
              <div className="source-filter-panel">
                <input
                  className="source-filter-search"
                  value={knowledgeDocumentSearch}
                  onChange={(event) => setKnowledgeDocumentSearch(event.target.value)}
                  placeholder="Keresés a tudásbázis dokumentumokban"
                />
                <div className="compact-list knowledge-document-list">
                  {knowledgeDocuments.length === 0 && (
                    <div className="research-empty-state rag-empty-state">
                      <strong>Nincs importált Markdown tudásanyag</strong>
                      <p>Importálj egy `.md` fájlt, majd indexeld a tudásbázist a kérdezéshez.</p>
                    </div>
                  )}
                  {knowledgeDocuments.length > 0 && filteredKnowledgeDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelő tudásbázis dokumentum.</p>}
                  {filteredKnowledgeDocuments.map((document) => (
                    <label
                      key={document.id}
                      className={`checkbox-label source-document-option ${knowledgeDocumentIds.includes(document.id) ? "is-selected" : ""} ${document.processing_status === "archived" ? "is-muted" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={knowledgeDocumentIds.includes(document.id)}
                        onChange={() => toggleKnowledgeDocumentFilter(document.id)}
                      />
                      <span>
                        {document.relative_path ?? document.original_filename}
                        <small>
                          {labelKnowledgeStatus(document.processing_status)} | {document.chunk_count} szövegrész | {document.indexed_chunk_count}/{document.chunk_count} indexelt
                          {document.indexed_at ? ` | ${formatDateTime(document.indexed_at)}` : ""}
                        </small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </section>

          </div>

          <section className={`panel rag-answer-panel knowledge-answer-panel ${knowledgeCurrentResponse ? "has-current-answer" : ""}`}>
            <div className="section-heading">
              <h2>Aktuális tudásbázis válasz</h2>
              <MessageSquare size={20} />
            </div>
            {!knowledgeCurrentResponse && (
              <div className="research-empty-state rag-empty-state knowledge-answer-empty-state">
                <strong>Nincs aktuális tudásbázis válasz</strong>
                <p>Itt jelenik meg a legutóbbi tudásbázis-kérdésre adott válasz és a felhasznált Markdown források.</p>
              </div>
            )}
            {knowledgeCurrentResponse && (
              <div className="rag-answer-layout">
                <article className={`rag-answer-card ${knowledgeCurrentResponse.answer.insufficient_source ? "is-unconfirmed" : ""}`}>
                  <div className="metrics">
                    <span>{labelRagAnswerMode(knowledgeCurrentResponse.answer.answer_mode)}</span>
                    <span>{labelRetrievalStrategy(knowledgeCurrentResponse.retrieval_metadata.retrieval_strategy)}</span>
                    <span>{knowledgeCurrentResponse.retrieval_metadata.document_count} dokumentum</span>
                    <span>{knowledgeCurrentResponse.retrieval_metadata.selected_chunk_count} szövegrész</span>
                    {knowledgeCurrentResponse.answer.insufficient_source && <span>Nincs elég forrás</span>}
                  </div>
                  <MarkdownAnswer>{knowledgeCurrentResponse.answer.answer_text}</MarkdownAnswer>
                  {knowledgeCurrentResponse.answer.source_summary && (
                    <div className="module-note">
                      Forrásalap: <strong>{knowledgeCurrentResponse.answer.source_summary}</strong>
                    </div>
                  )}
                </article>
              </div>
            )}
          </section>
          {knowledgeCurrentResponse && (
            <section className="panel knowledge-used-sources-panel">
              <div className="section-heading">
                <h2>Felhasznált Markdown források</h2>
                <span className="status-pill">{knowledgeCurrentResponse.used_sources.length}</span>
              </div>
              <details
                className="knowledge-used-sources-disclosure"
                open={knowledgeSourcesPanelOpen}
                onToggle={(event) => setKnowledgeSourcesPanelOpen(event.currentTarget.open)}
              >
                <summary>
                  Források megtekintése
                  <span>{knowledgeCurrentResponse.used_sources.length} szövegrész</span>
                </summary>
                {knowledgeSourcesPanelOpen && renderKnowledgeUsedSources(knowledgeCurrentResponse.used_sources)}
              </details>
            </section>
          )}
        </section>

      </section>
    );
  }

  function renderGeneralRagSurface() {
    return (
      <section className="surface-placeholder general-rag-surface">
        {renderSurfaceHeader("general_rag")}
        <section className="workbench-status-row rag-status-row">
          {renderRagIndexStatusStrip()}
          {renderRagRunSummaryStrip()}
        </section>
        <section className="general-rag-grid">
          <section className="panel rag-query-panel">
            <div className="section-heading">
              <h2>Kérdés az iratállományhoz</h2>
              <MessageSquare size={20} />
            </div>
            <div className="surface-form">
              <div className="form-row">
                <label>
                  Válasz típusa
                  <select value={ragAnswerMode} onChange={(event) => setRagAnswerMode(event.target.value as RagAnswerMode)}>
                    {ragAnswerModes.map((mode) => (
                      <option key={mode} value={mode}>{ragAnswerModeLabels[mode]}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Forráskör
                  <select value={ragSourceMode} onChange={(event) => setRagSourceMode(event.target.value as RagSourceMode)}>
                    <option value="case">{labelRagSourceMode("case")}</option>
                    <option value="document">{labelRagSourceMode("document")}</option>
                    <option value="collection">{labelRagSourceMode("collection")}</option>
                  </select>
                </label>
              </div>
              {ragSourceMode === "case" && (
                <div className="source-filter-panel">
                  <p className="field-hint source-filter-hint">
                    Ha nem jelölsz ki konkrét iratot, az iratkérdező az összes elemzésre kész aktív iratban keres.
                  </p>
                  <div className="source-filter-list">
                    <div className="source-filter-list-heading">
                      <button
                        className="secondary-button"
                        onClick={() => setRagDocumentIds([])}
                        disabled={ragDocumentIds.length === 0 || Boolean(busy)}
                      >
                        Kijeloles torlese
                      </button>
                      <input
                        className="source-filter-search"
                        value={ragDocumentSearch}
                        onChange={(event) => setRagDocumentSearch(event.target.value)}
                        placeholder="Iratnev keresese"
                        disabled={analysisReadyDocuments.length === 0}
                      />
                    </div>
                    {activeDocuments.length === 0 && <p className="muted">Nincs aktív irat.</p>}
                    {activeDocuments.length > 0 && analysisReadyDocuments.length === 0 && (
                      <p className="muted">Nincs elemzésre kész irat. PDF esetén előbb hozd létre a szövegrészeket.</p>
                    )}
                    {analysisReadyDocuments.length > 0 && filteredRagCaseDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelő elemzésre kész irat.</p>}
                    {filteredRagCaseDocuments.map((document) => (
                      <label key={document.id} className="checkbox-label source-document-option">
                        <input
                          type="checkbox"
                          checked={ragDocumentIds.includes(document.id)}
                          onChange={() => toggleRagDocumentFilter(document.id)}
                        />
                        <span>
                          {document.original_filename}
                          <small>{labelProcessingStatus(document.processing_status)} | {document.current_chunk_count} szövegrész</small>
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              {ragSourceMode === "document" && (
                <div className="source-filter-panel">
                  <p className="field-hint source-filter-hint">
                    Válassz ki egy elemzésre kész iratot. Az iratkérdező a kijelölt irat teljes szöveganyagában keres.
                  </p>
                  <div className="source-filter-list">
                    <div className="source-filter-list-heading">
                      <button
                        className="secondary-button"
                        onClick={() => setRagDocumentId("")}
                        disabled={!ragDocumentId || Boolean(busy)}
                      >
                        Kijeloles torlese
                      </button>
                      <input
                        className="source-filter-search"
                        value={ragDocumentSearch}
                        onChange={(event) => setRagDocumentSearch(event.target.value)}
                        placeholder="Iratnev keresese"
                        disabled={analysisReadyDocuments.length === 0}
                      />
                    </div>
                    {activeDocuments.length === 0 && <p className="muted">Nincs aktív irat.</p>}
                    {activeDocuments.length > 0 && analysisReadyDocuments.length === 0 && (
                      <p className="muted">Nincs elemzésre kész irat. PDF esetén előbb hozd létre a szövegrészeket.</p>
                    )}
                    {analysisReadyDocuments.length > 0 && filteredRagCaseDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelő elemzésre kész irat.</p>}
                    {filteredRagCaseDocuments.map((document) => (
                      <label key={document.id} className="checkbox-label source-document-option">
                        <input
                          type="radio"
                          name="rag-document-source"
                          checked={ragDocumentId === document.id}
                          onChange={() => setRagDocumentId(document.id)}
                        />
                        <span>
                          {document.original_filename}
                          <small>{labelProcessingStatus(document.processing_status)} | {document.current_chunk_count} szövegrész</small>
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              {ragSourceMode === "collection" && (
                <div className="source-filter-panel">
                  <label>
                    Iratgyűjtemény
                    {renderSearchableSelect({
                      queryKey: "rag-collection",
                      value: ragCollectionId,
                      onChange: setRagCollectionId,
                      options: documentCollectionTargetOptions,
                      placeholder: "Válassz iratgyűjteményt",
                      searchPlaceholder: "Keresés az iratgyűjtemények között",
                      ariaLabel: "Iratkérdező iratgyűjtemény kiválasztása"
                    })}
                  </label>
                  {documentCollections.length === 0 && <p className="muted">Még nincs iratgyűjtemény.</p>}
                  {ragCollection && (
                    <div className="collection-scope-preview">
                      <strong>{ragCollection.name}</strong>
                      <span>{ragCollection.document_count} irat</span>
                      <span>{ragCollection.active_document_count} aktív irat</span>
                    </div>
                  )}
                </div>
              )}
              <div className="analysis-settings-row rag-settings-row">
                <label>
                  Szövegrész plafon
                  <input
                    type="number"
                    min={1}
                    max={90}
                    value={ragMaxChunks}
                    onChange={(event) => setRagMaxChunks(clampNumberInput(event.target.value, 1, 90, 45))}
                  />
                </label>
                <label>
                  Forráskeresés
                  <select value={ragRetrievalStrategy} onChange={(event) => setRagRetrievalStrategy(event.target.value as RetrievalStrategy)}>
                    {retrievalStrategies.map((item) => <option key={item} value={item}>{labelRetrievalStrategy(item)}</option>)}
                  </select>
                </label>
                <span className="field-hint analysis-settings-hint">
                  A keresési mód a kérdés alapján választja ki a feldolgozandó szövegrészeket. Szemantikus vagy hybrid módhoz előbb indexeld a szövegrészeket.
                </span>
              </div>
              <label>
                Kérdés
                <textarea
                  value={ragQuestion}
                  onChange={(event) => setRagQuestion(event.target.value)}
                  rows={6}
                  placeholder="Írd be, mire szeretnél választ kapni kizárólag az ügy iratai alapján."
                />
              </label>
              <p className="field-hint">
                A válasz ideiglenes: a következő kérdés felülírja. Csak akkor kerül mentésre, ha külön rányomsz a válasz mentésére.
              </p>
              {!ragHasSource && <p className="error-text">A kiválasztott forráskörben nincs használható, elemzésre kész aktív irat.</p>}
              <button onClick={handleRunRagQuery} disabled={!canRunRagQuery}>
                <Play size={18} /> Kérdezés indítása
              </button>
            </div>
          </section>

          <section className="panel rag-saved-panel">
            <div className="section-heading">
              <h2>Mentett válaszok</h2>
              <button className="icon-button" onClick={() => refreshRagAnswers(true)} title="Mentett válaszok frissítése" disabled={!selectedCaseId || Boolean(busy)}>
                <RefreshCw size={18} />
              </button>
            </div>
            <div className="compact-list">
              {ragSavedAnswers.length === 0 && (
                <div className="research-empty-state rag-empty-state">
                  <strong>Nincs mentett iratkérdező válasz</strong>
                  <p>
                    A mentett válaszok akkor jelennek meg itt, ha egy aktuális iratkérdező választ külön elmentesz.
                  </p>
                </div>
              )}
              {ragSavedAnswers.map((answer) => (
                <article key={answer.id} className={`compact-item ${selectedRagAnswerId === answer.id ? "is-selected" : ""}`}>
                  <strong>{answer.title || truncateText(answer.question, 110)}</strong>
                  <span>{labelRagSourceMode(answer.source_mode as RagSourceMode)} | {labelRagAnswerMode(answer.answer_mode as RagAnswerMode)} | {answer.used_source_count} forrás</span>
                  <span>{formatDateTime(answer.created_at)}</span>
                  <div className="button-row">
                    <button className="secondary-button" onClick={() => handleLoadRagAnswer(answer.id)} disabled={Boolean(busy)}>
                      Megnyitás
                    </button>
                    <button className="danger-button" onClick={() => handleDeleteRagAnswer(answer)} disabled={Boolean(busy)}>
                      <Trash2 size={16} /> Törlés
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </section>

        <section className={`panel rag-answer-panel ${ragCurrentResponse ? "has-current-answer" : ""}`}>
          <div className="section-heading">
            <h2>Aktuális válasz</h2>
            <MessageSquare size={20} />
          </div>
          {!ragCurrentResponse && (
            <div className="research-empty-state rag-empty-state">
              <strong>Nincs aktuális iratkérdező válasz</strong>
              <p>
                Itt jelenik meg a legutóbbi kérdésre adott válasz. A következő kérdés ezt a nézetet felülírja, a fontos válaszokat külön lehet menteni.
              </p>
            </div>
          )}
          {ragCurrentResponse && (
            <div
              className="rag-answer-layout rag-current-answer-layout"
              style={{ "--rag-source-panel-height": ragCurrentAnswerHeight > 0 ? `${ragCurrentAnswerHeight}px` : "50rem" } as CSSProperties}
            >
              <article
                ref={ragCurrentAnswerCardRef}
                className={`rag-answer-card ${ragCurrentResponse.answer.insufficient_source ? "is-unconfirmed" : ""}`}
              >
                <div className="metrics">
                  <span>{labelRagAnswerMode(ragCurrentResponse.answer.answer_mode)}</span>
                  <span>{labelRagSourceMode(ragCurrentResponse.source_scope.source_mode)}</span>
                  <span>{ragCurrentResponse.source_scope.resolved_document_count} irat</span>
                  <span>{ragCurrentResponse.retrieval_metadata.selected_chunk_count} szövegrész</span>
                  {ragCurrentResponse.retrieval_metadata.document_answer_count > 1 && (
                    <span>{ragCurrentResponse.retrieval_metadata.document_answer_count} részválasz</span>
                  )}
                  {ragCurrentResponse.answer.insufficient_source && <span>Nincs elég forrás</span>}
                </div>
                <MarkdownAnswer>{ragCurrentResponse.answer.answer_text}</MarkdownAnswer>
                {ragCurrentResponse.answer.source_summary && (
                  <div className="module-note">
                    Forrásalap: <strong>{ragCurrentResponse.answer.source_summary}</strong>
                  </div>
                )}
                {ragCurrentResponse.source_scope.warnings.length > 0 && (
                  <div className="module-note module-note-warning">
                    <strong>Forráskör figyelmeztetések</strong>
                    <ul>
                      {ragCurrentResponse.source_scope.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}
                    </ul>
                  </div>
                )}
                <div className="rag-save-panel">
                  <label>
                    Mentési cím
                    <input value={ragSaveTitle} onChange={(event) => setRagSaveTitle(event.target.value)} />
                  </label>
                  <label>
                    Megjegyzés
                    <textarea value={ragSaveNote} onChange={(event) => setRagSaveNote(event.target.value)} rows={2} />
                  </label>
                  <button onClick={handleSaveRagAnswer} disabled={Boolean(busy) || !ragCurrentResponse.can_save}>
                    Válasz mentése
                  </button>
                </div>
              </article>
              <section className="rag-sources-panel">
                <div className="section-heading">
                  <strong>Felhasznált források</strong>
                  <span className="status-pill">{ragCurrentResponse.used_sources.length}</span>
                </div>
                {renderRagUsedSources(ragCurrentResponse.used_sources)}
              </section>
            </div>
          )}
        </section>

        <section className="panel rag-saved-detail-panel" ref={ragSavedDetailPanelRef}>
          <div className="section-heading">
            <h2>Mentett válasz részletei</h2>
            <Archive size={20} />
          </div>
          {!selectedRagAnswer && <p className="muted">Válassz mentett választ a részletekhez.</p>}
          {selectedRagAnswer && (
            <div className="rag-answer-layout">
              <article className="rag-answer-card">
                <div className="metrics">
                  <span>{labelRagAnswerMode(selectedRagAnswer.answer_mode as RagAnswerMode)}</span>
                  <span>{labelRagSourceMode(selectedRagAnswer.source_scope.source_mode as RagSourceMode)}</span>
                  <span>{selectedRagAnswer.used_sources.length} forrás</span>
                  {selectedRagAnswer.model_name && <span>{selectedRagAnswer.model_name}</span>}
                </div>
                <strong>{selectedRagAnswer.title || selectedRagAnswer.question}</strong>
                <p className="field-hint">{selectedRagAnswer.question}</p>
                <MarkdownAnswer>{selectedRagAnswer.answer_text}</MarkdownAnswer>
                {selectedRagAnswer.source_summary && (
                  <div className="module-note">
                    Forrásalap: <strong>{selectedRagAnswer.source_summary}</strong>
                  </div>
                )}
                {selectedRagAnswer.note && <div className="module-note">{selectedRagAnswer.note}</div>}
              </article>
              <section className="rag-sources-panel">
                <div className="section-heading">
                  <strong>Mentett források</strong>
                  <span className="status-pill">{selectedRagAnswer.used_sources.length}</span>
                </div>
                {renderRagUsedSources(selectedRagAnswer.used_sources)}
              </section>
            </div>
          )}
        </section>      </section>
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
          <span><Database size={16} /> forráshivatkozott</span>
          <span><CheckCircle2 size={16} /> emberi ellenorzes</span>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleThemeMode}
            aria-label={themeMode === "dark" ? "Vilagos mod bekapcsolasa" : "Sotet mod bekapcsolasa"}
            title={themeMode === "dark" ? "Vilagos mod" : "Sotet mod"}
          >
            {themeMode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            <span>{themeMode === "dark" ? "Világos" : "Sötét"}</span>
          </button>
        </div>
      </header>

      <section className="workspace">
        <div className="surface-layout">
          <aside className="surface-sidebar">
            {renderModelStatusBar()}
            <nav className="surface-nav" aria-label="Munkafelület választása">
              {workSurfaces.map((surface) => (
                <button
                  key={surface}
                  className={`surface-tab ${activeSurface === surface ? "is-active" : ""}`}
                  onClick={() => handleSurfaceNavClick(surface)}
                  type="button"
                  aria-current={activeSurface === surface ? "page" : undefined}
                >
                  {surface === "document_organizer" && <FolderPlus size={18} />}
                  {surface === "case_workbench" && <Database size={18} />}
                  {surface === "relationship_map" && <GitMerge size={18} />}
                  {surface === "full_document_processing" && <FilePlus2 size={18} />}
                  {surface === "general_rag" && <MessageSquare size={18} />}
                  {surface === "knowledge_base" && <Database size={18} />}
                  {surface === "ai_assistant" && <MessageSquare size={18} />}
                  {surface === "audit_log" && <Archive size={18} />}
                  <span>{workSurfaceLabels[surface]}</span>
                </button>
              ))}
            </nav>
          </aside>

          <div className="surface-content">
        {(activeSurface === "document_organizer" || activeSurface === "case_workbench") && (
        <section className={`main-grid ${activeSurface === "case_workbench" ? "case-workbench-grid" : ""}`}>
          {renderSurfaceHeader(activeSurface)}

          {activeSurface === "case_workbench" && (
            <div className="workbench-status-row">
              {renderAnalysisReadinessStrip()}
              {renderResearchRunSummaryStrip()}
            </div>
          )}

          <div
            className={`workflow-column ${
              activeSurface === "document_organizer" ? "document-organizer-column" : activeSurface === "case_workbench" ? "case-workbench-column" : ""
            }`}
          >
          {activeSurface === "document_organizer" && (
          <>
          <section className="case-strip document-organizer-case-panel">
            <div className="section-heading">
              <h2>Ugyek</h2>
              <button className="secondary-button" onClick={refreshCases} title="Ügylista frissítése" disabled={Boolean(busy)}>
                <RefreshCw size={18} /> Ügylista frissítése
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
                <RefreshCw size={18} /> Ugyadatok frissítése
              </button>
              <button className="danger-button" onClick={handleDeleteSelectedCase} disabled={!selectedCaseId || Boolean(busy)}>
                <Trash2 size={18} /> Ügy végleges törlése
              </button>
            </div>
          </section>
          <section className="panel document-collections-panel">
            <div className="section-heading">
              <h2>Iratgyűjtemények</h2>
              <FolderPlus size={20} />
            </div>
            <div className="collection-create-row">
              <input
                value={newDocumentCollectionName}
                onChange={(event) => setNewDocumentCollectionName(event.target.value)}
                placeholder="Új gyűjtemény neve"
                disabled={!selectedCaseId || Boolean(busy)}
              />
              <button onClick={handleCreateDocumentCollection} disabled={!selectedCaseId || !newDocumentCollectionName.trim() || Boolean(busy)}>
                <FolderPlus size={18} /> Létrehozás
              </button>
            </div>
            <input
              value={newDocumentCollectionDescription}
              onChange={(event) => setNewDocumentCollectionDescription(event.target.value)}
              placeholder="Leírás opcionális"
              disabled={!selectedCaseId || Boolean(busy)}
            />
            {documentCollections.length === 0 && <p className="muted">Még nincs iratgyűjtemény.</p>}
            {documentCollections.length > 0 && (
              <>
                {renderSearchableSelect({
                  queryKey: "selected-document-collection",
                  value: selectedDocumentCollectionId,
                  onChange: (value) => {
                    setSelectedDocumentCollectionId(value);
                    setSelectedDocumentCollectionMarkedDocumentIds([]);
                    setDocumentCollectionScopePreview(null);
                  },
                  options: documentCollectionTargetOptions,
                  placeholder: "Iratgyűjtemény",
                  searchPlaceholder: "Keresés az iratgyűjtemények között",
                  ariaLabel: "Iratgyűjtemény kiválasztása"
                })}
                {!selectedDocumentCollection && (
                  <div className="research-empty-state collection-empty-state">
                    <strong>Nincs kiválasztott iratgyűjtemény</strong>
                    <p>Válassz ki egy iratgyűjteményt a tartalom megjelenítéséhez.</p>
                  </div>
                )}
                {selectedDocumentCollection && (
                  <div className="collection-summary">
                    <div>
                      <strong>{selectedDocumentCollection.name}</strong>
                      {selectedDocumentCollection.description && <span>{selectedDocumentCollection.description}</span>}
                    </div>
                    <div className="metrics">
                      <span>{selectedDocumentCollection.document_count} irat</span>
                      <span>{selectedDocumentCollection.active_document_count} aktív</span>
                    </div>
                    <div className="button-row">
                      <button className="secondary-button" onClick={() => void refreshDocumentCollections(true)} disabled={Boolean(busy)}>
                        <RefreshCw size={18} /> Gyűjtemények frissítése
                      </button>
                      <button className="secondary-button" onClick={handleResolveDocumentCollectionScope} disabled={Boolean(busy)}>
                        Forráskör előnézet
                      </button>
                      <button className="danger-button" onClick={handleDeleteDocumentCollection} disabled={Boolean(busy)}>
                        <Trash2 size={18} /> Törlés
                      </button>
                    </div>
                    {documentCollectionScopePreview && (
                      <div className="collection-scope-preview">
                        <strong>{documentCollectionScopePreview.active_document_count} egyedi aktív irat a forráskörben</strong>
                        <span>{documentCollectionScopePreview.inactive_document_count} inaktív irat kimarad</span>
                        <span>{documentCollectionScopePreview.duplicate_membership_count} duplikált tagság kiszűrve</span>
                        {documentCollectionScopePreview.warnings.length > 0 && (
                          <span>{documentCollectionScopePreview.warnings.length} figyelmeztetés</span>
                        )}
                      </div>
                    )}
                    <div className="collection-content-area">
                      <input
                        className="panel-search-input"
                        value={documentCollectionContentSearch}
                        onChange={(event) => setDocumentCollectionContentSearch(event.target.value)}
                        placeholder="Keresés a gyűjtemény iratai között"
                        disabled={selectedDocumentCollectionDocuments.length === 0}
                      />
                      <div className="metrics">
                        <span>{selectedDocumentCollectionMarkedDocumentIds.length} kijelölve</span>
                        <span>{selectedCollectionVisibleMarkedDocumentIds.length} látható kijelölve</span>
                      </div>
                      <div className="button-row">
                        <button
                          className="secondary-button"
                          onClick={() => void refreshSelectedDocumentCollectionDocuments(true)}
                          disabled={Boolean(busy)}
                        >
                          <RefreshCw size={18} /> Tartalom frissítése
                        </button>
                        <button
                          className="secondary-button"
                          onClick={markAllVisibleSelectedCollectionDocuments}
                          disabled={filteredSelectedDocumentCollectionDocuments.length === 0 || Boolean(busy)}
                        >
                          Összes látható kijelölése
                        </button>
                        <button
                          className="secondary-button"
                          onClick={clearSelectedDocumentCollectionDocumentMarks}
                          disabled={selectedDocumentCollectionMarkedDocumentIds.length === 0 || Boolean(busy)}
                        >
                          Kijelölés törlése
                        </button>
                        <button
                          className="danger-button"
                          onClick={handleRemoveMarkedDocumentsFromSelectedCollection}
                          disabled={selectedDocumentCollectionMarkedDocumentIds.length === 0 || Boolean(busy)}
                        >
                          Kijelöltek kivétele
                        </button>
                      </div>
                      <div className="compact-list collection-content-list">
                        {selectedDocumentCollectionDocuments.length === 0 && <p className="muted">A gyűjteményben még nincs irat.</p>}
                        {selectedDocumentCollectionDocuments.length > 0 && filteredSelectedDocumentCollectionDocuments.length === 0 && (
                          <p className="muted">Nincs a keresésnek megfelelő gyűjteményi irat.</p>
                        )}
                        {filteredSelectedDocumentCollectionDocuments.map((document) => (
                          <article
                            key={document.id}
                            className={`compact-item document-list-item ${
                              selectedDocumentCollectionMarkedDocumentIds.includes(document.id) ? "is-collection-marked" : ""
                            }`}
                          >
                            <div className="document-list-main">
                              <strong>{document.original_filename}</strong>
                              <span>
                                {labelProcessingStatus(document.processing_status)} | {labelDocumentLifecycleStatus(document.lifecycle_status)} |{" "}
                                {formatBytes(document.file_size_bytes)}
                              </span>
                              <code>{document.sha256_hash}</code>
                              <div className="button-row document-list-extra-actions">
                                <button
                                  className="secondary-button"
                                  onClick={() => toggleSelectedDocumentCollectionDocumentMark(document.id)}
                                  disabled={Boolean(busy)}
                                >
                                  {selectedDocumentCollectionMarkedDocumentIds.includes(document.id)
                                    ? "Kijelölés levétele"
                                    : "Gyűjteményből kivételre jelölés"}
                                </button>
                                <button
                                  className="secondary-button"
                                  onClick={() => void handleRemoveDocumentFromSelectedCollection(document)}
                                  disabled={Boolean(busy)}
                                >
                                  Kivétel a gyűjteményből
                                </button>
                              </div>
                            </div>
                            <button className="document-detail-button" onClick={() => handleDocumentDetail(document)} disabled={Boolean(busy)}>
                              Reszletek
                            </button>
                          </article>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>

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
                <article
                  key={document.id}
                  className={`compact-item document-list-item ${
                    documentCollectionMarkedDocumentIds.includes(document.id) ? "is-collection-marked" : ""
                  }`}
                >
                  <div className="document-list-main">
                    <strong>{document.original_filename}</strong>
                    <span>
                      {labelProcessingStatus(document.processing_status)} | {labelDocumentLifecycleStatus(document.lifecycle_status)} | {formatBytes(document.file_size_bytes)}
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
                    {targetDocumentCollection && (
                      <div className="button-row document-list-extra-actions">
                        <button
                          onClick={() => handleAddDocumentToTargetCollection(document)}
                          disabled={Boolean(busy) || !documentCollectionTargetId || targetCollectionDocumentIds.has(document.id)}
                        >
                          {targetCollectionDocumentIds.has(document.id) ? "Már benne van" : "Hozzáadás a kiválasztott gyűjteményhez"}
                        </button>
                        <button
                          className="secondary-button"
                          onClick={() => toggleDocumentCollectionDocumentMark(document.id)}
                          disabled={Boolean(busy)}
                        >
                          {documentCollectionMarkedDocumentIds.includes(document.id) ? "Kijelölés levétele" : "Iratgyűjteményhez adásra jelölés"}
                        </button>
                        <span>
                          {targetCollectionDocumentIds.has(document.id)
                            ? `Benne van: ${targetDocumentCollection.name}`
                            : `Cél: ${targetDocumentCollection.name}`}
                        </span>
                      </div>
                    )}
                    {!targetDocumentCollection && (
                      <div className="button-row document-list-extra-actions">
                        <button className="secondary-button" onClick={() => toggleDocumentCollectionDocumentMark(document.id)} disabled={Boolean(busy)}>
                          {documentCollectionMarkedDocumentIds.includes(document.id) ? "Kijelölés levétele" : "Iratgyűjteményhez adásra jelölés"}
                        </button>
                        <span>Válassz célgyűjteményt az iratpanel alján.</span>
                      </div>
                    )}
                  </div>
                  <button className="document-detail-button" onClick={() => handleDocumentDetail(document)} disabled={Boolean(busy)}>
                    Reszletek
                  </button>
                </article>
              ))}
            </div>
            <div className="document-collection-bulk-bar">
              <div className="document-collection-target-select">
                {renderSearchableSelect({
                  queryKey: "document-collection-target",
                  value: documentCollectionTargetId,
                  onChange: (value) => {
                    setDocumentCollectionTargetId(value);
                    setDocumentCollectionScopePreview(null);
                  },
                  options: documentCollectionTargetOptions,
                  placeholder: "Cél iratgyűjtemény",
                  searchPlaceholder: "Keresés az iratgyűjtemények között",
                  ariaLabel: "Cél iratgyűjtemény kiválasztása"
                })}
              </div>
              <div className="metrics">
                <span>{documentCollectionMarkedDocumentIds.length} kijelölve</span>
                <span>{visibleMarkedDocumentIds.length} látható kijelölve</span>
              </div>
              <div className="button-row">
                <button
                  className="secondary-button"
                  onClick={markAllVisibleDocumentsForCollection}
                  disabled={filteredDocuments.length === 0 || Boolean(busy)}
                >
                  Összes látható kijelölése
                </button>
                <button
                  className="secondary-button"
                  onClick={clearDocumentCollectionDocumentMarks}
                  disabled={documentCollectionMarkedDocumentIds.length === 0 || Boolean(busy)}
                >
                  Kijelölés törlése
                </button>
                <button
                  onClick={handleAddMarkedDocumentsToTargetCollection}
                  disabled={!documentCollectionTargetId || documentCollectionMarkedDocumentIds.length === 0 || Boolean(busy)}
                >
                  Jelöltek iratgyűjteményhez adása
                </button>
              </div>
              {targetDocumentCollection && (
                <p className="field-hint">
                  Célgyűjtemény: {targetDocumentCollection.name}. Sikeres hozzáadás után a kijelölés megmarad.
                </p>
              )}
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
                  <span>{labelProcessingStatus(selectedDocument.processing_status)}</span>
                  <span>{labelDocumentLifecycleStatus(selectedDocument.lifecycle_status)}</span>
                </div>
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
                        <button className="danger-button" onClick={handleDocumentDiscard} disabled={Boolean(busy)}>
                          <Trash2 size={16} /> Elvetés / törlés
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
                      <details>
                        <summary>Meglévő találathoz csatolás</summary>
                        <div className="manual-entry-panel">
                          <div className="finding-conversion-type-row">
                            <label>
                              Cél típusa
                              <select
                                value={manualSourceAttachType}
                                onChange={(event) => {
                                  setManualSourceAttachType(event.target.value as ManualObjectType);
                                  setManualSourceAttachTargetId("");
                                }}
                              >
                                {(Object.keys(manualObjectTypeLabels) as ManualObjectType[]).map((type) => (
                                  <option key={type} value={type}>
                                    {manualObjectTypeLabels[type]}
                                  </option>
                                ))}
                              </select>
                            </label>
                            {renderSearchableSelect({
                              queryKey: "manual-source-attach-target",
                              value: manualSourceAttachTargetId,
                              onChange: setManualSourceAttachTargetId,
                              options: manualSourceAttachTargetOptions(manualSourceAttachType),
                              placeholder: "Válassz céltalálatot",
                              searchPlaceholder: "Keresés a céltalálatok között",
                              ariaLabel: "Kézi forráshivatkozás csatolási célja"
                            })}
                          </div>
                          <button onClick={handleAttachManualSourceToExistingObject} disabled={Boolean(busy) || !manualSourceAttachTargetId}>
                            Forráshivatkozás csatolása
                          </button>
                        </div>
                      </details>
                      <details open>
                        <summary>Új találat létrehozása</summary>
                        <div className="manual-entry-panel">
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
                          <button onClick={handleCreateManualObject} disabled={Boolean(busy)}>
                            Rögzítés forráshivatkozásból
                          </button>
                        </div>
                      </details>
                      <button className="secondary-button" onClick={() => setManualSource(null)} disabled={Boolean(busy)}>
                        Mégse
                      </button>
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
                Irat fajl
                <input
                  ref={importFileInputRef}
                  type="file"
                  multiple
                  accept=".txt,.pdf,text/plain,application/pdf"
                  onChange={(event) => setImportFiles(Array.from(event.target.files ?? []))}
                />
              </label>
            </div>
            {importFiles.length > 0 && (
              <p className="field-hint">
                Kijelolve: {importFiles.length} fajl
              </p>
            )}
            <button onClick={handleImport} disabled={!selectedCaseId || importFiles.length === 0 || Boolean(busy)}>
              <FilePlus2 size={18} /> {importFiles.length > 1 ? "Iratok importalasa" : "Importalas"}
            </button>
          </section>

          </>
          )}

          {activeSurface === "case_workbench" && (
          <>
          <section className="panel analysis-panel" ref={analysisPanelRef}>
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
            {showCaseDocumentFilters && (
              <div className="source-filter-panel">
                <p className="field-hint source-filter-hint">
                  A kijelölés csak a teljes ügy forráskörben érvényes. Ha nem jelölsz ki konkrét iratot, a rendszer az összes elemzésre kész iratban keres.
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
                      disabled={analysisReadyDocuments.length === 0}
                    />
                  </div>
                  {activeDocuments.length === 0 && <p className="muted">Nincs aktív irat.</p>}
                  {activeDocuments.length > 0 && analysisReadyDocuments.length === 0 && (
                    <p className="muted">Nincs elemzésre kész irat. PDF esetén előbb hozd létre a szövegrészeket.</p>
                  )}
                  {analysisReadyDocuments.length > 0 && filteredCaseAnalysisDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelo elemzésre kész irat.</p>}
                  {filteredCaseAnalysisDocuments.map((document) => (
                    <label key={document.id} className="checkbox-label source-document-option">
                      <input
                        type="checkbox"
                        checked={analysisDocumentIds.includes(document.id)}
                        onChange={() => toggleAnalysisDocumentFilter(document.id)}
                      />
                      <span>
                        {document.original_filename}
                        <small>{labelProcessingStatus(document.processing_status)} | {document.current_chunk_count} szövegrész</small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            {canUseBatchScope && effectiveAnalysisSourceMode === "document" && (
              <div className="source-filter-panel">
                <p className="field-hint source-filter-hint">
                  Valassz ki egy elemzésre kész iratot. A keresés a kijelölt irat teljes szöveganyagában dolgozik.
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
                      disabled={analysisReadyDocuments.length === 0}
                    />
                  </div>
                  {activeDocuments.length === 0 && <p className="muted">Nincs aktív irat.</p>}
                  {activeDocuments.length > 0 && analysisReadyDocuments.length === 0 && (
                    <p className="muted">Nincs elemzésre kész irat. PDF esetén előbb hozd létre a szövegrészeket.</p>
                  )}
                  {analysisReadyDocuments.length > 0 && filteredDocumentAnalysisDocuments.length === 0 && <p className="muted">Nincs a keresésnek megfelelo elemzésre kész irat.</p>}
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
                        <small>{labelProcessingStatus(document.processing_status)} | {document.current_chunk_count} szövegrész</small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            {canUseBatchScope && effectiveAnalysisSourceMode === "collection" && (
              <div className="source-filter-panel">
                <label>
                  Iratgyűjtemény
                  {renderSearchableSelect({
                    queryKey: "analysis-document-collection",
                    value: analysisCollectionId,
                    onChange: setAnalysisCollectionId,
                    options: documentCollectionTargetOptions,
                    placeholder: "Iratgyűjtemény",
                    searchPlaceholder: "Keresés az iratgyűjtemények között",
                    ariaLabel: "Elemzési iratgyűjtemény kiválasztása"
                  })}
                </label>
                {documentCollections.length === 0 && <p className="muted">Még nincs iratgyűjtemény.</p>}
                {analysisDocumentCollection && (
                  <div className="collection-scope-preview">
                    <strong>{analysisDocumentCollection.name}</strong>
                    <span>{analysisDocumentCollection.document_count} irat</span>
                    <span>{analysisDocumentCollection.active_document_count} aktív irat</span>
                  </div>
                )}
              </div>
            )}
            {canUseBatchScope && (
              <div className="analysis-settings-row">
                <label>
                  Szovegresz plafon
                  <input
                    type="number"
                    min={1}
                    max={90}
                    value={maxChunks}
                    onChange={(event) => setMaxChunks(clampNumberInput(event.target.value, 1, 90, 45))}
                  />
                </label>
                <label>
                  Maximális batch méret
                  <input
                    type="number"
                    min={1}
                    max={15}
                    value={batchSize}
                    onChange={(event) => setBatchSize(clampNumberInput(event.target.value, 1, 15, 3))}
                  />
                </label>
                <label>
                  Forráskeresés
                  <select
                    value={retrievalStrategy}
                    onChange={(event) => setRetrievalStrategy(event.target.value as RetrievalStrategy)}
                  >
                    {retrievalStrategies.map((item) => <option key={item} value={item}>{labelRetrievalStrategy(item)}</option>)}
                  </select>
                </label>
                <span className="field-hint analysis-settings-hint">
                  A keresesi mod a fokusz alapjan valasztja ki a feldolgozando szovegreszeket. Szemantikus vagy hybrid modhoz elobb indexeld a szovegreszeket.
                </span>
              </div>
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
            </label>
            <p className="field-hint">
              {isContradictionModule
                ? "Kötelező: ez szűri a már kinyert állításokat és forráshivatkozási idézeteiket."
                : "Kötelező: ez választja ki a releváns szövegrészeket a megadott forráskörben. (Rövid, konkrét fókusznál a 3 feletti batch méret ronthatja a találatok kiemelését. Ilyenkor érdemes 1-3 közötti értéket próbálni.)"}
            </p>
            {requiresFocusText && query.trim().length === 0 && (
              <p className="error-text">A feldolgozashoz adj meg fokuszt; enelkul nagy ugyeknel nem inditunk vak feldolgozast.</p>
            )}
          <button onClick={handleRunAnalysis} disabled={!canRunAnalysis}>
              <Play size={18} /> Futtatas
            </button>
          </section>

          <section className="panel manual-contradiction-panel">
            <div className="section-heading">
              <h2>Kézi ellentmondásjelölt</h2>
              <GitMerge size={20} />
            </div>
            <p className="field-hint">
              Két érvényes forráshivatkozású, nem elutasított állításból hoz létre ellenőrizendő jelöltet. A rögzítés nem bizonyított ellentmondás, hanem emberi ellenőrzésre váró pár.
            </p>
            <div className="manual-contradiction-select-row">
              <div className="manual-contradiction-select-field">
                <span>1. állítás</span>
                {renderSearchableSelect({
                  queryKey: "manual-contradiction:claim-a",
                  value: manualContradiction.claim_id_a,
                  onChange: (value) => updateManualContradictionField("claim_id_a", value),
                  options: manualContradictionClaimOptions.map((item) => ({
                    id: item.object_id,
                    label: truncateText(item.title || item.body_text || item.object_id, 90),
                    searchText: `${item.title} ${item.body_text}`,
                    disabled: item.object_id === manualContradiction.claim_id_b
                  })),
                  placeholder: "Válassz állítást",
                  searchPlaceholder: "Keresés az állítások között",
                  ariaLabel: "Első állítás kiválasztása"
                })}
              </div>
              <div className="manual-contradiction-select-field">
                <span>2. állítás</span>
                {renderSearchableSelect({
                  queryKey: "manual-contradiction:claim-b",
                  value: manualContradiction.claim_id_b,
                  onChange: (value) => updateManualContradictionField("claim_id_b", value),
                  options: manualContradictionClaimOptions.map((item) => ({
                    id: item.object_id,
                    label: truncateText(item.title || item.body_text || item.object_id, 90),
                    searchText: `${item.title} ${item.body_text}`,
                    disabled: item.object_id === manualContradiction.claim_id_a
                  })),
                  placeholder: "Válassz állítást",
                  searchPlaceholder: "Keresés az állítások között",
                  ariaLabel: "Második állítás kiválasztása"
                })}
              </div>
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
              className="manual-contradiction-create-button"
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
              <GitMerge size={18} /> Kézi jelölt létrehozása
            </button>
          </section>

          <section className="history-export-row">
            <section className="panel analysis-history-panel">
              <div className="section-heading">
                <h2>Elemzesi elozmenyek</h2>
                <Archive size={20} />
              </div>
              <div className="analysis-history-toggle" aria-label="Elemzési előzmények típusa">
                <button
                  type="button"
                  className={analysisHistoryKind === "search_findings" ? "" : "secondary-button"}
                  onClick={() => {
                    setAnalysisHistoryKind("search_findings");
                    if (analysisRunDetail && analysisRunDetail.run.run_type !== "search_findings") {
                      setAnalysisRunDetail(null);
                    }
                  }}
                  disabled={Boolean(busy)}
                >
                  Kutatási találatok keresése ({analysisHistoryCounts.search_findings})
                </button>
                <button
                  type="button"
                  className={analysisHistoryKind === "manual_entry" ? "" : "secondary-button"}
                  onClick={() => {
                    setAnalysisHistoryKind("manual_entry");
                    if (analysisRunDetail && analysisRunDetail.run.run_type !== "manual_entry") {
                      setAnalysisRunDetail(null);
                    }
                  }}
                  disabled={Boolean(busy)}
                >
                  Kézi rögzítés ({analysisHistoryCounts.manual_entry})
                </button>
              </div>
              <div className="compact-list">
                {visibleAnalysisRuns.length === 0 && <p className="muted">Nincs ilyen típusú elemzési futás.</p>}
                {visibleAnalysisRuns.slice(0, 8).map((run) => (
                  <article
                    key={run.id}
                    className={`compact-item analysis-run-list-item ${analysisRunDetail?.run.id === run.id ? "is-selected" : ""}`}
                  >
                    <div className="analysis-run-list-main">
                      <strong>{analysisRunHistoryTitle(run)}</strong>
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

            <div className="history-export-stack">
              <section className="panel export-history-panel">
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

              <section className="panel export-panel">
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

          <section className="panel detail-panel analysis-detail-panel">
            <div className="section-heading">
              <h2>Elemzesi futas reszletei</h2>
              <Archive size={20} />
            </div>
            {!analysisRunDetail && <p className="muted">Valassz elemzesi futast a reszletekhez.</p>}
            {analysisRunDetail && (
              renderAnalysisRunDetailView(analysisRunDetail)
            )}
          </section>

          </>
          )}

          </div>

          {activeSurface === "case_workbench" && (
          <div className="review-column case-workbench-review-column">
          <section className="panel research-findings-panel" ref={researchFindingsPanelRef}>
            <div className="section-heading">
              <h2>Kutatási találatok</h2>
              <Search size={20} />
            </div>
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
                className="secondary-button"
                onClick={markAllVisibleResearchFindingsForDeletion}
                disabled={Boolean(busy) || markableResearchFindingIds.length === 0 || allVisibleResearchFindingsMarked}
              >
                Összes törlésre jelölése
              </button>
              <button
                type="button"
                className="danger-button"
                onClick={handleBulkDeleteResearchFindings}
                disabled={Boolean(busy) || markedResearchFindingCount === 0}
              >
                <Trash2 size={16} /> Jelöltek törlése ({markedResearchFindingCount})
              </button>
            </div>
            {visibleResearchFindings.length === 0 && (
              <div className="research-empty-state">
                <strong>Nincs megjeleníthető kutatási találat</strong>
                <p>
                  Itt jelennek meg a kutatási találatjelöltek a keresés lefutása után. Ha korábban voltak találatok, elképzelhető, hogy
                  át lettek alakítva, félre lettek téve vagy törölve lettek.
                </p>
              </div>
            )}
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
                      } ${finding.source_validation_status === "source_invalid" ? "is-unconfirmed" : ""}`}
                    >
                      <div className="research-finding-header">
                        <div>
                          <h3>{finding.title}</h3>
                          <p>{finding.finding_text}</p>
                        </div>
                        <span className="status-pill">{labelResearchFindingType(finding.suggested_type)}</span>
                      </div>
                      <div className="tags">
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
            <div className="report-filter-row">
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
                      <div className="source-action-row">
                        <button className="secondary-button" onClick={() => handleSelectReportItem(item)}>
                          Részletek
                        </button>
                        {reviewItemCanBeDeleted(item) && (
                          <button className="danger-button" onClick={() => handleDeleteReviewReportItem(item)} disabled={Boolean(busy)}>
                            <Trash2 size={16} /> Végleges törlés
                          </button>
                        )}
                      </div>
                      {renderReportSourceGroups(item, "card")}
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
                        {reviewItemCanOpenRelationshipGraph(item) && (
                          <button
                            title="Kapcsolati térkép megnyitása"
                            onClick={() => handleOpenRelationshipGraphFromReportItem(item)}
                            disabled={Boolean(busy)}
                          >
                            <GitMerge size={18} />
                            Kapcsolati térkép
                          </button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}
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
                {selectedReportItem.object_type === "contradiction_candidate" && (selectedReportItem.claim_id_a || selectedReportItem.claim_id_b) && (
                  <div className="source-action-row">
                    {selectedReportItem.claim_id_a && (
                      <button
                        className="secondary-button"
                        onClick={() => handleDetachContradictionCandidateClaim(selectedReportItem, "a")}
                        disabled={Boolean(busy)}
                      >
                        A állítás leválasztása
                      </button>
                    )}
                    {selectedReportItem.claim_id_b && (
                      <button
                        className="secondary-button"
                        onClick={() => handleDetachContradictionCandidateClaim(selectedReportItem, "b")}
                        disabled={Boolean(busy)}
                      >
                        B állítás leválasztása
                      </button>
                    )}
                  </div>
                )}
                <div className="object-facts">
                  {objectDetailFacts(selectedReportItem).map((fact) => (
                    <div key={fact.label}>
                      <span>{fact.label}</span>
                      <strong>{fact.value}</strong>
                    </div>
                  ))}
                </div>
                {reviewItemTextCanBeEdited(selectedReportItem) && (
                  <details>
                    <summary>Találat szövegének módosítása</summary>
                    <div className="manual-entry-panel">
                      <label>
                        Cím
                        <input
                          value={objectTextEdit.title}
                          onChange={(event) => setObjectTextEdit((current) => ({ ...current, title: event.target.value }))}
                        />
                      </label>
                      <label>
                        Leírás
                        <textarea
                          value={objectTextEdit.description}
                          onChange={(event) => setObjectTextEdit((current) => ({ ...current, description: event.target.value }))}
                          rows={5}
                        />
                      </label>
                      <button
                        className="secondary-button"
                        onClick={() => handleUpdateReviewReportItemText(selectedReportItem)}
                        disabled={
                          Boolean(busy) ||
                          !objectTextEdit.title.trim() ||
                          !objectTextEdit.description.trim() ||
                          objectTextEditUnchanged(selectedReportItem)
                        }
                      >
                        Módosítás mentése
                      </button>
                    </div>
                  </details>
                )}
                {renderClaimMergeControls(selectedReportItem)}
                {renderEntityMergeControls(selectedReportItem)}
                {renderEventMergeControls(selectedReportItem)}
                {renderMissingItemMergeControls(selectedReportItem)}
                <details>
                  <summary>Forráshivatkozások</summary>
                  {renderReportSourceGroups(selectedReportItem, "detail")}
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

          <section className="panel detached-sources-panel">
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
                        {renderSearchableSelect({
                          queryKey: `detached-source-attach:${item.id}`,
                          value: detachedSourceTargets[item.id] ?? "",
                          onChange: (value) => setDetachedSourceTargets((current) => ({ ...current, [item.id]: value })),
                          options: detachedSourceTargetOptions(item),
                          placeholder: "Visszacsatolás célja",
                          searchPlaceholder: "Keresés a visszacsatolási célok között",
                          ariaLabel: "Leválasztott forráshivatkozás csatolási célja"
                        })}
                        <button
                          className="secondary-button source-action"
                          onClick={() => handleAttachDetachedSource(item)}
                          disabled={Boolean(busy) || !detachedSourceTargets[item.id]}
                        >
                          Csatolás
                        </button>
                        <button className="danger-button source-action" onClick={() => handleDeleteDetachedSource(item)} disabled={Boolean(busy)}>
                          <Trash2 size={16} /> Végleges törlés
                        </button>
                      </div>
                      {item.source_text_excerpt && (
                        <details className="detached-source-context-details">
                          <summary>Szövegrész megtekintése</summary>
                          <div className="compact-item detached-source-context-card">
                            <strong>
                              {item.source_snapshot_json?.source_kind ? labelSourceExcerpt(item.source_snapshot_json.source_kind) : "Forrásszöveg"}{" "}
                              {formatRange(item.source_text_excerpt_char_start, item.source_text_excerpt_char_end)}
                            </strong>
                            <p className="excerpt">
                              {highlightedSourceExcerpt(item.source_text_excerpt, item.source_snapshot_json?.quote_text)}
                            </p>
                          </div>
                        </details>
                      )}
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

          </div>
          )}

        </section>
        )}

        {activeSurface === "general_rag" && renderGeneralRagSurface()}

        {activeSurface === "relationship_map" && renderRelationshipMapSurface()}

        {activeSurface === "knowledge_base" && renderKnowledgeBaseSurface()}

        {activeSurface === "ai_assistant" && renderAssistantSurface()}

        {activeSurface === "full_document_processing" && (
          <section className="surface-placeholder">
            {renderSurfaceHeader("full_document_processing")}
            <section className="full-document-grid">
              <section className="panel">
              <div className="section-heading">
                <h2>Irat és feldolgozási profil</h2>
                <FilePlus2 size={20} />
              </div>
              <div className="surface-form">
                <div className="form-field">
                  <span className="field-label">Feldolgozandó irat</span>
                  {renderSearchableSelect({
                    queryKey: "full-document-target",
                    value: fullDocumentId,
                    onChange: setFullDocumentId,
                    options: fullDocumentOptions,
                    placeholder: "Válassz aktív iratot",
                    searchPlaceholder: "Keresés az aktív iratok között",
                    ariaLabel: "Feldolgozandó irat"
                  })}
                </div>
                <div className="form-row full-document-settings-row">
                  <label>
                    Feldolgozási profil
                    <select
                      value={fullDocumentProfile}
                      onChange={(event) => setFullDocumentProfile(event.target.value)}
                      disabled={fullDocumentProfiles.length === 0}
                    >
                      {fullDocumentProfiles.map((profile) => (
                        <option key={profile.key} value={profile.key}>
                          {profile.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Oldaltól
                    <input
                      type="number"
                      min={1}
                      max={fullDocumentMaxPage}
                      value={fullDocumentPageStart}
                      onChange={(event) =>
                        setFullDocumentPageStart(String(clampNumberInput(event.target.value, 1, fullDocumentMaxPage, 1)))
                      }
                      disabled={!selectedFullDocument}
                    />
                  </label>
                  <label>
                    Oldalig
                    <input
                      type="number"
                      min={1}
                      max={fullDocumentMaxPage}
                      value={fullDocumentPageEnd}
                      onChange={(event) =>
                        setFullDocumentPageEnd(String(clampNumberInput(event.target.value, 1, fullDocumentMaxPage, fullDocumentMaxPage)))
                      }
                      disabled={!selectedFullDocument}
                    />
                  </label>
                </div>
                {fullDocumentProfileIsFreeQuestion && (
                  <label>
                    Kérdés
                    <input
                      type="text"
                      value={fullDocumentQuestion}
                      onChange={(event) => setFullDocumentQuestion(event.target.value)}
                      placeholder="Írd le, mire keressen választ a kijelölt irat megadott oldalai alapján"
                      disabled={!selectedFullDocument}
                    />
                  </label>
                )}
                {!fullDocumentPageRangeValid && selectedFullDocument && (
                  <p className="error-text">Az oldaltartomány csak 1 és {fullDocumentMaxPage} között lehet, és az első oldal nem lehet nagyobb az utolsónál.</p>
                )}
                <button
                  onClick={handleRunFullDocumentProcessing}
                  disabled={
                    !selectedCaseId ||
                    !selectedFullDocument ||
                    !fullDocumentProfile ||
                    !fullDocumentPageRangeValid ||
                    (fullDocumentProfileIsFreeQuestion && !fullDocumentQuestion.trim()) ||
                    Boolean(busy)
                  }
                >
                  <Play size={18} /> Feldolgozás indítása
                </button>
              </div>
            </section>
              <section className="panel">
                <div className="section-heading">
                  <h2>Iratösszefoglaló</h2>
                  <Database size={20} />
                </div>
                {!selectedFullDocument && <p className="muted">Válassz aktív iratot a teljes iratfeldolgozáshoz.</p>}
                {selectedFullDocument && (
                  <div className="detail-stack">
                    <strong>{selectedFullDocument.original_filename}</strong>
                    <div className="metrics">
                      <span>{labelProcessingStatus(selectedFullDocument.processing_status)}</span>
                      <span>{labelDocumentLifecycleStatus(selectedFullDocument.lifecycle_status)}</span>
                      <span>{formatBytes(selectedFullDocument.file_size_bytes)}</span>
                    </div>
                    <code>{selectedFullDocument.sha256_hash}</code>
                    <p className="field-hint">
                      A teljes iratfeldolgozás csak aktív, feldolgozott iratokon fog dolgozni. A létrejövő munkadarabok nem lesznek automatikusan szakmai tények; később emberi döntéssel kerülhetnek át a kutatási vagy strukturált objektum workflow-ba.
                    </p>
                  </div>
                )}
              </section>
            </section>
            <section className="panel">
              <div className="section-heading">
                <h2>{fullDocumentProfileIsFreeQuestion ? "Iratválasz" : "Előkészített munkalista"}</h2>
                {fullDocumentProfileIsFreeQuestion ? <MessageSquare size={20} /> : <Search size={20} />}
              </div>
              {lastFullDocumentRun && !fullDocumentProfileIsFreeQuestion && (
                <div className="detail-stack">
                  <div className="metrics">
                    <span>{labelValidationStatus(lastFullDocumentRun.validation_status)}</span>
                    <span>{lastFullDocumentRun.created_item_count} mentett elem</span>
                    <span>{lastFullDocumentRun.unsupported_count} nem megerősített jelölt</span>
                  </div>
                  {lastFullDocumentRun.created_item_count === 0 && (
                    <p className="error-text">Nem jött létre mentett munkalista-elem. Az okok az alábbi validációs üzenetekben láthatók.</p>
                  )}
                  {lastFullDocumentRun.unsupported_items.length > 0 && (
                    <div className="module-note module-note-warning">
                      <strong>Nem megerősített jelöltek / feldolgozási okok</strong>
                      <ul>
                        {lastFullDocumentRun.unsupported_items.map((item, index) => (
                          <li key={`${index}-${item}`}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {fullDocumentProfileIsFreeQuestion ? (
                <>
                  <div className="full-document-worklist-toolbar">
                    <button
                      className="secondary-button"
                      onClick={() => refreshFullDocumentAnswers()}
                      disabled={!selectedCaseId || !selectedFullDocument || Boolean(busy)}
                    >
                      <RefreshCw size={18} /> Iratválaszok frissítése
                    </button>
                    <div className="metrics">
                      <span>{fullDocumentAnswers.length} mentett iratválasz</span>
                      {fullDocumentCurrentAnswer && <span>{formatDateTime(fullDocumentCurrentAnswer.created_at)}</span>}
                    </div>
                  </div>
                  {!selectedFullDocument && <p className="muted">Válassz iratot az iratválaszok betöltéséhez.</p>}
                  {selectedFullDocument && !fullDocumentCurrentAnswer && (
                    <div className="research-empty-state rag-empty-state full-document-answer-empty-state">
                      <strong>Nincs iratválasz</strong>
                      <p>Adj meg kérdést, majd futtasd a Szabad iratkérdés profilt.</p>
                    </div>
                  )}
                  {fullDocumentCurrentAnswer && (
                    <div className="rag-answer-layout full-document-answer-layout">
                      <article className="rag-answer-card full-document-answer-card">
                        <div className="item-card-header">
                          <div>
                            <strong>{fullDocumentCurrentAnswer.question_text}</strong>
                            <div className="metrics">
                              <span>{fullDocumentCurrentAnswer.page_start}-{fullDocumentCurrentAnswer.page_end}. oldal</span>
                              <span>{fullDocumentCurrentAnswer.source_page_count} forrásoldal</span>
                              <span>{formatDateTime(fullDocumentCurrentAnswer.created_at)}</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="danger-button"
                            onClick={() => handleDeleteFullDocumentAnswer(fullDocumentCurrentAnswer.id)}
                            disabled={Boolean(busy)}
                          >
                            <Trash2 size={16} /> Törlés
                          </button>
                        </div>
                        <MarkdownAnswer>{fullDocumentCurrentAnswer.answer_text}</MarkdownAnswer>
                        {fullDocumentCurrentAnswer.source_summary && (
                          <div className="module-note">
                            Forrásalap: <strong>{fullDocumentCurrentAnswer.source_summary}</strong>
                          </div>
                        )}
                      </article>
                      {fullDocumentAnswers.length > 0 && (
                        <aside className="rag-source-card compact-item full-document-answer-history">
                          <strong>Korábbi iratválaszok</strong>
                          <div className="compact-list">
                            {fullDocumentAnswers.map((answer) => (
                              <button
                                key={answer.id}
                                type="button"
                                className={answer.id === fullDocumentCurrentAnswer.id ? "surface-tab full-document-answer-history-button is-active" : "surface-tab full-document-answer-history-button"}
                                onClick={() => setFullDocumentCurrentAnswer(answer)}
                              >
                                <span className="full-document-answer-history-label">{answer.question_text}</span>
                              </button>
                            ))}
                          </div>
                        </aside>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <>
              <div className="full-document-worklist-toolbar">
                <button
                  className="secondary-button"
                  onClick={() => refreshFullDocumentItems()}
                  disabled={!selectedCaseId || !selectedFullDocument || Boolean(busy)}
                >
                  <RefreshCw size={18} /> Munkalista frissítése
                </button>
                <input
                  className="full-document-worklist-search-input"
                  value={documentProcessingItemSearch}
                  onChange={(event) => setDocumentProcessingItemSearch(event.target.value)}
                  placeholder="Keresés a találatokban"
                  aria-label="Keresés a találatokban"
                />
                <div className="full-document-status-toggle" aria-label="Teljes iratfeldolgozási munkalista nézet">
                  <button
                    type="button"
                    className={fullDocumentWorkStatus === "active" ? "" : "secondary-button"}
                    onClick={() => setFullDocumentWorkStatus("active")}
                    disabled={Boolean(busy)}
                  >
                    Aktív
                  </button>
                  <button
                    type="button"
                    className={fullDocumentWorkStatus === "set_aside" ? "" : "secondary-button"}
                    onClick={() => setFullDocumentWorkStatus("set_aside")}
                    disabled={Boolean(busy)}
                  >
                    Félretett
                  </button>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={markAllVisibleDocumentProcessingItemsForDeletion}
                  disabled={Boolean(busy) || markableDocumentProcessingItemIds.length === 0 || allVisibleDocumentProcessingItemsMarked}
                >
                  Összes törlésre jelölése
                </button>
                <button
                  type="button"
                  className="danger-button"
                  onClick={handleBulkDeleteDocumentProcessingItems}
                  disabled={Boolean(busy) || markedDocumentProcessingItemCount === 0}
                >
                  <Trash2 size={16} /> Jelöltek törlése ({markedDocumentProcessingItemCount})
                </button>
              </div>
              {!selectedFullDocument && <p className="muted">Válassz iratot a munkalista betöltéséhez.</p>}
              {selectedFullDocument && documentProcessingItems.length === 0 && (
                <div className="full-document-output">
                  <div>
                    <span>Várható elem</span>
                    <strong>név / cím</strong>
                    <p>Rövid, forráshű leírás és keresési fókuszjavaslatok.</p>
                  </div>
                  <div>
                    <span>Adatátadás</span>
                    <strong>kutatási fókusz</strong>
                    <p>Az eredmény később átadható lesz a kutatási találatok munkafolyamatának.</p>
                  </div>
                  <div>
                    <span>Forráselv</span>
                    <strong>No source - no claim</strong>
                    <p>A teljes iratfeldolgozás sem hozhat létre forrás nélküli állítást.</p>
                  </div>
                </div>
              )}
              {documentProcessingItems.length > 0 && (
                <>
                  {documentProcessingItemSearch.trim() && (
                    <div className="metrics">
                      <span>{visibleDocumentProcessingItems.length} megjelenítve</span>
                      <span>{documentProcessingItems.length} összesen</span>
                    </div>
                  )}
                  {visibleDocumentProcessingItems.length === 0 && (
                    <p className="muted">Nincs a keresésnek megfelelő munkalista-elem.</p>
                  )}
                  <div className="full-document-items">
                    {visibleDocumentProcessingItems.map((item) => {
                    const isMarkedForDeletion = documentProcessingItemsMarkedForDeletion.includes(item.id);
                    const isUnconfirmedDocumentProcessingItem = item.source_evidence_json.length === 0;
                    const unconfirmedDetail = item.source_supported_details_json.find(isDocumentProcessingUnconfirmedDetail);
                    return (
                      <article
                        key={item.id}
                        className={`full-document-item ${item.work_status === "set_aside" ? "is-set-aside" : ""} ${
                          isMarkedForDeletion ? "is-marked-delete" : ""
                        } ${isUnconfirmedDocumentProcessingItem ? "is-unconfirmed" : ""
                        }`}
                      >
                        <div className="item-card-header">
                          <div>
                            <strong>{item.display_label}</strong>
                            <div className="metrics">
                              <span>{labelDocumentProcessingItemKind(item.item_kind)}</span>
                              <span>{labelDocumentProcessingWorkStatus(item.work_status)}</span>
                              {isUnconfirmedDocumentProcessingItem && <span>Nem megerősített</span>}
                              <span>{labelDocumentProcessingOccurrence(item.occurrence_status)}</span>
                            </div>
                          </div>
                          <div className="button-row">
                            {item.work_status === "set_aside" ? (
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleDocumentProcessingItemStatus(item.id, "active")}
                                disabled={Boolean(busy)}
                              >
                                Vissza az aktív listába
                              </button>
                            ) : (
                              <>
                                <button
                                  type="button"
                                  className="secondary-button"
                                  onClick={() => {
                                    setQuery(item.recommended_search_focus ?? item.display_label);
                                    setModuleKey("search_findings");
                                    setActiveSurface("case_workbench");
                                    scrollToAnalysisPanel();
                                  }}
                                  disabled={Boolean(busy)}
                                >
                                  <Search size={16} /> Fókuszba teszem
                                </button>
                                <button
                                  type="button"
                                  className="secondary-button"
                                  onClick={() => handleDocumentProcessingItemStatus(item.id, "set_aside")}
                                  disabled={Boolean(busy)}
                                >
                                  Félreteszem
                                </button>
                              </>
                            )}
                            <button
                              type="button"
                              onClick={() => toggleDocumentProcessingItemDeletionMark(item)}
                              disabled={Boolean(busy)}
                            >
                              {isMarkedForDeletion ? "Törlésre jelölve" : "Törlésre jelölés"}
                            </button>
                          </div>
                        </div>
                        {item.recommended_search_focus && (
                          <div className="module-note">
                            Keresési fókusz: <strong>{item.recommended_search_focus}</strong>
                          </div>
                        )}
                        {isUnconfirmedDocumentProcessingItem && unconfirmedDetail && (
                          <div className="module-note module-note-warning full-document-unconfirmed-note">
                            {typeof unconfirmedDetail.validation_message === "string" && <span>{unconfirmedDetail.validation_message}</span>}
                            {typeof unconfirmedDetail.llm_source_label === "string" && (
                              <span>
                                LLM által megadott forrásoldal: <strong>{formatPageSourceLabel(unconfirmedDetail.llm_source_label)}</strong>
                              </span>
                            )}
                          </div>
                        )}
                        {item.source_evidence_json[0] && (
                          <div className="full-document-source">
                            <strong>
                              {item.source_evidence_json[0].page_number
                                ? `${item.source_evidence_json[0].page_number}. oldal`
                                : item.source_evidence_json[0].source_label ?? "Forrás"}
                            </strong>
                            {item.source_evidence_json[0].quote_text && <span>{item.source_evidence_json[0].quote_text}</span>}
                          </div>
                        )}
                      </article>
                    );
                    })}
                  </div>
                </>
              )}
                </>
              )}
            </section>
          </section>
        )}

        {activeSurface === "audit_log" && (
          <section className="surface-placeholder">
            {renderSurfaceHeader("audit_log")}
            <section className="panel">
              <div className="section-heading">
                <h2>Tervezett naplófelület</h2>
                <Archive size={20} />
              </div>
              <div className="module-note">
                Ez a felület az audit események önálló áttekintésére készül. Nem azonos az Elemzési előzmények panellel: az ottani lista elemzési futásokat mutat, az audit napló pedig később az audit_events eseményeit fogja időrendben és szűrhetően megjeleníteni.
              </div>
              <div className="metrics">
                <span>iratbesorolás</span>
                <span>iratállapot</span>
                <span>forrásműveletek</span>
                <span>kézi beavatkozások</span>
              </div>
            </section>
          </section>
        )}
          </div>
        </div>
      </section>
      {appDialog && (
        <div className="app-dialog-backdrop" onMouseDown={() => resolveAppDialog(null)} role="presentation">
          <form
            className="app-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="app-dialog-title"
            onMouseDown={(event) => event.stopPropagation()}
            onSubmit={(event) => {
              event.preventDefault();
              submitAppDialog();
            }}
          >
            <div className="app-dialog-heading">
              <strong id="app-dialog-title">{appDialog.title}</strong>
              <span className="field-hint">{appDialog.message}</span>
            </div>
            {appDialog.detail && <p className="app-dialog-detail">{appDialog.detail}</p>}
            {appDialog.mode === "text_confirm" && (
              <label className="app-dialog-field">
                <span>{appDialog.inputLabel ?? "Megerősítés"}</span>
                <input
                  ref={appDialogInputRef}
                  value={appDialogInput}
                  onChange={(event) => setAppDialogInput(event.target.value)}
                  disabled={Boolean(busy)}
                />
              </label>
            )}
            <div className="app-dialog-actions">
              <button type="button" className="secondary-button" onClick={() => resolveAppDialog(null)} disabled={Boolean(busy)}>
                {appDialog.cancelLabel ?? "Mégse"}
              </button>
              <button
                type="submit"
                className={appDialog.danger ? "danger-button" : undefined}
                disabled={Boolean(busy) || (appDialog.mode === "text_confirm" && appDialog.expectedValue !== undefined && appDialogInput !== appDialog.expectedValue)}
              >
                {appDialog.confirmLabel ?? "Rendben"}
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}

function formatRange(start: number | null, end: number | null) {
  if (start === null || end === null) {
    return "-";
  }
  return `${start}-${end}`;
}

function buildKnowledgeBatchRelativeDirectory(file: File, baseDirectory: string) {
  const cleanedBase = cleanRelativeDirectory(baseDirectory);
  const browserRelativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  const browserDirectory = browserRelativePath ? cleanRelativeDirectory(browserRelativePath.split("/").slice(0, -1).join("/")) : "";
  return [cleanedBase, browserDirectory].filter(Boolean).join("/");
}

function cleanRelativeDirectory(value: string) {
  return value.trim().replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
}

function validateKnowledgeBatchRelativeDirectory(value: string) {
  const cleaned = cleanRelativeDirectory(value);
  if (!cleaned) return "Adj meg relatív mappaútvonalat.";
  const parts = cleaned.split("/").filter(Boolean);
  if (parts.length < 2) return "Adj meg útvonalszerű mappaútvonalat, legalább két szegmenssel. Példa: notes/linux";
  const hasInvalidSegment = parts.some((part) => part === "." || part === ".." || !/[0-9A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]/.test(part));
  if (hasInvalidSegment) return "A mappaútvonal érvénytelen szegmenst tartalmaz.";
  return "";
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

function analysisRunHistoryTitle(run: AnalysisRunRead) {
  const baseTitle = labelModule(run.run_type);
  if (!run.display_label) {
    return baseTitle;
  }
  return `${baseTitle} - ${truncateText(run.display_label, 90)}`;
}

function labelAnalysisSourceMode(value: AnalysisSourceMode) {
  return analysisSourceModeLabels[value] ?? value;
}

function analysisSourceSummaryLabel(value: AnalysisSourceMode, selectedDocumentCount: number, collectionName?: string) {
  if (value === "case" && selectedDocumentCount > 0) {
    return `Teljes ugy, ${selectedDocumentCount} kijelolt irat`;
  }
  if (value === "collection" && collectionName) {
    return `Iratgyűjtemény: ${collectionName}`;
  }
  return labelAnalysisSourceMode(value);
}

function labelClaimReviewScope(value: ClaimReviewScope) {
  return claimReviewScopeLabels[value] ?? value;
}

function labelRetrievalStrategy(value: RetrievalStrategy) {
  return retrievalStrategyLabels[value] ?? value;
}

function labelRagSourceMode(value: RagSourceMode) {
  if (value === "document") return "Kiválasztott irat";
  if (value === "collection") return "Iratgyűjtemény";
  return "Teljes ügy";
}

function labelRagAnswerMode(value: RagAnswerMode) {
  return ragAnswerModeLabels[value] ?? value;
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
  if (value.collection_id) return "Iratgyűjtemény";
  if (value.document_ids.length > 0) return `Teljes ugy, ${value.document_ids.length} kijelolt irat`;
  return "Teljes ugy";
}

function filterDocumentsByName(documents: DocumentRead[], searchText: string) {
  const needle = searchText.trim().toLocaleLowerCase("hu-HU");
  if (!needle) return documents;
  return documents.filter((document) => document.original_filename.toLocaleLowerCase("hu-HU").includes(needle));
}

function filterKnowledgeDocuments(documents: KnowledgeDocumentRead[], searchText: string) {
  const needle = searchText.trim().toLocaleLowerCase("hu-HU");
  if (!needle) return documents;
  return documents.filter((document) =>
    `${document.original_filename} ${document.relative_path ?? ""} ${document.sha256_hash}`
      .toLocaleLowerCase("hu-HU")
      .includes(needle)
  );
}

function filterDocumentProcessingItemsByName(items: DocumentProcessingItemRead[], searchText: string) {
  const needle = searchText.trim().toLocaleLowerCase("hu-HU");
  if (!needle) return items;
  return items.filter((item) => item.display_label.toLocaleLowerCase("hu-HU").includes(needle));
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

function relationshipFocusKey(objectType: string, objectId: string) {
  return `${objectType}:${objectId}`;
}

function filterRelationshipGraphByLayers(
  graph: RelationshipGraph | null,
  layers: RelationshipGraphLayerState
): RelationshipGraph | null {
  if (!graph) return null;

  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const focusNodeIds = graph.focus_node_ids.length > 0 ? graph.focus_node_ids : [graph.focus_node_id];
  const focusNodeIdSet = new Set(focusNodeIds);
  const visibleNodeIds = new Set<string>(focusNodeIds);
  const sourceCarrierNodeIds = new Set<string>(focusNodeIds);
  const focusSourceReferenceIds = new Set<string>();
  const sourceReferenceChains = new Map<string, { documentId?: string; pageId?: string; chunkId?: string }>();

  graph.edges.forEach((edge) => {
    if ((edge.type === "CONTRADICTS_CLAIM_A" || edge.type === "CONTRADICTS_CLAIM_B") && focusNodeIdSet.has(edge.target)) {
      sourceCarrierNodeIds.add(edge.source);
    }
  });

  graph.edges.forEach((edge) => {
    if (edge.type === "HAS_SOURCE" && sourceCarrierNodeIds.has(edge.source)) {
      const targetNode = nodesById.get(edge.target);
      if (targetNode?.type === "source_reference") {
        focusSourceReferenceIds.add(targetNode.id);
        sourceReferenceChains.set(targetNode.id, sourceReferenceChains.get(targetNode.id) ?? {});
      }
    }
  });

  graph.edges.forEach((edge) => {
    if (edge.type === "SOURCE_FROM_CHUNK" && focusSourceReferenceIds.has(edge.target)) {
      const chain = sourceReferenceChains.get(edge.target) ?? {};
      chain.chunkId = edge.source;
      sourceReferenceChains.set(edge.target, chain);
    } else if (edge.type === "SOURCE_FROM_PAGE" && focusSourceReferenceIds.has(edge.target)) {
      const chain = sourceReferenceChains.get(edge.target) ?? {};
      chain.pageId = edge.source;
      sourceReferenceChains.set(edge.target, chain);
    } else if (edge.type === "SOURCE_FROM_DOCUMENT" && focusSourceReferenceIds.has(edge.target)) {
      const chain = sourceReferenceChains.get(edge.target) ?? {};
      chain.documentId = edge.source;
      sourceReferenceChains.set(edge.target, chain);
    }
  });

  graph.edges.forEach((edge) => {
    if (edge.type === "PAGE_HAS_CHUNK") {
      for (const chain of sourceReferenceChains.values()) {
        if (chain.chunkId === edge.target) {
          chain.pageId = edge.source;
        }
      }
    } else if (edge.type === "DOCUMENT_HAS_PAGE") {
      for (const chain of sourceReferenceChains.values()) {
        if (chain.pageId === edge.target) {
          chain.documentId = edge.source;
        }
      }
    } else if (edge.type === "DOCUMENT_HAS_CHUNK") {
      for (const chain of sourceReferenceChains.values()) {
        if (chain.chunkId === edge.target) {
          chain.documentId = edge.source;
        }
      }
    }
  });

  graph.edges.forEach((edge) => {
    if (edge.type === "DOCUMENT_HAS_PAGE") {
      for (const chain of sourceReferenceChains.values()) {
        if (chain.pageId === edge.target || chain.chunkId) {
          const pageToChunkEdge = graph.edges.find((candidate) => candidate.type === "PAGE_HAS_CHUNK" && candidate.source === edge.target && candidate.target === chain.chunkId);
          if (chain.pageId === edge.target || pageToChunkEdge) {
            chain.documentId = edge.source;
          }
        }
      }
    }
  });

  sourceReferenceChains.forEach((chain, sourceReferenceId) => {
    if (layers.document_node && chain.documentId) {
      visibleNodeIds.add(chain.documentId);
    }
    if (layers.page_node && chain.pageId) {
      visibleNodeIds.add(chain.pageId);
    }
    if (layers.source_chunk && chain.chunkId) {
      visibleNodeIds.add(chain.chunkId);
    }
    if (layers.source_reference) {
      visibleNodeIds.add(sourceReferenceId);
    }
  });

  if (layers.related_objects) {
    graph.nodes.forEach((node) => {
      if (focusNodeIdSet.has(node.id)) return;
      if (node.type === "claim" || node.type === "event" || node.type === "entity" || node.type === "missing_item_candidate") {
        visibleNodeIds.add(node.id);
      }
    });
  }

  graph.edges.forEach((edge) => {
    if ((edge.type === "CONTRADICTS_CLAIM_A" || edge.type === "CONTRADICTS_CLAIM_B") && focusNodeIdSet.has(edge.target)) {
      visibleNodeIds.add(edge.source);
    }
  });

  if (layers.contradictions) {
    graph.nodes.forEach((node) => {
      if (node.type === "contradiction_candidate") {
        visibleNodeIds.add(node.id);
      }
    });
    graph.edges.forEach((edge) => {
      if ((edge.type === "CONTRADICTS_CLAIM_A" || edge.type === "CONTRADICTS_CLAIM_B") && visibleNodeIds.has(edge.target)) {
        visibleNodeIds.add(edge.source);
      }
    });
  }

  const visibleNodes = graph.nodes.filter((node) => visibleNodeIds.has(node.id));
  const visibleEdges = graph.edges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target));
  const bridgeEdges: RelationshipGraphEdge[] = [];
  const visibleEdgeKeys = new Set(visibleEdges.map((edge) => `${edge.source}->${edge.target}`));
  const visibleEdgePairKeys = new Set(visibleEdges.map((edge) => [edge.source, edge.target].sort().join("<->")));
  const bridgeIds = new Set<string>();
  graph.edges
    .filter((edge) => edge.type === "HAS_SOURCE" && sourceCarrierNodeIds.has(edge.source) && focusSourceReferenceIds.has(edge.target))
    .forEach((sourceEdge) => {
      const chain = sourceReferenceChains.get(sourceEdge.target);
      const visibleChain = [
        chain?.documentId,
        chain?.pageId,
        chain?.chunkId,
        layers.source_reference ? sourceEdge.target : undefined,
        sourceEdge.source
      ].filter((nodeId): nodeId is string => Boolean(nodeId && visibleNodeIds.has(nodeId)));
      for (let index = 0; index < visibleChain.length - 1; index += 1) {
        const source = visibleChain[index];
        const target = visibleChain[index + 1];
        if (visibleEdgeKeys.has(`${source}->${target}`)) continue;
        if (visibleEdgePairKeys.has([source, target].sort().join("<->"))) continue;
        const bridgeId = `visual:${source}--SOURCE_BRIDGE--${target}`;
        if (bridgeIds.has(bridgeId)) continue;
        bridgeIds.add(bridgeId);
        bridgeEdges.push({
          id: bridgeId,
          type: "VISUAL_SOURCE_BRIDGE",
          source,
          target,
          label: "",
          metadata: {
            source_reference_id: sourceEdge.target,
            visual_only: true
          }
        });
      }
    });
  return {
    ...graph,
    nodes: visibleNodes,
    edges: [...visibleEdges, ...bridgeEdges],
    limits: {
      ...graph.limits,
      node_count: visibleNodes.length,
      edge_count: visibleEdges.length + bridgeEdges.length
    }
  };
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

function labelResearchFindingRunOutcome(run: ResearchFindingLatestRunSummary) {
  if (run.status === "failed") return "Sikertelen keresés";
  if (run.status === "running") return "Folyamatban";
  if (run.validation_status === "warning") return "Sikeres, figyelmeztetéssel";
  if (run.validation_status === "passed") return "Sikeres keresés";
  if (run.validation_status === "failed") return "Sikertelen keresés";
  return labelRunStatus(run.status);
}

function labelRagRunOutcome(run: RagLatestRunSummary) {
  if (run.status === "failed") return "Sikertelen kérdezés";
  if (run.status === "running") return "Folyamatban";
  if (run.insufficient_source) return "Nincs elég forrás";
  if (run.saved_answer_id) return "Mentett válasz";
  if (run.status === "succeeded") return "Sikeres válasz";
  return labelRunStatus(run.status);
}

function labelDocumentProcessingItemKind(value: string) {
  const labels: Record<string, string> = {
    person: "Személy",
    organization: "Szervezet",
    location: "Hely",
    document_reference: "Irathivatkozás",
    case_reference: "Ügyhivatkozás",
    attachment: "Melléklet",
    other: "Egyéb"
  };
  return labels[value] ?? value;
}

function labelDocumentProcessingWorkStatus(value: string) {
  const labels: Record<string, string> = {
    active: "Aktív munkalista-elem",
    set_aside: "Félretéve",
    converted: "Átalakítva",
    deleted: "Törölve"
  };
  return labels[value] ?? value;
}

function labelDocumentProcessingOccurrence(value: string) {
  return value === "repeated" ? "Többször előforduló" : "Egyedi";
}

function formatPageSourceLabel(value: string) {
  const match = /^page_(\d+)$/.exec(value);
  return match ? `${match[1]}. oldal` : value;
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
      source.source_text_excerpt ?? "",
    ])
  ]
    .join(" ")
    .toLocaleLowerCase("hu-HU");
  return haystack.includes(queryText);
}

function formatSourceReferenceCount(count: number) {
  return `${count} forráshivatkozás`;
}

function highlightedSourceExcerpt(excerpt: string, quoteText: string | null | undefined): ReactNode {
  if (!quoteText) return excerpt;
  const matchStart = excerpt.indexOf(quoteText);
  if (matchStart < 0) return excerpt;
  const matchEnd = matchStart + quoteText.length;
  return (
    <>
      {excerpt.slice(0, matchStart)}
      <mark className="source-quote-highlight">{excerpt.slice(matchStart, matchEnd)}</mark>
      {excerpt.slice(matchEnd)}
    </>
  );
}

function firstExactQuoteInExcerpt(excerpt: string, quoteTexts: Array<string | null | undefined>): string | null {
  return quoteTexts.find((quoteText) => Boolean(quoteText) && excerpt.includes(quoteText as string)) ?? null;
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
  };
  return labels[value] ?? value;
}

function normalizeComboboxText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("hu-HU")
    .trim();
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

function labelKnowledgeStatus(value: string) {
  const labels: Record<string, string> = {
    imported: "Importálva",
    processed: "Feldolgozva",
    indexing: "Indexelés alatt",
    indexed: "Indexelve",
    failed: "Sikertelen",
    archived: "Archivált"
  };
  return labels[value] ?? value;
}

function labelKnowledgeBatchPreviewStatus(value: string) {
  const labels: Record<string, string> = {
    ready: "Importálható",
    same_hash: "Azonos tartalom",
    same_relative_path: "Azonos útvonal",
    invalid: "Hibás fájl"
  };
  return labels[value] ?? value;
}

function labelKnowledgeBatchImportAction(value: string) {
  const labels: Record<string, string> = {
    imported: "Importálva",
    skipped: "Kihagyva",
    replaced: "Cserélve",
    failed: "Hibás"
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

function labelSourceExcerpt(value: string) {
  const labels: Record<string, string> = {
    chunk_quote: "teljes szövegrész",
    page_quote: "teljes oldal",
    manual: "forrásszöveg"
  };
  return labels[value] ?? "forrásszöveg";
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

function renderAnalysisRunDetailView(detail: AnalysisRunDetail) {
  if (detail.run.run_type === "manual_entry") {
    return renderManualEntryRunDetailView(detail);
  }

  const focusInput = detail.inputs.find((input) => input.input_type === "query_text");
  const focusText = typeof focusInput?.payload_json?.query === "string" ? focusInput.payload_json.query : null;
  const sourceInputs = detail.inputs.filter((input) => input.input_type === "chunk" || input.source_summary);
  const outputGroups = groupAnalysisRunOutputs(detail.outputs);
  const processRows = buildAnalysisProcessRows(sourceInputs, outputGroups);
  const unmatchedOutputGroups = outputGroups.filter((group) => !groupMatchedSourceChunkId(group));

  return (
    <div className="analysis-run-detail-view">
      <section className="analysis-run-overview analysis-readable-card">
        <div>
          <strong>{labelModule(detail.run.run_type)}</strong>
          <span>{detail.run.model_name ?? "nincs modell"}</span>
        </div>
        <div className="metrics">
          <span>{labelRunStatus(detail.run.status)}</span>
          <span>{detail.run.validation_status ? labelValidationStatus(detail.run.validation_status) : "nincs validacio"}</span>
          <span>{sourceInputs.length} forrás</span>
          <span>{outputGroups.length} eredménycsoport</span>
          <span>{detail.run.finished_at ? formatDateTime(detail.run.finished_at) : formatDateTime(detail.run.started_at)}</span>
        </div>
        <code>{detail.run.id}</code>
        {detail.run.error_message && <p className="error-text">{detail.run.error_message}</p>}
      </section>

      <section className="analysis-detail-block">
        <div className="section-heading compact-heading">
          <h3>Keresési fókusz</h3>
        </div>
        <div className="module-note">
          {focusText ? focusText : "Ehhez a futáshoz nincs külön keresési fókusz rögzítve."}
        </div>
      </section>

      <section className="analysis-detail-block">
        <div className="section-heading compact-heading">
          <h3>Forrásból létrejött eredmények</h3>
          <span>{processRows.length} forrássor</span>
        </div>
        <div className="analysis-process-list">
          {processRows.length === 0 && <p className="muted">Nincs megjeleníthető forrásfolyamat.</p>}
          {processRows.map((row) => renderAnalysisProcessRow(row))}
          {unmatchedOutputGroups.length > 0 && (
            <article className="analysis-process-row analysis-process-row-unmatched">
              <div className="analysis-process-source">
                <strong>Forráshoz nem párosított eredmények</strong>
                <p className="muted">Ezekhez a kimenetekhez a részletes válaszban nincs közvetlen szövegrész-kapcsolat.</p>
              </div>
              <div className="analysis-process-arrow">{"->"}</div>
              <div className="analysis-process-results">
                {unmatchedOutputGroups.map((group) => renderAnalysisOutputGroup(group))}
              </div>
            </article>
          )}
        </div>
      </section>

    </div>
  );
}

function renderManualEntryRunDetailView(detail: AnalysisRunDetail) {
  const sourceInput = detail.inputs.find((input) => input.source_summary) ?? detail.inputs[0] ?? null;
  const createdOutputs = detail.outputs.filter((output) => output.output_type !== "source_reference");
  const sourceOutput = detail.outputs.find((output) => output.output_type === "source_reference");

  return (
    <div className="analysis-run-detail-view">
      <section className="analysis-run-overview analysis-readable-card">
        <div>
          <strong>{labelModule(detail.run.run_type)}</strong>
          <span>Kézzel létrehozott vagy csatolt forráshivatkozott elem</span>
        </div>
        <div className="metrics">
          <span>{labelRunStatus(detail.run.status)}</span>
          <span>{detail.run.validation_status ? labelValidationStatus(detail.run.validation_status) : "nincs validacio"}</span>
          <span>{createdOutputs.length} célobjektum</span>
          <span>{sourceOutput ? "1 forráshivatkozás" : "nincs forráshivatkozás"}</span>
          <span>{detail.run.finished_at ? formatDateTime(detail.run.finished_at) : formatDateTime(detail.run.started_at)}</span>
        </div>
        {detail.run.error_message && <p className="error-text">{detail.run.error_message}</p>}
      </section>

      <section className="analysis-detail-block">
        <div className="section-heading compact-heading">
          <h3>Kézi rögzítés folyamata</h3>
        </div>
        <div className="analysis-process-list">
          <article className="analysis-process-row">
            <div className="analysis-process-source">
              <strong>Kiválasztott forrás</strong>
              {sourceInput?.source_summary ? renderAnalysisSourceSummary(sourceInput.source_summary, sourceInput.payload_json) : (
                <p className="muted">Ehhez a kézi futáshoz nincs megjeleníthető forrásbemenet.</p>
              )}
            </div>
            <div className="analysis-process-arrow">{"->"}</div>
            <div className="analysis-process-results">
              {createdOutputs.length === 0 && <p className="muted">Nincs megjeleníthető létrehozott vagy csatolt célobjektum.</p>}
              {createdOutputs.map((output) => (
                <article key={output.id} className="compact-item analysis-output-group">
                  <div className="analysis-output-group-heading">
                    <strong>{labelAnalysisOutputType(output.output_type)}</strong>
                  </div>
                  {renderAnalysisOutputSummary(output.output_summary)}
                </article>
              ))}
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}

function groupAnalysisRunOutputs(outputs: AnalysisRunDetail["outputs"]) {
  const groups = new Map<string, AnalysisRunDetail["outputs"]>();
  outputs.forEach((output) => {
    const key = output.output_position === null ? output.id : String(output.output_position);
    groups.set(key, [...(groups.get(key) ?? []), output]);
  });
  return Array.from(groups.entries()).map(([key, items]) => ({ key, items }));
}

function buildAnalysisProcessRows(
  sourceInputs: AnalysisRunDetail["inputs"],
  outputGroups: Array<{ key: string; items: AnalysisRunDetail["outputs"] }>
) {
  return sourceInputs.map((input) => ({
    input,
    outputGroups: outputGroups.filter((group) => groupMatchedSourceChunkId(group) === input.chunk_id)
  }));
}

function groupMatchedSourceChunkId(group: { key: string; items: AnalysisRunDetail["outputs"] }) {
  return group.items.find((output) => output.output_summary?.chunk_id)?.output_summary?.chunk_id ?? null;
}

function renderAnalysisProcessRow(row: {
  input: AnalysisRunDetail["inputs"][number];
  outputGroups: Array<{ key: string; items: AnalysisRunDetail["outputs"] }>;
}) {
  return (
    <article key={row.input.id} className="analysis-process-row">
      <div className="analysis-process-source">
        <strong>{row.input.sequence_no}. {labelAnalysisInputType(row.input.input_type)}</strong>
        {renderAnalysisSourceSummary(row.input.source_summary, row.input.payload_json)}
        {row.input.payload_json && renderAnalysisInputPayload(row.input.payload_json)}
      </div>
      <div className="analysis-process-arrow">{"->"}</div>
      <div className="analysis-process-results">
        {row.outputGroups.length === 0 && <p className="muted">Ebből a forrásból nem jött létre mentett eredmény.</p>}
        {row.outputGroups.map((group) => renderAnalysisOutputGroup(group))}
      </div>
    </article>
  );
}

function renderAnalysisOutputGroup(group: { key: string; items: AnalysisRunDetail["outputs"] }) {
  const primaryOutput = group.items.find((output) => output.output_type !== "source_reference") ?? group.items[0];
  const companionOutputs = group.items.filter((output) => output.id !== primaryOutput.id && output.output_type !== "source_reference");

  return (
    <article key={group.key} className="compact-item analysis-output-group">
      <div className="analysis-output-group-heading">
        <strong>{labelAnalysisOutputType(primaryOutput.output_type)}</strong>
        <span>pozíció {primaryOutput.output_position ?? group.key}</span>
      </div>
      {renderAnalysisOutputSummary(primaryOutput.output_summary)}
      {companionOutputs.map((output) => (
        <div key={output.id} className="analysis-output-companion">
          <span>{labelAnalysisOutputType(output.output_type)}</span>
          {renderAnalysisOutputSummary(output.output_summary)}
        </div>
      ))}
    </article>
  );
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
  if (!summary) {
    return (
      <div className="analysis-readable-card analysis-output-missing">
        <strong>Az eredmény már nem elérhető</strong>
        <p className="muted">A futásnaplóban megmaradt a kimenet nyoma, de a hozzá tartozó elem már nem áll rendelkezésre. Valószínűleg törölve lett.</p>
      </div>
    );
  }
  return (
    <div className="analysis-readable-card">
      {summary.title && <strong>{summary.title}</strong>}
      <div className="source-meta">
        {summary.review_status && <span>{labelReviewStatus(summary.review_status)}</span>}
        {summary.source_validation_status && <span>{labelSourceValidationStatus(summary.source_validation_status)}</span>}
        {summary.source_count !== null && summary.source_count !== undefined && <span>{formatSourceReferenceCount(summary.source_count)}</span>}
        {summary.document_filename && <span>{summary.document_filename}</span>}
        {summary.page_number !== null && summary.page_number !== undefined && <span>{summary.page_number}. oldal</span>}
        {summary.chunk_index !== null && summary.chunk_index !== undefined && <span>{summary.chunk_index}. szövegrész</span>}
      </div>
      {summary.body_text && <p className="analysis-source-preview">{summary.body_text}</p>}
      {summary.quote_text && summary.quote_text !== summary.body_text && <blockquote>{summary.quote_text}</blockquote>}
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

  return null;
}

function labelRetrievalMatchType(value: unknown) {
  const labels: Record<string, string> = {
    keyword: "Kulcsszavas",
    semantic: "Szemantikus",
    hybrid: "Hybrid",
    section_context: "Szekciókörnyezet",
    context_neighbor: "Környezeti szövegrész",
    heading_bridge: "Cím alatti szövegrész"
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

function isDocumentProcessingUnconfirmedDetail(value: unknown): value is DocumentProcessingUnconfirmedDetail {
  return isRecord(value) && value.validation_status === "unconfirmed";
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
