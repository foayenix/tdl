# DESIGN.md — The Deposit Ledger, build reference

Transcribed from artboard **10 — handoff**, which states: *values are literal · no derivation at runtime*. Take that seriously. Do not compute a shade, do not tint programmatically, do not run a colour through an opacity. Every value below is written out because it was chosen, not generated.

Where this file and prose elsewhere disagree, **this file wins**. Where this file and the artboards disagree, the artboards win — fix this file and note it in `STATE.md`.

Source: `design/artboards.dc.html` — ten artboards, four doubled in dark, 1440 × 1024.

---

## 1 · Colour tokens

Both themes are authored. **The dark theme is rebuilt against `#0F1412`, not inverted** — the artboard says so explicitly. Never generate one theme from the other.

| token | light | dark | for |
|---|---|---|---|
| `ground` | `#F7F7F4` | `#0F1412` | app background |
| `surface` | `#FFFFFF` | `#161D1A` | cards, tables, sidebar |
| `inset` | `#F7F7F4` | `#0F1412` | inputs, note body |
| `zebra` | `#FCFCFA` | `#191F1C` | alternate row (**off by default**) |
| `row-focus` | `#FBFBF9` | `#1A2320` | today / focused row |
| `row-hover` | `#F2F4F1` | `#1C2422` | row hover |
| `ink` | `#16211D` | `#E9EDE8` | primary text |
| `muted` | `#5E6B65` | `#9AA79F` | labels, meta, mono |
| `hairline` | `#DEE1DB` | `#252E2A` | rules, borders |
| `outline` | `#DEE1DB` | `#48544E` | empty box, dash marks |
| `primary` | `#14705B` | `#57C4A4` | herbal accent, links |
| `primary-wash` | `#E6F0EC` | `#122A24` | accent fill |
| `primary-ring` | `#C9E0D8` | `#1E4438` | accent border |
| `secondary` | `#A8681F` | `#DFA65C` | build / AI, caution |
| `secondary-wash` | `#F5EBDD` | `#2A2015` | caution fill |
| `secondary-ring` | `#E8D6BC` | `#40311D` | caution border |
| `positive` | `#2F7D4F` | `#5FBF7E` | read, floor met |
| `critical` | `#A33A2E` | `#E2705F` | contraindication |
| `warn-row` | `#FDF6EC` | `#1F1A12` | **unsourced row tint** |
| `disabled` | `#EDEFEA` | `#1C2422` | disabled fill |
| `disabled-ink` | `#B4BBB6` | `#5B6661` | disabled text |

Dark-only supporting values: `rule2 #3E4B45`, `critical-wash #2A1614`, `critical-ring #45211C`, and `#08150F` as the "ink on bright accent" colour — dark theme flips polarity at the top of the accent range, so text on a bright green sits near-black.

Zebra striping is **off by default**. Turn it on only where a row is very wide (the day log). Row separation is a hairline, not a fill.

---

## 2 · Type scale

Three families: **Fraunces**, **IBM Plex Sans**, **IBM Plex Mono**. All SIL OFL, all self-hosted as woff2 in `app/src/fonts/`. No CDN, no `<link>` to Google Fonts — the app must render correctly with the network off.

| role | family | size | weight | line-height | tracking |
|---|---|---|---|---|---|
| board title | Fraunces | 22 | 600 | 1.15 | -0.01em |
| record name | Fraunces | 26 | 600 *italic* | 1.1 | -0.015em |
| section head | Fraunces | 17 | 600 | 1.2 | -0.01em |
| body | Plex Sans | 13.5 | 400 | 1.6 | 0 |
| table cell | Plex Sans | 13 | 400 | 1.35 | 0 |
| table cell sm | Plex Sans | 12.5 | 400 | 1.35 | 0 |
| emphasis | Plex Sans | 12 | 500 | 1.45 | 0 |
| label | Plex Mono | 10 | 400 | 1 | 0.14em, uppercase |
| micro label | Plex Mono | 9.5 | 400 | 1 | 0.12em, uppercase |
| numeric | Plex Mono | 11.5 | 400 | 1 | 0 |
| display num | Plex Mono | 44 | 400 | 1 | -0.02em |

**Botanical names are always italic. The authority string never is.** `*Khaya senegalensis*` then upright `(Desr.) A.Juss.` The record name role bakes the italic in because a monograph's title *is* a binomial.

