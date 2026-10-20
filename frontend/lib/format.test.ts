import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { paymentSummary } from "./format";

describe("paymentSummary", () => {
  test("an unpaid cash-on-delivery order shows the amount due", () => {
    assert.equal(
      paymentSummary({ payment_method: "cod", payment_status: "unpaid", total_cents: 3095 }),
      "Cash on delivery · $30.95 due on delivery",
    );
  });

  test("without an amount it just names the method", () => {
    assert.equal(paymentSummary({ payment_method: "cod", payment_status: "unpaid", total_cents: null }), "Cash on delivery");
  });

  test("otherwise method and status", () => {
    assert.equal(paymentSummary({ payment_method: "cod", payment_status: "paid", total_cents: 3095 }), "Cash on delivery · Paid");
    assert.equal(paymentSummary({ payment_method: "card", payment_status: "refunded", total_cents: null }), "Card · Refunded");
  });
});
