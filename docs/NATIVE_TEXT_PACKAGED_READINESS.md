# Native text packaged readiness consistency

A targeted source check found that Claude/Gemini host registration considered only settings.enable_packaged_runtime when deciding whether an environment credential made the provider configured. The original shared transport already treats PACKAGED_WINDOWS_MODE=true as vault-only. With that packaged marker true, the settings flag false, a synthetic environment key and no vault credential, registration therefore advertised configured/available even though the original transport would refuse the key.

Two pre-fix regressions genuinely failed, one per native provider. Registration now uses the same effective packaged predicate as the existing Bailian preset and shared credential transport. No credential resolution, account permission, host setting or actual API call was changed. A configured provider still says configured_unverified, never quality-verified or free.

Final targeted suite: 37 passed, including 8 readiness cases, existing native request/stream/error contracts, Bailian boundaries, API catalog binding and an actual offline PUBLIC wheel. Positive development-env and packaged-vault registration cases remain supported; cloud execution remains disabled in the readiness cases. Original RED and GREEN receipts/logs are retained. Frontend source is unchanged from the prior checked build.

The catalog remains 2367 method/path entries, fingerprint e91a0f52adad17a199f0fa20d422c18bcb2565a10dadc77937305d92f4879af3. This is a bounded readiness correction, not evidence of credential exfiltration, real provider connectivity, Windows installer acceptance or global closure of legacy runtime paths. Other settings-only predicates observed in legacy/DeepSeek code were not reproduced or modified by this slice.