Every date, DOI, InChIKey, minute count and percentage is monospace. This is not decoration — it is how the eye finds data in a dense table.

---

## 3 · Spacing, radius, layout

**Spacing scale** — `2 · 4 · 6 · 7 · 8 · 12 · 14 · 16 · 18 · 20 · 28 · 40`. The four load-bearing steps are **12, 14, 16, 28**; reach for those first.

Note: artboard 01's caption still reads "8px grid". It is wrong — the real scale includes 6, 7, 14 and 18. Artboard 10 is the build reference. Do not force values onto an 8px grid.

**Radius** — and nothing else:

| px | for |
|---|---|
| 1 | the unsourced-row marker |
| 2 | checkbox |
| 3 | chip, pill, table card, keycap |
| 4 | button, field, panel |
| 5 | overlay surface |

> Corrected in session 16: this file listed 2 for "checkbox, marker". The
> artboards draw the checkbox at radius 2 but the unsourced-row marker at
> radius 1. 1 is now in the scale; it is used for that mark and nothing else.

**Layout rules** — literal:

| rule | value |
|---|---|
| table row height | 33px · 26px compact |
| table row padding | 7px 16px · 4px compact |
| table row padding, inset | 7px 14px — tables inside a record or a narrow panel |
| table head height | 30px, mono 9.5 uppercase |
| sidebar width | 208px fixed |
| filter rail width | 208px fixed |
| library detail rail | 384px fixed |
| record rail width | 224px, sticky top 0 |
| content padding | 18px 28px |
| prose max-width | 74ch |
| card border | 1px hairline, radius 3–4 |
| artboard | 1440 × 1024, overflow hidden |
| overlay width | 772px, top 104px |
| scrim | `rgba(14,21,18,0.62)` |
| focus ring | 2px primary, offset 1px |

**No box-shadows anywhere. No gradients.** Depth is hairlines and ground/surface contrast only.

---

## 4 · Component states

Five states per interactive component: default · hover · focus · selected · disabled. A dash in the artboard means the state does not apply.

### Button — primary

| state | light | dark |
|---|---|---|
| default | fg `#FFFFFF` bg `#14705B` | fg `#08150F` bg `#57C4A4` |
| hover | bg `#0F5947` | bg `#6FD9B7` |
| focus | default + `outline: 2px solid` primary, offset 1px | default + outline `#9BE8CE` |
| selected | — | — |
| disabled | fg `#B4BBB6` bg `#EDEFEA` | fg `#5B6661` bg `#1C2422` |

Padding `7px 14px`, radius 4, Plex Sans 12.5 / 500.

### Button — quiet

| state | light | dark |
|---|---|---|
| default | fg `#5E6B65` bg `#FFFFFF` border `#DEE1DB` | fg `#9AA79F` bg transparent border `#48544E` |
| hover | fg `#16211D` bg `#F7F7F4` border `#D2D6D0` | fg `#E9EDE8` bg `#1C2422` border `#5B6661` |
| focus | default + focus ring | default + focus ring |
| selected | fg `#14705B` bg `#E6F0EC` border `#C9E0D8` | fg `#57C4A4` bg `#122A24` border `#1E4438` |
| disabled | fg `#B4BBB6` border `#EDEFEA` | fg `#5B6661` border `#1E2622` |

Padding `4px 10px`, radius 4, Plex Sans 11.5 / 500.

### Nav item

Label Plex Sans 12.5, count Plex Mono 10. Default: label `ink`, count `muted`; hover adds `row-hover` behind. **Selected turns both label and count `primary`, adds a `primary-wash` fill and a 2px `primary` bar on the leading edge, and sets the label to weight 500.** Radius `0 4px 4px 0`, padding `3px 8px`. Disabled is `disabled-ink`.

> Corrected in session 14. This file previously read "it does not add a fill or a bar", and gave the default count as `ink`. Artboard 10's specimen row and artboard 02's real left nav both show the fill, the bar and the muted count. The artboards win.

### Checkbox

**11px** box, radius 2. Off: `surface` fill, `outline` ring, label `muted`. Hover keeps the fill and darkens the ring to `#8A938D` light / `#7A8781` dark. On: `primary` fill, `primary` ring, label `ink`. Disabled: `disabled` fill and ring, label `disabled-ink`. Label is Plex Sans 12.

> Corrected in session 14: this file said 12px; both artboard specimens are 11px. The hover ring was not recorded here at all.

