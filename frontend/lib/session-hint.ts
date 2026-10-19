// Small, dependency-free helpers about the logged-in user's ROLE, for routing and display only.
// Kept free of imports so the proxy, server components and plain Node tests can all use them.

export type Role = "admin" | "customer";

/**
 * Read the "role" claim from the session JWT WITHOUT verifying its signature.
 *
 * That's safe only because of what we use it for: deciding where to send someone (proxy.ts) and
 * which icon to show (the header). It never decides what data anyone may see; Flask checks the
 * real role in the database on every API call. A forged hint just leads to a page that then
 * refuses to load any data.
 */
export function roleHint(token: string | undefined): Role | null {
  const payload = token?.split(".")[1];
  if (!payload) return null;
  try {
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const role = (JSON.parse(json) as { role?: unknown }).role;
    return role === "admin" || role === "customer" ? role : null;
  } catch {
    return null; // not a JWT we understand: treat as "unknown"
  }
}

/** Only allow redirects to our own pages. `?next=https://evil.example` must not work (open redirect). */
export function safeNextPath(next: string | null | undefined, fallback = "/account"): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : fallback;
}

/**
 * Where to go after logging in. Admins go to the admin dashboard (or the admin page they asked
 * for); customers go back to the page they came from, or their account. Neither is sent to the
 * other's area: an admin doesn't land on customer pages, a customer isn't sent into /admin.
 */
export function postLoginPath(role: Role, next: string | null | undefined): string {
  const target = safeNextPath(next, "");
  const isAdminPage = target === "/admin" || target.startsWith("/admin/");
  if (role === "admin") return isAdminPage ? target : "/admin";
  if (!target || isAdminPage) return "/account";
  return target;
}
