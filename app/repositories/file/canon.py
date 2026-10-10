from __future__ import annotations
from copy import deepcopy
import json
from ...repository import FileRepository, read_json
from ...storage import atomic_write, append_pending
from ...privacy import privacy_record
from ...file_project_lifecycle import project_operation


class FileCanonRepository:
    def __init__(self, backend: FileRepository): self.backend = backend

    @staticmethod
    def _safe_id(pending_id):
        if not isinstance(pending_id, str) or not pending_id or pending_id in {'.', '..'} or any(x in pending_id for x in ('/', '\\', '\x00', ':')):
            raise FileNotFoundError(pending_id)

    def list(self, novel_id):
        with project_operation(self.backend.data, novel_id):
            return [privacy_record(row) for row in read_json(self.backend.novels / novel_id / 'canon.json', [])]

    def _find(self, pending_id):
        self._safe_id(pending_id)
        for root in self.backend.novels.iterdir():
            path = root / 'pending_canon' / f'{pending_id}.json'
            if path.exists(): return root, path, read_json(path, {})
        raise FileNotFoundError(pending_id)

    def _project_pending(self, nid, pid):
        self._safe_id(pid)
        path = self.backend.novels / nid / 'pending_canon' / f'{pid}.json'
        item = read_json(path, None)
        if item is None or item.get('novel_id') != nid: raise FileNotFoundError(pid)
        return path, item

    def list_pending(self, novel_id):
        with project_operation(self.backend.data, novel_id):
            root = self.backend.novels / novel_id / 'pending_canon'
            return [item for p in root.glob('*.json') if (item := read_json(p, {})).get('status') == 'PENDING']

    def get_pending(self, pending_id): return self._find(pending_id)[2]

    def save_pending(self, item):
        item = {"status": "PENDING", **item}
        if 'id' not in item: raise ValueError('pending canon id is required')
        self._safe_id(item['id'])
        with project_operation(self.backend.data, item['novel_id']):
            root = self.backend.novels / item['novel_id']
            old = read_json(root / 'pending_canon' / f"{item['id']}.json", {})
            if old.get("status") in {"APPROVED", "REJECTED"}:
                if old.get("proposals") != item.get("proposals"): raise ValueError("CANON_TERMINAL_EDIT_FORBIDDEN")
                return old
            self._legacy_guard(old)
            append_pending(root, item)
            return item

    @staticmethod
    def _legacy_guard(item):
        if item.get('review_owner') or item.get('_review_commit'):
            raise ValueError('VERSIONED_CANON_REVIEW_REQUIRED')

    def approve(self, pending_id, proposals=None):
        from ...services.finding_review_service import digest
        root, _, _ = self._find(pending_id)
        with project_operation(self.backend.data, root.name):
            _, _, old = self._find(pending_id)
            if old.get('review_owner'): raise ValueError('VERSIONED_CANON_REVIEW_REQUIRED')
            selected = deepcopy(proposals if proposals is not None else old.get('proposals', []))
            if old.get('status', 'PENDING') == 'APPROVED':
                if selected != old.get('proposals', []): raise ValueError('CANON_TERMINAL_EDIT_FORBIDDEN')
                return old
            if old.get('status', 'PENDING') != 'PENDING': raise ValueError('CANON_ALREADY_REVIEWED')
            fingerprint = digest({'id': pending_id, 'proposals': selected})
            def decide(row):
                if row.get('status', 'PENDING') != 'PENDING': raise ValueError('CANON_ALREADY_REVIEWED')
                row.update(proposals=selected, status='APPROVED')
                return row, True
            return self.review_pending_atomic(root.name, pending_id, 'legacy-approve-' + fingerprint,
                                              fingerprint, decide, lambda: None)

    def reject(self, pending_id):
        root, _, _ = self._find(pending_id)
        with project_operation(self.backend.data, root.name):
            _, path, item = self._find(pending_id)
            self._legacy_guard(item)
            if item.get('status', 'PENDING') == 'REJECTED': return item
            if item.get('status', 'PENDING') != 'PENDING': raise ValueError('CANON_ALREADY_REVIEWED')
            item['status'] = 'REJECTED'; atomic_write(path, json.dumps(item, ensure_ascii=False, indent=2))
            return item

    def review_pending_atomic(self, nid, pid, operation_id, request_digest, callback, check):
        """Recoverable two-file commit; the intent stays in its original pending row.

        Canon replacement is atomic and additions have receipt identities. A lost
        response or process restart can replay bookkeeping without duplicate facts.
        """
        from ...services.finding_review_service import FindingReviewConflict, digest
        with project_operation(self.backend.data, nid):
            path, old = self._project_pending(nid, pid)
            canon_path = self.backend.novels / nid / 'canon.json'
            canonical = read_json(canon_path, [])
            journal = old.get('_review_commit')
            check()
            if journal:
                if journal['operation_id'] != operation_id or journal['request_digest'] != request_digest:
                    raise FindingReviewConflict('CANON_RECOVERY_REQUIRED')
                applied = {row.get('review_receipt') for row in canonical}
                if all(row['review_receipt'] in applied for row in journal['additions']):
                    # The authorized facts already committed. Only finalize the
                    # durable receipt; a newer chapter must not duplicate facts.
                    atomic_write(path, json.dumps(journal['result'], ensure_ascii=False, indent=2))
                    return deepcopy(journal['result'])
                original = {k: v for k, v in old.items() if k != '_review_commit'}
                callback(deepcopy(original))  # Current permission and source fence.
                result, additions = journal['result'], journal['additions']
            else:
                result, approve = callback(deepcopy(old))
                if result == old: return result
                additions = [{**privacy_record(p), 'source': f'pending:{pid}', 'confidence': 'USER_APPROVED',
                              'review_receipt': digest([pid, operation_id, i])}
                             for i, p in enumerate(result.get('proposals', []))] if approve else []
                journal = {'operation_id': operation_id, 'request_digest': request_digest,
                           'result': result, 'additions': additions}
                check()
                atomic_write(path, json.dumps({**old, '_review_commit': journal}, ensure_ascii=False, indent=2))
            check()
            if additions:
                applied = {row.get('review_receipt') for row in canonical}
                canonical.extend(row for row in additions if row['review_receipt'] not in applied)
                atomic_write(canon_path, json.dumps(canonical, ensure_ascii=False, indent=2))
            atomic_write(path, json.dumps(result, ensure_ascii=False, indent=2))
            return deepcopy(result)

    def cancel_pending_recovery(self, nid, pid, actor, expected_version, check):
        from ...services.finding_review_service import FindingReviewConflict, now
        with project_operation(self.backend.data, nid):
            path, row = self._project_pending(nid, pid); check()
            if row.get('review_version', 1) != expected_version: raise FindingReviewConflict('CANON_VERSION_CONFLICT')
            journal = row.get('_review_commit')
            if not journal: raise ValueError('CANON_NO_PENDING_RECOVERY')
            receipts = {x.get('review_receipt') for x in read_json(self.backend.novels / nid / 'canon.json', [])}
            if any(x['review_receipt'] in receipts for x in journal['additions']): raise FindingReviewConflict('CANON_ALREADY_COMMITTED_RECOVER_RECEIPT')
            row.pop('_review_commit')
            row.update(review_version=expected_version + 1, review_owner='PENDING_CANON_REVIEW_V1')
            row.setdefault('review_history', []).append({'version': expected_version, 'action': 'CANCELLED_RECOVERY', 'actor_id': actor,
                                                         'reason': 'Cancelled before any Canon facts committed', 'timestamp': now()})
            check(); atomic_write(path, json.dumps(row, ensure_ascii=False, indent=2))
            return row

    def list_reviewable(self, nid):
        with project_operation(self.backend.data, nid):
            return [read_json(path, {}) for path in sorted((self.backend.novels / nid / 'pending_canon').glob('*.json'))]

    def recover_pending_committed(self, nid, pid, expected_version, check):
        from ...services.finding_review_service import FindingReviewConflict
        with project_operation(self.backend.data, nid):
            path, row = self._project_pending(nid, pid); check()
            if row.get('review_version', 1) != expected_version: raise FindingReviewConflict('CANON_VERSION_CONFLICT')
            journal = row.get('_review_commit')
            if not journal: raise ValueError('CANON_NO_PENDING_RECOVERY')
            receipts = {x.get('review_receipt') for x in read_json(self.backend.novels / nid / 'canon.json', [])}
            if not all(x['review_receipt'] in receipts for x in journal['additions']): raise FindingReviewConflict('CANON_REVIEW_RETRY_REQUIRED')
            check(); atomic_write(path, json.dumps(journal['result'], ensure_ascii=False, indent=2))
            return journal['result']
