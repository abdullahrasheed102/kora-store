// The one place the frontend talks to the Flask API. Every call is typed.
import type {
  Address,
  AddressInput,
  CartQuote,
  Category,
  HealthStatus,
  Policy,
  ProductDetail,
  ProductPage,
  ProductQuery,
  ShippingMethod,
  User,
} from "@/lib/types";

/** An error response from the API: { "error": { "code", "message" } }. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// On the server (server components) we call Flask directly: it's a server-to-server request.
// In the browser we use a relative "/api/..." URL, which next.config.ts rewrites to Flask.
function baseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.BACKEND_URL ?? "http://localhost:5000";
  }
  return "";
}

/** The CSRF token the backend put in a readable cookie (the session cookie itself is httpOnly). */
function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrf_access_token="))
    ?.split("=")[1];
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? "GET";
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (method !== "GET") {
    // Copying the cookie into a header proves the request came from our own pages:
    // other sites can make the browser send our cookies, but can't read them.
    const token = csrfToken();
    if (token) headers.set("X-CSRF-TOKEN", token);
  }
  const response = await fetch(`${baseUrl()}/api${path}`, { ...init, headers });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error ?? {};
    throw new ApiError(response.status, error.code ?? "unknown_error", error.message ?? response.statusText);
  }
  return body as T;
}

export function toSearchParams(query: ProductQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === "") continue;
    // Lists become repeated keys: size=S&size=M, which the backend reads as a list.
    for (const item of Array.isArray(value) ? value : [value]) params.append(key, String(item));
  }
  return params;
}

/** A JSON request body. Every write sends JSON (the backend refuses anything else). */
function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

export const api = {
  products: (query: ProductQuery = {}) => request<ProductPage>(`/products?${toSearchParams(query)}`),
  product: (slug: string) => request<ProductDetail>(`/products/${encodeURIComponent(slug)}`),
  categories: () => request<Category[]>("/categories"),
  policies: () => request<Policy[]>("/policies"),
  policy: (key: string) => request<Policy>(`/policies/${encodeURIComponent(key)}`),
  health: () => request<HealthStatus>("/health"),

  // Cart: only ids and quantities go up; prices and totals come back from the server.
  quoteCart: (items: { variant_id: number; quantity: number }[], shipping_method: ShippingMethod, signal?: AbortSignal) =>
    request<CartQuote>("/cart/quote", { ...json("POST", { items, shipping_method }), signal }),

  // Auth and account (browser only: these rely on the browser's cookies).
  signup: (body: { email: string; password: string; name: string }) =>
    request<{ user: User }>("/auth/signup", json("POST", body)),
  login: (body: { email: string; password: string }) => request<{ user: User }>("/auth/login", json("POST", body)),
  logout: () => request<{ ok: true }>("/auth/logout", json("POST")),
  createAddress: (body: AddressInput) => request<Address>("/account/addresses", json("POST", body)),
  updateAddress: (id: number, body: AddressInput) => request<Address>(`/account/addresses/${id}`, json("PUT", body)),
  deleteAddress: (id: number) => request<void>(`/account/addresses/${id}`, json("DELETE")),
};

/** Only allow redirects to our own pages. `?next=https://evil.example` must not work (open redirect). */
export function safeNextPath(next: string | null | undefined, fallback = "/account"): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : fallback;
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
