# QA contract

## Codex v2 atlas

- atlas size: 1536 x 2288
- grid: 8 columns x 11 rows
- cell size: 192 x 208
- active animation cells: 73
- dedicated neutral look frame: row 0, column 6
- inactive cells: 14, all fully transparent
- sprite version: `2`

## State rows

| Row | State | Active columns |
| --- | --- | --- |
| 0 | idle + neutral look frame | idle 0-5; neutral 6 |
| 1 | running-right | 0-7 |
| 2 | running-left | 0-7 |
| 3 | waving | 0-3 |
| 4 | jumping | 0-4 |
| 5 | failed | 0-7 |
| 6 | waiting | 0-5 |
| 7 | running | 0-5 |
| 8 | review | 0-5 |
| 9 | look 000 through 157.5 | 0-7 |
| 10 | look 180 through 337.5 | 0-7 |

## Pet Derby

The example plan runs 564 ticks with weighted state selection. Warmup guarantees
that every enabled state and look direction is visited before random selection.
The report records:

- exact state and frame selected at every tick
- visited state and direction coverage
- centroid movement normalized to cell size
- visible-area ratio
- bounding-box size change
- canonical sequence SHA-256

Thresholds are policy, not universal animation law. A project may tune them in
a checked-in plan, but CI and repairs must reuse the same plan.

Every standard state is evaluated as a cycle, including the last-to-first
transition. The release gate caught a one-way `failed` collapse whose original
`7 -> 0` wrap had a normalized bounding-box jump of `0.463542`. A deterministic
whole-row reorder made it a collapse-and-recovery loop: the wrap is `0.005208`,
the worst transition is `0.265625`, and all original RGBA cells are preserved.

## Backdrop Gauntlet

For every active cell, configured scale, and background:

1. Resize the cell with Lanczos when scale is below 1.
2. Find foreground pixels on the alpha boundary.
3. Alpha-composite their RGB values over the background.
4. Measure foreground-to-background luminance contrast.
5. Record the 10th percentile, median, and low-contrast fraction.

A measurement fails only when its lower-tail contrast and its low-contrast
edge fraction both breach policy. This keeps a few translucent antialiasing
pixels visible in the evidence without misclassifying them as broad silhouette
loss; a sprite whose edge broadly blends into its background still fails.

This is an artwork legibility heuristic. It is not a WCAG conformance result,
because WCAG contrast requirements target text and specified user-interface
components, not arbitrary character artwork.

## Published artwork evidence

The repository keeps the accepted release evidence under `artwork/qa/`:

- `contact-sheet.png`: all 73 active animation cells plus the dedicated neutral
  look frame
- `standard-frame-review.json`: portable frame counts and the accepted visual
  result for every standard state
- `failed-loop.gif` and `failed-loop-repair.json`: the reviewed cyclic failed
  animation plus before/after metrics and pixel-preservation proof
- `look-directions.png`: neutral plus all 16 labeled look directions at normal
  and enlarged review sizes
- `direction-blind-pairs.png`: randomized unlabeled horizontal and vertical
  A/B challenges
- `direction-blind-verdicts-1.json` through
  `direction-blind-verdicts-3.json`: three context-isolated classifications
- `direction-blind-validation.json`: strict-majority comparison with hard
  cardinal gates
- `direction-semantics.json`: labeled per-direction horizontal and vertical
  evidence
- `look-continuity.json`: adjacent-pair area, center, and pixel-difference
  measurements
- `chroma-despill.json` and `atlas-validation.json`: authoritative chroma and
  v2 structural results

The accepted release has no failed direction. The only reviewed semantic
warning is that `337.5` has a subtle horizontal cue at normal pet size; its
vertical up cue, labeled up-left quadrant, ordered-loop continuity, and all
four cardinal hard gates pass. The remaining `157.5 -> 180` numeric continuity
warning was independently reviewed at normal size and reads as the intended
down-right-to-down pose transition, without a visible scale pop, identity
break, clipping, or loop reversal.
