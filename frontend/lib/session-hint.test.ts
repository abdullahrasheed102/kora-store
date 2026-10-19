// Run with: npm test   (Node's built-in test runner; tsx lets it read TypeScript)
import assert from "node:assert/strict";
import { test } from "node:test";

import { postLoginPath, roleHint, safeNextPath } from "./session-hint";

function fakeJwt(claims: object): string {
  const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(claims)}.signature`;
}

test("admin login goes to /admin", () => {
  assert.equal(postLoginPath("admin", null), "/admin");
  assert.equal(postLoginPath("admin", "/account"), "/admin"); // never the customer pages
  assert.equal(postLoginPath("admin", "/checkout"), "/admin");
  assert.equal(postLoginPath("admin", "/admin/orders/KO-1003"), "/admin/orders/KO-1003"); // the admin page asked for
});

test("customer login goes back where they came from, or /account", () => {
  assert.equal(postLoginPath("customer", null), "/account");
  assert.equal(postLoginPath("customer", "/checkout"), "/checkout");
  assert.equal(postLoginPath("customer", "/account/addresses"), "/account/addresses");
  assert.equal(postLoginPath("customer", "/admin"), "/account"); // not sent into a 404
});

test("login never redirects off-site", () => {
  for (const next of ["https://evil.example", "//evil.example", "/\\evil.example"]) {
    assert.equal(postLoginPath("customer", next), "/account");
    assert.equal(postLoginPath("admin", next), "/admin");
    assert.equal(safeNextPath(next), "/account");
  }
});

test("roleHint reads the role claim", () => {
  assert.equal(roleHint(fakeJwt({ sub: "1", role: "admin" })), "admin");
  assert.equal(roleHint(fakeJwt({ sub: "2", role: "customer" })), "customer");
  assert.equal(roleHint(fakeJwt({ sub: "3" })), null); // sessions from before the hint existed
  assert.equal(roleHint(fakeJwt({ role: "superuser" })), null);
  assert.equal(roleHint("not-a-jwt"), null);
  assert.equal(roleHint(undefined), null);
});
