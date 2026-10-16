# Two-path Git EOL byte binding

This audit changed documentation only. It ran no product tests and changed no source, index, Git attributes, CI gate, skip policy or coverage manifest. The root agent independently applied the two-path packaging correction while preserving working source bytes.

## Exact difference and correction

The old source commit is `f8e97b167cb77c96d2885d0256e9a1083127e863`. Two tracked files had LF Git blobs but CRLF working bytes; `core.autocrlf=input` hid that difference in ordinary working-tree status. Current V2 coverage uses raw-byte hashes, so a fresh LF checkout would not match the tested working-byte identities.

| Path | Old Git LF SHA-256 | Working CRLF SHA-256 | CRLF lines |
| --- | --- | --- | --- |
| `app/application/persistence.py` | `9d026ce9b1f9d46644d9c1ec89656302f4273a0b7822fafd48103ad931776a0f` | `f34f58c6866cade1f85f1c81b9432a4cf39f3d30c07bab175c7bc3f19c4eca9d` | 350 |
| `tests/test_v2_project_retirement_file_io.py` | `13395f48e9a1dfab02cbebf95c51197ed45a748da05db400d709604053c190a0` | `8ed7589ab6d135bbdd533dc51e4c5788c209bd13872128eaf6579b7af8df58c0` | 73 |

`eol-source-byte-preservation-proof.json` proves for each file that replacing CRLF with LF exactly reproduces the old Git blob, the reverse LF-to-CRLF conversion exactly reproduces the working bytes, and both ASTs are identical. There is no other content difference between that old commit and the preserved working files.

The root's packaging commit `f7fd63a1fff3c0ec7fa88c9c111676f9539a41a5` stores those existing CRLF bytes and gives only these two paths `-text`. The audit independently reads that commit's blobs and confirms both now equal the unchanged working bytes and current V2 manifest source hashes. Git's bundled `gitattributes` manual confirms that unsetting `text` disables EOL conversion on both check-in and checkout.

Each of the same two path attributes also names `whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol`. This retains the three default whitespace checks while recognizing CR as part of the line terminator. Read-only `git apply --check --cached` probes showed the default CR trailing-whitespace diagnostic and successful checking with those defaults plus `cr-at-eol`; no patch was applied. Checked-in workflows/configuration have no Python Ruff/Black, mixed-line-ending or `git diff --check` gate. Frontend design-token lint is separate. This report does not claim a hosted CI outcome.

## Protected-history boundary

Both paths are absent from the **750** frozen test/gate source paths and the independently recomputed union of **752** protected artifact paths. Neither is a product test node in the original 9151-node manifest.

`persistence.py` **is** an application-source entry in that frozen manifest. Its original SHA-256 is `7d77e380f8fbf84928ade130c4c022469636a62bbe7fd4e89c1e42c44c50c3a4`; the source at `e21075d10801a60bdcb4282a6d5ce8068be21503` exactly matches that hash and its AST differs from old `f8e97b1`. That semantic difference therefore predates this EOL packaging correction. This is not a claim that current application code is identical to the frozen V1 source.

The frozen 9151 manifest remains byte-identical at SHA-256 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`. The current V2 manifest at this proof has 2352 source entries; this audit verifies only the two paths above. The root agent owns full-manifest Git-blob reconciliation and the independent 2290-file runtime snapshot no-drift check.

Changing manifest generation to canonical LF alone would leave the running working-byte evidence outside the CI raw-hash domain. Converting working sources to LF would also change their runtime snapshot bytes and require a separate, documented evidence transition after active PostgreSQL validation. Preserving the existing two raw files in Git is the bounded correction that keeps the tested bytes, exact CI hashes and fresh-checkout content aligned without weakening a gate.
