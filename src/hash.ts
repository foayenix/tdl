// All filter state lives in the URL hash (DESIGN.md §8, artboard 03).
//
// `#/corpus?status=sourced,reviewed&family=Meliaceae&evidence=rct`
//
// Which means a filtered view is a place you can go back to, and the back
// button undoes a filter — both for free, and neither possible if the state
// lived in a variable.

export type HashState = {
  route: string;
  params: URLSearchParams;
};

export function readHash(): HashState {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [route = "", query = ""] = raw.split("?", 2);
  return { route, params: new URLSearchParams(query) };
}

/** The values of one filter group. Empty when the group is off. */
export function readList(params: URLSearchParams, key: string): string[] {
  const value = params.get(key);
  if (!value) return [];
  return value.split(",").filter(Boolean);
}

export function writeList(route: string, params: URLSearchParams, key: string, values: string[]): void {
  const next = new URLSearchParams(params);
  if (values.length) next.set(key, values.join(","));
  else next.delete(key);

  const query = next.toString();
  window.location.hash = query ? `/${route}?${query}` : `/${route}`;
}

/** Add or remove one value from a group, leaving the other groups alone. */
export function toggleInList(
  route: string,
  params: URLSearchParams,
  key: string,
  value: string,
): void {
  const current = readList(params, key);
  const next = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
  writeList(route, params, key, next);
}
