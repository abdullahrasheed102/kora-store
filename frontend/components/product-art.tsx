import Image from "next/image";

import { swatchColor } from "@/lib/colors";

// Placeholder artwork until products have real photos (CLAUDE.md: no copyrighted brand imagery).
// A simple line drawing of the garment type on a panel tinted with the product's colour.

type Shape = { paths: string[] };

const SHAPES: Record<string, Shape> = {
  tee: { paths: ["M38 30 L52 24 Q60 32 68 24 L82 30 L96 44 L86 54 L80 49 L80 96 L40 96 L40 49 L34 54 L24 44 Z"] },
  longsleeve: {
    paths: ["M40 28 L52 22 Q60 30 68 22 L80 28 L94 40 L100 88 L90 90 L84 52 L84 98 L36 98 L36 52 L30 90 L20 88 L26 40 Z"],
  },
  tank: { paths: ["M46 22 L50 22 Q50 40 60 40 Q70 40 70 22 L74 22 Q74 38 82 46 L82 98 L38 98 L38 46 Q46 38 46 22 Z"] },
  pants: { paths: ["M40 20 L80 20 L84 100 L66 100 L60 48 L54 100 L36 100 Z", "M40 28 L80 28"] },
  shorts: { paths: ["M38 34 L82 34 L88 80 L66 84 L60 56 L54 84 L32 80 Z", "M38 42 L82 42"] },
  skirt: { paths: ["M44 28 L76 28 L92 92 Q60 100 28 92 Z", "M52 34 L46 94", "M60 34 L60 96", "M68 34 L74 94"] },
  coat: {
    paths: [
      "M42 22 L52 18 L60 30 L68 18 L78 22 L94 36 L100 92 L88 94 L84 56 L84 102 L36 102 L36 56 L32 94 L20 92 L26 36 Z",
      "M60 30 L60 102",
    ],
  },
  bag: { paths: ["M30 46 L90 46 L86 100 L34 100 Z", "M46 46 Q46 24 60 24 Q74 24 74 46"] },
  beanie: { paths: ["M30 76 Q30 34 60 34 Q90 34 90 76 Z", "M28 76 L92 76 L92 90 L28 90 Z"] },
  belt: { paths: ["M14 54 L106 54 L106 66 L14 66 Z", "M38 48 L54 48 L54 72 L38 72 Z"] },
  sneaker: { paths: ["M18 72 L22 52 L44 52 L58 62 L92 68 Q104 72 102 84 L18 84 Z", "M18 76 L102 76"] },
  boot: { paths: ["M40 24 L64 24 L64 66 L94 74 Q104 78 102 92 L40 92 Z", "M40 84 L102 84"] },
  sock: { paths: ["M46 20 L70 20 L70 70 L84 84 Q90 98 76 100 L48 82 Q44 78 46 70 Z", "M46 30 L70 30"] },
  gift: { paths: ["M22 36 L98 36 L98 88 L22 88 Z", "M22 54 L98 54", "M44 36 L44 88"] },
};

// The first matching keyword in the slug picks the drawing; otherwise the category does.
const SLUG_KEYWORDS: [string, string][] = [
  ["tee", "tee"],
  ["tank", "tank"],
  ["shirt", "longsleeve"],
  ["sweater", "longsleeve"],
  ["hoodie", "longsleeve"],
  ["skirt", "skirt"],
  ["shorts", "shorts"],
  ["jeans", "pants"],
  ["chino", "pants"],
  ["joggers", "pants"],
  ["tote", "bag"],
  ["beanie", "beanie"],
  ["belt", "belt"],
  ["socks", "sock"],
  ["sneakers", "sneaker"],
  ["boots", "boot"],
  ["gift", "gift"],
];

const CATEGORY_SHAPES: Record<string, string> = {
  tops: "tee",
  bottoms: "pants",
  outerwear: "coat",
  footwear: "sneaker",
  accessories: "bag",
  "gift-cards": "gift",
};

export function shapeFor(slug: string, categorySlug: string): string {
  return SLUG_KEYWORDS.find(([keyword]) => slug.includes(keyword))?.[1] ?? CATEGORY_SHAPES[categorySlug] ?? "tee";
}

type Props = {
  name: string;
  slug: string;
  categorySlug: string;
  color?: string;
  imageUrl?: string | null;
  className?: string;
  sizes?: string; // for next/image: how wide the image is at each breakpoint
  eager?: boolean; // load immediately (e.g. the first row of a grid) instead of lazily
};

export function ProductArt({ name, slug, categorySlug, color, imageUrl, className = "", sizes, eager }: Props) {
  if (imageUrl) {
    return (
      <div className={`relative overflow-hidden bg-card ${className}`}>
        {/* unoptimized: admins can paste any image URL, and we don't want our server to proxy arbitrary hosts. */}
        <Image src={imageUrl} alt={name} fill sizes={sizes} loading={eager ? "eager" : "lazy"} unoptimized className="object-cover" />
      </div>
    );
  }

  const hex = swatchColor(color ?? "Natural");
  const shape = SHAPES[shapeFor(slug, categorySlug)];
  return (
    <div
      role="img"
      aria-label={color ? `${name} in ${color}` : name}
      className={`relative flex items-center justify-center overflow-hidden ${className}`}
      style={{ background: `color-mix(in srgb, ${hex} 18%, #f3ede3)` }}
    >
      <svg viewBox="0 0 120 120" className="h-3/5 w-3/5 drop-shadow-sm" aria-hidden="true">
        {shape.paths.map((d, index) => (
          <path
            key={index}
            d={d}
            fill={index === 0 ? hex : "none"}
            fillOpacity={0.9}
            stroke="#1f1b16"
            strokeOpacity={0.55}
            strokeWidth={1.6}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
      </svg>
    </div>
  );
}
