import { Icon, LanguageToggle, NotificationBell, t, useAuth } from "@shohor/web-core";
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { useCart } from "../api/orders";

const nav = [
  { to: "/services", label: "সার্ভিস" },
  { to: "/shop", label: "শপ" },
  { to: "/subscriptions", label: "সাবস্ক্রিপশন" },
  { to: "/issues", label: "শহরের সমস্যা" },
  { to: "/custom-requests/new", label: "কাস্টম রিকোয়েস্ট" },
];

export default function Header() {
  const { user, logout } = useAuth();
  const { data: cart } = useCart(!!user);
  const [menu, setMenu] = useState(false);
  const navigate = useNavigate();
  const count = cart?.items.length ?? 0;

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-7 gap-y-3 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5 text-ink no-underline">
          <span className="flex size-9 items-center justify-center rounded-[10px] bg-brand text-white">
            <Icon name="home" />
          </span>
          <span className="text-[22px] font-bold">{t("শহরসাথী")}</span>
        </Link>

        <nav aria-label={t("প্রধান মেনু")} className="order-last flex w-full gap-x-5 overflow-x-auto font-medium lg:order-none lg:w-auto lg:flex-auto">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `shrink-0 py-2 no-underline ${isActive ? "text-brand-strong" : "text-ink"}`}
            >
              {t(item.label)}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <LanguageToggle />
          {user && <NotificationBell />}
          <Link
            to="/cart"
            aria-label={t("কার্ট, {count}টি আইটেম", { count })}
            className="relative flex size-11 items-center justify-center rounded-full border border-line bg-surface text-ink"
          >
            <Icon name="cart" />
            {count > 0 && (
              <span className="absolute -top-1 -right-1 flex min-w-5 items-center justify-center rounded-full bg-alert px-1 text-xs font-bold text-ink">
                {count}
              </span>
            )}
          </Link>
          {user ? (
            <div className="relative">
              <button
                type="button"
                aria-expanded={menu}
                onClick={() => setMenu(!menu)}
                className="flex h-11 items-center gap-2 rounded-full border border-line bg-surface px-3 text-[15px] font-semibold"
              >
                <Icon name="user" size={18} />
                <span className="max-w-28 truncate">{user.name}</span>
              </button>
              {menu && (
                <div className="absolute right-0 mt-2 flex w-56 flex-col rounded-2xl border border-line bg-surface p-2 shadow-lg" onClick={() => setMenu(false)}>
                  {[
                    ["/orders", t("আমার অর্ডার")],
                    ["/subscriptions/mine", t("আমার সাবস্ক্রিপশন")],
                    ["/custom-requests", t("কাস্টম রিকোয়েস্ট")],
                    ["/chat", t("চ্যাট ও সাপোর্ট")],
                    ["/issues/mine", t("আমার রিপোর্ট")],
                    ["/wallet", t("ওয়ালেট ও পয়েন্ট")],
                    ["/notifications", t("নোটিফিকেশন")],
                    ["/profile", t("প্রোফাইল ও ঠিকানা")],
                  ].map(([to, label]) => (
                    <Link key={to} to={to} className="rounded-xl px-3 py-2.5 text-ink no-underline hover:bg-subtle">
                      {label}
                    </Link>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      logout();
                      navigate("/");
                    }}
                    className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-left text-bad hover:bg-bad-soft"
                  >
                    <Icon name="logout" size={18} /> {t("লগআউট")}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to="/login" className="flex h-11 items-center rounded-full bg-brand px-5 text-[15px] font-semibold text-white no-underline">
              {t("লগইন")}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
