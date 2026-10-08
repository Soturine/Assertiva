export type Tier = "VIP" | "REGULAR";

export function discount(total: number, tier: Tier): number {
  if (total < 0) {
    throw new Error("negative total");
  }
  return tier === "VIP" ? (total * 90) / 100 : total;
}
