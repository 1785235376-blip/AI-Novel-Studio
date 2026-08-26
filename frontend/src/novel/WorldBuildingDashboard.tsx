import { useMemo, useState } from "react";
import { AlertTriangle, GitBranch, ListTree, MapPin } from "lucide-react";
import { Badge, Button, EmptyState, Spinner, StatusMessage } from "../ui/primitives";
import type { StoryDatabaseKind } from "./StoryDatabase";
import { WorldRelationshipGraph } from "./WorldRelationshipGraph";
import { WorldTimelineView } from "./WorldTimelineView";
import "./WorldBuildingDashboard.css";

type RecordValue = Record<string, unknown>;
type DashboardView = "relationships" | "timeline" | "foreshadowing";

export type WorldBuildingDashboardProps = {
  characters?: RecordValue[];
  relationships?: RecordValue[];
  timeline?: RecordValue[];
  foreshadowing?: RecordValue[];
  locations?: RecordValue[];
  chapters?: RecordValue[];
  loading?: boolean;
  errors?: Partial<Record<DashboardView, string>>;
  onOpen: (kind: StoryDatabaseKind, id?: string) => void;
};

const viewLabels: Record<DashboardView, string> = {
  relationships: "角色关系",
  timeline: "故事时间线",
  foreshadowing: "伏笔追踪",
};

const text = (value: unknown, fallback = "未填写") => typeof value === "string" && value.trim() ? value : fallback;
const ids = (value: unknown) => Array.isArray(value) ? value.map(String) : [];

export function WorldBuildingDashboard({
  characters = [], relationships = [], timeline = [], foreshadowing = [], locations = [], chapters = [], loading = false, errors = {}, onOpen,
}: WorldBuildingDashboardProps) {
  const [view, setView] = useState<DashboardView>("relationships");
  const characterNames = useMemo(() => new Map(characters.map((item) => [String(item.id), text(item.name || item.title, String(item.id))])), [characters]);
  const locationNames = useMemo(() => new Map(locations.map((item) => [String(item.id), text(item.name || item.title, String(item.id))])), [locations]);
  const eventNames = useMemo(() => new Map(timeline.map((item) => [String(item.id), text(item.title || item.event, String(item.id))])), [timeline]);
  const orderedTimeline = useMemo(() => [...timeline].sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0)), [timeline]);
  const activeRows = view === "relationships" ? relationships : view === "timeline" ? orderedTimeline : foreshadowing;

  return (
    <section className="world-dashboard" aria-labelledby="world-dashboard-title">
      <header className="world-dashboard__header">
        <div><h3 id="world-dashboard-title">世界观总览</h3><p>从已保存的故事资料查看人物网络、事件顺序与伏笔状态。</p></div>
        <Button variant="ghost" type="button" onClick={() => onOpen(view)}>打开{viewLabels[view]}编辑</Button>
      </header>
      <div className="world-dashboard__tabs" role="tablist" aria-label="世界观视图">
        {(Object.keys(viewLabels) as DashboardView[]).map((item) => (
          <button key={item} role="tab" aria-selected={view === item} onClick={() => setView(item)}>
            {item === "relationships" ? <GitBranch aria-hidden="true" /> : item === "timeline" ? <ListTree aria-hidden="true" /> : <MapPin aria-hidden="true" />}
            <span>{viewLabels[item]}</span>
            <Badge tone="neutral">{item === "relationships" ? relationships.length : item === "timeline" ? timeline.length : foreshadowing.length}</Badge>
          </button>
        ))}
      </div>
      {loading ? <div className="world-dashboard__loading" role="status"><Spinner size="sm" />正在读取世界观资料…</div> : errors[view] ? (
        <StatusMessage tone="error"><div className="world-dashboard__error"><span><AlertTriangle aria-hidden="true" />{errors[view]}</span><Button type="button" onClick={() => onOpen(view)}>前往{viewLabels[view]}</Button></div></StatusMessage>
      ) : !activeRows.length ? (
        <EmptyState title={`还没有${viewLabels[view]}数据`} detail={`前往“${viewLabels[view]}”录入真实资料后，这里会自动形成总览。`} />
      ) : view === "relationships" ? (
        <>
        <WorldRelationshipGraph characters={characters} relationships={relationships} timeline={timeline} onOpen={onOpen} />
        <div className="world-dashboard__network" role="list" aria-label="角色关系图">
          {relationships.map((item) => (
            <button key={String(item.id)} role="listitem" type="button" onClick={() => onOpen("relationships", String(item.id))}>
              <span className="world-dashboard__person">{characterNames.get(String(item.source_character_id)) || text(item.source_character_id, "未知角色")}</span>
              <span className="world-dashboard__relation"><span>{text(item.relationship_type || item.type, "关系")}</span><i aria-hidden="true" /></span>
              <span className="world-dashboard__person">{characterNames.get(String(item.target_character_id)) || text(item.target_character_id, "未知角色")}</span>
              <small>{text(item.description, "未填写关系说明")}{item.valid_from_event_id ? ` · 起于 ${eventNames.get(String(item.valid_from_event_id)) || String(item.valid_from_event_id)}` : ""}</small>
              {Boolean(item.status) && <Badge tone={item.status === "ACTIVE" ? "success" : "neutral"}>{String(item.status)}</Badge>}
            </button>
          ))}
        </div>
        </>
      ) : view === "timeline" ? (
        <WorldTimelineView timeline={orderedTimeline} characters={characters} locations={locations} chapters={chapters} onOpen={(kind, id) => onOpen(kind, id)} />
      ) : (
        <div className="world-dashboard__threads" role="list">
          {foreshadowing.map((item) => {
            const relatedCharacters = ids(item.characters).map((id) => characterNames.get(id) || id);
            const relatedEvents = ids(item.events).map((id) => eventNames.get(id) || id);
            const resolved = ["PAID_OFF", "RESOLVED"].includes(String(item.status));
            return <button key={String(item.id)} role="listitem" type="button" onClick={() => onOpen("foreshadowing", String(item.id))}>
              <span><strong>{text(item.title, "未命名伏笔")}</strong><Badge tone={resolved ? "success" : "warning"}>{resolved ? "已解决" : text(item.status, "进行中")}</Badge></span>
              <p>{text(item.description, "未填写伏笔说明")}</p>
              <dl><div><dt>首次出现</dt><dd>{item.planted_chapter ? `第 ${item.planted_chapter} 章` : "未记录"}</dd></div><div><dt>目标章节</dt><dd>{item.target_chapter ? `第 ${item.target_chapter} 章` : "未设置"}</dd></div><div><dt>关联角色</dt><dd>{relatedCharacters.length ? relatedCharacters.join("、") : "无"}</dd></div><div><dt>关联事件</dt><dd>{relatedEvents.length ? relatedEvents.join("、") : "无"}</dd></div></dl>
            </button>;
          })}
        </div>
      )}
    </section>
  );
}
