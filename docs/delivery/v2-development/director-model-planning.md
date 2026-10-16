# Model-led Director candidate planning

The existing Creative proposal/model-preview/review/adoption owner now carries an optional, bounded `planning` object on Director notes. New model previews explicitly request scene-specific shot decisions, evidence excerpts, sequence/rhythm and estimated-duration reasoning, assumptions, uncertainty and up to three alternatives. This is a planning contract, not evidence of actual model quality.

Evidence validation checks the owning scene, field, dialogue index and exact excerpt. It rejects invented excerpts and unknown references, including nested scene/shot notes. It cannot prove that a dramatic interpretation is correct. Unsupported geometry remains unknown. Candidate choices and reasoning remain editable and edits reset the UI review acknowledgement. The displayed total adds only the current candidate durations; alternatives are excluded and it is not measured film runtime.

Auxiliary camera-vocabulary checks reuse the existing camera-language owner and are labelled as checks of the original candidate. They do not infer continuity or silently rewrite choices. No rule template is relabelled as model output. Existing local rules remain a visible manual fallback.

Absent planning fields retain legacy serialized document identities and default output schema. Existing source/version binding, explicit local model dispatch, original exact review and independent document adoption remain in place. No route, price, permission, credential or lifecycle gates were changed. Standalone screenplays without a source chapter remain unsupported by the existing model coordinator; no alternate dispatch was added.

## Verification

- Isolated File/mocked transport tests: 35 passed, 22 skipped in the focused planning and existing director/storyboard-production suites. PostgreSQL cases were not exercised.
- Frontend proposal/model controls/authoring: 27 passed, including planning edits invalidating review and payload preservation.
- UI token guard, geometry unit tests and production type/build checks run separately.
- All model transport was synthetic. No real model/provider/API call, paid compute, Windows acceptance or browser visual validation was performed. These remain required before claiming model quality or real-device acceptance.
