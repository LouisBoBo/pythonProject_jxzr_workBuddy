#!/usr/bin/env node
/**
 * 无框架：chatIntent 车道启发式冒烟（P0-07a）。
 * 用法（仓库根）: node apps/web/scripts/smoke_chat_intent.mjs
 */
import {
  classifyScreenshotIntent,
  extractGitRepoUrl,
  isBareGitRepoUrlMessage,
  looksLikeCodeDevIntent,
  looksLikeCodeReview,
  looksLikeGitRepoReview,
  looksLikeLocalCommitBatch,
  looksLikePasteCodeAnalyze,
} from '../src/chatIntent.js'

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL', msg)
    process.exit(1)
  }
  console.log('OK  ', msg)
}

assert(looksLikeCodeReview('帮我审核代码'), 'code review phrase')
assert(looksLikeCodeReview('代码审核一下'), 'code review alternate')
assert(!looksLikeCodeReview('改登录页界面'), 'review false on UI edit')
assert(looksLikeCodeDevIntent('改登录页界面'), 'code_dev UI edit')
assert(!looksLikeCodeDevIntent('帮我审核代码'), 'code_dev false on review')
assert(looksLikeLocalCommitBatch('提交今天的代码'), 'commit batch today')
assert(looksLikeLocalCommitBatch('把这批改动提交'), 'commit batch phrase')
assert(!looksLikeLocalCommitBatch('提交工单审批'), 'not MES submit')
assert(!looksLikeCodeDevIntent('提交今天的代码'), 'commit batch not code_dev')
assert(!looksLikeLocalCommitBatch('帮我审核代码'), 'commit batch false on review')
assert(
  looksLikePasteCodeAnalyze('帮我看看这段\n```js\nconst a = 1\nconst b = 2\n```'),
  'paste_code fence',
)
assert(
  extractGitRepoUrl('审核 https://github.com/org/repo.git 仓库') ===
    'https://github.com/org/repo.git',
  'extract git url',
)
assert(looksLikeGitRepoReview('审核 https://github.com/org/repo.git 仓库'), 'git repo review')
assert(isBareGitRepoUrlMessage('https://github.com/org/repo.git'), 'bare git url')
assert(
  classifyScreenshotIntent('改成这种侧边栏', [{ kind: 'image', name: 'a.png' }]).lane ===
    'code_dev',
  'screenshot redesign → code_dev',
)
assert(
  classifyScreenshotIntent('改成这种侧边栏', [{ kind: 'image', name: 'a.png' }]).uiMode ===
    'match',
  'screenshot 改成这种 → match',
)
assert(
  classifyScreenshotIntent('红框处去掉', [{ kind: 'image', name: 'a.png' }]).uiMode === 'edit',
  'screenshot 红框 → edit',
)
assert(
  classifyScreenshotIntent('改登录页', [{ kind: 'image', name: 'a.png' }]).lane === 'ambiguous',
  'screenshot vague UI → ask 按图改还是复原',
)
assert(
  classifyScreenshotIntent('', [{ kind: 'image', name: 'a.png' }]).lane === 'ambiguous',
  'screenshot only → ambiguous',
)

console.log('SMOKE_OK chatIntent')
