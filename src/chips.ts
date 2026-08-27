// The chips of DESIGN.md §5, built in one place so every screen agrees.

import { el } from "./dom";
import { evidenceCode, EVIDENCE_LABEL, EVIDENCE_RAMP, type Evidence } from "./evidence";

type Size = "sm" | undefined;

function size(extra: Size): string {
  return extra === "sm" ? " chip--sm" : "";
}

export function statusChip(status: string, small?: Size): HTMLElement {
  return el("span", { class: `chip chip--status-${status}${size(small)}` }, status);
}

export function severityChip(severity: string, small?: Size): HTMLElement {
  return el("span", { class: `chip chip--severity-${severity}${size(small)}` }, severity);
}

export function readStateChip(state: string, small?: Size): HTMLElement {
  return el("span", { class: `chip chip--read-${state}${size(small)}` }, state);
}

/**
 * `E5 RCT`. The code sits beside the colour so the exact level stays
 * recoverable, which is the whole reason six levels can share four steps.
 */
export function evidenceChip(level: Evidence, small?: Size): HTMLElement {
  const step = EVIDENCE_RAMP[level];
  return el(
    "span",
    { class: `chip chip--ev chip--ev${step}${size(small)}` },
    el("span", { class: "chip__code" }, evidenceCode(level)),
    el("span", { class: "chip__label" }, EVIDENCE_LABEL[level]),
  );
}
