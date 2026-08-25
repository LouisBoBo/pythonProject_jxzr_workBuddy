/**
 * Cursor 写码机器块解析（从 ChatView 抽出）：options / propose 围栏、宽松 JSON、合入 boilerplate。
 * 不依赖 Vue；技术栈锁定通过 opts.stackLocked 注入。
 */

export const CURSOR_DEV_PROPOSE_START_RE = /:::cursor_dev_propose\b/i
export const CURSOR_DEV_OPTIONS_START_RE = /:::cursor_dev_options\b/i

/**
 * 抽取写码机器块：允许缺少结尾 :::（模型常漏写），避免主线确认卡消失。
 * 返回 { index, end, body } 或 null。
 */
export function extractCursorDevFence(text, kind) {
  const s = String(text || '')
  const startRe = kind === 'options' ? CURSOR_DEV_OPTIONS_START_RE : CURSOR_DEV_PROPOSE_START_RE
  const m = startRe.exec(s)
  if (!m) return null
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
  return { index: start, end, body }
}

export function hideCursorDevMachineBlocks(text) {
  let s = String(text || '')
  for (let i = 0; i < 4; i++) {
    const opt = extractCursorDevFence(s, 'options')
    const prop = extractCursorDevFence(s, 'propose')
    const hit = [opt, prop].filter(Boolean).sort((a, b) => a.index - b.index)[0]
    if (!hit) break
    s = (s.slice(0, hit.index) + s.slice(hit.end)).trim()
  }
  return s
}

export function hideCursorDevPropose(text) {
  return hideCursorDevMachineBlocks(text)
}

/** 有合入指引卡时，去掉正文里与卡片同义的 push/合入说明 */
export function stripCursorDevMergeBoilerplate(text) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const dropRe =
    /代码已\s*push|已\s*push\s*至|如需合入\s*main|请本地自行合并|没有自动合入|尚未合入\s*main|请在\s*GitHub\s*自行|本轮写码已完成[，,].*工作分支|可继续补充需求做续聊改码/i
  const paras = raw.split(/\n{2,}/)
  const kept = []
  for (const p of paras) {
    let s = String(p || '').trim()
    if (!s) continue
    const lines = s.split('\n').map((ln) => ln.replace(/\s+$/, ''))
    while (lines.length && dropRe.test(lines[lines.length - 1]) && lines[lines.length - 1].length < 200) {
      lines.pop()
    }
    s = lines.join('\n').trim()
    if (!s) continue
    if (dropRe.test(s) && s.length < 220 && !/改动说明|验收/.test(s)) continue
    kept.push(s)
  }
  return kept.join('\n\n').trim() || raw
}

/** 技术栈已锁定时，剥掉模型误出的技术栈选项组 */
export function stripLockedStackOptionGroups(options, stackLocked = false) {
  if (!options || !Array.isArray(options.groups)) return options
  if (!stackLocked) return options
  const filtered = options.groups.filter((g) => {
    const id = String(g?.id || '').toLowerCase()
    const label = String(g?.label || '')
    if (/^(stack|backend|frontend|tech|tech_stack|render)$/.test(id)) return false
    if (/技术栈|后端框架|前端框架|渲染方式/.test(label)) return false
    return true
  })
  if (!filtered.length) return null
  return { ...options, groups: filtered, summary: options.summary || '技术栈已锁定，只需确认本轮范围' }
}

/** 宽松解析 propose JSON：主线不能因模型 JSON 瑕疵丢确认卡 */
export function parseProposeJsonLoose(raw) {
  const text = String(raw || '').trim()
  if (!text) return null
  const attempts = [text]
  const fenced = text.match(/^```(?:json)?\s*([\s\S]*?)```$/i)
  if (fenced) attempts.unshift(fenced[1].trim())
  for (const chunk of attempts) {
    try {
      const data = JSON.parse(chunk)
      if (data && typeof data === 'object') return data
    } catch {
      /* continue */
    }
  }
  const repoM = text.match(/"repo"\s*:\s*"([^"]*)"/)
  const refM = text.match(/"ref"\s*:\s*"([^"]*)"/)
  let requirement = ''
  const reqBlock = text.match(/"requirement"\s*:\s*"([\s\S]*?)"\s*,\s*"repo"\s*:/)
  if (reqBlock) {
    requirement = reqBlock[1]
      .replace(/\\n/g, '\n')
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
  } else {
    const reqAlt = text.match(/"requirement"\s*:\s*"((?:[^"\\]|\\.)*)"/)
    if (reqAlt) {
      try {
        requirement = JSON.parse(`"${reqAlt[1]}"`)
      } catch {
        requirement = reqAlt[1]
      }
    }
  }
  if (!requirement.trim()) {
    const soft = text.match(/requirement["']?\s*[:：]\s*([\s\S]+?)(?:\n\s*["']?repo["']?\s*[:：]|$)/i)
    if (soft) requirement = soft[1].replace(/^["'\s]+|["'\s]+$/g, '')
  }
  if (!requirement.trim()) return null
  return {
    requirement: requirement.trim(),
    repo: repoM ? repoM[1] : '',
    ref: refM ? refM[1] : '',
  }
}

