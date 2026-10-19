// Swatch colours for the colour names used in the catalog. Unknown names fall back to a neutral.
const SWATCHES: Record<string, string> = {
  Black: "#1f1f1f",
  Brown: "#6b4a32",
  Camel: "#c19a6b",
  Charcoal: "#3d3f42",
  Clay: "#b56a4d",
  "Dark Indigo": "#2b3550",
  Digital: "#b4532a",
  Forest: "#2f4a38",
  Grey: "#9a9a96",
  "Heather Grey": "#b7b5b0",
  Khaki: "#b8a77f",
  "Light Wash": "#9db4cc",
  "Mixed neutrals": "#d8cbb8",
  Mustard: "#d1a23b",
  Natural: "#efe6d5",
  Navy: "#26324a",
  Oatmeal: "#e3d8c4",
  Olive: "#6b6b3e",
  Rose: "#d9a5a0",
  Sage: "#a8b59a",
  Sand: "#d9c7a7",
  "Sky Blue": "#a9c8e2",
  Stone: "#c9c1b3",
  Tan: "#c8a27a",
  White: "#fbfaf7",
  Yellow: "#e8cd5c",
};

export function swatchColor(name: string): string {
  return SWATCHES[name] ?? "#cfc6b8";
}

/** Light colours need a visible border on the swatch, and dark text on top of them. */
export function isLightColor(hex: string): boolean {
  const value = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  return 0.299 * r + 0.587 * g + 0.114 * b > 186;
}
