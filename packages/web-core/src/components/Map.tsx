import "leaflet/dist/leaflet.css";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";

import { api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { t } from "../lib/i18n";
import { Button } from "./ui";

// Dhaka by default; the first city.
export const DEFAULT_CENTER: [number, number] = [23.8103, 90.4125];
const OSM = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

export type MapPoint = { id: number | string; lat: number; lng: number; color?: string; label?: ReactNode; radius?: number };

function Recenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center[0], center[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** Markers are drawn as circles, so no marker image assets are needed. */
export function MapView({ points, center, zoom = 14, height = 360, onMove }: {
  points: MapPoint[];
  center?: [number, number];
  zoom?: number;
  height?: number;
  onMove?: (center: [number, number]) => void;
}) {
  const c = center ?? (points[0] ? [points[0].lat, points[0].lng] : DEFAULT_CENTER);
  function Watcher() {
    useMapEvents({ moveend: (e) => onMove?.([e.target.getCenter().lat, e.target.getCenter().lng]) });
    return null;
  }
  return (
    <div style={{ height }} className="overflow-hidden rounded-[20px] border border-line">
      <MapContainer center={c as [number, number]} zoom={zoom} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
        <TileLayer url={OSM} attribution={ATTRIBUTION} />
        {center && <Recenter center={center} />}
        {onMove && <Watcher />}
        {points.map((p) => (
          <CircleMarker key={p.id} center={[p.lat, p.lng]} radius={p.radius ?? 9} pathOptions={{ color: "#fff", weight: 2, fillColor: p.color ?? "#17784A", fillOpacity: 0.9 }}>
            {p.label && <Popup>{p.label}</Popup>}
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}

/** Tap the map (or use the device location) to choose a point. */
export function MapPicker({ value, onChange, height = 280 }: {
  value: { lat: number; lng: number } | null;
  onChange: (v: { lat: number; lng: number }) => void;
  height?: number;
}) {
  const [center, setCenter] = useState<[number, number]>(value ? [value.lat, value.lng] : DEFAULT_CENTER);
  const [error, setError] = useState("");

  function Clicker() {
    useMapEvents({ click: (e) => onChange({ lat: Number(e.latlng.lat.toFixed(6)), lng: Number(e.latlng.lng.toFixed(6)) }) });
    return null;
  }

  function locate() {
    setError("");
    if (!("geolocation" in navigator)) return setError(t("এই ডিভাইসে লোকেশন পাওয়া যায় না।"));
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const v = { lat: Number(pos.coords.latitude.toFixed(6)), lng: Number(pos.coords.longitude.toFixed(6)) };
        onChange(v);
        setCenter([v.lat, v.lng]);
      },
      () => setError(t("লোকেশনের অনুমতি পাওয়া যায়নি। ম্যাপে চাপ দিয়ে জায়গা দেখান।")),
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div style={{ height }} className="overflow-hidden rounded-[20px] border border-line">
        <MapContainer center={center} zoom={15} style={{ height: "100%", width: "100%" }}>
          <TileLayer url={OSM} attribution={ATTRIBUTION} />
          <Recenter center={center} />
          <Clicker />
          {value && <CircleMarker center={[value.lat, value.lng]} radius={11} pathOptions={{ color: "#fff", weight: 3, fillColor: "#B42318", fillOpacity: 1 }} />}
        </MapContainer>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" icon="pin" onClick={locate}>{t("আমার লোকেশন")}</Button>
        <span className="text-sm text-muted">{value ? `${value.lat}, ${value.lng}` : t("ম্যাপে চাপ দিয়ে জায়গা দেখান")}</span>
      </div>
      {error && <span className="text-sm text-bad">{error}</span>}
    </div>
  );
}

type Tracking = { available: boolean; status: string; provider_name?: string; latitude?: string; longitude?: string; updated_at?: string; destination?: { latitude: string | null; longitude: string | null } };

/** Customer's live view of the provider while they are on the way or working. */
export function LiveTracking({ source, sourceId }: { source: string; sourceId: number }) {
  const { data } = useQuery({
    queryKey: ["tracking", source, sourceId],
    queryFn: async () => (await api.get<Tracking>(`/providers/tracking/${source}/${sourceId}/`)).data,
    refetchInterval: 15_000,
  });
  if (!data?.available) return <p className="m-0 text-sm text-muted">{t("প্রোভাইডার লোকেশন শেয়ার করলে এখানে ম্যাপে দেখাবে।")}</p>;
  const provider: MapPoint = { id: "p", lat: Number(data.latitude), lng: Number(data.longitude), color: "#17784A", label: data.provider_name };
  const dest = data.destination?.latitude ? [{ id: "d", lat: Number(data.destination.latitude), lng: Number(data.destination.longitude), color: "#B42318", label: t("আপনার ঠিকানা") } as MapPoint] : [];
  return (
    <div className="flex flex-col gap-1">
      <MapView points={[provider, ...dest]} center={[provider.lat, provider.lng]} height={260} />
      <span className="text-[13px] text-muted">
        {t("শেষ আপডেট")}: {data.updated_at && formatDateTime(data.updated_at)}
      </span>
    </div>
  );
}
