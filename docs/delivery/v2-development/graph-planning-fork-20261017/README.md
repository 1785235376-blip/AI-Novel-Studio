# Updated planning-source independent draft evidence

Read ../../../CANVAS_PLANNING_SOURCE_FORK.md for the bounded feature contract and limitations. Source3c977f1 modifies two existing frontend runtime files and adds two runtime helpers/components plus two test files. Backend, original tests, runners, gates and package manifest stay unchanged.

Final source-identical receipts: graph-planning-fork-ui-r4 (71 overlapping UI checks plus TS/build/token), graph-planning-fork-ui-full-r1 (450 UI /35files plus TS/build/token), graph-planning-fork-native-file-r1, and graph-planning-fork-native-postgres-r1. The two native scripts use real original HTTP/app startup/shutdown and bootstrap authority, manually prepare separate exact current-pin graphs, preserve old graphs, and reopen both after a third app process starts. PG uses a fresh original-migration database; all app processes and PG are stopped. No model requested and no browser UI executed.

Four unchanged prior PUBLIC backend packages were reopened and fully checked against their recorded payload hashes and current included source in reused-backend-packages. They were not rebuilt or represented as packages of the new UI. Current UI production output is established by the fresh Vite builds.

Raw r1/r2 failures remain adjacent; final evidence excludes the malformed new-test tuple table's false-positive negative cases. Complete release, real model quality, browser geometry and Windows/GPU are still unverified.
