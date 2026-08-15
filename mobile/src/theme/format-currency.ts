/** "LKR 250,000.00" — comma thousands, always two decimals. LKR amounts
 * routinely run into six figures, so this isn't cosmetic. */
export function formatCurrency(amount: number, currency = "LKR"): string {
  return `${currency} ${amount.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
