import { useEffect, useState } from "react";
import { t } from "@shohor/web-core";

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (!deferredPrompt || dismissed) return null;

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setDeferredPrompt(null);
    }
  };

  return (
    <div
      style={{
        background: "linear-gradient(90deg, #064E3B 0%, #0F766E 100%)",
        color: "#fff",
        padding: "10px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        fontSize: 14,
        zIndex: 50,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 20 }}>📲</span>
        <span>
          <strong>{t("শহরসাথী অ্যাপ")}:</strong> {t("সহজে এবং দ্রুত সেবা পেতে মোবাইল অ্যাপটি ইনস্টল করুন")}
        </span>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={handleInstall}
          style={{
            background: "#FACC15",
            color: "#000",
            fontWeight: 700,
            border: 0,
            borderRadius: 6,
            padding: "6px 14px",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          {t("ইনস্টল করুন")}
        </button>
        <button
          onClick={() => setDismissed(true)}
          style={{
            background: "transparent",
            color: "#fff",
            border: "1px solid rgba(255,255,255,0.4)",
            borderRadius: 6,
            padding: "6px 10px",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          {t("পরে")}
        </button>
      </div>
    </div>
  );
}
