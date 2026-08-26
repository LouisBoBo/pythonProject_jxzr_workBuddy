/**
 * 对话车道 / 意图纯函数（从 ChatView 抽出，便于单测与复用）。
 * 不依赖 Vue ref；含截图分流、写码/审核/贴码互斥启发式。
 */

export function looksLikeCodeReview(text) {
  const t = String(text || '').trim()
  if (!t) return false
  return /审核代码|代码审核|代码审查|审查代码|检查代码|code\s*review|review\s+(this\s+)?code|帮我审(一下|下)?(代码|工程|项目)/i.test(
    t,
  )
}

/** 消息里已有粘贴源码围栏：走贴码车道，不弹 Git/IDE/写码选卡 */
export function hasPastedSourceFence(text) {
  const s = String(text || '')
  if (/```[\w.+-]*[ \t]*\r?\n[\s\S]{20,}?```/.test(s)) return true
  if (/```[\w.+-]*[ \t]+[\s\S]{20,}?```/.test(s)) return true
  if (/~~~[\w.+-]*[ \t]*\r?\n[\s\S]{20,}?~~~/.test(s)) return true
  return false
}

/** 无围栏时：多行 + 源码形态（防「先选仓库」误抢贴码） */
export function looksLikeRawPastedCode(text) {
  const lines = String(text || '').split(/\r?\n/)
  if (lines.length < 3) return false
  let hits = 0
  for (const line of lines) {
    if (
      /^\s*(def |class |function |const |let |var |import |from |return |if |for |while |public |private |protected |\/\/|#include|package )/i.test(
        line,
      ) ||
      /[{};]\s*$/.test(line) ||
      /^\s*\/\*|\*\/\s*$/.test(line)
    ) {
      hits += 1
    }
  }
  return hits >= 2
}

/** 写码动词：改/写/加功能界面等（不含审核）。允许中间夹仓库 URL。 */
export function hasCodeDevActionWords(text) {
  const t = String(text || '')
  const action =
    /(写代码|改代码|开发功能|帮我写|生成代码|开\s*PR|pull\s*request|写|改|开发|实现|新增|增加|添加|加入|加一个|加个|做一?个|做成|改成|改为|照着|仿照|参考|加上)/i.test(
      t,
    )
  const target =
    /(代码|功能|界面|页面|首页|主页|登录|模块|接口|下拉|输入|选择框|按钮|表单|字段|侧边栏|菜单|导航|布局|样式|风格|主题|仪表盘|看板|UI)/i.test(
      t,
    )
  if (action && target) return true
  return /(登录页|页面|界面|表单|侧边栏|菜单|导航|布局).{0,24}(增加|加入|添加|加一个|加个|改成|改为|做成|照着|仿照|加上|改)/i.test(
    t,
  )
}

/** 从自然语言中抽出干净的公开 HTTPS 仓库地址（去掉尾部中文/标点） */
export function extractGitRepoUrl(text) {
  const t = String(text || '')
  const hostRe =
    /https:\/\/(?:github\.com|gitlab\.com|gitee\.com|bitbucket\.org)\/[A-Za-z0-9_.\-]+\/[A-Za-z0-9_.\-]+(?:\.git)?/i
  const genericRe = /https:\/\/[A-Za-z0-9.\-]+(?:\/[A-Za-z0-9_.\-]+)+\.git\b/i
  const m = t.match(hostRe) || t.match(genericRe)
  if (!m) return ''
  let url = String(m[0]).replace(/\/+$/, '')
  const gitIdx = url.toLowerCase().indexOf('.git')
  if (gitIdx >= 0) url = url.slice(0, gitIdx + 4)
  return url
}

/**
 * 公开 Git 仓库审核意图。
 * 与写码对等互斥：有写/改/加功能意图则绝不走审核；仅 URL ≠ 审核（须澄清）。
 */
export function looksLikeGitRepoReview(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (hasCodeDevActionWords(t)) return false
  if (looksLikeCodeReview(t) && extractGitRepoUrl(t)) return true
  return /(?:审|审核|审查|检查).{0,16}(?:git|Git|远程)?\s*仓库|(?:git|Git)\s*仓库.{0,12}(?:审|审核|审查)|review\s+(?:this\s+)?(?:git\s+)?repo|审核\s*https:\/\//i.test(
    t,
  )
}