### Keycap

Plex Mono 9.5, radius 3, padding `4px 0 5px`, width **17px**. Default `fg muted / bg surface / border outline`. Selected inverts to a `primary` fill: **`#FFFFFF` text in light, `#08150F` in dark**. Disabled uses `disabled` fill and ring with `disabled-ink` text. Focus is the standard ring. No hover state.

> Corrected in session 14: this file said "near-black text" for both themes. That is the dark theme only — the light artboard is white on `#14705B`. It is the same polarity flip the evidence ramp makes at step 3, and it only applies where the accent is bright.

---

## 5 · Status and evidence

### Monograph status — four, ordered

`skeleton → drafted → sourced → reviewed`

| status | light bg/fg/ring | dark bg/fg/ring |
|---|---|---|
| skeleton | `#EFEFEA` `#5E6B65` `#DEE1DB` | `#1C2422` `#9AA79F` `#252E2A` |
| drafted | `#F5EBDD` `#A8681F` `#E8D6BC` | `#2A2015` `#DFA65C` `#40311D` |
| sourced | `#E6F0EC` `#14705B` `#C9E0D8` | `#122A24` `#57C4A4` `#1E4438` |
| reviewed | `#14705B` `#FFFFFF` `#14705B` | `#57C4A4` `#08150F` `#57C4A4` |

### Evidence — six levels on a four-step ramp

```
E1 traditional only    → ramp[0]
E2 in vitro            → ramp[1]
E3 in vivo             → ramp[1]
E4 human uncontrolled  → ramp[2]
E5 RCT                 → ramp[3]
E6 meta-analysis       → ramp[3]
```

| step | light bg/fg/ring | dark bg/fg/ring |
|---|---|---|
| 0 | `#E6F0EC` `#14705B` `#C9E0D8` | `#16211E` `#8FB8AA` `#2A3831` |
| 1 | `#BFDCD2` `#14705B` `#A9CCC1` | `#17352C` `#5FD3B0` `#2B5A4B` |
| 2 | `#4F9683` `#FFFFFF` `#4F9683` | `#2E7D66` `#EAF6F1` `#3E9C80` |
| 3 | `#14705B` `#FFFFFF` `#14705B` | `#6FD9B7` `#08150F` `#6FD9B7` |

The collapse is deliberate: the eye reads four bands of confidence, not six. The code (`E3`) sits beside the colour so the exact level stays recoverable. **Polarity flips at step 3** in both themes — that flip is what makes the top of the range read as arrival.

A monograph's headline evidence is the **maximum** across its indications.

### Severity — safety rows

| severity | bg | fg | ring |
|---|---|---|---|
| critical | `#F6E4E1` | `#A33A2E` | `#E8C9C3` |
| caution | `#F5EBDD` | `#A8681F` | `#E8D6BC` |
| note | `#EFEFEA` | `#5E6B65` | `#DEE1DB` |

### Reading state — references

| state | bg | fg | ring |
|---|---|---|---|
| read | `#E6F0EC` | `#14705B` | `#C9E0D8` |
| reading | `#F5EBDD` | `#A8681F` | `#E8D6BC` |
| queued | `#EFEFEA` | `#5E6B65` | `#DEE1DB` |

### Output kind

paper `#14705B` · talk `#16211D` · long-form `#A8681F` · release `#A8681F` · note `#5E6B65`

---

## 6 · The unsourced row

**The single most important visual rule in the application.**

Any claim row — vernacular, indication, constituent, safety finding — without a source renders:

- row background `warn-row` (`#FDF6EC` light, `#1F1A12` dark)
- a **4 × 16px** `secondary` mark, radius 1, in the leading `mk` column — see §7
- source cell reads `⚠ source needed` in `secondary`, never blank

> Corrected in session 16: this file said "a 2px `secondary` marker on the
> leading edge", which reads as a row border. Artboard 05 draws a 4 × 16px
> element inside the `mk` column §7 already reserves, and gives the row no
> border at all — the tint alone carries the row. The mark is present but
> transparent on a sourced row, so nothing shifts when one appears.

It follows into the section header (`7 · 1 unsourced`, count in `secondary`), the record rail, and the record header (`3 rows unsourced`). At the foot of the record:

> **3 rows unsourced** — Status cannot advance to `reviewed` while any claim row is missing a source.

That is a hard invariant, not a hint. Enforce it in the database layer, not only in the UI.

