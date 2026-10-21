import { Button, Empty, errorMessage, ErrorNote, formatTaka, Icon, Loading, localName, PageHeader, t, useAuth, useCategories, useProducts } from "@shohor/web-core";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAddToCart } from "../api/orders";

export default function Shop() {
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const q = params.get("q") ?? "";
  const { data: categories } = useCategories("product");
  const { data, isPending } = useProducts({ category: category || undefined, q: q || undefined });
  const addToCart = useAddToCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [added, setAdded] = useState<string>("");
  const [error, setError] = useState("");

  async function add(slug: string) {
    if (!user) return navigate("/login?next=/shop");
    setError("");
    try {
      await addToCart.mutateAsync({ item_type: "product", slug, quantity: 1 });
      setAdded(slug);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <section className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-8 sm:px-6">
      <PageHeader title={t("শপ")} subtitle={t("ঘরের দরকারি জিনিস, ইলেকট্রিক ও প্লাম্বিং সামগ্রী")} />
      <div className="flex flex-wrap gap-2">
        {[{ slug: "", name_bn: t("সব"), name_en: t("সব") }, ...(categories ?? [])].map((c) => (
          <button
            key={c.slug}
            type="button"
            onClick={() => setParams(c.slug ? { category: c.slug } : {})}
            className={`h-11 rounded-full border px-4 text-[15px] ${category === c.slug ? "border-brand bg-brand text-white" : "border-line bg-surface"}`}
          >
            {localName(c)}
          </button>
        ))}
      </div>
      <ErrorNote>{error}</ErrorNote>
      {isPending && <Loading />}
      {data?.results.length === 0 && <Empty icon="bag" title={t("এই ক্যাটাগরিতে এখন কোনো পণ্য নেই")} />}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
        {data?.results.map((p) => (
          <article key={p.id} className="flex flex-col overflow-hidden rounded-[20px] border border-line bg-surface">
            {p.image_url ? (
              <img src={p.image_url} alt="" className="h-40 w-full object-cover" />
            ) : (
              <div className="flex h-40 items-center justify-center bg-subtle text-muted">
                <Icon name="bag" size={36} />
              </div>
            )}
            <div className="flex flex-1 flex-col gap-1.5 p-4">
              <h3 className="m-0 text-base font-bold">{localName(p)}</h3>
              {p.shop_name && <span className="text-sm text-muted">{p.shop_name}</span>}
              <span className="text-lg font-bold">
                {formatTaka(p.price)} <span className="text-sm font-normal text-muted">/ {p.unit}</span>
              </span>
              <span className={`text-sm ${p.stock > 0 ? "text-brand-strong" : "text-bad"}`}>{p.stock > 0 ? t("স্টকে আছে") : t("স্টক শেষ")}</span>
              <Button
                variant={added === p.slug ? "secondary" : "primary"}
                icon={added === p.slug ? "check" : "cart"}
                disabled={p.stock === 0}
                loading={addToCart.isPending && addToCart.variables?.slug === p.slug}
                onClick={() => add(p.slug)}
                className="mt-auto"
              >
                {added === p.slug ? t("কার্টে যোগ হয়েছে") : t("কার্টে যোগ করুন")}
              </Button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
