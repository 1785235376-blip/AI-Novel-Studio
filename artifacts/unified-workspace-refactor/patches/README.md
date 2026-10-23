# patches — [HERMIA-FE-20261023 M1]
0001-wire-docklayout-preview.patch — base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (App.tsx identical at M1 commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e). NOT applied.
Adds opt-in `?uw=1` preview: App() returns UnifiedWorkspacePreview, otherwise renders unchanged LegacyApp (renamed body). New file frontend/src/workspace/UnifiedWorkspacePreview.tsx.
Verified: `git apply --check` OK. Not verified: tsc/tests/browser after applying.
