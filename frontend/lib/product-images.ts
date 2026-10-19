// Which product photo to show where. Pure functions (no React), so they're easy to unit test.
// Photos arrive gradually, so every function must cope with a product having some, or none.
import type { ProductImage } from "./types";

/** The photo of one colour of the garment, if it has been taken yet. */
export function colorPhoto(images: ProductImage[], color: string): ProductImage | undefined {
  return images.find((image) => image.kind === "product" && image.color === color);
}

/**
 * Product card: the photo of the first colour (in swatch order) that has one, and the lifestyle
 * photo to fade to on hover. With only a lifestyle photo, that becomes the main one.
 */
export function cardImages(images: ProductImage[], colors: string[]): { main?: ProductImage; hover?: ProductImage } {
  const main = colors.map((color) => colorPhoto(images, color)).find(Boolean);
  const lifestyle = images.find((image) => image.kind === "lifestyle");
  return main ? { main, hover: lifestyle } : { main: lifestyle };
}

export type GalleryItem = { kind: "photo"; image: ProductImage } | { kind: "placeholder"; color: string };

/**
 * Product page gallery for the chosen colour: that colour's photo first (or a placeholder in
 * that colour if it has no photo yet), then the lifestyle photo.
 */
export function galleryFor(images: ProductImage[], color: string): GalleryItem[] {
  const photo = colorPhoto(images, color);
  const lifestyle = images.filter((image) => image.kind === "lifestyle");
  return [
    photo ? { kind: "photo", image: photo } : { kind: "placeholder", color },
    ...lifestyle.map((image) => ({ kind: "photo" as const, image })),
  ];
}
