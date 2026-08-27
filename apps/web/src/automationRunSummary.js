/** 自动化运行摘要 → 早报式结构化数据（去掉 markdown 展示） */

const NEWS_EMOJIS = ['📈', '🔥', '🏭', '💡', '🚀', '⚡', '📊', '🧪']

const URL_RE = /https?:\/\/[^\s<>[\]()，。；;]+/gi

/** 用户不应看到的 Agent 元说明（搜索限制、接口备注等） */
const META_FOOTER_RE = /\n---+\s*\n+\s*(?:\*\*)?(?:说明|数据说明)(?:\*\*)?[：:][\s\S]*$/
const META_INLINE_RE = /\n\s*(?:说明|数据说明)[：:][\s\S]*$/
const PRODUCTION_META_INTRO_RE =
  /^(?:[^\n]*(?:所有数据已取齐|交叉核对|以下为昨日生产运营日报)[^\n]*\n+)*/i
const PRODUCTION_HEADER_RE = /^#+\s*昨日生产运营日报[^\n]*\n+/gim
const PRODUCTION_BLOCKQUOTE_RE = /^>\s[^\n]*\n+/gm

function stripAgentMeta(text) {
  return String(text || '')
    .replace(META_FOOTER_RE, '')
    .replace(META_INLINE_RE, '')
    .replace(PRODUCTION_HEADER_RE, '')
    .replace(PRODUCTION_BLOCKQUOTE_RE, '')
    .replace(PRODUCTION_META_INTRO_RE, '')
    .trim()
}

export function isProductionDailyReport(text, automationName = '') {
  const name = String(automationName || '')
  if (/生产运营日报|生产日报|昨日生产/.test(name)) return true
  const raw = String(text || '')
  return (
    /\*\*1\.\s*工单概况\*\*/.test(raw) ||
    /^1\.\s*工单概况/m.test(raw) ||
    /一、工单概况/.test(raw)
  )
}

const SOURCE_META_PAREN_RE =
  /[（(][^）)]*(?:接口未返回|检索接口|未返回\s*URL|未返回可直接引用|检索结果未附|检索结果未返回|搜索结果未返回|未附可点击链接|未返回可点击链接)[^）)]*[）)]/gi
const TRAILING_DATE_SOURCE_RE = /[（(]([^）)]*\d{4}-\d{2}-\d{2}[^）)]*)[）)]\s*$/
const LEADING_DATE_BODY_RE = /^\s*[（(]([^）)]*\d{4}-\d{2}-\d{2}[^）)]*)[）)]\s*/
const TITLE_DATE_RE = /[（(]([^）)]*\d{4}-\d{2}-\d{2}[^）)]*)[）)]/g
const SOURCE_LINE_RE =
  /(?:^|\n)\s*(?:[-*]\s+)?来源[：:]\s*([\s\S]*?)(?=\n---|\n\s*(?:\*\*)?(?:说明|补充说明|趋势小结|小结|数据缺口|数据说明)[：:]|$)/
const DETAIL_LINE_RE =
  /(?:^|\n)\s*(?:[-*]\s+)?细分[：:]\s*([\s\S]*?)(?=\n---|\n\s*(?:\*\*)?(?:说明|补充说明|趋势小结|小结|数据缺口|数据说明)[：:]|$)/
const POINTS_LINE_RE =
  /(?:^|\n)\s*(?:[-*]\s+)?要点[：:]\s*([\s\S]*?)(?=\n\s*(?:[-*]\s+)?(?:来源|细分)[：:]|$)/

function sanitizeSource(source) {
  return String(source || '')
    .replace(URL_RE, '')
    .replace(SOURCE_META_PAREN_RE, '')
    .replace(/[（(]\s*[）)]/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/[，,、；;]\s*$/, '')
    .replace(/[。．]?\s*无原文链接[。．]?/g, '')
    .trim()
}

function extractTrailingSourceMeta(text) {
  const raw = String(text || '').trim()
  const m = raw.match(TRAILING_DATE_SOURCE_RE)
  if (!m) return { text: raw, source: '' }
  return {
    text: raw.slice(0, m.index).replace(/[，,、]\s*$/, '').trim(),
    source: m[1].trim(),
  }
}

