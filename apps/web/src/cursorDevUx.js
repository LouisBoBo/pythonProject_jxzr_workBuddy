/**
 * 写码主线体验文案：状态可信 + 失败可理解 + 速度体感。
 * 只做展示层归一，不改变后端状态机。
 */

/** @typedef {'patch'|'cloud'|'resume'|''} CursorDevChannel */
/** @typedef {'fast'|'cold_start'|'resume'|'fallback'|''} CursorDevSpeedHint */

/**
 * 把后端/异常原文收成「一句话原因 + 一条下一步」。
 * @param {string} raw
 * @param {{ userStopped?: boolean }} [opts]
 */
export function friendlyCursorDevFailure(raw, opts = {}) {
  const d = String(raw || '').trim()
  const userStopped = Boolean(opts.userStopped) || /已停止|用户停止|强制结束|用户取消|已取消/.test(d)

  if (userStopped) {
    return {
      title: '已停止写码',
      next: '点「重试写码」用同一需求再跑；若要改需求，先取消再继续聊。',
      userStopped: true,
      kind: 'stopped',
    }
  }
  if (/并发已满|resource_exhausted|rate limit|配额/i.test(d)) {
    return {
      title: '写码名额已满或账号限流',
      next: '点「重试写码」：系统会先结束旧任务再开新任务。',
      userStopped: false,
      kind: 'quota',
    }
  }
  if (/不可续聊|已取消.*不可|任务已取消/.test(d)) {
    return {
      title: '上一任务已结束，不能直接续跑',
      next: '点「重试写码」开新任务（仓库与需求会保留）。',
      userStopped: true,
      kind: 'cancelled_job',
    }
  }
  if (/重新挂接|流式中断|对账|接管|软挂接|无新推送/.test(d)) {
    return {
      title: '进度一度中断',
      next: '先点「重新挂接」找回结果；仍不行再「重试写码」。',
      userStopped: false,
      kind: 'detach',
    }
  }
  if (/无法连接|Connection refused|ECONNREFUSED|network|timeout|超时/i.test(d)) {
    return {
      title: '暂时连不上写码服务',
      next: '检查网络后点「重试写码」；若反复失败请联系管理员。',
      userStopped: false,
      kind: 'network',
    }
  }
  if (/CURSOR_API_KEY|白名单|未开启|不可用|GitHub|授权/i.test(d)) {
    return {
      title: '写码车道配置不可用',
      next: '请到「系统配置」检查 Cursor Key、写码开关与仓库白名单；并确认 Cursor↔GitHub 授权。',
      userStopped: false,
      kind: 'admin',
    }
  }
  if (/快速补丁未采用|回退 Cursor Cloud|回退 Cloud/.test(d)) {
    return {
      title: '快速补丁未命中，已改走 Cloud',
      next: '无需操作，等待 Cloud 写码完成即可。',
      userStopped: false,
      kind: 'patch_fallback',
    }
  }

  const short = d.length > 160 ? `${d.slice(0, 160)}…` : d
  return {
    title: short || '写码未成功结束',
    next: '点「重试写码」继续；需求有变则先取消再聊。',
    userStopped: false,
    kind: 'generic',
  }
}

/** 确认卡失败摘要：原因 + 下一步（单段，避免技术堆叠） */
export function formatPickFailureSummary(raw, opts = {}) {
  const f = friendlyCursorDevFailure(raw, opts)
  return `${f.title}。下一步：${f.next}`
}

/** 聊天气泡里的失败说明（比确认卡稍完整，仍只一条下一步） */
export function formatCursorDevUserError(raw, opts = {}) {
  const f = friendlyCursorDevFailure(raw, opts)
  if (f.kind === 'admin') {
    return `${f.title}：${String(raw || '').trim()}\n下一步：${f.next}`
  }
  return `${f.title}。\n下一步：${f.next}`
}

/**
 * 速度体感文案（确认卡 progress / 过程区）。
 * @param {{ channel?: CursorDevChannel, speedHint?: CursorDevSpeedHint, progressText?: string, phase?: string }} pick
 * @param {{ elapsedSec?: number }} [ctx]
 */
