import { AuthPage, Icon, Loading, RequireAuth, useAuth, type IconName } from "@shohor/web-core";
import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { useProvider } from "./api";
import Apply from "./pages/Apply";
import Earnings from "./pages/Earnings";
import JobDetail from "./pages/JobDetail";
import Jobs from "./pages/Jobs";
import Profile from "./pages/Profile";
import Schedule from "./pages/Schedule";

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "জব ইনবক্স", icon: "list" },
  { to: "/schedule", label: "ক্যালেন্ডার", icon: "calendar" },
  { to: "/earnings", label: "আয় ও পেআউট", icon: "money" },
  { to: "/profile", label: "প্রোফাইল", icon: "user" },
];

function Shell({ children }: { children: ReactNode }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen flex-wrap">
      <aside className="flex w-full flex-col gap-1 bg-night p-4 text-night-text md:sticky md:top-0 md:h-screen md:w-60">
        <div className="flex items-center gap-2 px-2 pb-4">
          <span className="text-xl font-bold text-white">শহরসাথী</span>
          <span className="rounded-full bg-alert px-2 py-0.5 text-xs font-semibold text-ink">পার্টনার</span>
        </div>
        <nav aria-label="প্রোভাইডার মেনু" className="flex gap-1 overflow-x-auto md:flex-col">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) => `flex shrink-0 items-center gap-2 rounded-xl px-3 py-3 no-underline ${isActive ? "bg-night-raised font-semibold text-white" : "text-night-text"}`}
            >
              <Icon name={n.icon} size={18} /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden flex-col gap-2 px-2 pt-6 text-sm md:flex">
          <span>{user?.name}</span>
          <button type="button" onClick={() => { logout(); navigate("/login"); }} className="flex items-center gap-2 text-left text-night-text">
            <Icon name="logout" size={16} /> লগআউট
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 sm:p-7">{children}</main>
    </div>
  );
}

/** Applicants without an approved profile see the application / status page instead of the portal. */
function Gate({ children }: { children: ReactNode }) {
  const { data: provider, isPending } = useProvider();
  if (isPending) return <Loading />;
  if (!provider || provider.status !== "approved") return <Apply provider={provider ?? null} />;
  return <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage appName="শহরসাথী পার্টনার" roles={["customer", "provider"]} />} />
      <Route
        path="/*"
        element={
          <RequireAuth roles={["customer", "provider"]}>
            <Gate>
              <Routes>
                <Route path="/" element={<Jobs />} />
                <Route path="/jobs/:id" element={<JobDetail />} />
                <Route path="/schedule" element={<Schedule />} />
                <Route path="/earnings" element={<Earnings />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Gate>
          </RequireAuth>
        }
      />
    </Routes>
  );
}
