function discount(total, tier) {
  if (total < 0) {
    const error = new Error("negative total");
    error.code = "NEGATIVE_TOTAL";
    throw error;
  }
  if (tier === "VIP" && total >= 100) {
    return Math.round(total * 90) / 100;
  }
  return total;
}

module.exports = { discount };
