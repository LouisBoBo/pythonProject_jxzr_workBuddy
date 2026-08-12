/** 与聊天气泡一致的轻量 Markdown → HTML（已转义）。 */
export function renderMarkdown(text) {
  if (!text) return ''
  let html = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

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

  html = html.replace(/^\|(.+)\|$/gm, (match) => {
    const cells = match.split('|').filter((c) => c.trim())
    const isHeader = /^[-:\s|]+$/.test(match.replace(/\|/g, ''))
    if (isHeader) return ''
    return `<tr>${cells
      .map((c) => {
        const isBold = /^\*\*(.+)\*\*$/.test(c.trim())
        const cellText = c.trim().replace(/\*\*/g, '')
        return isBold ? `<th>${cellText}</th>` : `<td>${cellText}</td>`
      })
      .join('')}</tr>`
  })
  html = html.replace(/(<tr>.*?<\/tr>)\n(<tr>)/g, '$1$2')
  html = html.replace(/(<tr>[\s\S]*?<\/tr>)/g, (match) => {
    if (match.includes('<table')) return match
    return `<table class="md-table">${match}</table>`
  })
  html = html.replace(/<\/table>\s*<table[^>]*>/g, '')

  html = html.replace(/^- (.+)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/(<li class="md-li">[\s\S]*?<\/li>)/g, (match) => {
    if (match.includes('<ul')) return match
    return `<ul class="md-ul">${match}</ul>`
  })
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n/g, '<br>')
  return html
}
