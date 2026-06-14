import { useEffect, useMemo, type ReactNode } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge as FlowEdge,
  type Node as FlowNode
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { RelationshipGraph, RelationshipGraphNode } from "./api";

type RelationshipFlowNodeData = {
  label: ReactNode;
};

type RelationshipFlowCanvasProps = {
  graph: RelationshipGraph;
  labelObjectType: (value: string) => string;
  labelSourceValidationStatus: (value: string) => string;
  selectedEdgeId?: string | null;
  selectedNodeId?: string | null;
  onEdgeSelect?: (edgeId: string) => void;
  onNodeSelect?: (nodeId: string) => void;
};

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
}

type RelationshipLayoutLayer = "document" | "page" | "chunk" | "source_reference" | "object" | "contradiction";

const relationshipLayerX: Record<RelationshipLayoutLayer, number> = {
  document: 0,
  page: 340,
  chunk: 680,
  source_reference: 1040,
  object: 1440,
  contradiction: 1840
};

const relationshipLayerOrder: RelationshipLayoutLayer[] = ["document", "page", "chunk", "source_reference", "object", "contradiction"];

function relationshipFocusNodeIds(graph: RelationshipGraph) {
  return new Set(graph.focus_node_ids.length > 0 ? graph.focus_node_ids : [graph.focus_node_id]);
}

function relationshipFlowLayer(graph: RelationshipGraph, node: RelationshipGraphNode): RelationshipLayoutLayer {
  const focusNodeIds = relationshipFocusNodeIds(graph);
  if (node.type === "document") return "document";
  if (node.type === "page") return "page";
  if (node.type === "chunk") return "chunk";
  if (node.type === "source_reference") return "source_reference";
  if (node.type === "contradiction_candidate") return "contradiction";
  if (focusNodeIds.has(node.id)) return "object";
  return "object";
}

function relationshipNodeDegree(graph: RelationshipGraph) {
  const degree = new Map<string, number>();
  graph.nodes.forEach((node) => degree.set(node.id, 0));
  graph.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });
  return degree;
}

function relationshipNodeSortValue(graph: RelationshipGraph, degree: Map<string, number>, node: RelationshipGraphNode) {
  const focusIndex = graph.focus_node_ids.indexOf(node.id);
  const focusSort = focusIndex >= 0 ? focusIndex : 999;
  const documentOrder =
    typeof node.metadata.document_name === "string"
      ? node.metadata.document_name
      : typeof node.metadata.filename === "string"
        ? node.metadata.filename
        : "";
  const pageNumber =
    typeof node.metadata.page_number === "number"
      ? node.metadata.page_number
      : typeof node.metadata.page_index === "number"
        ? node.metadata.page_index
        : 999999;
  const chunkIndex = typeof node.metadata.chunk_index === "number" ? node.metadata.chunk_index : 999999;
  const inverseDegree = String(9999 - (degree.get(node.id) ?? 0)).padStart(4, "0");
  return [
    String(focusSort).padStart(3, "0"),
    documentOrder.toLocaleLowerCase("hu-HU"),
    String(pageNumber).padStart(6, "0"),
    String(chunkIndex).padStart(6, "0"),
    inverseDegree,
    node.type,
    node.label.toLocaleLowerCase("hu-HU"),
    node.id
  ].join("|");
}

function relationshipVisualEdgeDirection(edge: { source: string; target: string; type: string }) {
  if (edge.type === "HAS_SOURCE") {
    return { source: edge.target, target: edge.source };
  }
  if (
    edge.type === "DOCUMENT_HAS_PAGE" ||
    edge.type === "PAGE_HAS_CHUNK" ||
    edge.type === "DOCUMENT_HAS_CHUNK" ||
    edge.type === "SOURCE_FROM_CHUNK" ||
    edge.type === "SOURCE_FROM_PAGE" ||
    edge.type === "SOURCE_FROM_DOCUMENT" ||
    edge.type === "VISUAL_SOURCE_BRIDGE"
  ) {
    return { source: edge.source, target: edge.target };
  }
  if (edge.type === "SOURCE_IN_CHUNK" || edge.type === "SOURCE_IN_DOCUMENT" || edge.type === "SOURCE_ON_PAGE") {
    return { source: edge.target, target: edge.source };
  }
  return { source: edge.source, target: edge.target };
}

