// [HERMIA-FE-CONTRACTS G-AUD-5] Backend semantics:
// POST /studio/assets/{id}/restore is UNDELETE (version increments), not a rollback; only Timeline has version history.
// [HERMIA-FE-20261025 MERGE-FEC i18n] getters resolve through i18n at read time (zh default unchanged; en available).
import { t } from '../../i18n';
export const AUDIO_HISTORY_TEXT = {
  get assetRestore() { return t('fc.aud.assetRestore'); },
  get assetRestoreHint() { return t('fc.aud.assetRestoreHint'); },
  get timelineOnly() { return t('fc.aud.timelineOnly'); },
  get assetHistory() { return t('fc.aud.assetHistory'); },
};
