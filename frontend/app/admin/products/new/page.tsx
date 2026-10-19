import type { Metadata } from "next";
import Link from "next/link";

import { ProductForm } from "@/components/admin/product-form";
import { AdminPageHeader, Card } from "@/components/admin/ui";

export const metadata: Metadata = { title: "New product" };

export default function NewProductPage() {
  return (
    <div>
      <Link href="/admin/products" className="text-sm text-muted hover:text-ink">← Products</Link>
      <AdminPageHeader title="New product" description="Add sizes and colours (variants) after creating it." />
      <Card>
        <ProductForm />
      </Card>
    </div>
  );
}
