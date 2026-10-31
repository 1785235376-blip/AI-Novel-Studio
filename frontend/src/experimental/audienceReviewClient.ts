import type { ExperimentalClient } from './api';
import type { JudgeEvidence, JudgeFinding, JudgeReviewInput, JudgeRun, ReviewChapter } from './styleReviewClient';

export type AudienceProfile = {
  name: string;
  genre_experience: 'NOVICE' | 'FAMILIAR' | 'EXPERIENCED';
  target_age_group: 'GENERAL' | 'CHILDREN' | 'TEENS' | 'ADULTS';
  language_habit: string;
  reading_speed: number;
};
export type AudienceComparison = 'DIFFERENT_ADVICE' | 'AGREEMENT' | 'NOT_ASSESSED';
export type AudienceSource = { chapter_id: string; chapter_version: number; source_digest: string; paragraphs: Omit<JudgeEvidence, 'chapter_id' | 'chapter_version'>[]; unsupported_paragraphs?: number };
export type AudienceFinding = Omit<JudgeFinding, 'origin'> & { origin: 'AUTHOR_ENTERED'; audience_profile_index: 0 | 1 };
export type AudienceRun = Omit<JudgeRun, 'findings'> & {
  findings: AudienceFinding[];
  audience?: {
    profiles: (AudienceProfile & { digest: string; schema_version: number })[];
    measurements: { profile_index: 0 | 1; nonspace_characters: number; estimated_seconds: number }[];
    comparison: AudienceComparison;
    chapter_id: string;
    chapter_version: number;
  };
};
export type AudienceInput = {
  chapter_id: string;
  expected_version: number;
  expected_source_digest: string;
  profiles: [AudienceProfile, AudienceProfile];
  observations: { profile_index: 0 | 1; evidence: JudgeEvidence; observation: string; suggestion: string }[];
  comparison: AudienceComparison;
};
export function audienceReviewClient(client: ExperimentalClient) {
  const base = '/narrative-judge/audience';
  return {
    catalog: (signal?: AbortSignal) => client.get<{ chapters: ReviewChapter[]; profiles: AudienceProfile[] }>(`${base}/catalog`, signal),
    source: (chapterId: string, version: number, signal?: AbortSignal) => client.get<AudienceSource>(`${base}/source/${encodeURIComponent(chapterId)}?expected_version=${version}`, signal),
    prepareSource: (chapterId: string, version: number) => client.post<AudienceSource>(`${base}/source/${encodeURIComponent(chapterId)}/prepare`, { expected_version: version }),
    comparisons: (signal?: AbortSignal) => client.get<{ items: AudienceRun[] }>(`${base}/comparisons`, signal),
    create: (body: AudienceInput) => client.post<AudienceRun>(`${base}/comparisons`, body),
    review: (id: string, body: JudgeReviewInput) => client.post<AudienceFinding>(`/narrative-judge/findings/${encodeURIComponent(id)}/review`, body),
  };
}
export type AudienceReviewClient = ReturnType<typeof audienceReviewClient>;
