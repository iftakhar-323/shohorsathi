import { useState, useEffect } from "react";

const STORAGE_KEY = "shohor_low_data";

export function isLowDataMode(): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored !== null) return stored === "true";
  // Check browser network saveData setting if available
  // @ts-ignore
  return !!navigator.connection?.saveData;
}

export function setLowDataMode(val: boolean) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, String(val));
  window.dispatchEvent(new CustomEvent("shohor:low-data", { detail: val }));
}

export function useLowDataMode(): [boolean, (val: boolean) => void] {
  const [lowData, setLowData] = useState<boolean>(isLowDataMode());

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<boolean>;
      setLowData(customEvent.detail);
    };
    window.addEventListener("shohor:low-data", handler);
    return () => window.removeEventListener("shohor:low-data", handler);
  }, []);

  const update = (val: boolean) => {
    setLowDataMode(val);
    setLowData(val);
  };

  return [lowData, update];
}

