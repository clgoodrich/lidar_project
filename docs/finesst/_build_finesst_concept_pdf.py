"""Render the FINESST concept brief (expanding Barlow 2026 into a Future
Investigator project) to a formatted PDF via reportlab.

Output: docs/finesst/FINESST_Barlow_Expansion_Concept.pdf
Run:    python docs/finesst/_build_finesst_concept_pdf.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle, HRFlowable)

OUT = Path(__file__).resolve().parent / "FINESST_Barlow_Expansion_Concept.pdf"

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceBefore=14,
                    spaceAfter=6, textColor=colors.HexColor("#1a3e6e"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, spaceBefore=10,
                    spaceAfter=4, textColor=colors.HexColor("#244c7a"))
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10.2, leading=14.5,
                      alignment=TA_JUSTIFY, spaceAfter=6)
BULLET = ParagraphStyle("Bullet", parent=BODY, spaceAfter=3)
TITLE = ParagraphStyle("Title2", parent=ss["Title"], fontSize=19, leading=23,
                       textColor=colors.HexColor("#13294b"), spaceAfter=2)
SUB = ParagraphStyle("Sub", parent=ss["Normal"], fontSize=10.5, leading=14,
                     textColor=colors.HexColor("#555555"), spaceAfter=2)
SMALL = ParagraphStyle("Small", parent=ss["Normal"], fontSize=8.5, leading=11,
                       textColor=colors.HexColor("#666666"))


def b(text: str) -> Paragraph:
    return Paragraph(text, BODY)


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(t, BULLET), leftIndent=12) for t in items],
        bulletType="bullet", start="•", leftIndent=14, bulletColor=colors.HexColor("#244c7a"),
    )


def main() -> int:
    doc = SimpleDocTemplate(str(OUT), pagesize=letter,
                            leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            title="FINESST Concept — Expanding Barlow (2026)")
    e: list = []

    # --- Header ---
    e.append(Paragraph("FINESST Concept Brief", TITLE))
    e.append(Paragraph("Expanding Barlow (2026) into a Future Investigator Research Project",
                       SUB))
    e.append(Paragraph("NASA ROSES-2025 F.5 — Future Investigators in NASA Earth and Space "
                       "Science and Technology &nbsp;|&nbsp; Proposal deadline: 14 July 2026",
                       SUB))
    e.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#244c7a"),
                        spaceBefore=6, spaceAfter=10))

    # --- Parent work ---
    e.append(Paragraph("1.&nbsp; The parent work", H1))
    e.append(b("Barlow (2026) trained a U-Net to delineate ephemeral-stream boundaries in the "
               "McMurdo Dry Valleys (MDVs), Antarctica, <b>from terrain shape alone</b> "
               "(elevation, slope, aspect — no water/color signal), validated free satellite "
               "elevation models (REMA) against airborne lidar for centimeter-to-meter change "
               "detection, and quantified two decades of fluvial geomorphic change across four "
               "valleys. The dissertation rests on three transferable pillars:"))
    e.append(bullets([
        "<b>Terrain-only semantic segmentation</b> of channels from DEM derivatives "
        "(elevation/slope/aspect most informative).",
        "<b>Satellite-DEM validation</b> via point-to-plane ICP alignment, Laplacian error "
        "modeling, and NMAD-based (outlier-robust) uncertainty.",
        "<b>Multi-epoch change detection</b> — DEM-of-Difference inside segmented stream masks, "
        "level-of-detection thresholds (LOD95 = 1.96 × NMAD), and per-stream erosion/deposition "
        "and acceleration rates.",
    ]))
    e.append(Paragraph("Citation: Barlow, M. C. (2026). <i>A Comprehensive Spatial Analysis of "
                       "Stream Boundary and Geomorphological Change Detection: McMurdo Dry "
                       "Valleys, Antarctica.</i> PhD Dissertation, Dept. of Civil &amp; "
                       "Environmental Engineering, University of Houston.", SMALL))

    # --- The gap / core move ---
    e.append(Paragraph("2.&nbsp; The opening (core move)", H1))
    e.append(b("Barlow's thesis ends at <i>description</i> — it maps where change is happening "
               "(Denton Hills is the erosion hotspot; parts of Taylor Valley are accelerating) "
               "but explicitly defers two threads to future work: <b>(a)</b> coupling geomorphic "
               "change to physical / climate drivers, and <b>(b)</b> generalizing the model "
               "beyond the MDVs. A Future Investigator (FI) project lives precisely in that gap: "
               "turn her <i>monitor</i> into an <i>explanatory and predictive</i> tool. This is a "
               "genuine increment, not a replication — exactly what FINESST rewards."))

    # --- Proposed project ---
    e.append(Paragraph("3.&nbsp; Proposed FI project", H1))
    e.append(Paragraph("Target division: Earth Science (EARTH25) — continuing the Antarctic "
                       "cryosphere / climate thread.", H2))
    e.append(b("<b><i>“From detection to attribution: physically-coupled, cross-domain monitoring "
               "of ephemeral-channel geomorphic change from terrain alone.”</i></b>"))

    obj = [
        ["#", "Objective", "Increment over Barlow"],
        ["1", "Attribution (headline science)",
         "Pair per-stream gross / net / acceleration rates with energy-balance drivers "
         "(temperature, insolation, melt degree-days, active-layer depth from MDV-LTER + "
         "reanalysis); model why hotspots occur and predict where acceleration migrates next. "
         "Listed verbatim as Barlow future work."],
        ["2", "Cross-sensor &amp; cross-valley generalization",
         "Make the terrain-only segmenter robust across sensors (airborne lidar 2001 / 2014 and "
         "REMA satellite) and across all four valleys — quantifying and correcting the "
         "lidar-to-satellite domain shift that limits the satellite epoch. Barlow flags sensor "
         "generalization as future work."],
        ["3", "Calibrated uncertainty",
         "Extend the Laplacian / NMAD / LOD framework into a per-pixel, sensor-aware confidence "
         "layer so every change map carries calibrated uncertainty — aligned with NASA's "
         "trustworthy-EO-product priorities."],
    ]
    t = Table(obj, colWidths=[0.3 * inch, 1.7 * inch, 4.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244c7a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    # wrap long cells as paragraphs (white bold for the header row)
    HEADW = ParagraphStyle("HeadW", parent=BULLET, textColor=colors.white,
                           fontName="Helvetica-Bold")
    obj_wrapped = [[Paragraph(c, HEADW) if r == 0 else Paragraph(c, BULLET)
                    for c in row] for r, row in enumerate(obj)]
    t = Table(obj_wrapped, colWidths=[0.3 * inch, 1.6 * inch, 4.3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244c7a")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    # recolor header text white
    e.append(t)
    e.append(Spacer(1, 4))

    # --- Why competitive ---
    e.append(Paragraph("4.&nbsp; Why it is competitive (maps to the review criteria)", H1))
    e.append(bullets([
        "<b>Scientific merit.</b> Advances the MDV “climate canary” from <i>measured</i> to "
        "<i>explained and predicted</i>; novel attribution plus calibrated-uncertainty change "
        "detection.",
        "<b>Relevance to SMD.</b> Quantifying cryosphere and climate sensitivity in Earth's most "
        "geomorphically stable landscape maps squarely onto NASA Earth Science Division "
        "objectives (cryosphere, terrestrial hydrology, climate change).",
        "<b>FI qualifications &amp; development.</b> The applicant already operates the complete "
        "toolchain — U-Net segmentation on terrain derivatives, ICP alignment, DEM-of-Difference "
        "— in an independent application domain (see Feasibility), a concrete anchor most FI "
        "applicants lack.",
    ]))

    # --- Feasibility ---
    e.append(Paragraph("5.&nbsp; Feasibility anchor", H1))
    e.append(b("An existing, working pipeline (“WellSight”) already runs the identical "
               "architecture — U-Net semantic segmentation on lidar-derived terrain rasters "
               "(DEM, slope, local relief, openness), ICP-based co-registration, and "
               "DEM-of-Difference change analysis — on a completely different landscape "
               "(Appalachian Plateau channels, roads, and well-pad scars detected from elevation "
               "alone). This demonstrates the method generalizes beyond a single sensor and biome, "
               "directly de-risking Objective 2 and evidencing the FI's readiness to execute."))

    # --- Data requirements ---
    e.append(Paragraph("6.&nbsp; Data requirements", H1))
    e.append(b("The pipeline runs on DEM-derived rasters, so elevation data is the backbone. "
               "Nearly all of it is free / public; the single access-gated dependency is Barlow's "
               "hand-digitized training labels. None is currently held locally — the existing "
               "WellSight holdings serve only as method-feasibility evidence."))

    e.append(Paragraph("A.&nbsp; Core terrain / elevation inputs", H2))
    e.append(bullets([
        "<b>MDV airborne lidar, 2001 &amp; 2014</b> (NCALM; via OpenTopography) — Barlow's "
        "gold-standard epochs.",
        "<b>REMA</b> (Reference Elevation Model of Antarctica), 2021–2023 — Polar Geospatial "
        "Center, free — the satellite epoch.",
        "Derived per epoch: elevation, slope, aspect, curvature, intensity (lidar), flow "
        "accumulation.",
    ]))

    e.append(Paragraph("B.&nbsp; Training labels (ground truth)", H2))
    e.append(bullets([
        "<b>Barlow's hand-digitized stream-boundary polygons</b> (217 Taylor tiles + the "
        "multi-valley set) — <b>the only access-gated dependency</b>: obtain from her group, or "
        "re-digitize.",
        "MCM-LTER stream centerlines as auxiliary / QC.",
    ]))

    e.append(Paragraph("C.&nbsp; Climate &amp; physical-driver data — required for the new "
                       "science (Objective 1, attribution)", H2))
    e.append(bullets([
        "<b>MDV-LTER meteorological network</b> — air/ground temperature, incoming solar "
        "radiation, humidity, wind (free, MCM-LTER data portal).",
        "LTER stream-discharge gauges (melt-season flow); glacier mass-balance / melt; "
        "permafrost / active-layer measurements.",
        "Reanalysis for spatial gap-fill: <b>ERA5</b> and/or <b>AMPS</b> (Antarctic Mesoscale "
        "Prediction System).",
    ]))

    e.append(Paragraph("D.&nbsp; Cross-sensor / cross-valley data (Objective 2)", H2))
    e.append(bullets([
        "All four valleys (Taylor, Wright, Victoria / Barwick, Denton Hills) across both lidar "
        "epochs and the REMA epoch — the spread needed to test generalization within the MDV "
        "system.",
        "The lidar-vs-REMA pairing is itself the key test case: quantify and correct the "
        "airborne-to-satellite domain shift that currently limits the satellite epoch.",
        "Optional broader reach (still Antarctic / polar): other polar-desert DEMs via ArcticDEM "
        "(PGC), if a wider generalization test is wanted.",
    ]))

    e.append(Paragraph("E.&nbsp; Validation / auxiliary", H2))
    e.append(bullets([
        "High-resolution imagery for label QC — WorldView / Maxar via PGC over the MDVs.",
        "Published geomorphic-change rates for cross-validation.",
    ]))

    e.append(Paragraph("Status: none held locally yet, but almost all is free / public (REMA &amp; "
                       "ArcticDEM from PGC, MDV-LTER climate, airborne lidar from OpenTopography). "
                       "The lone true dependency is Barlow's training labels.", SMALL))

    # --- Logistics ---
    e.append(Paragraph("7.&nbsp; Program logistics", H1))
    e.append(bullets([
        "<b>Solicitation:</b> NASA ROSES-2025 F.5 (FINESST) — <b>Earth Science Division "
        "(EARTH25)</b>. (FINESST spans five SMD divisions; this proposal targets Earth Science.)",
        "<b>Deadline:</b> 14 July 2026 (11:59 PM EDT). Pre-proposal webinar 28 May 2026; "
        "Earth Science office hours 23–24 June 2026.",
        "<b>Structure:</b> the graduate student is the Future Investigator, primary author, and "
        "intellectual lead; advisor serves as PI of record. Award up to ~$50,000/yr for up to "
        "three years.",
        "<b>Deliverable to draft next:</b> ~6-page Scientific/Technical/Management section "
        "(Background &amp; gap → objectives/hypotheses → methodology → expected results &amp; "
        "novelty → FI role &amp; development → timeline), references, and data-management plan.",
    ]))

    # --- Open decisions ---
    e.append(Paragraph("8.&nbsp; Open decisions before drafting the full proposal", H1))
    e.append(bullets([
        "<b>Data access:</b> whether Barlow's MDV training labels and the lidar / REMA DEMs can be "
        "used and extended directly, or the proposal must assume re-deriving them.",
        "<b>Scope:</b> which valleys and epoch pairs to prioritize for the attribution analysis, "
        "given REMA's uneven post-2014 coverage.",
    ]))

    e.append(Spacer(1, 8))
    e.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#b8c4d6"),
                        spaceBefore=4, spaceAfter=4))
    e.append(Paragraph("Prepared as a planning brief; not a submitted proposal. Sources: "
                       "Barlow (2026) dissertation; NASA ROSES-2025 F.5 FINESST solicitation "
                       "(NSPIRES).", SMALL))

    doc.build(e)
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
