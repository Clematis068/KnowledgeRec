export const TIME_SLOT_OPTIONS = [
  { label: '清晨 / 夜间', value: 'night' },
  { label: '上午', value: 'morning' },
  { label: '中午', value: 'noon' },
  { label: '下午', value: 'afternoon' },
  { label: '晚上', value: 'evening' },
]

export const REGION_OPTIONS = [
  { label: '中国 (CN)', value: 'CN' },
  { label: '美国 (US)', value: 'US' },
  { label: '英国 (GB)', value: 'GB' },
  { label: '日本 (JP)', value: 'JP' },
  { label: '韩国 (KR)', value: 'KR' },
  { label: '新加坡 (SG)', value: 'SG' },
  { label: '德国 (DE)', value: 'DE' },
  { label: '法国 (FR)', value: 'FR' },
  { label: '加拿大 (CA)', value: 'CA' },
  { label: '澳大利亚 (AU)', value: 'AU' },
]

export const TIME_SLOT_LABELS = Object.fromEntries(
  TIME_SLOT_OPTIONS.map((item) => [item.value, item.label]),
)
