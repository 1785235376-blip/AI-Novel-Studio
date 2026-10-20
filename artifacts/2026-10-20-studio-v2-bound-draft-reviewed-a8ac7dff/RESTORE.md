# Restore schemas3-6 bound authoring recovery

Schema7 DEFAULT OFF. Recovery evidence is JSDOM/localStorage+Mock transport; retained independent schema6 File owner source subcheck is separate, not live Host/PG/fullE2E.

Unique prerequisite `7883878ae862326ff3ca256d9a111d8462920fe0` is recovered from `artifacts/2026-10-20-studio-v2-condition-draft-reviewed-7883878a/RESTORE.md` at archive `6b96a125043c4f08a495836a7d126e196d0b4ad6` and its prior chain. Ordinary main/archive report trees are not this product. Verify SHA256SUMS. In an independent Git database already containing788:

```powershell
git bundle verify ./studio-v2-7883878a-to-a8ac7dff.bundle
git fetch ./studio-v2-7883878a-to-a8ac7dff.bundle refs/heads/work/v2-bound-draft-reviewed-20261020:refs/heads/recovered-bound-draft
git rev-parse recovered-bound-draft
git rev-parse 'recovered-bound-draft^{tree}'
git rev-list --count recovered-bound-draft ^7883878ae862326ff3ca256d9a111d8462920fe0
git diff --name-only 7883878ae862326ff3ca256d9a111d8462920fe0 recovered-bound-draft
git fsck --strict --no-dangling
```

Expect exact original `a8ac7dff36c94e3b58d2edc7116708ef4e42f742`, tree `bdee896c0e48891af0484eb3569571909b49faa1`,1 commit,9 paths,15 objects. Check every file mode/blob/length/SHA256 and new object type/length/cat-file digest against MANIFEST. ZIP evidence-index.json hashes every other payload and records original source hashes. Source selection is direct: do not apply a patch or replay dependencies on top of this commit.

Reproduction commands are in combined/run-validation.py and finish-validation.py. Adapt paths to an isolated restored workspace and reuse authorized existing dependencies. Materialize the two unchanged tests/fixtures JSON files named in validation-initial-stop.json before the single complete-worktree TS/build. No credentials, model execution, schema7 enablement or production service is required. The prior trim path-count correction remains in the previous788 archive; no historical file or hash is changed.