function extractDateFromTitle(title) {
  const matches = [...String(title || '').matchAll(TITLE_DATE_RE)]
  if (!matches.length) return ''
  return matches[matches.length - 1][1].trim()
}

function extractLeadingDateFromBody(body) {
  const raw = String(body || '')
  const m = raw.match(LEADING_DATE_BODY_RE)
  if (!m) return { date: '', rest: raw }
  return { date: m[1].trim(), rest: raw.slice(m[0].length) }
}

function finalizeSource(source, title, leadDate) {
  let value = String(source || '').trim()
  if (!value && leadDate) value = leadDate
  if (!value) value = extractDateFromTitle(title)
  return sanitizeSource(value)
}

function isMetaParagraph(text) {
  const t = String(text || '').trim()
  if (!t) return true
  if (/^(?:说明|数据说明)[：:]/.test(t)) return true
  if (/搜索接口.*未返回|检索接口.*未返回|未编造\s*URL|无法实时检索/.test(t)) return true
  return false
}

export function stripMarkdownInline(text) {
  return String(text || '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function stripReportBlock(text) {
  return String(text || '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^---+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function stripBlock(text) {
  return String(text || '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^---+$/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function extractUrls(text) {
  const matches = String(text || '').match(URL_RE)
  return matches ? [...new Set(matches.map((u) => u.replace(/[.,;:!?)]+$/, '')))] : []
}

function stripItemFooter(text) {
  return String(text || '')
    .replace(/\n---[\s\S]*$/, '')
    .replace(/\n\s*\*\*(?:说明|补充说明|趋势小结|小结)[：:][\s\S]*$/, '')
    .trim()
}

function parseItemBody(body) {
  const raw = stripBlock(stripItemFooter(body))
  let points = ''
  let source = ''
  let sourceLabel = '来源'

  const pointsMatch = raw.match(POINTS_LINE_RE)
  const detailMatch = raw.match(DETAIL_LINE_RE)
  const sourceMatch = raw.match(SOURCE_LINE_RE)

  if (pointsMatch) points = pointsMatch[1].replace(/\n+/g, ' ').trim()
  if (detailMatch) {
    source = detailMatch[1].replace(/\n+/g, ' ').trim()
    sourceLabel = '细分'
  } else if (sourceMatch) {
    source = sourceMatch[1].replace(/\n+/g, ' ').trim()
    sourceLabel = '来源'
  }

  // 仅有「来源/细分」行、要点以 bullet 列表呈现时，来源前的正文归入要点
  const metaMatch = detailMatch || sourceMatch
  if (!points && metaMatch) {
    const before = raw.slice(0, metaMatch.index).trim()
    if (before) points = before.replace(/\n+/g, ' ').trim()
  }

  if (!points && !source && raw) {
    points = raw.replace(/\n+/g, ' ').trim()
  }

  if (points && !source) {
    const extracted = extractTrailingSourceMeta(points)
    if (extracted.source) {
      source = extracted.source
      points = extracted.text
      sourceLabel = '细分'
    }
  }

  const urls = extractUrls(source || raw)
  return {
    points,
    source: sanitizeSource(source),
    sourceLabel,
    link: urls[0] || '',
  }
}

function parseNewsItemFields(title, body) {
  const { date: leadDate, rest } = extractLeadingDateFromBody(body)
  const { points, source, sourceLabel, link } = parseItemBody(rest)
  return {
    points,
    source: finalizeSource(source, title, leadDate),
    sourceLabel,
    link,
  }
}

function parseNewsItems(text) {
  const items = []
  const cleaned = stripAgentMeta(text)
  const boldPattern = /\*\*(\d+)\.\s*([\s\S]*?)\*\*/g
  const boldMatches = [...cleaned.matchAll(boldPattern)]
  if (boldMatches.length) {
    for (let i = 0; i < boldMatches.length; i += 1) {
      const m = boldMatches[i]
      const index = Number(m[1])
      const title = stripMarkdownInline(m[2])
      const start = m.index + m[0].length
      const end = i + 1 < boldMatches.length ? boldMatches[i + 1].index : cleaned.length
      const body = cleaned.slice(start, end)
      const { points, source, sourceLabel, link } = parseNewsItemFields(title, body)
      items.push({
        index,
        title,
        points,
        source,
        sourceLabel,
        link,
        emoji: NEWS_EMOJIS[(index - 1) % NEWS_EMOJIS.length],
      })
    }
    return items
  }

  const plainPattern = /(?:^|\n)\s*(\d+)\.\s*([^\n]+)/g
  const plainMatches = [...cleaned.matchAll(plainPattern)]
  if (!plainMatches.length || Number(plainMatches[0][1]) !== 1) return items

  for (let i = 0; i < plainMatches.length; i += 1) {
    const m = plainMatches[i]
    const index = Number(m[1])
    const title = stripMarkdownInline(m[2])
    const start = m.index + m[0].length
    const end = i + 1 < plainMatches.length ? plainMatches[i + 1].index : cleaned.length
    const body = cleaned.slice(start, end)
    const { points, source, sourceLabel, link } = parseNewsItemFields(title, body)
    items.push({
      index,
      title,
      points,
      source,
      sourceLabel,
      link,
      emoji: NEWS_EMOJIS[(index - 1) % NEWS_EMOJIS.length],
    })
  }
  return items
}

function splitIntro(text, items) {
  if (!items.length) {
    return stripBlock(stripAgentMeta(text))
  }

  const cleaned = stripAgentMeta(text)
  const plainIdx = cleaned.search(/(?:^|\n)\s*1\.\s+/)
  if (plainIdx > 0) {
    return stripBlock(cleaned.slice(0, plainIdx))
  }
  const boldIdx = cleaned.search(/\*\*1\.\s/)
  if (boldIdx > 0) {
    return stripBlock(cleaned.slice(0, boldIdx))
  }
  return ''
}

function parsePlainParagraphs(text) {
  return stripBlock(stripAgentMeta(text))
    .split(/\n{2,}/)
    .map((p) => formatPlainBlock(p))
    .filter((p) => p && !isMetaParagraph(p))
}

/** 单段内若有 1. / 1、 列表，拆成多行展示 */
function formatPlainBlock(block) {
  const raw = String(block || '').trim()
  if (!raw) return ''
  const numbered = splitNumberedLines(raw)
  if (numbered.length > 1) {
    return numbered.map((line) => line.text).join('\n')
  }
  return raw.replace(/\n+/g, ' ').trim()
}

function splitNumberedLines(text) {
  const raw = String(text || '').trim()
  const re = /(?:^|\n)\s*(\d+)[.、．]\s*/g
  const matches = [...raw.matchAll(re)]
  if (!matches.length) return []

  const items = []
  for (let i = 0; i < matches.length; i += 1) {
    const start = matches[i].index + matches[i][0].length
    const end = i + 1 < matches.length ? matches[i + 1].index : raw.length
    const body = stripMarkdownInline(raw.slice(start, end)).trim()
    if (body) {
      items.push({ index: Number(matches[i][1]), text: body })
    }
  }
  return items
}

function splitBulletLines(text) {
  let raw = String(text || '').trim()
  if (!raw) return []
  raw = raw.replace(/^[-*]\s+/, '')
  const parts = raw.split(/\n\s*[-*]\s+/)
  return parts
    .map((p) => stripMarkdownInline(p).trim())
    .filter(Boolean)
}

const REPORT_SECTION_RE =
  /(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*\*)?([一二三四五六七八九十]+、[^\n*]+?)(?:\*\*)?\s*(?:\n|$)/g

function parseReportSections(text) {
  const cleaned = stripReportBlock(stripAgentMeta(text))
  if (!/[一二三四五六七八九十]+、/.test(cleaned)) return null

  const matches = [...cleaned.matchAll(REPORT_SECTION_RE)]
  if (!matches.length) return null

  const firstIdx = matches[0].index ?? 0
  const intro = stripMarkdownInline(cleaned.slice(0, firstIdx)).trim()

  const sections = []
  for (let i = 0; i < matches.length; i += 1) {
    const m = matches[i]
    const title = stripMarkdownInline(m[1]).trim()
    const start = m.index + m[0].length
    const end = i + 1 < matches.length ? matches[i + 1].index : cleaned.length
    const body = cleaned.slice(start, end).trim()

    const numbered = splitNumberedLines(body)
    if (numbered.length > 0) {
      sections.push({ title, type: 'numbered', items: numbered })
      continue
    }

    const bullets = splitBulletLines(body)
    if (bullets.length > 0) {
      sections.push({
        title,
        type: 'bullets',
        items: bullets.map((t, idx) => ({ index: idx + 1, text: t })),
      })
      continue
    }

    const para = stripMarkdownInline(body).trim()
    if (para) sections.push({ title, type: 'text', items: [{ index: 1, text: para }] })
  }

  if (!sections.length) return null
  return { intro, sections }
}

function isReportSummary(text) {
  const raw = stripAgentMeta(text)
  return /[一二三四五六七八九十]+、/.test(raw) || /##\s*本周工作/.test(raw)
}

/**
 * @returns {{
 *   kind: 'news' | 'report' | 'plain' | 'empty',
 *   intro?: string,
 *   sections?: Array<{ title: string, type: string, items: Array<{ index: number, text: string }> }>,
 *   items?: Array<{ index: number, title: string, points: string, source: string, link: string, emoji: string }>,
 *   paragraphs?: string[],
 * }}
 */
export function parseRunSummary(text) {
  const raw = String(text || '').trim()
  if (!raw) return { kind: 'empty' }

  const items = parseNewsItems(raw)
  if (items.length) {
    const intro = splitIntro(raw, items)
    return { kind: 'news', intro, items }
  }

  if (isReportSummary(raw)) {
    const report = parseReportSections(raw)
    if (report) {
      return { kind: 'report', intro: report.intro, sections: report.sections }
    }
  }

  return { kind: 'plain', paragraphs: parsePlainParagraphs(raw) }
}

function bannerTitleForKind(kind, automationName, text = '') {
  if (isProductionDailyReport(text, automationName)) return '生产日报'
  if (kind === 'news') return '今日精选'
  if (kind === 'report') return '本周简报'
  const name = String(automationName || '').trim()
  return name || '任务摘要'
}

/** 运行摘要 → 可粘贴的纯文本（复制到邮件/企微等） */
export function formatRunSummaryForCopy(text, automationName = '') {
  const parsed = parseRunSummary(text)
  if (parsed.kind === 'empty') return ''

  const lines = []
  lines.push(`📰 ${bannerTitleForKind(parsed.kind, automationName, text)} 📰`)
  lines.push('')

  if (parsed.kind === 'news') {
    if (parsed.intro) {
      lines.push(parsed.intro)
      lines.push('')
    }
    for (const item of parsed.items || []) {
      lines.push(`${item.index}. ${item.title}`)
      if (item.points) lines.push(`要点：${item.points}`)
      if (item.link) lines.push(`${item.sourceLabel || '来源'}：${item.link}`)
      else if (item.source) lines.push(`${item.sourceLabel || '来源'}：${item.source}`)
      lines.push('')
    }
  } else if (parsed.kind === 'report') {
    if (parsed.intro) {
      lines.push(parsed.intro)
      lines.push('')
    }
    for (const sec of parsed.sections || []) {
      lines.push(sec.title)
      if (sec.type === 'numbered') {
        for (const row of sec.items) {
          lines.push(`${row.index}、${row.text}`)
        }
      } else if (sec.type === 'bullets') {
        for (const row of sec.items) {
          lines.push(`• ${row.text}`)
        }
      } else {
        const t = sec.items?.[0]?.text
        if (t) lines.push(t)
      }
      lines.push('')
    }
  } else if (parsed.kind === 'plain') {
    for (const para of parsed.paragraphs || []) {
      lines.push(para)
      lines.push('')
    }
  }

  return lines.join('\n').trim()
}

export function summaryPreviewText(text) {
  const parsed = parseRunSummary(text)
  if (parsed.kind === 'news' && parsed.items?.length) {
    return `${parsed.items[0].title}${parsed.items.length > 1 ? ` 等 ${parsed.items.length} 条` : ''}`
  }
  if (parsed.kind === 'report' && parsed.sections?.length) {
    const first = parsed.sections[0]
    const head = first.title || '周报'
    const n = first.items?.length || 0
    return n ? `${head} · ${n} 条` : head
  }
  if (parsed.kind === 'plain' && parsed.paragraphs?.length) {
    const raw = parsed.paragraphs[0]
    return raw.length > 80 ? `${raw.slice(0, 80)}…` : raw
  }
  return '—'
}
