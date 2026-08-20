/** 与聊天气泡一致的轻量 Markdown → HTML（已转义）。 */

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function isTableRowLine(line) {
  const t = String(line || '').trim()
  return t.startsWith('|') && t.endsWith('|') && t.length >= 3
}

function isSeparatorRowLine(line) {
  const t = String(line || '').trim()
  if (!t.startsWith('|')) return false
  return /^\|[\s|:/-]+\|$/.test(t)
}

function isPipeyLine(line) {
  const t = String(line || '').trim()
  return t.startsWith('|')
}

function rowToTr(line) {
  const cells = String(line)
    .trim()
    .split('|')
    .filter((_, i, arr) => i > 0 && i < arr.length - 1)
  return `<tr>${cells
    .map((c) => {
      const raw = c.trim()
      const bold = /^\*\*(.+)\*\*$/.test(raw)
      const cellText = raw.replace(/\*\*/g, '')
      const tag = bold ? 'th' : 'td'
      return `<${tag}>${cellText}</${tag}>`
    })
    .join('')}</tr>`
}

/** 把连续 GFM 表行合成一张 table */
function convertGfmTables(html) {
  const lines = String(html).split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    if (!isTableRowLine(lines[i]) && !isSeparatorRowLine(lines[i])) {
      out.push(lines[i])
      i += 1
      continue
    }
    const block = []
    while (i < lines.length && (isTableRowLine(lines[i]) || isSeparatorRowLine(lines[i]))) {
      block.push(lines[i])
      i += 1
    }
    const bodyRows = block.filter((l) => !isSeparatorRowLine(l))
    if (!bodyRows.length) continue
    const sepIdx = block.findIndex(isSeparatorRowLine)
    const trs = bodyRows.map((line, idx) => {
      const asHeader = sepIdx > 0 ? idx === 0 : false
      if (asHeader) {
        const cells = line
          .trim()
          .split('|')
          .filter((_, ci, arr) => ci > 0 && ci < arr.length - 1)
        return `<tr>${cells
          .map((c) => `<th>${c.trim().replace(/\*\*/g, '')}</th>`)
          .join('')}</tr>`
      }
      return rowToTr(line)
    })
    out.push(`<table class="md-table">${trs.join('')}</table>`)
  }
  return out.join('\n')
}

/**
 * 流式期间：所有 | 表块（含未写完行）一律变成 <pre>，禁止出 <table>。
 * 结束落盘后再用 renderMarkdown 一次成形，避免每行重算列宽导致闪烁。
 */
function convertPipeBlocksToPlainPre(html) {
  const lines = String(html).split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    if (!isPipeyLine(lines[i])) {
      out.push(lines[i])
      i += 1
      continue
    }
    const block = []
    while (i < lines.length && (isPipeyLine(lines[i]) || lines[i].trim() === '')) {
      // 空行结束表块（除非还在块首）
      if (lines[i].trim() === '' && block.length) break
      block.push(lines[i])
      i += 1
    }
    const body = block.join('\n').replace(/\s+$/, '')
    if (body) {
      out.push(`<pre class="md-table-plain">${body}</pre>`)
    }
  }
  return out.join('\n')
}

function applyInlineMarkdown(html, { tables = true } = {}) {
  html = html.replace(/([\w\-~.:/\\]+[\\/])([\w\-]+\.(xlsx|csv|json))/g, (match, _dir, filename) => {
    return `<a class="file-link" href="/api/download/${encodeURIComponent(filename)}" download target="_blank">${match}</a>`
  })

  html = html.replace(/```(\w*)\r?\n([\s\S]*?)```/g, (_, lang, code) => {
    const label = (lang || '').trim()
    const langHtml = label
      ? `<span class="code-lang">${label}</span>`
      : '<span class="code-lang"></span>'
    return (
      `<div class="code-block-wrap">` +
      `<div class="code-block-bar">${langHtml}` +
      `<button type="button" class="code-copy-btn" data-code-copy title="复制代码">复制</button>` +
      `</div>` +
      `<pre class="code-block"><code>${code}</code></pre>` +
      `</div>`
    )
  })
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')

  if (tables) {
    html = convertGfmTables(html)
  } else {
    html = convertPipeBlocksToPlainPre(html)
  }

  html = html.replace(/^- (.+)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/(<li class="md-li">[\s\S]*?<\/li>)/g, (match) => {
    if (match.includes('<ul')) return match
    return `<ul class="md-ul">${match}</ul>`
  })
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  // 不要把 <pre>/<table> 内部换行打成 <br>
  html = html
    .split(/(<pre[\s\S]*?<\/pre>|<table[\s\S]*?<\/table>)/)
    .map((part) =>
      part.startsWith('<pre') || part.startsWith('<table')
        ? part
        : part.replace(/\n/g, '<br>'),
    )
    .join('')
  return html
}

export function renderMarkdown(text) {
  if (!text) return ''
  return applyInlineMarkdown(escapeHtml(text), { tables: true })
}

/** 流式气泡：表格只出等宽预排，不出 HTML table */
export function renderStreamingMarkdown(text) {
  if (!text) return ''
  return applyInlineMarkdown(escapeHtml(text), { tables: false })
}

/** @deprecated 保留给单测兼容 */
export function splitStreamingMarkdown(text) {
  const raw = String(text || '')
  if (!/\|/.test(raw)) return { stable: raw, pending: '' }
  return { stable: '', pending: raw }
}
