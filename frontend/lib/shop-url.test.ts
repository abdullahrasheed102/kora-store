import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { parseShopFilters, shopHref, tagLabel } from "./shop-url";

describe("tags in the shop URL", () => {
  test("a well-formed tag is read from the URL", () => {
    assert.equal(parseShopFilters({ tag: "autumn-edit" }).tag, "autumn-edit");
  });

  test("a malformed tag is dropped instead of sent to the API", () => {
    assert.equal(parseShopFilters({ tag: "Autumn Edit" }).tag, undefined);
    assert.equal(parseShopFilters({ tag: "<script>" }).tag, undefined);
  });

  test("the tag survives building a filtered link", () => {
    assert.equal(shopHref("outerwear", { tag: "new", sort: "price_asc" }), "/shop/outerwear?tag=new&sort=price_asc");
  });

  test("known tags have friendly names, others are labelled as tags", () => {
    assert.equal(tagLabel("autumn-edit"), "The Autumn Edit");
    assert.equal(tagLabel("spring-sale"), "Tag: spring-sale");
  });
});
