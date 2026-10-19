import { NextResponse, type NextRequest } from "next/server";

// Runs before /account pages render. It only checks that a session cookie EXISTS, which is
// cheap and early: logged-out visitors get a real redirect instead of a flash of the page.
// It does NOT check the cookie is valid. Flask does that on every API call, so a fake cookie
// gets past this check but still sees no data (see lib/api-server.ts requireUser).
export function proxy(request: NextRequest) {
  if (!request.cookies.has("access_token_cookie")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/account", "/account/:path*"] };
