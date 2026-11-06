# Field methane screening protocol (draft, 2026-11-05)

**Status.** Draft written by the build agent. Not approved. The partner and the safety reviewer approve it before any field day.
**What a reading is.** A screening concentration at one place and time. It is not an emission rate. A reading below the limit means below the instrument limit at that time and place.
**Values.** Every number below comes from `src/config_6_5.json`. Each one is assumed until verified (framework section 4A).

## Before the field day
1. Check the instrument model, serial number, units and detection limit against the registry in the config.
2. Check the span gas certificate and its expiry date.
3. Read the safety plan. Confirm the stop threshold with the safety reviewer.
4. Load the site list from 7.5. Sites come from the 7.5 sample, never from smell or reports.

## At the start of each day
1. Zero check in zero air. Record it as a `zero` row.
2. Span check with the span gas. Record it as a `span` row.
3. If either check is outside tolerance, recalibrate and repeat. If it fails twice, stop for the day and report.

## At each site
1. Approach from upwind. Watch the reading the whole time.
2. Stop at once on a reading at or above the stop threshold, on odour or on hissing. Log a `stop` row with the reason. Leave upwind.
3. Background. Stand 20 to 50 m upwind. Record readings for at least 5 minutes as `background` rows with the distance.
4. Screening. Record the peak at 10, 5 and 1 m downwind as `screen` rows with position 10, 5 and 1.
5. Wellhead and casing readings only if safe. Positions `wellhead` and `casing`.
6. Record wind speed and direction, temperature and pressure on every row.

## Repeat visit
Visit every site again on a different day. Use the same positions.

## After the day
1. Run `src/_methane_sheet_check.py` on the sheet. Fix entry errors. Never edit a reading value.
2. Run `src/_methane_field_table.py`. Then `src/_methane_claim_audit.py` on the outputs and any report.

## Reporting rules
- Report the background and the range over visits. Never a single reading.
- Say screening.
- Never write no leak, leak-free, emission rate or flux values for these readings.
- Keep point readings (ppm) and open-path readings (ppm·m) in separate tables.

## Sheet columns
One row per reading. Required columns are listed in `src/config_6_5.json` under `sheet_schema`. A synthetic worked example is `results/tables/methane_example_sheet.csv`. It is labelled synthetic on every row.
