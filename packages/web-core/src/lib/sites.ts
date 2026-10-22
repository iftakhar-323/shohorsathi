export type Site = "customer" | "provider" | "admin";

const DEV_PORTS: Record<Site, string> = { customer: "5173", provider: "5174", admin: "5175" };
const SUBDOMAINS: Record<Site, string> = { customer: "", provider: "partner.", admin: "admin." };

/** Where another of the three apps lives: :5173/:5174/:5175 in development, shohorsathi.com / partner. / admin. in production. */
export function siteUrl(site: Site, path = "/"): string {
  const { protocol, hostname, port } = window.location;
  if (Object.values(DEV_PORTS).includes(port)) return `${protocol}//${hostname}:${DEV_PORTS[site]}${path}`;
  const base = hostname.replace(/^(partner|admin)\./, "");
  return `${protocol}//${SUBDOMAINS[site]}${base}${port ? `:${port}` : ""}${path}`;
}
