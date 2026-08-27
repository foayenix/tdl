// The evidence enum, its E-codes, its labels and the four-step ramp.
// Do not rename these values (BUILD.md §4).

export const EVIDENCE = [
  "traditional_only",
  "in_vitro",
  "in_vivo",
  "human_uncontrolled",
  "rct",
  "meta_analysis",
] as const;

export type Evidence = (typeof EVIDENCE)[number];

export const EVIDENCE_LABEL: Record<Evidence, string> = {
  traditional_only: "traditional only",
  in_vitro: "in vitro",
  in_vivo: "in vivo",
  human_uncontrolled: "human uncontrolled",
  rct: "RCT",
  meta_analysis: "meta-analysis",
};

/** Six levels on a four-step ramp. Polarity flips at step 3 (DESIGN.md §5). */
export const EVIDENCE_RAMP: Record<Evidence, 0 | 1 | 2 | 3> = {
  traditional_only: 0,
  in_vitro: 1,
  in_vivo: 1,
  human_uncontrolled: 2,
  rct: 3,
  meta_analysis: 3,
};

export function evidenceCode(level: Evidence): string {
  return `E${EVIDENCE.indexOf(level) + 1}`;
}

export const STATUSES = ["skeleton", "drafted", "sourced", "reviewed"] as const;
export type Status = (typeof STATUSES)[number];
