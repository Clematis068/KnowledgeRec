function escapeXml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildPalette(seed = 0) {
  const palettes = [
    ['#F4F4F1', '#E7E5E4', '#111111'],
    ['#EFEFED', '#E2E2DE', '#18181B'],
    ['#F7F7F5', '#EAEAE6', '#27272A'],
    ['#F1F1EF', '#DCDCD8', '#09090B'],
    ['#F8F8F6', '#E5E7EB', '#1F2937'],
  ]
  return palettes[Math.abs(seed) % palettes.length]
}

export function createPostThumbnail({ title = '', domainName = '', tags = [], seed = 0 } = {}) {
  const [bg, accent, text] = buildPalette(seed)
  const safeDomain = escapeXml((domainName || '知识推荐').slice(0, 18))
  const safeTitle = escapeXml((title || '知识帖子').slice(0, 54))
  const safeTagA = escapeXml((tags[0] || '阅读').slice(0, 12))
  const safeTagB = escapeXml((tags[1] || '洞察').slice(0, 12))

  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="360" height="240" viewBox="0 0 360 240" fill="none">
    <rect width="360" height="240" rx="20" fill="${bg}"/>
    <rect x="18" y="18" width="324" height="204" rx="16" fill="${accent}" fill-opacity="0.55"/>
    <circle cx="298" cy="62" r="38" fill="${bg}" fill-opacity="0.95"/>
    <circle cx="84" cy="188" r="58" fill="${bg}" fill-opacity="0.7"/>
    <rect x="32" y="34" width="112" height="22" rx="11" fill="${bg}"/>
    <text x="44" y="49" fill="${text}" font-size="12" font-family="Inter, Arial, sans-serif" font-weight="700" letter-spacing="1">${safeDomain.toUpperCase()}</text>
    <text x="32" y="104" fill="${text}" font-size="28" font-family="Newsreader, Georgia, serif" font-weight="700">${safeTitle}</text>
    <text x="32" y="188" fill="${text}" font-size="14" font-family="Inter, Arial, sans-serif" font-weight="700">${safeTagA}</text>
    <text x="122" y="188" fill="${text}" font-size="14" font-family="Inter, Arial, sans-serif" font-weight="700">${safeTagB}</text>
  </svg>`

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}
