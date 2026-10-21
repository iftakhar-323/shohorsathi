import { AuthPage, Icon, LanguageToggle, RequireAuth, t, type IconName, useAuth } from "@shohor/web-core";
import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import Analytics from "./pages/Analytics";
import Areas from "./pages/Areas";
import Business from "./pages/Business";
import Catalog from "./pages/Catalog";
import CustomRequests from "./pages/CustomRequests";
import Dashboard from "./pages/Dashboard";
import Issues from "./pages/Issues";
import Jobs from "./pages/Jobs";
import Loyalty from "./pages/Loyalty";
import Orders from "./pages/Orders";
import Payments from "./pages/Payments";
import Payouts from "./pages/Payouts";
import Providers from "./pages/Providers";
import Safety from "./pages/Safety";
import Insurance from "./pages/Insurance";
import Training from "./pages/Training";
import Subscriptions from "./pages/Subscriptions";
import { Broadcast, SupportInbox } from "./pages/Support";
import Users from "./pages/Users";
import Warranty from "./pages/Warranty";

export const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "ড্যাশবোর্ড", icon: "grid" },
  { to: "/analytics", label: "অ্যানালিটিক্স", icon: "chart" },
  { to: "/orders", label: "অর্ডার ও বুকিং", icon: "cart" },
  { to: "/jobs", label: "জব ও অ্যাসাইন", icon: "wrench" },
  { to: "/custom-requests", label: "কাস্টম রিকোয়েস্ট", icon: "send" },
  { to: "/subscriptions", label: "সাবস্ক্রিপশন", icon: "repeat" },
  { to: "/payments", label: "পেমেন্ট ও রিফান্ড", icon: "money" },
  { to: "/safety", label: "সেফটি ও ট্রাস্ট", icon: "alert" },
  { to: "/insurance", label: "সুরক্ষা বিমা", icon: "shield" },
  { to: "/training", label: "ট্রেনিং মডিউল", icon: "sparkle" },
  { to: "/issues", label: "শহরের সমস্যা", icon: "flag" },
  { to: "/business", label: "বিল্ডিং ও ব্যবসা", icon: "building" },
  { to: "/loyalty", label: "লয়্যালটি ও ক্রেডিট", icon: "gift" },
  { to: "/support", label: "সাপোর্ট চ্যাট", icon: "chat" },
  { to: "/broadcast", label: "নোটিফিকেশন পাঠান", icon: "bell" },
  { to: "/providers", label: "প্রোভাইডার যাচাই", icon: "shield" },
  { to: "/catalog", label: "ক্যাটালগ", icon: "bag" },
  { to: "/payouts", label: "পেআউট", icon: "money" },
  { to: "/warranty", label: "ওয়ারেন্টি", icon: "refresh" },
  { to: "/areas", label: "এলাকা", icon: "pin" },
  { to: "/users", label: "ইউজার", icon: "user" },
];

function Shell({ children }: { children: ReactNode }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen flex-wrap">
      <aside className="flex w-full flex-col gap-1 border-r border-line bg-surface p-4 md:sticky md:top-0 md:h-screen md:w-60 md:overflow-y-auto">
        <div className="flex items-center gap-2 px-2 pb-4">
          <span className="text-xl font-bold">{t("শহরসাথী")}</span>
          <span className="rounded-full bg-ink px-2 py-0.5 text-xs font-semibold text-white">{t("অ্যাডমিন")}</span>
          <span className="ml-auto md:hidden"><LanguageToggle /></span>
        </div>
        <nav aria-label={t("অ্যাডমিন মেনু")} className="flex gap-1 overflow-x-auto md:flex-col">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) => `flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-[15px] no-underline ${isActive ? "bg-brand-soft font-semibold text-brand-strong" : "text-ink"}`}
            >
              <Icon name={n.icon} size={18} /> {t(n.label)}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden flex-col gap-2 px-2 pt-6 text-sm md:flex">
          <LanguageToggle className="self-start" />
          <span className="text-muted">{user?.name}</span>
          <button type="button" onClick={() => { logout(); navigate("/login"); }} className="flex items-center gap-2 text-left">
            <Icon name="logout" size={16} /> {t("লগআউট")}
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 sm:p-7">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage appName={t("শহরসাথী অ্যাডমিন")} allowRegister={false} roles={["admin"]} />} />
      <Route
        path="/*"
        element={
          <RequireAuth roles={["admin"]}>
            <Shell>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/orders" element={<Orders />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/custom-requests" element={<CustomRequests />} />
                <Route path="/providers" element={<Providers />} />
                <Route path="/catalog" element={<Catalog />} />
                <Route path="/subscriptions" element={<Subscriptions />} />
                <Route path="/payments" element={<Payments />} />
                <Route path="/safety" element={<Safety />} />
                <Route path="/insurance" element={<Insurance />} />
                <Route path="/training" element={<Training />} />
                <Route path="/support" element={<SupportInbox />} />
                <Route path="/issues" element={<Issues />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/business" element={<Business />} />
                <Route path="/loyalty" element={<Loyalty />} />
                <Route path="/broadcast" element={<Broadcast />} />
                <Route path="/payouts" element={<Payouts />} />
                <Route path="/warranty" element={<Warranty />} />
                <Route path="/areas" element={<Areas />} />
                <Route path="/users" element={<Users />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Shell>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
