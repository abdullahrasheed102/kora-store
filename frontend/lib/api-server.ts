// Server-only API calls that act as the logged-in user. They forward the browser's cookies to
// Flask, because a server-to-server request doesn't carry them automatically.
// `server-only` makes the build fail if a client component ever imports this file.
import "server-only";

import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { ApiError, request } from "@/lib/api";

import type {
  Address,
  AdminOrder,
  AdminOrderRow,
  AdminProduct,
  AdminProductRow,
  AdminReturn,
  AdminStats,
  OrderDetail,
  OrderSummary,
  Paged,
  Ticket,
  User,
} from "@/lib/types";

async function authed<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  return request<T>(path, { headers: { Cookie: cookieHeader } });
}

/** The logged-in user, or null. Never throws for "not logged in" or an expired session. */
export async function getCurrentUser(): Promise<User | null> {
  try {
    return (await authed<{ user: User | null }>("/auth/me")).user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null; // expired / invalid cookie
    throw error;
  }
}

/** For account pages: the user, or a redirect to the login page. */
export async function requireUser(next: string): Promise<User> {
  const user = await getCurrentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(next)}`);
  return user;
}

export const accountApi = {
  addresses: () => authed<Address[]>("/account/addresses"),
  orders: () => authed<OrderSummary[]>("/account/orders"),
  order: (orderNumber: string) => authed<OrderDetail>(`/account/orders/${encodeURIComponent(orderNumber)}`),
};

/**
 * For customer account pages: like requireUser, but admins are sent to /admin. proxy.ts already
 * does this before rendering; this second check covers sessions without the role hint (e.g. logged
 * in before it existed) and uses the role from the database.
 */
export async function requireCustomer(next: string): Promise<User> {
  const user = await requireUser(next);
  if (user.role === "admin") redirect("/admin");
  return user;
}

/**
 * For admin pages: logged-out visitors go to login; logged-in non-admins get a 404, so the admin
 * area doesn't even admit it exists. (Every admin API call is ALSO checked by Flask; this is the
 * page-level courtesy, not the security boundary.)
 */
export async function requireAdmin(next: string): Promise<User> {
  const user = await requireUser(next);
  if (user.role !== "admin") notFound();
  return user;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== "") search.set(key, String(value));
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const adminApi = {
  stats: () => authed<AdminStats>("/admin/stats"),
  products: (params: { q?: string; active?: string; page?: number }) =>
    authed<Paged<AdminProductRow>>(`/admin/products${query(params)}`),
  product: (id: string) => authed<AdminProduct>(`/admin/products/${encodeURIComponent(id)}`),
  orders: (params: { q?: string; status?: string; page?: number }) =>
    authed<Paged<AdminOrderRow>>(`/admin/orders${query(params)}`),
  order: (number: string) => authed<AdminOrder>(`/admin/orders/${encodeURIComponent(number)}`),
  returns: (params: { status?: string; page?: number }) => authed<Paged<AdminReturn>>(`/admin/returns${query(params)}`),
  tickets: (params: { status?: string; page?: number }) => authed<Paged<Ticket>>(`/admin/tickets${query(params)}`),
};
