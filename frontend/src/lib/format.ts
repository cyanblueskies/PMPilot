/** Shared number and date formatting. */

/** `86` not `86.0`; `5.48` -> `5.5`. One decimal is the precision a reader uses. */
export function num(value: number): string {
  return Number.isInteger(value)
    ? value.toLocaleString()
    : value.toLocaleString(undefined, { maximumFractionDigits: 1 })
}

export function percent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

export function days(value: number): string {
  return `${num(value)} d`
}

export function dateTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
