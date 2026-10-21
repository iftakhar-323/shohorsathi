import { Card, Icon, Loading, MapView, StatusBadge, api, formatDate, formatDateTime, slotLabel, t } from "@shohor/web-core";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

type Shared = {
  title: string;
  status: string;
  scheduled_date: string;
  slot: string;
  provider_first_name: string;
  provider_verified: boolean;
  location: { latitude: string; longitude: string; updated_at: string } | null;
  expires_at: string;
};

/** Public page a customer shares with family: the job's progress and the provider's position, no phone numbers. */
export default function Track() {
  const { token } = useParams();
  const { data, isPending, isError } = useQuery({
    queryKey: ["shared", token],
    queryFn: async () => (await api.get<Shared>(`/providers/share/${token}/`)).data,
    refetchInterval: 15_000,
    retry: false,
  });
  if (isPending) return <Loading />;
  if (isError || !data) return <section className="mx-auto max-w-[560px] px-4 py-16"><Card>{t("এই লিংকের মেয়াদ শেষ।")}</Card></section>;
  return (
    <section className="mx-auto flex max-w-[760px] flex-col gap-4 px-4 py-8">
      <Card className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h1 className="m-0 text-xl font-bold">{data.title}</h1>
          <StatusBadge status={data.status} />
        </div>
        <span className="text-muted">{formatDate(data.scheduled_date)}, {slotLabel(data.slot)}</span>
        {data.provider_first_name && (
          <span className="flex items-center gap-2">
            <Icon name={data.provider_verified ? "shield" : "user"} size={16} className="text-brand" />
            {data.provider_first_name} {data.provider_verified && `· ${t("যাচাইকৃত প্রোভাইডার")}`}
          </span>
        )}
      </Card>
      {data.location ? (
        <>
          <MapView points={[{ id: "p", lat: Number(data.location.latitude), lng: Number(data.location.longitude), label: data.provider_first_name }]}
            center={[Number(data.location.latitude), Number(data.location.longitude)]} height={320} />
          <span className="text-sm text-muted">{t("শেষ আপডেট")}: {formatDateTime(data.location.updated_at)}</span>
        </>
      ) : (
        <p className="m-0 text-muted">{t("প্রোভাইডার পথে রওনা দিলে এখানে লোকেশন দেখাবে।")}</p>
      )}
      <span className="text-[13px] text-muted">{t("লিংকটি {time} পর্যন্ত চালু থাকবে।", { time: formatDateTime(data.expires_at) })}</span>
    </section>
  );
}
