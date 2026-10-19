import type { Metadata } from "next";
import Link from "next/link";

import { ContactForm } from "@/components/contact-form";

export const metadata: Metadata = { title: "Contact us", description: "Questions about an order, sizing or returns? Get in touch." };

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-12 sm:px-6">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Contact us</h1>
      <p className="mt-3 text-muted">
        Want a quick answer? <Link href="/track" className="underline underline-offset-2">Track your order</Link> or{" "}
        <Link href="/returns" className="underline underline-offset-2">start a return</Link> yourself, any time.
      </p>
      <div className="mt-10">
        <ContactForm />
      </div>
    </div>
  );
}
