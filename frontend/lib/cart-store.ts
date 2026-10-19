// The cart lives in the browser's localStorage: just variant ids and quantities, never prices.
// This is a tiny store for React's useSyncExternalStore: components re-render when it changes,
// and other open tabs stay in sync through the "storage" event.

export type CartLine = { variantId: number; quantity: number };

const STORAGE_KEY = "kora-cart-v1";
export const MAX_QUANTITY = 10; // same limit as the backend (app/pricing.py)
const EMPTY: CartLine[] = [];

let cache: { raw: string | null; lines: CartLine[] } = { raw: null, lines: EMPTY };
const listeners = new Set<() => void>();

function parse(raw: string | null): CartLine[] {
  try {
    const value: unknown = JSON.parse(raw ?? "[]");
    if (!Array.isArray(value)) return EMPTY;
    // localStorage can be edited by the user: keep only well-formed lines.
    return value.filter(
      (line): line is CartLine =>
        Number.isInteger(line?.variantId) && Number.isInteger(line?.quantity) && line.quantity > 0,
    );
  } catch {
    return EMPTY;
  }
}

function getSnapshot(): CartLine[] {
  let raw: string | null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return cache.lines; // storage blocked (private mode): keep the in-memory cart
  }
  // Return the same array object while nothing changed, or React would re-render forever.
  if (raw !== cache.raw) cache = { raw, lines: parse(raw) };
  return cache.lines;
}

function getServerSnapshot(): CartLine[] {
  return EMPTY; // the server has no localStorage; the real cart appears after hydration
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

function setLines(lines: CartLine[]): void {
  const raw = JSON.stringify(lines);
  try {
    localStorage.setItem(STORAGE_KEY, raw);
  } catch {
    // storage full or blocked: the cart still works for this page view
  }
  cache = { raw, lines };
  listeners.forEach((listener) => listener());
}

export const cartStore = { subscribe, getSnapshot, getServerSnapshot, setLines };
