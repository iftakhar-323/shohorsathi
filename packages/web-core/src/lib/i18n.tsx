import { Fragment, createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { EN } from "../i18n/en";

/**
 * Bangla-first UI with English as the second language.
 * The Bangla text is the key: `t("লগইন")` returns "Login" in English mode. Keeping the Bangla in the code means
 * a missing translation still shows readable Bangla. `{name}` placeholders are filled from `vars`.
 */
export type Lang = "bn" | "en";

const KEY = "shohor.lang";

function initial(): Lang {
  try {
    return localStorage.getItem(KEY) === "en" ? "en" : "bn";
  } catch {
    return "bn";
  }
}

let current: Lang = initial();

export function getLang() {
  return current;
}

export function t(bn: string, vars?: Record<string, string | number>): string {
  let text = current === "en" ? (EN[bn] ?? bn) : bn;
  if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
  return text;
}

/** Catalog items and areas carry both names; show the one for the current language. */
export function localName(item: { name_bn: string; name_en: string } | null | undefined) {
  if (!item) return "";
  return current === "en" ? item.name_en || item.name_bn : item.name_bn || item.name_en;
}

export function locale() {
  return current === "en" ? "en-BD" : "bn-BD";
}

const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: current, setLang: () => {} });

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setState] = useState<Lang>(current);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  function setLang(l: Lang) {
    current = l;
    try {
      localStorage.setItem(KEY, l);
    } catch {
      // not remembered across visits
    }
    setState(l);
  }

  // Remounting on a switch re-renders every t() call; queries stay cached so nothing is refetched.
  return (
    <LangContext.Provider value={{ lang, setLang }}>
      <Fragment key={lang}>{children}</Fragment>
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}

export function LanguageToggle({ className = "" }: { className?: string }) {
  const { lang, setLang } = useLang();
  const next = lang === "bn" ? "en" : "bn";
  return (
    <button
      type="button"
      onClick={() => setLang(next)}
      aria-label={next === "en" ? "Switch to English" : "বাংলায় দেখুন"}
      className={`h-11 rounded-full border border-line bg-surface px-3 text-[15px] font-semibold text-ink ${className}`}
    >
      {next === "en" ? "English" : "বাংলা"}
    </button>
  );
}
