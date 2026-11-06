# 6.4 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Zero depth coverage stops the run. `--allow-no-depth` builds the package with the flag reported as not computable. The flag is never dropped silently. Review 6.4-01. Made by the fix agent, change freely.
- 2026-11-06. No held file has a real depth field. `TOTAL_MAXI`, `OLDEST_FOR` and `TARGET_FOR` are empty in every DEP export on disk. The config keeps `TOTAL_MAXI` so a future export with depths works unchanged. Made by the fix agent, change freely.
- 2026-11-05. The hydrogen partner and pilot field are declared hypothetical. The field boundary falls back to the 9t block extent. Made by the build agent, change freely.
- 2026-11-05. Reader questions Q_surface and Q_record are replaced by Q_h2_leak and Q_h2_material. Both are zero tolerance, with Q_complete. Made by the build agent, change freely.
- 2026-11-05. Record depths are in feet. Depth uncertainty is 50 ft. The flag is dropped under 50% depth coverage. Made by the build agent, change freely.
- 2026-11-05. Penetration categories are reaches reservoir, reaches seal only, above seal and unknown. All come from records. Made by the build agent, change freely.
- 2026-11-05. The profile lives in `src/config_6_4.json`. Each run writes the resolved profile as `screen_profile_hydrogen.json` in its run folder. Made by the build agent, change freely.
- 2026-11-05. No 6.1 script was edited for hydrogen. The delta is hooks plus config. Made by the build agent, change freely.

## Needs user decision
- 2026-11-06. Where record depths come from. The DEP export carries none. Options are a partner well file with `depth_ft`, the DEP well completion reports, or no penetration flag at all.
