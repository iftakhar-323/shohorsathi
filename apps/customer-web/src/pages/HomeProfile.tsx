import { api, Button, Card, errorMessage, ErrorNote, Field, Loading, PageHeader, t } from "@shohor/web-core";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface Reminder {
  id: number;
  title_en: string;
  title_bn: string;
  category_slug: string;
  recommended_service_slug: string;
  due_date: string;
  frequency_days: number;
  is_completed: boolean;
  notes: string;
}

interface HomeProfileData {
  id: number;
  name: string;
  address: string;
  property_type: "apartment" | "house" | "office";
  square_feet: number;
  ac_count: number;
  refrigerator_count: number;
  washing_machine: boolean;
  water_purifier: boolean;
  ips_inverter: boolean;
  wiring_age_years: number;
  plumbing_age_years: number;
  occupancy_mode: "owner" | "tenant" | "landlord";
  landlord_name: string;
  landlord_phone: string;
  landlord_approval_threshold: string;
  health_score: number;
  reminders: Reminder[];
}

export default function HomeProfile() {
  const [profile, setProfile] = useState<HomeProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState<Partial<HomeProfileData>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // New reminder form
  const [remTitle, setRemTitle] = useState("");
  const [remDate, setRemDate] = useState("");
  const [remService] = useState("ac-cleaning");

  const loadProfile = async () => {
    try {
      const res = await api.get("/home-profiles/");
      const items: HomeProfileData[] = res.data?.results || res.data || [];
      if (items.length > 0) {
        setProfile(items[0]);
        setFormData(items[0]);
      } else {
        // Create initial default profile
        const init = await api.post("/home-profiles/", {
          name: t("আমার বাসা"),
          address: t("ঢাকা, বাংলাদেশ"),
          property_type: "apartment",
          square_feet: 1200,
          ac_count: 2,
          water_purifier: true,
          wiring_age_years: 3,
          plumbing_age_years: 3,
          occupancy_mode: "owner",
        });
        setProfile(init.data);
        setFormData(init.data);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    try {
      const res = await api.patch(`/home-profiles/${profile.id}/`, formData);
      setProfile(res.data);
      setEditing(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleCompleteReminder = async (remId: number) => {
    if (!profile) return;
    try {
      await api.post(`/home-profiles/${profile.id}/complete-reminder/${remId}/`);
      loadProfile();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleAddReminder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile || !remTitle || !remDate) return;
    try {
      await api.post(`/home-profiles/${profile.id}/add-reminder/`, {
        title_bn: remTitle,
        title_en: remTitle,
        due_date: remDate,
        recommended_service_slug: remService,
      });
      setRemTitle("");
      setRemDate("");
      loadProfile();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (loading) return <Loading />;

  const score = profile?.health_score ?? 100;
  const scoreColor =
    score >= 80 ? "text-emerald-600 border-emerald-500 bg-emerald-50" :
    score >= 60 ? "text-amber-600 border-amber-500 bg-amber-50" :
    "text-rose-600 border-rose-500 bg-rose-50";

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-8 sm:px-6">
      <PageHeader
        title={t("ডিজিটাল হোম প্রোফাইল ও হেলথ স্কোর")}
        subtitle={t("বাসার যন্ত্রপাতি, ওয়্যারিং ও প্লাম্বিংয়ের সার্বিক অবস্থা এবং সময়োপযোগী সার্ভিসিং রিমাইন্ডার")}
      />
      <ErrorNote>{error}</ErrorNote>

      {profile && (
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          {/* Health Score Overview */}
          <Card className="p-6 text-center md:col-span-1 flex flex-col justify-center items-center">
            <h3 className="text-sm font-semibold text-ink-muted uppercase tracking-wider">
              {t("হোম হেলথ স্কোর")}
            </h3>
            <div className={`mt-4 inline-flex items-center justify-center rounded-full border-4 h-32 w-32 ${scoreColor}`}>
              <span className="text-4xl font-extrabold">{score}</span>
              <span className="text-xs font-semibold">/100</span>
            </div>
            <p className="mt-3 text-sm font-medium text-ink">
              {score >= 80 ? t("আপনার বাসার রক্ষণাবেক্ষণ চমৎকার অবস্থায় আছে!") :
               score >= 60 ? t("কিছু যন্ত্রপাতির রুটিন সার্ভিসিং প্রয়োজন।") :
               t("জরুরি সার্ভিসিং ও ওয়্যারিং চেক প্রয়োজন!")}
            </p>
            <div className="mt-4 w-full text-xs text-ink-muted space-y-1.5 border-t border-line pt-3">
              <div className="flex justify-between">
                <span>{t("ওয়্যারিং বয়স:")}</span>
                <span className="font-semibold text-ink">{profile.wiring_age_years} {t("বছর")}</span>
              </div>
              <div className="flex justify-between">
                <span>{t("প্লাম্বিং বয়স:")}</span>
                <span className="font-semibold text-ink">{profile.plumbing_age_years} {t("বছর")}</span>
              </div>
              <div className="flex justify-between">
                <span>{t("এসি সংখ্যা:")}</span>
                <span className="font-semibold text-ink">{profile.ac_count} {t("টি")}</span>
              </div>
            </div>
          </Card>

          {/* Profile & Mode Details */}
          <Card className="p-6 md:col-span-2">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div>
                <h3 className="text-lg font-bold text-ink">{profile.name}</h3>
                <p className="text-xs text-ink-muted">{profile.address}</p>
              </div>
              <Button variant="ghost" className="h-8 px-3 text-xs" onClick={() => setEditing(!editing)}>
                {editing ? t("বাতিল") : t("তথ্য পরিবর্তন")}
              </Button>
            </div>

            {editing ? (
              <form onSubmit={handleSaveProfile} className="mt-4 space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label={t("বাসার নাম")} value={formData.name || ""} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
                  <Field label={t("ঠিকানা")} value={formData.address || ""} onChange={(e) => setFormData({ ...formData, address: e.target.value })} required />
                  <Field label={t("সাইজ (বর্গফুট)")} type="number" value={formData.square_feet || 0} onChange={(e) => setFormData({ ...formData, square_feet: parseInt(e.target.value) || 0 })} />
                  <Field label={t("এসি সংখ্যা")} type="number" value={formData.ac_count || 0} onChange={(e) => setFormData({ ...formData, ac_count: parseInt(e.target.value) || 0 })} />
                  <Field label={t("ওয়্যারিং বয়স (বছর)")} type="number" value={formData.wiring_age_years || 0} onChange={(e) => setFormData({ ...formData, wiring_age_years: parseInt(e.target.value) || 0 })} />
                  <Field label={t("প্লাম্বিং বয়স (বছর)")} type="number" value={formData.plumbing_age_years || 0} onChange={(e) => setFormData({ ...formData, plumbing_age_years: parseInt(e.target.value) || 0 })} />
                </div>

                <div className="border-t border-line pt-4">
                  <h4 className="text-sm font-semibold text-ink mb-2">{t("ভাড়াটিয়া / বাড়িওয়ালা মোড")}</h4>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs font-semibold text-ink mb-1">{t("বসবাসের ধরন")}</label>
                      <select
                        value={formData.occupancy_mode || "owner"}
                        onChange={(e) => setFormData({ ...formData, occupancy_mode: e.target.value as any })}
                        className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink"
                      >
                        <option value="owner">{t("নিজের বাসা (মালিক)")}</option>
                        <option value="tenant">{t("ভাড়া বাসা (ভাড়াটিয়া)")}</option>
                        <option value="landlord">{t("বাড়িওয়ালা (রেন্টাল প্রপার্টি)")}</option>
                      </select>
                    </div>
                    {formData.occupancy_mode === "tenant" && (
                      <>
                        <Field label={t("বাড়িওয়ালার মোবাইল নম্বর")} value={formData.landlord_phone || ""} onChange={(e) => setFormData({ ...formData, landlord_phone: e.target.value })} />
                        <Field label={t("বাড়িওয়ালার অনুমোদন সীমা (৳)")} value={formData.landlord_approval_threshold || "1500"} onChange={(e) => setFormData({ ...formData, landlord_approval_threshold: e.target.value })} />
                      </>
                    )}
                  </div>
                </div>

                <Button type="submit" loading={saving} className="w-full justify-center mt-4">
                  {t("সংরক্ষণ করুন")}
                </Button>
              </form>
            ) : (
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                  <div className="p-2.5 rounded-lg bg-surface-tint border border-line">
                    <span className="text-xs text-ink-muted block">{t("প্রপার্টি ধরন")}</span>
                    <span className="font-semibold text-ink capitalize">{profile.property_type}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-tint border border-line">
                    <span className="text-xs text-ink-muted block">{t("আয়তন")}</span>
                    <span className="font-semibold text-ink">{profile.square_feet} {t("বর্গফুট")}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-tint border border-line">
                    <span className="text-xs text-ink-muted block">{t("বসবাস মোড")}</span>
                    <span className="font-semibold text-ink">
                      {profile.occupancy_mode === "tenant" ? t("ভাড়াটিয়া") : profile.occupancy_mode === "landlord" ? t("বাড়িওয়ালা") : t("মালিক")}
                    </span>
                  </div>
                </div>

                {profile.occupancy_mode === "tenant" && (
                  <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-3.5 text-xs text-sky-900">
                    <div className="font-bold flex items-center gap-1.5 text-sm mb-1 text-sky-950">
                      <span>🏢</span> {t("ভাড়াটিয়া ও বাড়িওয়ালা অনুমোদন সক্রিয়")}
                    </div>
                    <p>{t("মেরামত খরচ ৳ {amount}-এর বেশি হলে বাড়িওয়ালার কাছে অনুমোদনের অনুরোধ যাবে এবং অনুমোদিত হলে 'বাড়িভাড়া কর্তন রসিদ' তৈরি হবে।", { amount: profile.landlord_approval_threshold })}</p>
                    {profile.landlord_phone && (
                      <p className="mt-1 font-semibold">{t("বাড়িওয়ালার নম্বর:")} {profile.landlord_phone}</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Maintenance Reminders */}
      <div className="mt-8">
        <h3 className="text-lg font-bold text-ink mb-4">{t("রক্ষণাবেক্ষণ ও সার্ভিসিং রিমাইন্ডার")}</h3>
        <div className="grid gap-4 md:grid-cols-2">
          {profile?.reminders?.map((rem) => (
            <Card key={rem.id} className={`p-4 border ${rem.is_completed ? "bg-slate-50 opacity-70" : "bg-surface"}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className={`text-base font-bold ${rem.is_completed ? "line-through text-ink-muted" : "text-ink"}`}>
                    {rem.title_bn}
                  </h4>
                  <div className="text-xs text-ink-muted mt-1">
                    📅 {t("পরবর্তী সার্ভিসিং তারিখ:")} <span className="font-semibold text-ink">{rem.due_date}</span>
                  </div>
                  {rem.notes && <p className="text-xs text-ink-muted mt-1">{rem.notes}</p>}
                </div>
                {!rem.is_completed ? (
                  <div className="flex flex-col gap-1.5 shrink-0">
                    <Link to={`/services/${rem.recommended_service_slug}`}>
                      <Button className="h-8 text-xs px-2.5 py-1">
                        ⚡ {t("বুক করুন")}
                      </Button>
                    </Link>
                    <Button variant="ghost" onClick={() => handleCompleteReminder(rem.id)} className="h-8 text-xs px-2.5 py-1">
                      ✓ {t("সম্পন্ন")}
                    </Button>
                  </div>
                ) : (
                  <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
                    ✓ {t("সম্পন্ন হয়েছে")}
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>

        {/* Add custom reminder */}
        <Card className="p-4 mt-4 bg-surface-tint border-dashed">
          <h4 className="text-sm font-semibold text-ink mb-3">{t("নতুন সার্ভিসিং রিমাইন্ডার সেট করুন")}</h4>
          <form onSubmit={handleAddReminder} className="flex flex-wrap items-end gap-3 text-sm">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-ink mb-1">{t("কাজের নাম")}</label>
              <input
                type="text"
                placeholder={t("যেমন: ডিপ ফ্রিজ সার্ভিসিং")}
                value={remTitle}
                onChange={(e) => setRemTitle(e.target.value)}
                required
                className="w-full rounded-xl border border-line bg-surface px-3 py-1.5 text-sm text-ink"
              />
            </div>
            <div className="w-40">
              <label className="block text-xs font-medium text-ink mb-1">{t("তারিখ")}</label>
              <input
                type="date"
                value={remDate}
                onChange={(e) => setRemDate(e.target.value)}
                required
                className="w-full rounded-xl border border-line bg-surface px-3 py-1.5 text-sm text-ink"
              />
            </div>
            <Button type="submit" className="h-9 px-4">
              + {t("রিমাইন্ডার যোগ করুন")}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
