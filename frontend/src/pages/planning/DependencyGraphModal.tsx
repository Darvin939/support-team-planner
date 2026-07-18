import {useCallback, useEffect, useMemo, useRef} from 'react';
import {
  Background,
  BaseEdge,
  type Connection,
  type Edge,
  EdgeLabelRenderer,
  type EdgeProps,
  getBezierPath,
  Handle,
  MarkerType,
  type Node,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  useUpdateNodeInternals,
} from '@xyflow/react';
import dagre from 'dagre';
import {Empty, message, Modal, Spin, theme} from 'antd';
import {PlusOutlined} from '@ant-design/icons';
import '@xyflow/react/dist/style.css';
import {
  type DependencyGraphNode,
  useAddTaskDependency,
  useDependencyGraph,
  useRemoveTaskDependency,
} from '../../hooks/usePlanningData';
import {CriticalityBadge} from '../../components/planningBadges';

const NODE_WIDTH = 260;
// Оценка высоты узла для раскладки dagre — с запасом под 5-6 строк переносимого описания
// (реальный DOM-узел может быть чуть выше при исключительно длинном описании, тогда его
// css `overflowY: auto` не даёт ему наехать на соседний узел того же ранга).
const NODE_HEIGHT = 190;

interface GraphNodeData extends Record<string, unknown> {
  name: string;
  description: string | null;
  task_status: string;
  criticality: string;
  segment_name: string;
  isFocal: boolean;
  onHandlePointerDown: () => void;
}

const handleStyle = (token: ReturnType<typeof theme.useToken>['token']): React.CSSProperties => ({
  width: 16,
  height: 16,
  background: token.colorBgContainer,
  border: `1.5px solid ${token.colorPrimary}`,
  color: token.colorPrimary,
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 8,
});