---

## 7 · Table column widths

Percentages of inner row width, gutters excluded. Use them; do not let content decide.

**corpus** — 936px inner
`name 39.8 · family 12.0 · part 8.8 · status 9.7 · ind 3.7 · evidence 16.2 · written 9.8`

**day log** — 1148px inner
`date 8.7 · day 3.3 · min 4.4 · floor 8.0 · deposited 75.6`

**indications** — 904px inner
`mk 0.5 · condition 30.8 · tradition 12.3 · region 12.3 · evidence 16.6 · source 27.5`

**library** — 752px inner
`mk 0.4 · status 10.3 · title 44.1 · authors 17.0 · doi 22.7 · year 5.5`

`mk` is the unsourced/selected marker column.

---

## 8 · Screens

Ten artboards. Read the file alongside this section — prose loses to pixels.

### 01 — system
Component library, rendered live from the CSS variables. Colour swatches, type ramp, one specimen of every component. Build this first; every later screen is assembled from parts proven here.

### 02 — today
Opens on launch. Stat row: current streak · longest · floor met (`118 / 140`) · minutes worked · floor-day toggle, all `display num`. Autosaving note (2s debounce, footer `autosaved 14:22 · entry 1,412`) with an explicit `Save entry` as well. Three **deposit** quick-add rows — monograph `Open` (primary), reference `Fetch` (secondary, calls Crossref), output `Add` (quiet). Last-fourteen-days table, header `1,025 min · 73 avg · 4 floor days`, today's row `row-focus`.

The **floor** is 20 minutes. A floor day is a success. The interface must never render one as a shortfall — the word `floor` in `secondary`, never a red mark, never an empty bar.

### 03 — corpus
208px filter rail: **status** · **family** (top six, then `all 19 families`) · **evidence level** E1–E6 · **flags** (`never published on`, `conservation concern`, `benefit-sharing absent`). Additive across groups, OR within a group. All filter state in the URL hash.

`find` box with live hit count, backed by FTS5. Table per §7. Header `38 monographs · 22 shown · sorted by first written`; footer `22 of 38 · 118 indications · 9 never published on` — that last figure is the gap query, permanently visible.

### 04 — the wall
The trophy cabinet. `27 outputs · 2024-01-02 → 2026-06-18 · newest first`, kind counts across the top, grouped by year newest-first. Cards: kind in its colour, date mono, title Fraunces 17, venue muted, plants italic. Outputs with no specific plant read `whole corpus` or `method, no plant` — upright and muted, never italic.

No pagination. No load-more. The length of the scroll is the point.

### 05 — monograph
The detail record, and the screen where the work actually happens.

Header: breadcrumb `corpus › monograph 07`, binomial in record-name type, authority upright, status pill, `Meliaceae / stem bark /` plus a one-line habitat note. Identity strip: `wfo-id` · `gbif key` · `first written` · `last touched`. Summary strip: `7 indications · 19 references bound · strongest evidence E5 RCT · 3 rows unsourced`.

Sections, each with a count, an `+ add` quiet button, and per-row sourcing:

- **summary** — prose at 74ch, `sources R1, R2, R6`, `rewritten <date>`
- **vernacular names** — name · language · region · source
- **indications** — condition · tradition · region · evidence chip · source
- **constituents** — compound · class · InChIKey (mono) · source
- **safety** — kind · finding · severity chip · source
- **preparation** — prose, sources plus field-note reference
- **benefit-sharing** — prose, `agreement on file · MTA-2025-014 · expires 2028-06`
- **references** — `R1`–`Rn`, citation, DOI, read state

224px sticky right rail: section jump list with counts, unsourced counts in `secondary`; `cited by your outputs`; `3 references queued, unread →`.

**Benefit-sharing is not optional chrome.** It records consent, named attribution and the agreement under which vernacular and preparation knowledge was collected. It appears on every monograph and `benefit-sharing absent` is a corpus filter flag.

### 06 — library
`214 references · 26 shown · newest first`, with `23 queued · 4 reading · 141 read`. Segmented status filter, a year range (2019–2026), a journal dropdown, and a **`Cited by nothing`** filter — 31 references that exist in the library but are bound to no monograph. Rows carry a `secondary` marker and `· cited by nothing` appended to the meta line. Footer `26 of 214 · 9 cited by nothing in view`. `Add by DOI` is the primary action.

