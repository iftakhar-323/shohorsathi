import { Button, Card, ErrorNote, Loading, SuccessNote, api, errorMessage, formatDateTime, formatTaka, t } from "@shohor/web-core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

export type RentReceipt = {
  receipt_number: string;
  order_number: string;
  tenant_name: string;
  address: string;
  area: string;
  total_repair_amount: string;
  approval_status: "pending" | "approved" | "rejected";
  approved_at: string | null;
  items: { name: string; amount: string }[];
  certification_bn: string;
  certification_en: string;
};

export function ReceiptBody({ r }: { r: RentReceipt }) {
  return (
    <>
      <span className="text-muted">{r.tenant_name} · {r.address}, {r.area}</span>
      <ul className="m-0 flex flex-col gap-1 p-0">
        {r.items.map((i) => (
          <li key={i.name} className="flex justify-between border-b border-subtle py-1">
            <span>{i.name}</span>
            <span>{formatTaka(i.amount)}</span>
          </li>
        ))}
      </ul>
      <span className="text-lg font-bold">{t("মোট")}: {formatTaka(r.total_repair_amount)}</span>
    </>
  );
}

/** Public page the landlord opens from the SMS: agree (or not) to deduct the tenant's repair from next month's rent. */
export default function Landlord() {
  const { token } = useParams();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { data, isPending, isError } = useQuery({
    queryKey: ["landlord", token],
    queryFn: async () => (await api.get<RentReceipt>(`/orders/landlord/${token}/`)).data,
    retry: false,
  });

  async function decide(decision: "approve" | "reject") {
    setBusy(true);
    setError("");
    try {
      qc.setQueryData(["landlord", token], (await api.post<RentReceipt>(`/orders/landlord/${token}/`, { decision })).data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (isPending) return <Loading />;
  if (isError || !data) return <section className="mx-auto max-w-[560px] px-4 py-16"><Card>{t("লিংকটি সঠিক নয়।")}</Card></section>;
  return (
    <section className="mx-auto flex max-w-[640px] flex-col gap-4 px-4 py-8">
      <Card className="flex flex-col gap-3">
        <h1 className="m-0 text-xl font-bold">{t("ভাড়াটিয়ার মেরামত — ভাড়া থেকে কাটার অনুমতি")}</h1>
        <ReceiptBody r={data} />
        {data.approval_status === "pending" ? (
          <>
            <p className="m-0 text-muted">{t("রাজি হলে এই টাকা পরের মাসের ভাড়া থেকে কাটা হবে এবং ভাড়াটিয়া একটি রসিদ পাবেন।")}</p>
            <ErrorNote>{error}</ErrorNote>
            <div className="flex flex-wrap gap-2">
              <Button loading={busy} icon="check" onClick={() => decide("approve")}>{t("রাজি আছি")}</Button>
              <Button variant="ghost" loading={busy} onClick={() => decide("reject")}>{t("রাজি নই")}</Button>
            </div>
          </>
        ) : data.approval_status === "approved" ? (
          <SuccessNote>
            {t("আপনি রাজি হয়েছেন")} ({data.approved_at && formatDateTime(data.approved_at)}). {t("রসিদ নম্বর")}: {data.receipt_number}
          </SuccessNote>
        ) : (
          <ErrorNote>{t("আপনি রাজি হননি।")}</ErrorNote>
        )}
      </Card>
    </section>
  );
}
