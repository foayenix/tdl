import { append, el } from "../dom";
import { migrate } from "../ledger";

/** Does this error mean there is simply no ledger yet? */
export function isMissingLedger(error: string): boolean {
  return error.includes("no ledger at");
}

/**
 * The state before there is anything to record.
 *
 * The app ships a sidecar that carries `schema/` precisely so it can migrate
 * on a machine that has never had Python. Telling someone who has just
 * double-clicked a .dmg to go and run `ledger migrate` in a terminal spends
 * that for nothing — so this offers the button instead.
 */
export function renderFirstRun(root: HTMLElement, error: string, done: () => void): void {
  const path = error.replace(/^no ledger at /, "").replace(/\. Run.*$/, "");

  const card = el("section", { class: "firstrun" });
  append(
    card,
    el("p", { class: "label" }, "no ledger yet"),
    el(
      "h1",
      { class: "board-title" },
      "Nothing has been recorded here.",
    ),
    el(
      "p",
      { class: "body firstrun__blurb" },
      "One SQLite file holds every entry, monograph and reference. " +
        "It does not exist yet; creating it takes a moment and nothing else.",
    ),
    el("p", { class: "numeric firstrun__path" }, path),
  );

  const action = el("button", { class: "button", type: "button" }, "Create the ledger");
  const note = el("p", { class: "body firstrun__note" });

  action.addEventListener("click", () => {
    action.setAttribute("disabled", "");
    action.textContent = "creating…";
    note.textContent = "";
    void migrate()
      .then(() => done())
      .catch((problem: unknown) => {
        action.removeAttribute("disabled");
        action.textContent = "Create the ledger";
        note.textContent = String(problem);
        note.className = "body firstrun__note is-trouble";
      });
  });

  append(card, action, note);
  root.appendChild(card);
}