function TaskGraphNode({ id, data, selected }: { id: string; data: GraphNodeData; selected?: boolean }) {
  const { token } = theme.useToken();
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => {
    // Forces xyflow to re-measure this node's handle bounds right after mount. Under React
    // StrictMode's double-invoked effects (dev only), the handle-bounds registration that
    // xyflow's own internals do on mount can end up stale for a node — the store still reports
    // correct node.position/measured size (confirmed via inspection), but connected edges get
    // computed from the wrong handle bounds regardless, landing far from the visible "+" circles
    // until something forces a fresh registration. Deferred a frame so it runs *after* xyflow's
    // own internal post-mount measurement pass, not racing against/getting clobbered by it —
    // calling it synchronously in the effect body wasn't enough to win that race.
    const t = setTimeout(() => updateNodeInternals(id), 300);
    return () => clearTimeout(t);
  }, [id, updateNodeInternals]);
  const borderColor =
    data.task_status === 'done'
      ? token.colorSuccess
      : data.task_status === 'cancelled'
        ? token.colorError
        : selected
          ? token.colorPrimary
          : token.colorBorder;
  return (
    <div
      data-graph-node-id={id}
      style={{
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        position: 'relative',
        borderRadius: 14,
        border: `1.5px solid ${borderColor}`,
        background: token.colorBgContainer,
        boxShadow: data.isFocal
          ? `0 0 0 3px ${token.colorPrimaryBg}, 0 0 0 1.5px ${token.colorPrimary}, ${token.boxShadowTertiary}`
          : token.boxShadowTertiary,
        cursor: 'pointer',
      }}
    >
      {/* Handles must be direct children of this position:relative box (not nested inside the
          scrollable content div below) — xyflow positions/measures them relative to the nearest
          positioned ancestor, and a scrolling descendant is a documented anti-pattern for hit-testing. */}
      <Handle
        type="target"
        position={Position.Left}
        style={handleStyle(token)}
        onMouseDownCapture={data.onHandlePointerDown}
      >
        <PlusOutlined />
      </Handle>
      <Handle
        type="source"
        position={Position.Right}
        style={handleStyle(token)}
        onMouseDownCapture={data.onHandlePointerDown}
      >
        <PlusOutlined />
      </Handle>
      <div style={{ height: '100%', overflowY: 'auto', padding: '10px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <CriticalityBadge value={data.criticality} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <span data-graph-node-name style={{ display: 'block', fontWeight: 500, overflowWrap: 'anywhere' }}>
              {data.name}
            </span>
            <div
              data-graph-node-segment
              title={`Сегмент: ${data.segment_name}`}
              style={{
                marginTop: 2,
                color: token.colorTextTertiary,
                fontSize: '0.72rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              Сегмент: {data.segment_name}
            </div>
          </div>
        </div>
        {data.description && (
          <div
            data-graph-node-description
            style={{
              marginTop: 4,
              padding: '5px 8px',
              border: `1px solid ${token.colorBorder}`,
              borderRadius: 2,
              background: token.colorFillTertiary,
              fontSize: '0.85rem',
              color: token.colorTextSecondary,
              whiteSpace: 'pre-wrap',
              overflowWrap: 'anywhere',
            }}
          >
            {data.description}
          </div>
        )}
      </div>
    </div>
  );
}

const nodeTypes = { task: TaskGraphNode };

interface DependencyEdgeData extends Record<string, unknown> {
  onDelete: (taskId: number, depId: number) => void;
  taskId: number;
  depId: number;
}

function DependencyEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, selected, markerEnd, data }: EdgeProps<Edge<DependencyEdgeData>>) {
  const { token } = theme.useToken();
  const [edgePath, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  const stroke = selected ? token.colorPrimary : token.colorTextTertiary;
  const strokeWidth = selected ? 3.5 : 2;
  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke,
          strokeWidth,
          filter: selected ? `drop-shadow(0 0 4px ${token.colorPrimary})` : undefined,
        }}
      />
      {selected && data && (
        <EdgeLabelRenderer>
          <button
            className="nodrag nopan"
            onClick={() => data.onDelete(data.taskId, data.depId)}
            title="Удалить связь"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
              width: 20,
              height: 20,
              borderRadius: '50%',
              border: `1.5px solid ${token.colorError}`,
              background: token.colorBgContainer,
              color: token.colorError,
              fontSize: 12,
              lineHeight: 1,
              cursor: 'pointer',
            }}
          >
            ×
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const edgeTypes = { dependency: DependencyEdge };

function layout(
  nodes: DependencyGraphNode[],
  edges: { task_id: number; dep_id: number }[],
  onDeleteEdge: (taskId: number, depId: number) => void,
  onHandlePointerDown: () => void,
  focalTaskId?: number
) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'LR', nodesep: 56, ranksep: 130, ranker: 'longest-path' });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(String(n.id), { width: NODE_WIDTH, height: NODE_HEIGHT }));
  // Ребро "task зависит от dep" рисуем dep -> task, чтобы граф читался слева направо в
  // порядке выполнения (сначала зависимость, потом зависящая от неё задача).
  edges.forEach((e) => g.setEdge(String(e.dep_id), String(e.task_id)));
  dagre.layout(g);

  const rfNodes: Node<GraphNodeData>[] = nodes.map((n) => {
    const pos = g.node(String(n.id));
    return {
      id: String(n.id),
      type: 'task',
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        name: n.name,
        description: n.description,
        task_status: n.task_status,
        criticality: n.criticality,
        segment_name: n.segment_name,
        isFocal: n.id === focalTaskId,
        onHandlePointerDown,
      },
    };
  });
  const rfEdges: Edge<DependencyEdgeData>[] = edges.map((e) => ({
    id: `${e.dep_id}-${e.task_id}`,
    source: String(e.dep_id),
    target: String(e.task_id),
    type: 'dependency',
    reconnectable: true,
    markerEnd: { type: MarkerType.ArrowClosed },
    data: { onDelete: onDeleteEdge, taskId: e.task_id, depId: e.dep_id },
  }));
  return { rfNodes, rfEdges };
}

