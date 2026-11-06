# 5.6 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Dedupe rule is deployment. Matched rows stay. An unmatched blob inside a drawn pit is dropped. keep_all is the sensitivity. Made by the build agent, change freely.
- 2026-11-05. Assignment is global Hungarian across statuses with a 100 m gate. per_status gives labelled competing proposals. Made by the build agent, change freely.
- 2026-11-05. Footprints are per modality (115 pit blocks, 129 pad blocks). intersection is the alternative switch. Made by the build agent, change freely.
- 2026-11-05. The null rejects shifts losing more than 10% of records and redraws up to 20 times. report_retained keeps every shift and logs its retained count. Made by the build agent, change freely.
- 2026-11-05. Under the 10% rule plugged records at pit level get no accepted shift. The default run marks that cell unattainable. The retained-count run fills it as a sensitivity. Made by the build agent, change freely.
- 2026-11-05. Normalised excess is observed minus null mean, over one minus null mean. Its interval uses the null 2.5 and 97.5 percentiles. It is not PPV. Made by the build agent, change freely.
- 2026-11-05. The pad full output is the model_geometry layer of the 0.50 threshold products, matched to plat by greedy IoU 0.3. No raster rebuild. Made by the build agent, change freely.
- 2026-11-05. The annotated analysis uses pit_inside centroids and plat polygons. Made by the build agent, change freely.
- 2026-11-05. The adjudication sample is 60 pit links stratified by distance band (0, 10, 25, 50, 100 m). Slack moves to larger bands. Made by the build agent, change freely.
- 2026-11-05. Outputs stay in this folder, not data/9t/results/records/, under the build rule. Made by the build agent, change freely.