/** 贴码分析意图：粘贴源码问问题/怎么改（与写码、仓审核对等，互不抢） */
export function looksLikePasteCodeAnalyze(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (looksLikeGitRepoReview(t) && !hasPastedSourceFence(t) && !looksLikeRawPastedCode(t)) {
    return false
  }
  const ask =
    /帮我看(看|下|一下)?|看看这段|这段(代码|程序)|有没有(什么)?问题|哪里有问题|有啥问题|怎么改|分析(一下|下)?这段|这段.{0,8}(问题|bug)/i.test(
      t,
    )
  if (hasPastedSourceFence(t)) {
    if (ask) return true
    if (!hasCodeDevActionWords(t)) return true
  }
  if (ask && looksLikeRawPastedCode(t)) return true
  return false
}

export function pasteCodeStreamOpts() {
  return {
    force: true,
    workbuddyLane: 'paste_code',
    cursorDevLane: false,
  }
}

/** 截图 + 视觉对齐/按图改界面 → 明确写码（勿当普通闲聊） */
export function looksLikeScreenshotUiRedesign(text, files = []) {
  const hasImg = (files || []).some(
    (f) => f?.kind === 'image' || /\.(png|jpe?g|webp|gif)$/i.test(String(f?.name || f?.path || '')),
  )
  if (!hasImg) return false
  const t = String(text || '').trim()
  if (!t) return false
  return /(改成这种|改为这种|做成这种|照着|仿照|按这个|按截图|1\s*:\s*1|1：1|复刻|界面效果|像素级|高还原|跟(?:截图|这个|图)一样|和(?:截图|这个|图)一样|做成这样|调成这种|按这个效果|设计稿|效果图|按图|照图|参考.{0,8}(图|截图|界面|设计稿)|改成.{0,12}(侧边栏|菜单|导航|布局|风格|样式|仪表盘|首页|登录)|这种.{0,8}(侧边栏|菜单|导航|布局|风格)|截图里.{0,12}(改|调|修)|按截图.{0,8}(改|调|修)|侧边栏菜单)/i.test(
    t,
  )
}

/** 效果要跟截图一样（话术不限于「1:1」；排除「不要复刻」） */
export function looksLikeVisualMatchIntent(text) {
  const t = String(text || '')
  if (
    /(?:不(?:要|必|用)?|别|非|禁止|勿).{0,6}复刻/.test(t) &&
    !/(1\s*:\s*1|1：1|改成这种|做成这种|跟(?:截图|图)一样)/i.test(t)
  ) {
    return false
  }
  return /(1\s*:\s*1|1：1|按截图复刻|像素级|真正\s*1\s*:\s*1|(?:照着|仿照).{0,8}(?:做|改|还原)|改成这种|做成这种|改为这种|按这个界面|复刻|跟(?:着)?(?:截图|这个|图)一样|和(?:截图|这个|图里|图上)一样|做成图里|改成图上|做成这样|调成这种|长这样|按这个效果|效果跟.{0,10}一样|按图(?:还原|实现|做)|照图|还原成|设计稿|效果图|(?:按|参考)(?:这个|此|该)?(?:界面|页面|设计稿|效果图|UI\s*稿)|【用户意图·视觉对齐】)/i.test(
    t,
  )
}

/** 按截图做局部修改（非整页复刻） */
export function looksLikeGuidedShotEditIntent(text) {
  const t = String(text || '')
  return /(?:按|根据|参考|对照)截图.{0,16}(?:改|调|修|换|动)|截图里.{0,20}(?:改|调|修|做成|换成)|图上.{0,16}(?:按钮|颜色|布局|顶栏|侧栏|表单|Logo|logo|间距).{0,10}(?:改|调|修)|把.{0,24}(?:改成|换成|调成).{0,16}(?:截图|图里|图上)|(?:只改|仅改|先改).{0,16}(?:截图|图里|图上)|(?:红框|红圈|黄框|蓝框|框选|圈出|标注).{0,12}(?:处|里|内|中)?.{0,8}(?:去掉|删除|隐藏|移除|改|调|修|移|右移|左移)|(?:去掉|删除|隐藏|移除|右移|左移).{0,8}(?:红框|红圈|框|标注).{0,8}(?:处|里|内|中)|【用户意图·按图修改】/i.test(
    t,
  )
}

/**
 * 截图写码子意图：match=复原/对齐；edit=按图局部改；unclear=须追问。
 */
export function classifyScreenshotUiMode(text) {
  const t = String(text || '').trim()
  if (!t) return 'unclear'
  if (looksLikeVisualMatchIntent(t)) return 'match'
  if (looksLikeGuidedShotEditIntent(t)) return 'edit'
  if (
    /红框|红圈|黄框|蓝框|框选|圈出|标注/.test(t) &&
    /(改|调|修|移|删|去|去掉|右移|左移|隐藏|移除)/.test(t)
  ) {
    return 'edit'
  }
  return 'unclear'
}