export function DependencyGraphModal({
  open,
  teamId,
  taskId,
  onClose,
  onNavigate,
}: {
  open: boolean;
  teamId: number | undefined;
  taskId?: number;
  onClose: () => void;
  onNavigate: (taskId: number) => void;
}) {
  const { data, isLoading } = useDependencyGraph(teamId ?? 0, open, taskId);
  const addDependency = useAddTaskDependency();
  const removeDependency = useRemoveTaskDependency();

  // Kept referentially stable (empty dep array, reads the latest mutation via a ref) so it doesn't
  // invalidate the rfNodes/rfEdges useMemo below on every render — react-query's mutation object
  // gets a new identity each render, and including it directly in that memo's deps would recompute
  // a fresh edges array every render, which would re-trigger the sync effect in an infinite loop.
  const removeDependencyRef = useRef(removeDependency);
  removeDependencyRef.current = removeDependency;
  const handleDeleteEdge = useCallback((dependentTaskId: number, dependsOnTaskId: number) => {
    removeDependencyRef.current.mutate(
      { task_id: dependentTaskId, depends_on_task_id: dependsOnTaskId },
      { onError: (e: Error) => message.error(e.message) }
    );
  }, []);

  // xyflow never suppresses the native `click` that follows a connect/reconnect gesture's mouseup, so
  // releasing a new/reconnected connection over a node's body would otherwise also fire onNodeClick and
  // pop TaskModal open. A plain, zero-movement mousedown+mouseup *on the handle itself* doesn't even
  // reach xyflow's onConnectStart/onConnectEnd (those only fire once the drag exceeds a small movement
  // threshold), so the guard is set directly from each Handle's onMouseDownCapture (via node data,
  // see layout()) rather than solely from onConnectStart — that covers both a real drag and a plain
  // click on the "+" circle. Cleared on the next global mouseup (whatever/wherever it lands), deferred
  // one tick so it's still true when the browser's own trailing `click` event is checked.
  const suppressNodeClickRef = useRef(false);
  const suppressNodeClickUntilMouseUp = useCallback(() => {
    suppressNodeClickRef.current = true;
    const clear = () => {
      window.removeEventListener('mouseup', clear);
      setTimeout(() => {
        suppressNodeClickRef.current = false;
      }, 0);
    };
    window.addEventListener('mouseup', clear);
  }, []);

  const { rfNodes, rfEdges } = useMemo(() => {
    if (!data) return { rfNodes: [], rfEdges: [] };
    return layout(data.nodes, data.edges, handleDeleteEdge, suppressNodeClickUntilMouseUp, taskId);
  }, [data, handleDeleteEdge, suppressNodeClickUntilMouseUp, taskId]);

  // useNodesState/useEdgesState (not the raw layout() output passed straight through) is required
  // for @xyflow/react to apply its own selection/interaction changes — passing plain arrays with no
  // onNodesChange/onEdgesChange makes the canvas fully read-only (clicking an edge would never be
  // able to set `selected`, since nothing ever applies that change back).
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<GraphNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<DependencyEdgeData>>([]);
  useEffect(() => {
    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [rfNodes, rfEdges, setNodes, setEdges]);

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      addDependency.mutate(
        { task_id: Number(connection.target), depends_on_task_id: Number(connection.source) },
        { onError: (e: Error) => message.error(e.message) }
      );
    },
    [addDependency]
  );

  const handleReconnect = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (!newConnection.source || !newConnection.target) return;
      addDependency.mutate(
        { task_id: Number(newConnection.target), depends_on_task_id: Number(newConnection.source) },
        {
          onSuccess: () =>
            removeDependency.mutate({ task_id: Number(oldEdge.target), depends_on_task_id: Number(oldEdge.source) }),
          onError: (e: Error) => message.error(e.message),
        }
      );
    },
    [addDependency, removeDependency]
  );

  const focalTask = taskId ? data?.nodes.find((n) => n.id === taskId) : undefined;
  const isEmpty = (data?.nodes.length ?? 0) === 0 || (taskId !== undefined && (data?.edges.length ?? 0) === 0);

  return (
    <Modal
      title={focalTask ? `Граф зависимостей — ${focalTask.name}` : 'Граф зависимостей'}
      open={open}
      onCancel={onClose}
      footer={null}
      width="100vw"
      style={{ top: 0, maxWidth: '100vw', paddingBottom: 0 }}
      styles={{ body: { height: 'calc(100vh - 110px)', padding: 0 } }}
    >
      {isLoading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <Spin size="large" />
        </div>
      ) : isEmpty ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <Empty description={taskId !== undefined ? 'У работы нет зависимостей' : 'В команде нет задач'} />
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          nodesDraggable
          nodesConnectable
          onConnect={handleConnect}
          onReconnect={handleReconnect}
          onReconnectStart={suppressNodeClickUntilMouseUp}
          onNodeClick={(_, node) => {
            if (suppressNodeClickRef.current) return;
            onNavigate(Number(node.id));
          }}
        >
          <Background />
        </ReactFlow>
      )}
    </Modal>
  );
}