export function cursorDevSpeedLabel(pick, ctx = {}) {
  const channel = String(pick?.channel || '')
  const hint = String(pick?.speedHint || '')
  const elapsed = Number(ctx.elapsedSec || 0)

  if (channel === 'patch' || hint === 'fast') {
    return '快速补丁通道（通常几十秒，不重新拉仓）'
  }
  if (hint === 'resume' || channel === 'resume') {
    return '复用已有 Cloud Agent（免重新拉仓，一般更快）'
  }
  if (hint === 'fallback') {
    return '快速补丁未命中，已改走 Cursor Cloud'
  }
  if (hint === 'cold_start' || channel === 'cloud') {
    if (elapsed >= 60) {
      return `Cloud 首次拉仓写码中…已 ${elapsed}s（冷启动常见 1–3 分钟）`
    }
    return 'Cloud 首次写码：正在拉仓启动（常见 1–3 分钟）'
  }
  return String(pick?.progressText || '')
}

/** 确认卡角标 */
export function cursorDevChannelBadge(pick) {
  const channel = String(pick?.channel || '')
  const hint = String(pick?.speedHint || '')
  if (channel === 'patch' || hint === 'fast') return '快速补丁'
  if (hint === 'resume' || channel === 'resume') return '复用加速'
  if (hint === 'cold_start' || channel === 'cloud') return 'Cloud 写码'
  if (hint === 'fallback') return 'Cloud 回退'
  return ''
}

/**
 * 从 SSE status/done 事件推断通道与速度提示。
 * @param {Record<string, any>} event
 */
export function inferChannelFromEvent(event) {
  if (!event || typeof event !== 'object') return {}
  const channel = String(event.channel || '').trim()
  const speedHint = String(event.speed_hint || event.speedHint || '').trim()
  if (channel || speedHint) {
    return {
      ...(channel ? { channel } : {}),
      ...(speedHint ? { speedHint } : {}),
    }
  }
  const text = String(event.text || event.title || event.message || '')
  if (/快速补丁/.test(text) && !/未采用|回退|异常/.test(text)) {
    return { channel: 'patch', speedHint: 'fast' }
  }
  if (/快速补丁未采用|回退 Cursor Cloud|回退 Cloud/.test(text)) {
    return { channel: 'cloud', speedHint: 'fallback' }
  }
  if (/复用已有 Cloud Agent|免重新拉仓/.test(text)) {
    return { channel: 'resume', speedHint: 'resume' }
  }
  if (/新建（将拉仓）|首次|拉仓|冷启动|启动 Cursor/.test(text)) {
    return { channel: 'cloud', speedHint: 'cold_start' }
  }
  return {}
}

/**
 * 用服务端 job 状态校正确认卡（状态可信）。
 * @returns {object|null} 新的 pick 片段；无需改则 null
 */
export function pickPatchFromJobStatus(pick, job) {
  if (!pick || !job) return null
  const st = String(job.status || '')
  const err = String(job.error || '').trim()
  const channel = String(job.channel || pick.channel || '')

  if (st === 'cancelled' || st === 'failed') {
    const friendly = formatPickFailureSummary(err || st, {
      userStopped: /取消|停止/.test(err) || st === 'cancelled' || Boolean(pick.userStopped),
    })
    return {
      status: 'failed',
      phase: 'failed',
      error: friendly,
      userStopped: /取消|停止/.test(err) || st === 'cancelled' || Boolean(pick.userStopped),
      progressText: '',
      ...(channel ? { channel } : {}),
    }
  }
  if (st === 'idle_for_followup' || st === 'succeeded') {
    return {
      status: 'confirmed',
      phase: 'idle_for_followup',
      error: '',
      progressText: channel === 'patch' ? '快速补丁完成' : '写码完成',
      ...(channel ? { channel } : {}),
    }
  }
  if (st === 'queued' || st === 'running' || st === 'creating_pr') {
    if (pick.phase === 'failed' || pick.status === 'failed') return null
    return {
      status: 'confirmed',
      phase: 'running',
      error: '',
    }
  }
  return null
}
