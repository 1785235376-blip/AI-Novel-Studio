# Database Schema

`novels` 是多小说根；characters/locations/organizations/canon_entries/story_states/timeline_events/foreshadowing/secrets 全部带 novel_id。chapters 指向 Markdown，chapter_summaries 保存长期压缩记忆，pending_canon 隔离模型提案，canon_revisions 保留审计历史，cloud_requests 仅存 metadata、usage、cost 和 prompt hash。

