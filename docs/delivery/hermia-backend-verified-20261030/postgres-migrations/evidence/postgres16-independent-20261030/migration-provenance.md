# Exact original migration restoration

Before repair HEAD: 9f8ca0aff280eb7c055ae47ee3a610022fd90a3d, tree ad5c04b97939a6e842233da629e2cb447ae9b439.

Current ancestry started with ddf7997a4baebdc205f96ab245c82cccf8c2d52a containing SQL001–017 and an older loader requiring017 only. Commit94befa78b1bc097049f55654f13e1c9c2f402537 imported updated migration loaders and repository code requiring018–020, without those SQL files. Public395ac26dd2de3d473e56964dbeb9ac9806facb85 already has this omission. No migration deletion appears in full HEAD ancestry. The historical migrations exist in other locally available tracked histories, not current HEAD ancestry. Evidence supports integration omission, not an intentional removal or recent workspace loss.

Restored byte-for-byte, without ad hoc schema changes:

- 018_context_privacy.sql: commit78920f2f9435a9c1d5625479c37b0948c1db5b51, Git blob b454ddc859fd582421671e5c719a628c2dea8f0e, SHA256 e2e6c2c45a07b9593c5e4ff9400d3eb0e4bad6096ea0aaadb1bba691df3bb5b1.
- 019_experimental_scope_documents.sql: commit d9d6be53c8afea1348d91db0e8890ce1f1b01ac1, Git blob28b62185b70b8d28feed825002a824acafaee1a0, SHA256 eb3516c8f802e51efa523950807795ea9400bf91f62e9191d1c726a5cb10ffaf.
- 020_stable_chapter_identity.sql: latest original correction commit1d9b88ac36b1d75c06544e3aa69c3ab308164120, Git blob77f2b7471650669029859246aa672357e87c279d, SHA25692774a1b26f4e79056e7f0d5d3fedf76b77887a109de7a1251bd6b16081722f7. Earlier de92f5756ba8a789243d5a970ee865307a36e596 introduced this file. Selected latest fix preserves typed NULL::UUID identity reservation.

Actual pre-repair loader FileNotFoundError output is retained separately. Migration018 is not designed for blind raw SQL reruns (ADD CONSTRAINT); rerun safety must be tested through the original packaged migration ledger/checksum runner. Neither a mocked SQL executor nor loader success establishes real PostgreSQL migration success. Runtime verification is separately recorded.
