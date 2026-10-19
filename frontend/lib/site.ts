// Static site structure. Category links live here (not fetched) so the header and footer can
// be part of the prerendered shell; the shop sidebar shows live counts from /api/categories.

export const SITE_NAME = "Kora Outfitters";
export const SITE_DESCRIPTION =
  "Everyday clothing made to last: organic cotton tees, linen shirts, merino knits and outerwear.";

export const NAV_CATEGORIES = [
  { name: "Tops", slug: "tops", blurb: "Tees, shirts and knits in organic cotton, linen and merino." },
  { name: "Bottoms", slug: "bottoms", blurb: "Denim, chinos, skirts and joggers, cut to fit well." },
  { name: "Outerwear", slug: "outerwear", blurb: "Coats and shells for cold mornings and wet days." },
  { name: "Footwear", slug: "footwear", blurb: "Leather sneakers and suede boots, made to be resoled." },
  { name: "Accessories", slug: "accessories", blurb: "Totes, belts, beanies and socks to finish the look." },
  { name: "Gift Cards", slug: "gift-cards", blurb: "Delivered by email, never expires. Let them choose." },
] as const;

// Names for the tags that drive homepage sections, used as page titles on /shop?tag=...
// Any other tag still works; it's shown as "Tag: <tag>".
export const TAG_LABELS: Record<string, string> = {
  new: "New for autumn",
  bestseller: "Bestsellers",
  "autumn-edit": "The Autumn Edit",
};

// The AI assistant (Phase 8). Until it's live, the homepage shows "Coming soon".
// To switch it on: set NEXT_PUBLIC_ASSISTANT_ENABLED=true (and point href at the chat) and rebuild.
export const ASSISTANT = {
  name: "Kora",
  enabled: process.env.NEXT_PUBLIC_ASSISTANT_ENABLED === "true",
  href: "/assistant",
} as const;

export const ABOUT_LINK = { href: "/about", title: "About Kora" } as const;

export const HELP_LINKS = [
  { href: "/track", title: "Track your order" },
  { href: "/returns", title: "Start a return" },
  { href: "/contact", title: "Contact us" },
] as const;

export const POLICY_LINKS = [
  { key: "shipping", title: "Shipping" },
  { key: "returns", title: "Returns & exchanges" },
  { key: "refunds", title: "Refunds" },
  { key: "cancellations", title: "Cancellations" },
  { key: "support_hours", title: "Support hours" },
] as const;

export const AUTHOR = { name: "Abdullah Rasheed", url: "https://abdullahrasheed.tech" };
