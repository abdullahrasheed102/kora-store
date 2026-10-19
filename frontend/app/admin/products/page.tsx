import type { Metadata } from "next";
import Form from "next/form";
import Link from "next/link";

import { AdminPageHeader, buttonClass, Empty, inputClass, Pager, secondaryButtonClass, tableClass, tdClass, theadClass, thClass } from "@/components/admin/ui";
import { adminApi } from "@/lib/api-server";
import { formatPrice } from "@/lib/format";

export const metadata: Metadata = { title: "Products" };

export default async function AdminProductsPage({ searchParams }: PageProps<"/admin/products">) {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q : undefined;
  const active = params.active === "true" || params.active === "false" ? params.active : undefined;
  const page = Number(params.page) > 1 ? Number(params.page) : 1;
  const result = await adminApi.products({ q, active, page });

  return (
    <div>
      <AdminPageHeader
        title="Products"
        description={`${result.total} products`}
        action={<Link href="/admin/products/new" className={buttonClass}>New product</Link>}
      />
      <Form action="/admin/products" className="mb-6 flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <label htmlFor="q" className="text-sm font-medium">Search</label>
          <input id="q" name="q" defaultValue={q} placeholder="Name or slug" className={inputClass} />
        </div>
        <div>
          <label htmlFor="active" className="text-sm font-medium">Visibility</label>
          <select id="active" name="active" defaultValue={active ?? ""} className={inputClass}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Hidden</option>
          </select>
        </div>
        <button type="submit" className={secondaryButtonClass}>Filter</button>
      </Form>

      {result.items.length === 0 ? (
        <Empty>No products match.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className={tableClass}>
            <caption className="sr-only">Products</caption>
            <thead className={theadClass}>
              <tr>
                <th scope="col" className={thClass}>Product</th>
                <th scope="col" className={`${thClass} hidden md:table-cell`}>Category</th>
                <th scope="col" className={thClass}>Price</th>
                <th scope="col" className={`${thClass} text-right`}>Stock</th>
                <th scope="col" className={thClass}>Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {result.items.map((product) => (
                <tr key={product.id}>
                  <td className={tdClass}>
                    <Link href={`/admin/products/${product.id}`} className="font-medium underline-offset-4 hover:text-accent hover:underline">
                      {product.name}
                    </Link>
                    <span className="block text-xs text-muted">{product.variant_count} variants</span>
                  </td>
                  <td className={`${tdClass} hidden text-muted md:table-cell`}>{product.category}</td>
                  <td className={`${tdClass} tabular-nums`}>{formatPrice(product.price_cents)}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>
                    {product.total_stock}
                    {product.low_stock_variants > 0 && (
                      <span className="block text-xs text-accent-dark">{product.low_stock_variants} low</span>
                    )}
                  </td>
                  <td className={tdClass}>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${product.is_active ? "bg-sage" : "bg-line text-muted"}`}>
                      {product.is_active ? "Active" : "Hidden"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager basePath="/admin/products" params={{ q, active }} page={result.page} totalPages={result.total_pages} />
    </div>
  );
}
