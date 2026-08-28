// The browser preview's stand-in for Tauri's `invoke`.
//
// It answers from a dump produced by `cargo run --bin preview_dump`, which
// calls the same functions the window calls — so what you see here is what the
// real queries returned against a real SQLite file, not a mock-up.
//
// What it cannot do is write. Anything that would change the database says so
// and changes nothing; the preview is for looking at the screens, and the app
// is for using them.

type Dump = Record<string, unknown> & {
  records: Record<string, Record<string, unknown>>;
  corpus: { rows: Array<Record<string, unknown>> };
};

declare global {
  interface Window {
    __LEDGER_PREVIEW__?: Dump;
  }
}

export class PreviewOnly extends Error {}

function dump(): Dump {
  const data = window.__LEDGER_PREVIEW__;
  if (!data) throw new Error("the preview data did not load");
  return data;
}

/** Substring search over the dumped corpus, so `find` does something real. */
function search(query: string) {
  const data = dump();
  const needle = query.trim().toLowerCase();
  const counts = data.nav_counts as Record<string, number>;

  const searched = {
    monographs_searched: data.corpus.rows.length,
    references_searched: counts.references ?? 0,
    outputs_searched: counts.outputs ?? 0,
    milliseconds: 0,
  };

  if (!needle) return { monograph_ids: [], hits: 0, ...searched };

  const ids: number[] = [];
  let hits = 0;

  for (const row of data.corpus.rows) {
    const id = row.id as number;
    const record = data.records[String(id)];
    // Everything the FTS index covers: the record and its claim rows.
    const haystacks: string[] = [
      String(row.accepted_name ?? ""),
      String(row.family ?? ""),
      String(row.part ?? ""),
    ];

    const claims = (record?.claims ?? {}) as Record<string, Array<{ cells: (string | null)[] }>>;
    for (const rows of Object.values(claims)) {
      for (const claim of rows) haystacks.push(claim.cells.filter(Boolean).join(" "));
    }
    const full = (record?.record ?? {}) as Record<string, unknown>;
    haystacks.push(String(full.summary ?? ""), String(full.preparation ?? ""));

    const matched = haystacks.filter((text) => text.toLowerCase().includes(needle)).length;
    if (matched) {
      hits += matched;
      ids.push(id);
    }
  }

  return { monograph_ids: ids, hits, ...searched };
}

function nearest(query: string): [string, number] | null {
  const names = dump()
    .corpus.rows.map((row) => String(row.accepted_name ?? ""))
    .filter(Boolean);
  if (!names.length) return null;

  const distance = (a: string, b: string) => {
    let previous = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 0; i < a.length; i += 1) {
      const current = [i + 1];
      for (let j = 0; j < b.length; j += 1) {
        current.push(
          Math.min(
            (previous[j + 1] ?? 0) + 1,
            (current[j] ?? 0) + 1,
            (previous[j] ?? 0) + (a[i] === b[j] ? 0 : 1),
          ),
        );
      }
      previous = current;
    }
    return previous[b.length] ?? 0;
  };

  const lowered = query.toLowerCase();
  let best = names[0] as string;
  let shortest = distance(lowered, best.toLowerCase());
  for (const name of names.slice(1)) {
    const d = distance(lowered, name.toLowerCase());
    if (d < shortest) {
      best = name;
      shortest = d;
    }
  }
  return [best, shortest];
}

/* ── preview chrome ──────────────────────────────────────────────────────
   Not part of the app. It says once, and stays saying, what this page is:
   the app's own screens over a frozen answer set. When a write is refused
   the app reports it where the click happened, so this line does not. */

const CHROME = `
.preview-chrome {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 99;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 640px;
  padding: 9px 14px;
  border: 1px solid var(--secondary-ring, #e8d6bc);
  border-radius: 2px;
  background: var(--warn-row, #fdf6ec);
  color: var(--ink, #16211d);
  font-family: var(--font-sans, system-ui), sans-serif;
  font-size: 13px;
  line-height: 1.4;
}
.preview-chrome b {
  font-family: var(--font-mono, ui-monospace), monospace;
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
  color: var(--secondary, #a8681f);
}
`;

let chrome: HTMLElement | null = null;

const RESTING = "Real queries, run against a demo ledger and frozen into this page. Reading works; writing does not.";

function banner(): HTMLElement {
  if (chrome) return chrome;
  const style = document.createElement("style");
  style.textContent = CHROME;
  document.head.appendChild(style);

  chrome = document.createElement("aside");
  chrome.className = "preview-chrome";
  chrome.innerHTML = `<b>read-only preview</b><span></span>`;
  (chrome.lastElementChild as HTMLElement).textContent = RESTING;
  document.body.appendChild(chrome);
  return chrome;
}


if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => banner(), { once: true });
  } else {
    banner();
  }
}

export async function previewInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const data = dump();
  const id = String(args?.id ?? "");
  const record = data.records[id];

  switch (command) {
    case "ledger_status":
      return data.status as T;
    case "ledger_nav_counts":
      return data.nav_counts as T;
    case "ledger_today":
      return data.today as T;
    case "ledger_note":
      return data.note as T;
    case "ledger_day_log":
      return data.day_log as T;
    case "ledger_corpus":
      return data.corpus as T;
    case "ledger_wall":
      return data.wall as T;
    case "ledger_broken_streak":
      return data.broken_streak as T;
    case "ledger_next_skeleton":
      return data.next_skeleton as T;

    case "ledger_record":
      if (!record) throw new Error(`no monograph ${id}`);
      return record.record as T;
    case "ledger_claims":
      return ((record?.claims as Record<string, unknown>)?.[String(args?.table)] ?? []) as T;
    case "ledger_section_sources":
      return ((record?.section_sources as Record<string, unknown>)?.[String(args?.section)] ?? []) as T;
    case "ledger_record_references":
      return (record?.references ?? []) as T;
    case "ledger_cited_by_outputs":
      return (record?.cited_by_outputs ?? []) as T;
    case "ledger_queued_reading":
      return (record?.queued_reading ?? { count: 0, oldest: null }) as T;
    case "ledger_unsourced_by_section":
      return (record?.unsourced_by_section ?? []) as T;
    case "ledger_benefit_sharing":
      return (record?.benefit_sharing ?? { present: false }) as T;
    case "ledger_queue_position":
      return (record?.queue_position ?? null) as T;

    case "ledger_search":
      return search(String(args?.query ?? "")) as T;
    case "ledger_nearest_name":
      return nearest(String(args?.query ?? "")) as T;

    default:
      // Every write lands here. The preview reads a dump; it has nothing to
      // write to, and pretending otherwise would be the one thing worse than
      // saying so.
      throw new PreviewOnly(
        "This is a read-only preview — run the app to change anything.",
      );
  }
}
