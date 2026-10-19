import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { cardImages, galleryFor } from "./product-images";
import type { ProductImage } from "./types";

const photo = (color: string): ProductImage => ({
  url: `/images/products/tee-${color.toLowerCase()}.webp`,
  alt_text: `Tee in ${color}`,
  kind: "product",
  color,
});
const lifestyle: ProductImage = { url: "/images/products/tee-lifestyle.webp", alt_text: "Worn", kind: "lifestyle", color: null };

describe("cardImages", () => {
  test("uses the first colour that has a photo, and the lifestyle photo for hover", () => {
    // Black (first swatch) isn't photographed yet, so Olive is shown.
    const { main, hover } = cardImages([lifestyle, photo("Olive"), photo("White")], ["Black", "Olive", "White"]);
    assert.equal(main?.color, "Olive");
    assert.equal(hover, lifestyle);
  });

  test("no hover photo without a lifestyle photo", () => {
    assert.deepEqual(cardImages([photo("Black")], ["Black"]), { main: photo("Black"), hover: undefined });
  });

  test("a lifestyle photo alone becomes the main photo", () => {
    assert.deepEqual(cardImages([lifestyle], ["Black"]), { main: lifestyle });
  });

  test("no photos at all: nothing, so the card shows the placeholder", () => {
    assert.deepEqual(cardImages([], ["Black"]), { main: undefined });
  });
});

describe("galleryFor", () => {
  test("the chosen colour's photo comes first, then the lifestyle photo", () => {
    const gallery = galleryFor([photo("Black"), photo("Olive"), lifestyle], "Olive");
    assert.deepEqual(gallery, [
      { kind: "photo", image: photo("Olive") },
      { kind: "photo", image: lifestyle },
    ]);
  });

  test("a colour without a photo gets a placeholder in that colour", () => {
    assert.deepEqual(galleryFor([photo("Black"), lifestyle], "White"), [
      { kind: "placeholder", color: "White" },
      { kind: "photo", image: lifestyle },
    ]);
  });

  test("an unphotographed product is just the placeholder", () => {
    assert.deepEqual(galleryFor([], "Natural"), [{ kind: "placeholder", color: "Natural" }]);
  });
});