export function hasImageAttachments(files = []) {
  return (files || []).some(
    (f) => f?.kind === 'image' || /\.(png|jpe?g|webp|gif|bmp)$/i.test(String(f?.name || f?.path || '')),
  )
}

export function looksLikeMesBizIntent(text) {
  const t = String(text || '').trim()
  if (!t) return false
  return /(工单|生产计划|导入平台|查询报表|库存|物料|工序|报工|派工|MES|这个单号|计划号|订单号|查一下|导出)/i.test(
    t,
  )
}

export function looksLikeScreenshotExplainIntent(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (looksLikeScreenshotUiRedesign(t, [{ kind: 'image' }])) return false
  if (hasCodeDevActionWords(t)) return false
  return /(什么意思|啥意思|解释|这是什么|帮我看(看|下|一下)|怎么回事|为什么|报错|错误|异常|失败|红字|看不懂|识别|OCR|读一下)/i.test(
    t,
  )
}

export function laneLabel(lane) {
  return (
    {
      code_dev: '改代码/界面',
      code_review: '代码审核',
      paste_code: '贴码分析',
      mes: 'MES/业务',
      explain: '解释截图',
    }[lane] || lane
  )
}

/**
 * 截图附件意图分流。
 * confidence=high → 直接进对应车道；low/ambiguous → 弹出意图确认卡反问用户。
 * 写码子意图拿不准（按图改 vs 复原截图）时必须追问，禁止瞎猜。
 * @returns {{ lane: string, confidence: 'high'|'low', hint: string, uiMode?: string }}
 */
export function classifyScreenshotIntent(text, files = []) {
  if (!hasImageAttachments(files)) {
    return { lane: 'none', confidence: 'high', hint: '', uiMode: '' }
  }
  const t = String(text || '').trim()
  const hits = []

  if (looksLikePasteCodeAnalyze(t)) hits.push('paste_code')
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) hits.push('code_review')
  if (
    looksLikeScreenshotUiRedesign(t, files) ||
    hasCodeDevActionWords(t) ||
    looksLikeCodeDevIntent(t, files) ||
    classifyScreenshotUiMode(t) !== 'unclear'
  ) {
    hits.push('code_dev')
  }
  if (looksLikeMesBizIntent(t) && !hasCodeDevActionWords(t)) hits.push('mes')
  if (looksLikeScreenshotExplainIntent(t)) hits.push('explain')

  const unique = [...new Set(hits)]

  if (!t || t.length < 4) {
    return {
      lane: 'ambiguous',
      confidence: 'low',
      hint: '你只贴了截图，还没说明想做什么。请先点选：按图修改、复原成跟截图一样，或其它。',
      uiMode: 'unclear',
    }
  }

  const exclusive = unique.filter((x) => x !== 'explain')
  if (exclusive.length >= 2) {
    return {
      lane: 'ambiguous',
      confidence: 'low',
      hint: `截图相关，但我拿不准是「${exclusive.map(laneLabel).join('」还是「')}」。请点选一项，别让我猜。`,
      uiMode: 'unclear',
    }
  }

  if (unique.includes('code_dev')) {
    const uiMode = classifyScreenshotUiMode(t)
    if (uiMode === 'match') {
      return {
        lane: 'code_dev',
        confidence: 'high',
        hint: '复原/对齐截图（做成跟图一样）',
        uiMode: 'match',
      }
    }
    if (uiMode === 'edit') {
      return {
        lane: 'code_dev',
        confidence: 'high',
        hint: '按图局部修改（含红框/标注）',
        uiMode: 'edit',
      }
    }
    return {
      lane: 'ambiguous',
      confidence: 'low',
      hint:
        '已收到截图和改界面意图，但拿不准你要「按图局部修改」还是「复原成跟截图一样」。请点选，不要让我瞎猜。',
      uiMode: 'unclear',
    }
  }
  if (unique.includes('code_review')) {
    return { lane: 'code_review', confidence: 'high', hint: '审核相关代码', uiMode: '' }
  }
  if (unique.includes('paste_code')) {
    return { lane: 'paste_code', confidence: 'high', hint: '分析粘贴代码', uiMode: '' }
  }
  if (unique.includes('mes')) {
    return { lane: 'mes', confidence: 'high', hint: 'MES/业务处理', uiMode: '' }
  }
  if (unique.includes('explain')) {
    return { lane: 'explain', confidence: 'high', hint: '解释截图/报错', uiMode: '' }
  }

  return {
    lane: 'ambiguous',
    confidence: 'low',
    hint: '已收到截图和说明，但我还不确定你的目标。请点选最接近的一项，或选「补充说明」。',
    uiMode: 'unclear',
  }
}