function relationshipFlowNodeLabel(
  graph: RelationshipGraph,
  node: RelationshipGraphNode,
  labelObjectType: (value: string) => string,
  labelSourceValidationStatus: (value: string) => string
) {
  const isFocus = relationshipFocusNodeIds(graph).has(node.id);
  return (
    <div className="graph-flow-node-label">
      <strong>{truncateText(node.label, 52)}</strong>
      <span>{labelObjectType(node.type)}{isFocus ? " | fókusz" : ""}</span>
      {node.status.source_validation_status && <em>{labelSourceValidationStatus(node.status.source_validation_status)}</em>}
    </div>
  );
}

function buildRelationshipFlowElements(
  graph: RelationshipGraph,
  labelObjectType: (value: string) => string,
  labelSourceValidationStatus: (value: string) => string
): {
  nodes: FlowNode<RelationshipFlowNodeData>[];
  edges: FlowEdge[];
} {
  const focusNodeIds = relationshipFocusNodeIds(graph);
  const degree = relationshipNodeDegree(graph);
  const layerBuckets = new Map<RelationshipLayoutLayer, RelationshipGraphNode[]>();
  graph.nodes.forEach((node) => {
    const layer = relationshipFlowLayer(graph, node);
    layerBuckets.set(layer, [...(layerBuckets.get(layer) ?? []), node]);
  });

  const nodes: FlowNode<RelationshipFlowNodeData>[] = [];
  const sortedLayers = relationshipLayerOrder
    .filter((layer) => layerBuckets.has(layer))
    .map((layer) => [layer, layerBuckets.get(layer) ?? []] as const);
  sortedLayers.forEach(([layer, layerNodes]) => {
    const sortedLayerNodes = [...layerNodes].sort((left, right) =>
      relationshipNodeSortValue(graph, degree, left).localeCompare(relationshipNodeSortValue(graph, degree, right), "hu-HU")
    );
    const layerGap = 132;
    const centerOffset = ((sortedLayerNodes.length - 1) * layerGap) / 2;
    sortedLayerNodes.forEach((node, index) => {
      const isFocus = focusNodeIds.has(node.id);
      nodes.push({
        id: node.id,
        type: "default",
        position: {
          x: relationshipLayerX[layer],
          y: index * layerGap - centerOffset
        },
        data: {
          label: relationshipFlowNodeLabel(graph, node, labelObjectType, labelSourceValidationStatus)
        },
        className: [
          "graph-flow-node",
          `graph-flow-node-${node.type.replace(/_/g, "-")}`,
        ].filter(Boolean).join(" "),
        sourcePosition: Position.Right,
        targetPosition: Position.Left
      });
    });
  });

  const nodeIds = new Set(graph.nodes.map((node) => node.id));
  const edges: FlowEdge[] = graph.edges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => {
      const visualDirection = relationshipVisualEdgeDirection(edge);
      return {
        id: edge.id,
        source: visualDirection.source,
        target: visualDirection.target,
        label: edge.label,
        type: "bezier",
        markerEnd: { type: MarkerType.ArrowClosed },
        className: `graph-flow-edge graph-flow-edge-${edge.type.toLocaleLowerCase().replace(/_/g, "-")}`
      };
    });

  return { nodes, edges };
}

export default function RelationshipFlowCanvas({
  graph,
  labelObjectType,
  labelSourceValidationStatus,
  selectedEdgeId,
  selectedNodeId,
  onEdgeSelect,
  onNodeSelect
}: RelationshipFlowCanvasProps) {
  const flowElements = useMemo(
    () => buildRelationshipFlowElements(graph, labelObjectType, labelSourceValidationStatus),
    [graph, labelObjectType, labelSourceValidationStatus]
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(flowElements.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowElements.edges);

  useEffect(() => {
    setNodes(flowElements.nodes);
    setEdges(flowElements.edges);
  }, [flowElements, setEdges, setNodes]);

  const selectableNodes = nodes.map((node) => ({
    ...node,
    selected: node.id === selectedNodeId
  }));
  const selectableEdges = edges.map((edge) => ({
    ...edge,
    selected: edge.id === selectedEdgeId
  }));
  return (
    <div className="relationship-flow-canvas" aria-label="Kapcsolati térkép vizuális nézete">
      <ReactFlow
        nodes={selectableNodes}
        edges={selectableEdges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable
        nodesConnectable={false}
        edgesReconnectable={false}
        elementsSelectable
        minZoom={0.25}
        maxZoom={1.5}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onEdgeClick={(_, edge) => onEdgeSelect?.(edge.id)}
        onNodeClick={(_, node) => onNodeSelect?.(node.id)}
      >
        <Background gap={18} size={1} />
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
