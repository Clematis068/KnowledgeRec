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
  const timeSlot = getCurrentTimeSlot()

  return {
    'X-Client-Timezone': timezone,
    'X-Client-Time-Slot': timeSlot,
  }
}