export function buildScreenshotIntentClarifyCard(content, files, hint = '') {
  const uiFocus =
    /按图|复原|对齐|局部修改|做成跟/.test(String(hint || '')) ||
    classifyScreenshotUiMode(content) === 'unclear'
  const options = uiFocus
    ? [
        { id: 'code_dev_edit', label: '按图修改（红框/局部改，不必整页复原）' },
        { id: 'code_dev_match', label: '复原/对齐截图（做成跟图一样）' },
        { id: 'code_dev', label: '按截图写功能（不强制照抄视觉）' },
        { id: 'explain', label: '解释截图内容或报错' },
        { id: 'mes', label: '查 MES / 业务问题' },
        { id: 'other', label: '都不是，我补充说明' },
      ]
    : [
        { id: 'code_dev_edit', label: '按图修改（红框/局部改，不必整页复原）' },
        { id: 'code_dev_match', label: '复原/对齐截图（做成跟图一样）' },
        { id: 'code_dev', label: '按截图写/改功能（不强制照抄视觉）' },
        { id: 'explain', label: '解释截图内容或报错' },
        { id: 'mes', label: '查 MES / 业务问题' },
        { id: 'code_review', label: '审核相关代码' },
        { id: 'other', label: '都不是，我补充说明' },
      ]
  return {
    id: `shot-intent-${Date.now()}`,
    status: 'pending',
    summary: '已收到截图，请确认你想做什么',
    hint: hint || '拿不准时先确认：按图改，还是复原成跟截图一样。',
    pendingContent: content,
    pendingFiles: files,
    options,
  }
}

