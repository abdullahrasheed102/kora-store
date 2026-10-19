// The proxy's redirects, tested as a plain function with real NextRequest objects.
import assert from "node:assert/strict";
import { test } from "node:test";

import { NextRequest } from "next/server";

import { proxy } from "./proxy";

function sessionFor(role: string): string {
  const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256" })}.${encode({ sub: "1", role })}.sig`;
}

function visit(path: string, token?: string) {
  const headers = token ? { cookie: `access_token_cookie=${token}` } : undefined;
  return proxy(new NextRequest(new URL(path, "http://localhost:3000"), { headers }));
}

test("an admin opening /account is redirected to /admin before it renders", () => {
  for (const path of ["/account", "/account/orders", "/account/orders/KO-1001", "/account/addresses"]) {
    const response = visit(path, sessionFor("admin"));
    assert.equal(response.status, 307, path);
    assert.equal(response.headers.get("location"), "http://localhost:3000/admin", path);
  }
});

test("a customer opening /account is let through", () => {
  assert.equal(visit("/account", sessionFor("customer")).headers.get("location"), null);
});

test("an admin opening /admin is let through", () => {
  assert.equal(visit("/admin/orders", sessionFor("admin")).headers.get("location"), null);
});

test("no session cookie: sent to login, remembering the page", () => {
  const response = visit("/account/addresses");
  assert.equal(response.headers.get("location"), "http://localhost:3000/login?next=%2Faccount%2Faddresses");
});
