// Server-only API calls that act as the logged-in user. They forward the browser's cookies to
// Flask, because a server-to-server request doesn't carry them automatically.
// `server-only` makes the build fail if a client component ever imports this file.
import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, request } from "@/lib/api";
import type { Address, OrderDetail, OrderSummary, User } from "@/lib/types";

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