export function parseCursorDevOptions(text, { stackLocked = false } = {}) {
  const s = String(text || '')
  const fence = extractCursorDevFence(s, 'options')
  if (!fence) return { content: null, options: null }
  let options = null
  try {
    let raw = fence.body
    const fenced = raw.match(/^```(?:json)?\s*([\s\S]*?)```$/i)
    if (fenced) raw = fenced[1].trim()
    const data = JSON.parse(raw)
    const groups = Array.isArray(data.groups)
      ? data.groups.filter((g) => g?.id && Array.isArray(g.options))
      : []
    if (groups.length) {
      options = {
        id: `cursor-dev-opts-${Date.now()}`,
        status: 'pending',
        title: String(data.title || '请确认写码关键项'),
        summary: String(data.summary || '勾选即可，少打字'),
        notes_placeholder: String(data.notes_placeholder || '其它备注（可选）'),
        groups,
        defaults: data.defaults && typeof data.defaults === 'object' ? data.defaults : {},
        notes: '',
      }
      options = stripLockedStackOptionGroups(options, stackLocked)
    }
  } catch {
    options = null
  }
  const content = (s.slice(0, fence.index) + s.slice(fence.end)).trim()
  return { content, options }
}

export function parseCursorDevPropose(text) {
  const s = String(text || '')
  const fence = extractCursorDevFence(s, 'propose')
  if (!fence) return { content: s.trimEnd(), propose: null }
  let propose = null
  const data = parseProposeJsonLoose(fence.body)
  if (data) {
    const requirement = String(data.requirement || data.summary || '').trim()
    if (requirement) {
      const rawTarget = String(data.target || 'local').trim().toLowerCase()
      const target = rawTarget === 'github' || rawTarget === 'cloud' ? 'github' : 'local'
      propose = {
        requirement,
        target,
        workspace: String(data.workspace || data.path || data.local_path || '').trim(),
        repo: String(data.repo || '').trim(),
        ref: String(data.ref || '').trim(),
      }
    }
  }
  const content = (s.slice(0, fence.index) + s.slice(fence.end)).trim()
  return { content, propose }
}

export function parseCursorDevMachineBlocks(text, opts = {}) {
  const optParsed = parseCursorDevOptions(text, opts)
  if (optParsed.options) {
    const cleaned = parseCursorDevPropose(optParsed.content || '').content
    return { content: cleaned, options: optParsed.options, propose: null }
  }
  let working = text
  const optFence = extractCursorDevFence(working, 'options')
  if (optFence && !optParsed.options) {
    working = (working.slice(0, optFence.index) + working.slice(optFence.end)).trim()
  }
  const propParsed = parseCursorDevPropose(working)
  return { content: propParsed.content, options: null, propose: propParsed.propose }
}

export function formatCursorDevAdminGuide(detail = '') {
  const d = String(detail || '').trim()
  if (/并发已满|resource_exhausted|rate limit|配额/i.test(d)) {
    return (
      `${d}\n\n` +
      `若你并未暂停：多半是上一轮写码流断了但仍占着名额。请再点一次「重试写码」；` +
      `系统会自动结束上一任务再开新任务。`
    )
  }
  const head = d ? `写码车道暂不可用：${d}` : '写码车道暂不可用。'
  return (
    `${head}\n\n` +
    `请到侧栏「系统配置」检查 Cursor API Key、写码开关与仓库白名单；` +
    `并确认 Cursor Team↔GitHub 授权与 Cloud Agents 可用。`
  )
}
