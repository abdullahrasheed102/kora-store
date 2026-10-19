// Static site structure. Category links live here (not fetched) so the header and footer can
// be part of the prerendered shell; the shop sidebar shows live counts from /api/categories.

export const SITE_NAME = "Kora Outfitters";
export const SITE_DESCRIPTION =
  "Everyday clothing made to last: organic cotton tees, linen shirts, merino knits and outerwear.";

export const NAV_CATEGORIES = [
  { name: "Tops", slug: "tops" },
  { name: "Bottoms", slug: "bottoms" },
  { name: "Outerwear", slug: "outerwear" },
  { name: "Footwear", slug: "footwear" },
  { name: "Accessories", slug: "accessories" },
  { name: "Gift Cards", slug: "gift-cards" },
] as const;

export const POLICY_LINKS = [
  { key: "shipping", title: "Shipping" },
  { key: "returns", title: "Returns & exchanges" },
  { key: "refunds", title: "Refunds" },
  { key: "cancellations", title: "Cancellations" },
  { key: "support_hours", title: "Support hours" },
] as const;

export const AUTHOR = { name: "Abdullah Rasheed", url: "https://abdullahrasheed.tech" };
