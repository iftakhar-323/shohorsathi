import { Link, NavLink } from "react-router-dom";

import Icon from "./Icon";

const nav = [
  { to: "/shop", label: "শপ" },
  { to: "/services", label: "সার্ভিস" },
  { to: "/subscriptions", label: "সাবস্ক্রিপশন" },
  { to: "/issues", label: "শহরের সমস্যা" },
  { to: "/custom-request", label: "কাস্টম রিকোয়েস্ট" },
];

export default function Header() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-7 gap-y-4 px-6 py-3.5">
        <Link to="/" className="flex items-center gap-2.5 text-ink no-underline">
          <span className="flex size-9 items-center justify-center rounded-[10px] bg-brand text-white">
            <Icon name="home" />
          </span>
          <span className="text-[22px] font-bold">শহরসাথী</span>
        </Link>

        <nav aria-label="প্রধান মেনু" className="flex flex-auto flex-wrap gap-x-5 gap-y-1 font-medium">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `py-2.5 no-underline ${isActive ? "text-brand-strong" : "text-ink"}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            className="flex h-11 items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 text-[15px]"
          >
            <Icon name="pin" size={16} />
            ঢাকা · এলাকা বাছুন
          </button>
          <button
            type="button"
            aria-label="কার্ট"
            className="flex size-11 items-center justify-center rounded-full border border-line bg-surface"
          >
            <Icon name="cart" />
          </button>
          <button type="button" className="h-11 rounded-full bg-brand px-5 text-[15px] font-semibold text-white">
            লগইন
          </button>
        </div>
      </div>
    </header>
  );
}
