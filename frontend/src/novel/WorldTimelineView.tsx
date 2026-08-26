import { useMemo, useState } from "react";
import { AlertTriangle, BookOpen, CalendarClock, Clock3, MapPin, Users } from "lucide-react";
import { Badge, EmptyState } from "../ui/primitives";
import "./WorldTimelineView.css";

type StoryRecord = Record<string, unknown>;

export type WorldTimelineViewProps = {
  timeline?: StoryRecord[];
  characters?: StoryRecord[];
  locations?: StoryRecord[];
  chapters?: StoryRecord[];
  onOpen: (kind: "timeline", id: string) => void;
};

const value = (record: StoryRecord, keys: string[]) => {
  for (const key of keys) {
    const candidate = record[key];
    if (candidate !== undefined && candidate !== null && String(candidate).trim()) return String(candidate);
  }
  return "";
};

const referenceId = (record: StoryRecord) => value(record, ["id", "character_id", "location_id", "chapter_id"]);
const referenceLabel = (record: StoryRecord) => value(record, ["name", "title", "label"]) || referenceId(record);

const ids = (input: unknown) => {
  if (Array.isArray(input)) return input.map((item) => String(item)).filter(Boolean);
  if (typeof input === "string") return input.split(/[,，、]/).map((item) => item.trim()).filter(Boolean);
  return [];
};

const statusText = (status: string) => status || "未标记";

const statusTone = (status: string): "neutral" | "info" | "success" | "warning" | "error" => {
  const normalized = status.toUpperCase();
  if (normalized === "DISPUTED") return "warning";
  if (["CONFIRMED", "COMPLETED", "RESOLVED", "APPROVED"].includes(normalized)) return "success";
  if (["PLANNED", "DRAFT", "PENDING"].includes(normalized)) return "info";
  if (["FAILED", "ERROR"].includes(normalized)) return "error";
  return "neutral";
};

type TimelineEvent = {
  id: string;
  sequence: string;
  sequenceNumber: number;
  title: string;
  time: string;
  description: string;
  location: string;
  characters: string[];
  chapterId: string;
  chapterLabel: string;
  status: string;
  sourceIndex: number;
};

export function WorldTimelineView({ timeline = [], characters = [], locations = [], chapters = [], onOpen }: WorldTimelineViewProps) {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const characterNames = useMemo(() => new Map(characters.map((item) => [referenceId(item), referenceLabel(item)])), [characters]);
  const locationNames = useMemo(() => new Map(locations.map((item) => [referenceId(item), referenceLabel(item)])), [locations]);
  const chapterNames = useMemo(() => new Map(chapters.map((item) => [referenceId(item), referenceLabel(item)])), [chapters]);

  const events = useMemo<TimelineEvent[]>(() => timeline.map((item, sourceIndex) => {
    const locationId = value(item, ["location", "location_id"]);
    const characterIds = ids(item.characters ?? item.character_ids ?? item.characterIds ?? item.character_id);
    const chapterId = value(item, ["chapter_id", "chapterId"]);
    const sequence = value(item, ["sequence", "order", "position"]);
    const sequenceNumber = Number(sequence);
    return {
      id: value(item, ["id", "timeline_id"]),
      sequence: sequence || "未设置",
      sequenceNumber: Number.isFinite(sequenceNumber) ? sequenceNumber : Number.POSITIVE_INFINITY,
      title: value(item, ["title", "event", "name"]) || "未命名事件",
      time: value(item, ["time", "story_time", "date"]) || "未填写故事时间",
      description: value(item, ["description", "summary", "notes"]) || "未填写事件描述",
      location: locationNames.get(locationId) || locationId || "未关联地点",
      characters: characterIds.map((id) => characterNames.get(id) || id),
      chapterId: chapterId || "未关联章节",
      chapterLabel: chapterNames.get(chapterId) || chapterId || "未关联章节",
      status: value(item, ["status", "state"]),
      sourceIndex,
    };
  }).sort((a, b) => a.sequenceNumber - b.sequenceNumber || a.sourceIndex - b.sourceIndex), [timeline, characterNames, locationNames, chapterNames]);

  const statuses = useMemo(() => events.reduce<string[]>((result, event) => {
    if (event.status && !result.includes(event.status)) result.push(event.status);
    return result;
  }, []), [events]);
  const visibleEvents = statusFilter === "ALL" ? events : events.filter((event) => event.status === statusFilter);

  return <section className="world-timeline" aria-labelledby="world-timeline-title">
    <header className="world-timeline__header">
      <div>
        <h2 id="world-timeline-title">故事时间线</h2>
        <p>按事件顺序查看已保存的故事时间、关联对象与连续性状态。</p>
      </div>
      <Badge tone="neutral">{visibleEvents.length} / {events.length} 条事件</Badge>
    </header>
    {events.length > 0 && <div className="world-timeline__toolbar">
      <label htmlFor="world-timeline-status">状态筛选</label>
      <select id="world-timeline-status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
        <option value="ALL">全部状态</option>
        {statuses.map((status) => <option key={status} value={status}>{statusText(status)}</option>)}
      </select>
      {statusFilter !== "ALL" && <span role="status">当前显示“{statusText(statusFilter)}”事件</span>}
    </div>}
    {events.length === 0 ? <EmptyState title="还没有时间线事件" detail="保存真实的时间线事件后，这里会按顺序展示故事发展。" /> : visibleEvents.length === 0 ? (
      <EmptyState title="没有符合筛选的事件" detail="切换到“全部状态”以查看完整时间线。" />
    ) : <ol className="world-timeline__list" aria-label="故事时间线事件">
      {visibleEvents.map((event) => {
        const disputed = event.status.toUpperCase() === "DISPUTED";
        const content = <>
          <span className="world-timeline__event-header">
            <span className="world-timeline__sequence" aria-label={`顺序 ${event.sequence}`}>{event.sequence}</span>
            <strong>{event.title}</strong>
            {disputed && <span className="world-timeline__conflict"><AlertTriangle aria-hidden="true" />冲突待核实</span>}
            <Badge tone={statusTone(event.status)}>{statusText(event.status)}</Badge>
          </span>
          <span className="world-timeline__description">{event.description}</span>
          <span className="world-timeline__meta">
            <span><Clock3 aria-hidden="true" />故事时间：{event.time}</span>
            <span><MapPin aria-hidden="true" />地点：{event.location}</span>
            <span><Users aria-hidden="true" />角色：{event.characters.length ? event.characters.join("、") : "未关联角色"}</span>
            <span><BookOpen aria-hidden="true" />chapter_id：{event.chapterId === "未关联章节" ? event.chapterId : `${event.chapterLabel}（${event.chapterId}）`}</span>
          </span>
        </>;
        return <li key={`${event.id || "event"}-${event.sourceIndex}`} className={disputed ? "world-timeline__item world-timeline__item--disputed" : "world-timeline__item"}>
          {event.id ? <button type="button" onClick={() => onOpen("timeline", event.id)} aria-label={`打开时间线事件：${event.title}`}>{content}<CalendarClock aria-hidden="true" className="world-timeline__open-icon" /></button> : <div className="world-timeline__static-event">{content}</div>}
        </li>;
      })}
    </ol>}
  </section>;
}
