// Vanilla DOM, decided in session 12. These four helpers are the whole of it —
// there is no framework here and there is not going to be one.

type Attributes = Record<string, string | number | boolean | undefined>;
type Child = Node | string | null | undefined | false;

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attributes: Attributes = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);

  for (const [name, value] of Object.entries(attributes)) {
    if (value === undefined || value === false) continue;
    if (value === true) node.setAttribute(name, "");
    else node.setAttribute(name, String(value));
  }

  append(node, ...children);
  return node;
}

export function append(parent: Node, ...children: Child[]): void {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    parent.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
}

export function clear(node: Node): void {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/** A botanical name is always italic; the authority string never is. */
export function binomial(name: string, authority?: string | null): DocumentFragment {
  const fragment = document.createDocumentFragment();
  append(fragment, el("span", { class: "binomial" }, name));
  if (authority) append(fragment, " ", el("span", { class: "authority" }, authority));
  return fragment;
}
