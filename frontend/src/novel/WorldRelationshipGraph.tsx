import { useMemo, useRef } from "react";
import { Badge, EmptyState } from "../ui/primitives";
import "./WorldRelationshipGraph.css";

type StoryRecord = Record<string, unknown>;
type OpenKind = "characters" | "relationships" | "timeline";

export type WorldRelationshipGraphProps = {
  characters?: StoryRecord[];
  relationships?: StoryRecord[];
  timeline?: StoryRecord[];
  onOpen: (kind: OpenKind, id: string) => void;
};

type CharacterNode = { id: string; name: string; role: string; status: string; x: number; y: number };
type RelationshipEdge = {
  id: string; sourceId: string; targetId: string; type: string; description: string;
  status: string; certainty: string; eventIds: string[];
};

const value = (record: StoryRecord, keys: string[]) => {
  for (const key of keys) {
    const candidate = record[key];
    if (candidate !== undefined && candidate !== null && String(candidate).trim()) return String(candidate);
  }
  return "";
};

const relationshipTypeLabels: Record<string, string> = {
  FAMILY: "家族", FRIEND: "朋友", ENEMY: "敌对", MENTOR: "师徒",
  ROMANCE: "爱情", INTEREST: "利益", ALLY: "盟友", TRUSTS: "信任", OTHER: "其他",
};
const stateLabels: Record<string, string> = {
  ACTIVE: "有效", ENDED: "已结束", HIDDEN: "隐藏", ALIVE: "存活",
  MISSING: "失踪", DEAD: "死亡", UNKNOWN: "未知",
};
const labelType = (type: string) => relationshipTypeLabels[type.toUpperCase()] || type || "未标记关系";
const labelState = (status: string) => stateLabels[status.toUpperCase()] || status || "未标记";

export function WorldRelationshipGraph({ characters = [], relationships = [], timeline = [], onOpen }: WorldRelationshipGraphProps) {
  const nodeRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const graph = useMemo(() => {
    const eventNames = new Map(timeline.map((item) => [value(item, ["id", "event_id"]), value(item, ["title", "event", "name"]) || "未命名事件"]));
    const edges: RelationshipEdge[] = relationships.map((item, index) => {
      const from = value(item, ["source_character_id", "source_id", "from_character_id", "character_a_id"]);
      const to = value(item, ["target_character_id", "target_id", "to_character_id", "character_b_id"]);
      return {
        id: value(item, ["id"]) || `${from}-${to}-${index}`,
        sourceId: from,
        targetId: to,
        type: value(item, ["relationship_type", "type", "relation"]),
        description: value(item, ["description", "summary", "notes"]),
        status: value(item, ["status", "state"]),
        certainty: value(item, ["certainty"]),
        eventIds: [value(item, ["valid_from_event_id", "start_event_id"]), value(item, ["valid_to_event_id", "end_event_id"])].filter(Boolean),
      };
    }).filter((edge) => edge.sourceId || edge.targetId);
    const known = new Map(characters.map((item) => {
      const id = value(item, ["id", "character_id"]);
      return [id, { id, name: value(item, ["name", "title"]) || id, role: value(item, ["role", "archetype"]), status: value(item, ["status", "state"]) }];
    }).filter(([id]) => Boolean(id)) as Array<[string, Omit<CharacterNode, "x" | "y">]>);
    edges.forEach((edge) => {
      [edge.sourceId, edge.targetId].filter(Boolean).forEach((id) => {
        if (!known.has(id)) known.set(id, { id, name: id, role: "", status: "" });
      });
    });
    const baseNodes = [...known.values()];
    const nodes: CharacterNode[] = baseNodes.map((node, index) => {
      const angle = baseNodes.length === 1 ? 0 : (Math.PI * 2 * index) / baseNodes.length - Math.PI / 2;
      return { ...node, x: 50 + Math.cos(angle) * 35, y: 50 + Math.sin(angle) * 34 };
    });
    return { nodes, edges, names: new Map(nodes.map((node) => [node.id, node.name])), eventNames };
  }, [characters, relationships, timeline]);

  if (!graph.nodes.length && !graph.edges.length) {
    return <section className="world-relationship-graph"><EmptyState title="还没有角色关系" detail="保存角色和人物关系后，这里会显示真实的关系网络。" /></section>;
  }

  const moveNodeFocus = (index: number, direction: number) => {
    const next = (index + direction + graph.nodes.length) % graph.nodes.length;
    nodeRefs.current[next]?.focus();
  };

  return <section className="world-relationship-graph" aria-labelledby="relationship-graph-title">
    <header className="world-relationship-graph__header">
      <div><h3 id="relationship-graph-title">角色关系图</h3><p>查看已保存角色之间的关系、事件范围和当前状态。</p></div>
      <Badge tone="neutral">{graph.nodes.length} 人 · {graph.edges.length} 条关系</Badge>
    </header>
    <div className="world-relationship-graph__layout">
      <div className="world-relationship-graph__canvas" aria-label="角色关系几何视图">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {graph.edges.map((edge) => {
            const source = graph.nodes.find((node) => node.id === edge.sourceId);
            const target = graph.nodes.find((node) => node.id === edge.targetId);
            return source && target ? <line key={edge.id} x1={source.x} y1={source.y} x2={target.x} y2={target.y} /> : null;
          })}
        </svg>
        {graph.nodes.map((node, index) => <button
          key={node.id}
          ref={(element) => { nodeRefs.current[index] = element; }}
          className="world-relationship-graph__node"
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          type="button"
          aria-label={`${node.name}${node.role ? `，${node.role}` : ""}，状态：${labelState(node.status)}`}
          onClick={() => onOpen("characters", node.id)}
          onKeyDown={(event) => {
            if (["ArrowRight", "ArrowDown"].includes(event.key)) { event.preventDefault(); moveNodeFocus(index, 1); }
            if (["ArrowLeft", "ArrowUp"].includes(event.key)) { event.preventDefault(); moveNodeFocus(index, -1); }
          }}
        ><strong>{node.name}</strong>{node.role && <small>{node.role}</small>}<span>{labelState(node.status)}</span></button>)}
      </div>
      <div className="world-relationship-graph__adjacency">
        <h4>关系与关联事件</h4>
        {!graph.edges.length ? <p className="world-relationship-graph__empty">角色已建立，尚未保存人物关系。</p> : <ul aria-label="人物关系邻接列表">
          {graph.edges.map((edge) => <li key={edge.id}><button type="button" onClick={() => onOpen("relationships", edge.id)}>
            <span className="world-relationship-graph__edge-title"><strong>{graph.names.get(edge.sourceId) || edge.sourceId || "未知角色"}</strong><span>{labelType(edge.type)}</span><strong>{graph.names.get(edge.targetId) || edge.targetId || "未知角色"}</strong></span>
            <span className="world-relationship-graph__edge-meta"><Badge tone={edge.status.toUpperCase() === "ACTIVE" ? "success" : "neutral"}>{labelState(edge.status)}</Badge>{edge.certainty && <span>可信度：{edge.certainty}</span>}</span>
            {edge.description && <span className="world-relationship-graph__description">{edge.description}</span>}
            {edge.eventIds.length > 0 && <span className="world-relationship-graph__events">关联事件：{edge.eventIds.map((id) => graph.eventNames.get(id) || id).join(" → ")}</span>}
          </button></li>)}
        </ul>}
      </div>
    </div>
  </section>;
}
