import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ProductForm } from "@/components/admin/product-form";
import { AdminPageHeader, Card } from "@/components/admin/ui";
import { VariantsEditor } from "@/components/admin/variants-editor";
import { isNotFound } from "@/lib/api";
import { adminApi } from "@/lib/api-server";

export const metadata: Metadata = { title: "Edit product" };

export default async function EditProductPage({ params }: PageProps<"/admin/products/[id]">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const product = await adminApi.product(id).catch((error) => {
    if (isNotFound(error)) notFound();
    throw error;
  });

  return (
    <div className="space-y-6">
      <div>
        <Link href="/admin/products" className="text-sm text-muted hover:text-ink">← Products</Link>
        <AdminPageHeader
          title={product.name}
          description={`${product.total_stock} in stock across ${product.variant_count} variants`}
          action={product.is_active ? <Link href={`/products/${product.slug}`} className="text-sm underline underline-offset-4">View in shop</Link> : undefined}
        />
      </div>
      <Card title="Details">
        {/* key: reset the form's default values after a save + refresh. */}
        <ProductForm key={JSON.stringify(product)} product={product} />
      </Card>
      <Card title="Variants and stock">
        <VariantsEditor product={product} />
      </Card>
    </div>
  );
}
