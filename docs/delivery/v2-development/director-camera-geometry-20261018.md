# Authored Director camera geometry

Optional authored camera grammar now follows the original Director/Storyboard Save, CAS, derive and review owners. The original camera checker supplies supplementary findings pinned to document ID, version and digest; it does not claim image analysis or model inference. Missing scene ownership and missing geometry remain insufficient evidence. Legacy payloads without geometry and all four model schema hashes are preserved. Model-produced geometry is rejected.

Final receipts: director-camera-file-final2-20261018 (101 passed, 31 PostgreSQL skipped), director-camera-postgres-final-20261018 (31 passed, 101 deselected). PostgreSQL was stopped and cleanup completed. Targeted worker UI checks passed 113 cases. Combined root UI checks passed 242 cases, TypeScript, production build and token guard. Browser and Windows acceptance remain NOT_RUN.
