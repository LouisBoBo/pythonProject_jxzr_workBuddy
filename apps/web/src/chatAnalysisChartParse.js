/**
 * 分析图机器块解析（从 ChatView 抽出）：:::analysis_chart 围栏 + 去重合并。
 * 不依赖 Vue。
 */

export const ANALYSIS_CHART_START_RE = /:::analysis_chart\b/i

/**
 * 抽取 :::analysis_chart ... ::: 机器块，返回 { content, charts }。
 * 非法 JSON 时停止并保留剩余原文。
 */
export function parseAnalysisChartFences(text) {
  let s = String(text || '')
  const charts = []
  let guard = 0
  while (guard++ < 8) {
    const m = ANALYSIS_CHART_START_RE.exec(s)
    if (!m) break
    const start = m.index
    const afterTag = s.slice(start + m[0].length)
    const bodyBeginRel = afterTag.match(/^\s*/)?.[0]?.length ?? 0
    const bodyAndRest = afterTag.slice(bodyBeginRel)
    const close = bodyAndRest.match(/\n[ \t]*:::[ \t]*(?:\n|$)/)
    let body
    let end
    if (close && typeof close.index === 'number') {
      body = bodyAndRest.slice(0, close.index).trim()
      end = start + m[0].length + bodyBeginRel + close.index + close[0].length
    } else {
      body = bodyAndRest.replace(/\n?[ \t]*:::[ \t]*\s*$/, '').trim()
      end = s.length
    }
    try {
      const payload = JSON.parse(body)
      if (payload && typeof payload === 'object' && payload.option) {
        charts.push({
          id: `fence-${charts.length}-${Date.now()}`,
          title: payload.title || '分析图',
          chart_type: payload.chart_type || 'bar',
          option: payload.option,
          definition: payload.definition || '',
          caveats: Array.isArray(payload.caveats) ? payload.caveats : [],
          layout: payload.layout || payload.option?._wb_layout || {},
        })
      }
    } catch {
      /* 非法 JSON 则原样保留该段 */
      break
    }
    s = s.slice(0, start) + s.slice(end)
  }
  return { content: s.trim(), charts }
}

/** 图表指纹：避免 SSE 出图 + 正文 fence 各渲一次 */
export function chartFingerprint(ch) {
  if (!ch || typeof ch !== 'object') return ''
  const opt = ch.option || {}
  const series = Array.isArray(opt.series) ? opt.series : []
  const xdata = opt.xAxis?.data || opt.xAxis?.[0]?.data || []
  const pie = series[0]?.data
  try {
    return [
      String(ch.title || ''),
      String(ch.chart_type || ''),
      JSON.stringify(xdata),
      JSON.stringify(pie || series[0]?.data || []),
    ].join('|')
  } catch {
    return String(ch.title || '') + String(ch.chart_type || '')
  }
}

export function mergeUniqueCharts(...lists) {
  const out = []
  const seen = new Set()
  for (const list of lists) {
    for (const ch of list || []) {
      if (!ch?.option) continue
      const fp = chartFingerprint(ch)
      if (fp && seen.has(fp)) continue
      if (fp) seen.add(fp)
      out.push(ch)
    }
  }
  return out
}