384px detail rail for the selected reference: `reading` state, internal id (`ref 0187`), title with the binomial italic inline, full author list, a metadata table (journal, volume, year, DOI, type, access, added, read progress), then:

- **why this mattered** — a free-text note, editable in place, `last edited · 62 words`
- **cited by monographs** — which records use it and in which section
- **tags** — chips, `+ tag`
- footer `added 2026-07-02 · opened 4×`, actions `Bind to monograph` · `Mark read`

The *why this mattered* note is the reason to keep a library rather than a folder of PDFs. Do not cut it.

### 07 — overview
Four charts. `ledger.db · as of <date> · 14 months on record`. Stat row: monographs · references · outputs · current streak.

1. **Cumulative monographs** against the 250/year target line, with the shortfall as a filled band. Caption states the arithmetic plainly: `105 behind · 13.4 / month against 20.8 needed`.
2. **Days at the ledger** — twelve months of squares, four levels (`no entry` `#FFFFFF` · `20 min` `#DCEBE5` · `normal` `#63A28F` · `90 min+` `#14705B`). In dark, empty days are **hairline outlines rather than fills**, so absence reads as absence.
3. **Evidence held against publication status** — six evidence rows × `never published / drafted / published`. Caption: `137 traditional-only and case-report claims have never been published — the mass at top-left`.
4. **Deposits by kind** — true scale, not normalised. Caption: `notes are 91 % of all deposits · 3 published outputs in 14 months`.

This screen is designed to be uncomfortable. Charts 3 and 4 exist to show that private notes are not public work. **Do not soften them** — no encouraging copy, no rounding in your favour, no hiding the denominator.

### 08 — states
Six states, specified rather than left to chance. Build each as a real render, not a mock.

1. **First run** — 0 rows everywhere. Explains what a monograph is, offers `ledger seed --from ~/notes/plants.csv` or `N` for an empty skeleton. Footer shows real file size and `schema v4`.
2. **One record** — the table at n = 1, headers and footers intact, nothing collapsed.
3. **Overload** — 40 constituents, 22 vernacular names. Truncate with `+14 more · 28 constituents below`, sorted by assay.
4. **Unresolved name** — `Name not resolved — GBIF returned three candidates below the 0.90 threshold`, `confidence 0.42`, `queue 3 of 7`, candidates with GBIF keys and scores, actions `Accept top match` · `Enter name by hand` · `Keep in queue`.
5. **Broken streak** — streak reads `0`, `longest 96` stays. `The 41-day streak ended on 2026-08-20. Three days without an entry.` Missed days listed plainly. Actions `Log a floor day — 20 min` · `Open next skeleton`. Footer `counting resumes at 1`. No guilt copy, no flame iconography, no offer to restore the streak.
6. **No results** — `No monograph, no reference, no output mentions this name.` Shows what was searched and how fast (`searched 38 monographs · 312 references · 163 outputs · 11 ms`), the nearest corpus match with edit distance, and offers `New — <query>` with `resolves against GBIF on save`.

### 09 — capture
Three keyboard overlays. 772px wide, top 104px, scrim `rgba(14,21,18,0.62)`. Every overlay shows its own keycap legend along the bottom and closes on `esc`.

1. **Quick add** — a command line (`mono Khaya senegalensis --part bar`) parsing live into chips as you type. Resolved chips use `primary-wash`; the pending one is `secondary` with a **dashed** ring. Status `2 resolved · 1 pending`. Keys: `↵ create` · `⇥ complete part` · `esc dismiss`.
2. **DOI paste** — paste a DOI, Crossref resolves (`resolved in 240 ms`), title/authors/journal/volume fill in, binomials italic. Warns `not yet bound to a monograph`. Keys: `↵ save` · `⌫ discard` · `b bind to monograph` · `esc dismiss`.
3. **Inbox review** — the phone lines for a date, each numbered `1`–`6` with a keycap, routed to a destination (`monograph → Khaya senegalensis › safety`). Unclassified lines get `warn-row`, a `?` kind, a dashed destination box and `no match — choose destination`. Header counts `1 unclassified`. Keys: `1–6 accept` · `↑↓ move` · `e set destination` · `↵ accept all routed` · `esc dismiss`.

Global: `/` opens find. The app is usable from the keyboard alone during a work block — that is the whole design intent of this artboard.

### 10 — handoff
This document. Keep it in sync; it is what the next person (or the next you) builds from.
