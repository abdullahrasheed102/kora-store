import type { Metadata } from "next";
import { Suspense } from "react";

import { AddressBook } from "@/components/account/address-book";
import { TextSkeleton } from "@/components/skeletons";
import { accountApi, requireCustomer } from "@/lib/api-server";

export const metadata: Metadata = { title: "Your addresses", robots: { index: false } };

export default function AddressesPage() {
  return (
    <Suspense fallback={<TextSkeleton lines={6} />}>
      <Addresses />
    </Suspense>
  );
}

async function Addresses() {
  await requireCustomer("/account/addresses");
  return <AddressBook addresses={await accountApi.addresses()} />;
}
