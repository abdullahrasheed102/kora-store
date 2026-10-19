// Site photography. Static imports let Next.js read each image's width and height at build time
// (no layout shift) and make a tiny blurred placeholder (placeholder="blur") automatically.
// Files come from `npm run images` (scripts/optimize-images.mjs).
import type { StaticImageData } from "next/image";

import about from "@/public/images/site/about.webp";
import accessories from "@/public/images/site/category-accessories.webp";
import bottoms from "@/public/images/site/category-bottoms.webp";
import footwear from "@/public/images/site/category-footwear.webp";
import giftCards from "@/public/images/site/category-gift-cards.webp";
import outerwear from "@/public/images/site/category-outerwear.webp";
import tops from "@/public/images/site/category-tops.webp";
import hero from "@/public/images/site/hero.webp";

export type SitePhoto = {
  src: StaticImageData;
  // Describes what's IN the photo, for people using screen readers (not "image of…", not keywords).
  alt: string;
  // Which part to keep when the photo is cropped to a different shape (CSS object-position).
  focus?: string;
};

export const HERO_PHOTO: SitePhoto = {
  src: hero,
  alt: "A couple walking along a tree-lined city street in autumn, one in a camel coat, the other in a black puffer jacket.",
  focus: "70% center", // keep the couple in view when phones crop the sides
};

export const ABOUT_PHOTO: SitePhoto = {
  src: about,
  alt: "A sunlit design studio: a wooden worktable covered in fabric swatches, paper patterns and sketches pinned to the wall.",
};

// Category photos by category slug. A category without one gets a styled banner and placeholder art.
export const CATEGORY_PHOTOS: Partial<Record<string, SitePhoto>> = {
  tops: {
    src: tops,
    alt: "A man in an oatmeal crew-neck sweater sitting by a bright window, holding a mug.",
    focus: "center 30%",
  },
  bottoms: {
    src: bottoms,
    alt: "Light-wash straight-leg jeans and white sneakers, standing on a pale wooden floor.",
    focus: "center 40%",
  },
  outerwear: {
    src: outerwear,
    alt: "A man in a long camel overcoat and grey beanie in a misty autumn park.",
    focus: "center 25%",
  },
  footwear: {
    src: footwear,
    alt: "Tan suede Chelsea boots and white leather sneakers on stone steps scattered with autumn leaves.",
    focus: "center 60%",
  },
  accessories: {
    src: accessories,
    alt: "A canvas tote bag, a mustard knit beanie, a brown leather belt and cream socks on a wooden table.",
    focus: "center 45%",
  },
  "gift-cards": {
    src: giftCards,
    alt: "A kraft gift box holding a folded cream sweater, beside a wrapped present, eucalyptus and dried orange slices.",
    focus: "center 55%",
  },
};
