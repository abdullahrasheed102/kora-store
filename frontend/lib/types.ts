// Types for the Flask API responses. They mirror backend/app/catalog.py — keep them in sync.

export type ProductSummary = {
  slug: string;
  name: string;
  category: string;
  category_slug: string;
  price_cents: number;
  price_min_cents: number;
  price_max_cents: number;
  image_url: string | null;
  is_final_sale: boolean;
  in_stock: boolean;
  colors: string[];
};

export type Variant = {
  id: number;
  sku: string;
  size: string;
  color: string;
  stock: number;
  price_cents: number;
  in_stock: boolean;
};

export type ProductDetail = ProductSummary & {
  description: string;
  fit_notes: string | null;
  material_care: string | null;
  restock_note: string | null;
  sizes: string[];
  variants: Variant[];
  related: ProductSummary[];
};

export type Facets = {
  sizes: string[];
  colors: string[];
  price_min_cents: number | null;
  price_max_cents: number | null;
};

export type ProductPage = {
  items: ProductSummary[];
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  facets: Facets;
};

export type Category = { name: string; slug: string; product_count: number };

export type Policy = { key: string; title: string; body: string; updated_at: string };

export type SortOption = "best_selling" | "newest" | "price_asc" | "price_desc" | "name_asc";

export type ProductQuery = {
  category?: string;
  q?: string;
  size?: string[];
  color?: string[];
  min_price?: number;
  max_price?: number;
  sort?: SortOption;
  page?: number;
  per_page?: number;
};

export type HealthStatus = { status: "ok" | "degraded"; database: "ok" | "unavailable" };

// --- Phase 3: cart, accounts ---------------------------------------------------------------

export type ShippingMethod = "standard" | "express" | "international";
export type CartIssue = "unavailable" | "out_of_stock" | "insufficient_stock";

export type CartQuoteItem = {
  variant_id: number;
  requested_quantity: number;
  quantity: number;
  line_total_cents: number;
  issue: CartIssue | null;
  // Missing when the variant no longer exists (issue "unavailable").
  sku?: string;
  product_slug?: string;
  product_name?: string;
  category_slug?: string;
  image_url?: string | null;
  size?: string;
  color?: string;
  is_final_sale?: boolean;
  unit_price_cents?: number;
  available_quantity?: number;
};

export type CartQuote = {
  items: CartQuoteItem[];
  item_count: number;
  shipping_method: ShippingMethod;
  subtotal_cents: number;
  shipping_cents: number;
  total_cents: number;
  free_shipping_threshold_cents: number;
  amount_to_free_shipping_cents: number | null;
  has_issues: boolean;
};

export type User = { id: number; email: string; name: string; role: "customer" | "admin"; created_at: string };

export type Country = "US" | "GB" | "CA" | "AU";

export type AddressInput = {
  name: string;
  line1: string;
  line2: string | null;
  city: string;
  state: string | null;
  postal_code: string;
  country: Country;
  is_default: boolean;
};

export type Address = AddressInput & { id: number };

export type OrderStatus =
  | "pending_payment"
  | "processing"
  | "shipped"
  | "out_for_delivery"
  | "delivered"
  | "delayed"
  | "partially_shipped"
  | "cancelled"
  | "returned";

export type OrderSummary = {
  order_number: string;
  status: OrderStatus;
  total_cents: number;
  item_count: number;
  created_at: string;
};

export type OrderDetail = OrderSummary & {
  status_note: string | null;
  email: string;
  customer_name: string;
  subtotal_cents: number;
  shipping_cents: number;
  shipping_method: ShippingMethod;
  shipping_address: Omit<AddressInput, "name" | "is_default">;
  carrier: string | null;
  tracking_number: string | null;
  estimated_delivery: string | null;
  delivered_at: string | null;
  items: {
    id: number;
    product_name: string;
    size: string;
    color: string;
    unit_price_cents: number;
    quantity: number;
    line_total_cents: number;
    is_final_sale: boolean;
  }[];
  events: { status: OrderStatus; note: string | null; created_at: string }[];
};
