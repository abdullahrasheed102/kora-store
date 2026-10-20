// Types for the Flask API responses. They mirror backend/app/catalog.py — keep them in sync.

export type ProductImage = {
  url: string; // a file in public/images/products, e.g. /images/products/everyday-cotton-tee-olive.webp
  alt_text: string;
  kind: "product" | "lifestyle"; // the garment on its own (one per colour) / being worn
  color: string | null; // null for lifestyle photos
};

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
  tags: string[]; // merchandising labels: "new", "bestseller", "autumn-edit"
  images: ProductImage[]; // gallery order; empty until the product is photographed
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

export type Policy = {
  key: string;
  title: string;
  summary: string | null; // one line for the homepage perks strip
  body: string;
  updated_at: string;
};

export type SortOption = "best_selling" | "newest" | "price_asc" | "price_desc" | "name_asc";

export type ProductQuery = {
  category?: string;
  tag?: string;
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
  image?: { url: string; alt_text: string } | null; // the photo of this line's colour, if there is one
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

// How an order is paid, and whether the money has arrived (separate from where the parcel is).
export type PaymentMethod = "card" | "cod";
export type PaymentStatus = "unpaid" | "paid" | "refunded";

export type OrderSummary = {
  order_number: string;
  status: OrderStatus;
  payment_method: PaymentMethod;
  payment_status: PaymentStatus;
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
  returns: ReturnRequestView[];
};

// --- Phase 4: checkout ----------------------------------------------------------------------

export type CheckoutRequest = {
  email?: string;
  address: AddressInput;
  shipping_method: ShippingMethod;
  items: { variant_id: number; quantity: number }[];
  save_address: boolean;
  phone?: string; // required for cash on delivery
};

// --- Sandbox payment provider ------------------------------------------------------------------

export type SandboxSession = {
  session_id: string;
  status: "open" | "complete" | "expired";
  order_number: string;
  email: string;
  currency: string;
  line_items: { name: string; quantity: number; amount_cents: number }[];
  shipping: { name: string; amount_cents: number };
  amount_total_cents: number;
  expires_at: string;
  success_url: string;
};

export type SandboxCard = { card_number: string; expiry: string; cvc: string; name: string };

// --- Phase 5: tracking and returns --------------------------------------------------------------

export type TrackingResult = {
  order_number: string;
  status: OrderStatus;
  payment_method: PaymentMethod;
  payment_status: PaymentStatus;
  total_cents: number | null; // only for cash on delivery: the amount to have ready
  status_note: string | null;
  created_at: string;
  carrier: string | null;
  tracking_number: string | null;
  estimated_delivery: string | null;
  delivered_at: string | null;
  shipping_city: string;
  shipping_country: string;
  items: { product_name: string; size: string; color: string; quantity: number }[];
  events: { status: OrderStatus; note: string | null; created_at: string }[];
};

export type Refusal = { code: string; message: string };
export type ReturnShipping = "prepaid_label" | "customer_pays";

export type ReturnEligibility = {
  order_number: string;
  status: OrderStatus;
  eligible: boolean;
  reason: Refusal | null;
  delivered_at: string | null;
  return_deadline: string | null;
  days_left: number | null;
  return_shipping: ReturnShipping;
  items: {
    order_item_id: number;
    product_name: string;
    product_slug: string | null;
    size: string;
    color: string;
    quantity: number;
    returnable_quantity: number;
    unit_price_cents: number;
    is_final_sale: boolean;
    reason: Refusal | null;
    exchange_options: { variant_id: number; size: string; color: string }[];
  }[];
  returns: ReturnRequestView[];
};

export type ReturnReason = "doesnt_fit" | "changed_mind" | "not_as_described" | "damaged" | "wrong_item" | "other";

export type CreateReturnRequest = {
  order_number: string;
  email?: string;
  items: { order_item_id: number; quantity: number }[];
  type: "refund" | "exchange";
  reason: ReturnReason;
  comments?: string;
  exchange_variant_id?: number;
  condition_confirmed: boolean;
};

export type ReturnRequestView = {
  id: number;
  order_number: string;
  status: "requested" | "approved" | "label_sent" | "received" | "refunded" | "rejected";
  type: "refund" | "exchange";
  reason: string;
  exchange_details: string | null;
  items: { order_item_id: number; product_name: string; size: string; color: string; quantity: number }[];
  refund_estimate_cents: number;
  return_shipping: ReturnShipping;
  created_at: string;
};

// --- Phase 6: admin ----------------------------------------------------------------------------

export type Paged<T> = { items: T[]; page: number; per_page: number; total: number; total_pages: number };

export type AdminStats = {
  revenue_7d_cents: number;
  orders_7d: number;
  revenue_30d_cents: number;
  orders_30d: number;
  average_order_30d_cents: number;
  daily_revenue: { date: string; revenue_cents: number }[];
  orders_by_status: Record<OrderStatus, number>;
  orders_to_ship: number;
  open_returns: number;
  open_tickets: number;
  low_stock: { variant_id: number; sku: string; size: string; color: string; stock: number; product_id: number; product_name: string }[];
  low_stock_threshold: number;
};

export type AdminProductRow = {
  id: number;
  slug: string;
  name: string;
  category: string;
  price_cents: number;
  is_active: boolean;
  is_final_sale: boolean;
  variant_count: number;
  total_stock: number;
  low_stock_variants: number;
};

export type AdminVariant = {
  id: number;
  sku: string;
  size: string;
  color: string;
  stock: number;
  price_cents: number | null;
  effective_price_cents: number;
};

export type AdminProduct = AdminProductRow & {
  description: string;
  fit_notes: string | null;
  material_care: string | null;
  restock_note: string | null;
  image_url: string | null;
  tags: string[];
  variants: AdminVariant[];
};

export type ProductInput = {
  slug?: string;
  name: string;
  category: string;
  description: string;
  fit_notes: string | null;
  material_care: string | null;
  price_cents: number;
  is_final_sale: boolean;
  restock_note: string | null;
  image_url: string | null;
  tags: string[];
  is_active: boolean;
};

export type AdminOrderRow = {
  order_number: string;
  customer_name: string;
  email: string;
  status: OrderStatus;
  payment_method: PaymentMethod;
  payment_status: PaymentStatus;
  total_cents: number;
  item_count: number;
  created_at: string;
};

export type AdminOrder = Omit<OrderDetail, "events"> & {
  user_id: number | null;
  phone: string | null;
  can_mark_cash_collected: boolean;
  payment_id: string | null;
  payment_session_id: string | null;
  allowed_next_statuses: OrderStatus[];
  events: { status: OrderStatus; note: string | null; created_at: string; created_by: "system" | "admin" | "agent" }[];
};

export type AdminReturn = ReturnRequestView & {
  customer_name: string;
  email: string;
  created_by: "customer" | "agent" | "admin";
  allowed_next_statuses: ReturnRequestView["status"][];
};

export type Ticket = {
  id: number;
  order_number: string | null;
  email: string;
  name: string;
  subject: string;
  summary: string;
  priority: "low" | "normal" | "high" | "urgent";
  status: "open" | "in_progress" | "closed";
  source: "agent" | "contact_form";
  created_at: string;
};
