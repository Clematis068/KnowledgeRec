function extractRegionFromLocale(locale) {
  if (!locale) return ''
  const match = String(locale).match(/[-_]([a-z]{2}|\d{3})\b/i)
  return match?.[1]?.toUpperCase?.() || ''
}

function getBrowserRegion() {
  const locales = [
    ...(navigator.languages || []),
    navigator.language,
    Intl.DateTimeFormat().resolvedOptions().locale,
  ].filter(Boolean)

  for (const locale of locales) {
    const region = extractRegionFromLocale(locale)
    if (region) return region
  }
  return ''
}

export function getCurrentTimeSlot(date = new Date()) {
  const hour = date.getHours()
  if (hour < 6) return 'night'
  if (hour < 10) return 'morning'
  if (hour < 14) return 'noon'
  if (hour < 18) return 'afternoon'
  return 'evening'
}

export function getClientContextHeaders() {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  const region = getBrowserRegion()
  const timeSlot = getCurrentTimeSlot()

  return {
    'X-Client-Region': region,
    'X-Client-Timezone': timezone,
    'X-Client-Time-Slot': timeSlot,
  }
}
