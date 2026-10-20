// The one place the frontend talks to the Flask API. Every call is typed.
import type {
  Address,
  AddressInput,
  CartQuote,
  Category,
  CheckoutRequest,
  AdminOrder,
  AdminProduct,
  AdminReturn,
  CreateReturnRequest,
  OrderDetail,
  ReturnEligibility,
  ReturnRequestView,
  TrackingResult,
  HealthStatus,
  Policy,
  ProductDetail,
  ProductInput,
  ProductPage,
  ProductQuery,
  SandboxCard,
  SandboxSession,
  ShippingMethod,
  Ticket,
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
  newsletter: (email: string) => request<{ message: string }>("/newsletter", json("POST", { email })),
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

  // Checkout: the server creates a pending order and a Stripe page, and returns its URL.
  createCheckout: (body: CheckoutRequest) =>
    request<{ order_number: string; checkout_url: string }>("/checkout/session", json("POST", body)),
  // Cash on delivery: no payment page. The order is confirmed at once; checkout_url is our thank-you page.
  createCodOrder: (body: CheckoutRequest) =>
    request<{ order_number: string; checkout_url: string }>("/checkout/cod", json("POST", body)),
  // Sandbox provider: our own hosted payment page (used when PAYMENT_PROVIDER=sandbox).
  sandboxSession: (sessionId: string) => request<SandboxSession>(`/sandbox/sessions/${encodeURIComponent(sessionId)}`),
  sandboxPay: (sessionId: string, card: SandboxCard) =>
    request<{ redirect_url: string }>(`/sandbox/sessions/${encodeURIComponent(sessionId)}/pay`, json("POST", card)),

  // Tracking and returns. POST so the email never lands in URLs, logs or browser history.
  trackOrder: (order_number: string, email: string) =>
    request<TrackingResult>("/orders/track", json("POST", { order_number, email })),
  // email may be left out when logged in and the order belongs to the account.
  returnEligibility: (order_number: string, email?: string) =>
    request<ReturnEligibility>("/returns/eligibility", json("POST", { order_number, email })),
  createReturn: (body: CreateReturnRequest) => request<ReturnRequestView>("/returns", json("POST", body)),

  contact: (body: { name: string; email: string; order_number?: string; subject: string; message: string }) =>
    request<{ id: number }>("/support/contact", json("POST", body)),

  // Admin writes (browser only; Flask checks the admin role on every one).
  admin: {
    createProduct: (body: ProductInput) => request<AdminProduct>("/admin/products", json("POST", body)),
    updateProduct: (id: number, body: Partial<ProductInput>) => request<AdminProduct>(`/admin/products/${id}`, json("PATCH", body)),
    addVariant: (productId: number, body: { sku: string; size: string; color: string; stock: number; price_cents: number | null }) =>
      request<AdminProduct>(`/admin/products/${productId}/variants`, json("POST", body)),
    updateVariant: (id: number, body: { stock_change?: number; price_cents?: number; clear_price_override?: boolean }) =>
      request<AdminProduct>(`/admin/variants/${id}`, json("PATCH", body)),
    updateOrderStatus: (
      number: string,
      body: { status: string; note?: string; carrier?: string; tracking_number?: string; estimated_delivery?: string },
    ) => request<AdminOrder>(`/admin/orders/${encodeURIComponent(number)}/status`, json("POST", body)),
    markCashCollected: (number: string) =>
      request<AdminOrder>(`/admin/orders/${encodeURIComponent(number)}/cash-collected`, json("POST")),
    updateReturnStatus: (id: number, body: { status: string; note?: string }) =>
      request<AdminReturn>(`/admin/returns/${id}/status`, json("POST", body)),
    updateTicket: (id: number, body: { status?: string; priority?: string }) =>
      request<Ticket>(`/admin/tickets/${id}`, json("PATCH", body)),
    updatePolicy: (key: string, body: { title: string; summary: string; body: string }) =>
      request<{ key: string }>(`/admin/policies/${encodeURIComponent(key)}`, json("PUT", body)),
  },

  // Public, but only works with the payment session id the buyer got in their redirect URL.
  confirmation: (orderNumber: string, sessionId: string) =>
    request<OrderDetail>(
      `/orders/${encodeURIComponent(orderNumber)}/confirmation?session_id=${encodeURIComponent(sessionId)}`,
    ),
};

export { safeNextPath } from "@/lib/session-hint";

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