/** 几乎只有仓库 URL、无写/审动词 → 须澄清意图，禁止自动开审或开写 */
export function isBareGitRepoUrlMessage(text) {
  const t = String(text || '').trim()
  if (!t) return false
  const url = extractGitRepoUrl(t)
  if (!url) return false
  if (hasCodeDevActionWords(t) || looksLikeCodeReview(t)) return false
  if (/(?:审|审核|审查|检查).{0,16}(?:git|Git|仓库|代码)|(?:写|改|开发|实现|新增).{0,8}(代码|功能|界面|页面)/i.test(t)) {
    return false
  }
  const rest = t.replace(url, '').replace(/[\s，。,.!！？?；;：:、"'`「」【】（）()]+/g, '')
  return rest.length < 8
}

/** 部署意图核心匹配（无互斥；供 looksLikeDeploy / 提交互斥复用） */
function rawLooksLikeDeploy(t) {
  return (
    /部署\s*(到|至)\s*(预发|测试|staging|生产|正式|prod|线上|环境)/i.test(t) ||
    /发布\s*(到|至)\s*(预发|测试|staging|生产|正式|线上|环境)/i.test(t) ||
    // 口语：部署上线 / 发布上线（未点名环境时后端默认预发）
    /(部署|发布)\s*上线|上线\s*(部署|发布|发版)|发版\s*上线/i.test(t) ||
    /(上|发)\s*(到|至)\s*(预发|staging)|上预发|发预发/i.test(t) ||
    /(帮我|请).{0,6}(部署|发布|发版)(到|至|一下|下)?/i.test(t) ||
    /(把)?\s*(这[次批轮]|本次|本轮)\s*(的)?\s*(改动|代码|版本)\s*(部署|发布|上线)/i.test(t) ||
    /(跑|触发|执行).{0,8}(发布|部署|发版).{0,8}(流水线|workflow|actions|CI)/i.test(t) ||
    /\bdeploy\s+to\s+(staging|prod|production)\b/i.test(t) ||
    /\b(trigger|run)\s+(deploy|deployment|release)\b/i.test(t) ||
    /发版\s*(到|至)\s*(预发|测试|生产|线上)/i.test(t)
  )
}

/**
 * 人触发「部署到预发/发布」——与写码、全仓审核、提交批互斥。
 * 仅匹配明确部署/发布意图，避免误伤 MES「部署计划/工单」等。
 */
export function looksLikeDeploy(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (looksLikePasteCodeAnalyze(t)) return false
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) return false
  // 业务「部署/发布」：工单/计划/产线等，不是发版
  if (/(部署|发布).{0,12}(工单|审批|申请|计划|物料|产线|班组|单据|入库|报工|点检)/.test(t)) return false
  if (/(工单|审批|申请|计划|物料|产线|班组).{0,12}(部署|发布)/.test(t)) return false
  // 明确继续写码且无部署词 → 不走部署
  if (hasCodeDevActionWords(t) && !/(部署|发布|deploy)/i.test(t)) return false
  return rawLooksLikeDeploy(t)
}

/**
 * 人触发「提交本批/今天的代码」——与写码、全仓审核、部署互斥。
 * 仅匹配明确提交意图，避免误伤「提交工单」「提交审批」等业务话。
 */
export function looksLikeLocalCommitBatch(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (looksLikePasteCodeAnalyze(t)) return false
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) return false
  if (rawLooksLikeDeploy(t)) return false
  // 业务「提交」：工单/审批/表单等，不是 git
  if (/(提交|提报).{0,12}(工单|审批|申请|表单|单据|入库|报工|点检)/.test(t)) return false
  if (/(工单|审批|申请|表单|单据).{0,12}(提交|提报)/.test(t)) return false
  // 明确要继续写/改功能 → 走写码，不走提交批
  if (hasCodeDevActionWords(t) && !/(提交|commit)/i.test(t)) return false
  return (
    /提交\s*(今天|今日|这批|本轮|本次|这些)?\s*(的)?\s*(代码|改动|变更|修改)/i.test(t) ||
    /把\s*(今天|今日|这批|本轮|本次)?\s*(的)?\s*(代码|改动|变更|修改).{0,12}提交/i.test(t) ||
    /帮我\s*(把)?\s*(代码|改动)?\s*commit/i.test(t) ||
    /\bgit\s*commit\b/i.test(t) ||
    /提交到\s*(工作)?分支/i.test(t) ||
    /commit\s+(today'?s?\s+)?(code|changes|files)\b/i.test(t)
  )
}

/** 写码/开发功能意图（新窗先选仓，再讨论需求）——与审核、贴码、提交、部署对等互斥 */
export function looksLikeCodeDevIntent(text, files = []) {
  const t = String(text || '').trim()
  if (!t && !(files || []).length) return false
  if (looksLikeDeploy(t)) return false
  if (looksLikeLocalCommitBatch(t)) return false
  if (looksLikePasteCodeAnalyze(t)) return false
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) return false
  if (looksLikeScreenshotUiRedesign(t, files)) return true
  if (
    /工单|生产计划|导入|导出|查询|报表/.test(t) &&
    !hasCodeDevActionWords(t) &&
    !/(写|改|开发|实现|新增).{0,8}(代码|功能|界面|页面|首页|主页|接口|模块|侧边栏|菜单)/.test(t)
  ) {
    return false
  }
  if (hasCodeDevActionWords(t)) return true
  return /写代码|改代码|开发功能|开发一个|帮我写|实现(一个|功能)|生成代码|写个|写一个|开\s*PR|pull\s*request|代码实现|写登录|写界面|写页面|新增功能|我要开发|新增.{0,10}(首页|主页|页面|界面|模块|接口|功能)|做(一个|个)?.{0,8}(首页|主页|页面|界面)|加(一个|个)?.{0,8}(首页|主页|页面)|登录.{0,16}(首页|主页)|跳(转|入).{0,10}(首页|主页)|(系统|平台|ERP|MES).{0,12}(新增|改成|改为|做成)|改成这种|前端.{0,6}(首页|主页|页面|侧边栏|菜单)|后端.{0,6}(接口|API)|侧边栏菜单/i.test(
    t,
  )
}

export function isVagueCodeDevIntent(text) {
  const t = String(text || '').trim()
  if (!t) return true
  if (
    /^(我要开发(功能)?|开发功能|我想开发|帮我开发|写代码|改代码|新增功能|帮我写代码|我想写代码|我说需求帮我写代码|我说需求(,|，)?帮我写代码)[。.!！]?$/i.test(
      t,
    )
  ) {
    return true
  }
  if (t.length < 12 && !/(登录|页面|接口|模块|按钮|表单|列表|权限|导出|导入|下拉|首页|主页)/.test(t)) {
    return true
  }
  if (/我说需求.{0,12}写代码/.test(t) && !/(登录|页面|接口|模块|按钮|表单|列表|下拉|首页|主页|侧边栏)/.test(t)) {
    return true
  }
  return false
}
