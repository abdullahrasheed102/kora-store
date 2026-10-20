import { NextResponse, type NextRequest } from "next/server";

import { roleHint } from "@/lib/session-hint";

const SESSION_COOKIE = "access_token_cookie";

// Runs BEFORE /account and /admin pages render, so a redirect happens before anything is drawn.
// These are optimistic, routing-only checks on the cookie. They don't verify the token; Flask
// does that (and checks the real role in the database) on every API call the page makes.
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const token = request.cookies.get(SESSION_COOKIE)?.value;

  if (!token) {
    const login = new URL("/login", request.url);
    // Keep the query too, e.g. /account?email_confirmed=1 after confirming on another device.
    login.searchParams.set("next", pathname + search);
    return NextResponse.redirect(login);
  }

  // Admins don't use the customer account pages: send them to their dashboard instead,
  // before the customer page has a chance to flash on screen.
  const isAccountPage = pathname === "/account" || pathname.startsWith("/account/");
  if (isAccountPage && roleHint(token) === "admin") {
    return NextResponse.redirect(new URL("/admin", request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/account", "/account/:path*", "/admin", "/admin/:path*", "/check-email"] };
