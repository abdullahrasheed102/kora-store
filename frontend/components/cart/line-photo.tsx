import { ProductArt } from "@/components/product-art";
import { ProductPhoto } from "@/components/product-photo";
import type { CartQuoteItem } from "@/lib/types";

/** The photo of a bag line's colour, or the placeholder art while that colour has no photo. */
export function LinePhoto({ item, sizes, className }: { item: CartQuoteItem; sizes: string; className: string }) {
  const art = (
    <ProductArt
      name={item.product_name ?? "Product"}
      slug={item.product_slug ?? ""}
      categorySlug={item.category_slug ?? ""}
      color={item.color}
      imageUrl={item.image_url}
      className="h-full w-full"
    />
  );
  return (
    <div className={`relative overflow-hidden rounded-sm bg-card ${className}`}>
      {item.image ? <ProductPhoto image={item.image} fallback={art} sizes={sizes} /> : art}
    </div>
  );
}
