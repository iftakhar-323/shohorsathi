import { useEffect, useState } from "react";

const KEY = "shohor.area";

/** The area the customer browses in, remembered per browser. */
export function useSelectedArea(): [number | undefined, (id: number | undefined) => void] {
  const [area, setArea] = useState<number | undefined>(() => {
    try {
      const v = localStorage.getItem(KEY);
      return v ? Number(v) : undefined;
    } catch {
      return undefined;
    }
  });
  useEffect(() => {
    try {
      if (area) localStorage.setItem(KEY, String(area));
      else localStorage.removeItem(KEY);
    } catch {
      // not remembered; fine
    }
  }, [area]);
  return [area, setArea];
}
