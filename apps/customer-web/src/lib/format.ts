const taka = new Intl.NumberFormat("bn-BD", { maximumFractionDigits: 0 });

export function formatTaka(amount: string | number) {
  return `৳ ${taka.format(Number(amount))}`;
}
