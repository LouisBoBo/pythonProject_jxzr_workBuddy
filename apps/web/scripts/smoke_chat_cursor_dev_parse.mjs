#!/usr/bin/env node
/**
 * 写码机器块解析冒烟（P0-07b）。
 * 用法: node apps/web/scripts/smoke_chat_cursor_dev_parse.mjs
 */
import {
  formatCursorDevAdminGuide,
  hideCursorDevMachineBlocks,
  parseCursorDevMachineBlocks,
  parseProposeJsonLoose,
  stripLockedStackOptionGroups,
} from '../src/chatCursorDevParse.js'

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL', msg)
    process.exit(1)
  }
  console.log('OK  ', msg)
}

const withPropose = [
  '先确认范围。',
  ':::cursor_dev_propose',
  '{"requirement":"加登录页","target":"local","workspace":"/tmp/app","repo":"","ref":""}',
  ':::',
].join('\n')

const parsed = parseCursorDevMachineBlocks(withPropose)
assert(parsed.propose?.requirement === '加登录页', 'parse propose requirement')
assert(parsed.propose?.target === 'local', 'parse propose target')
assert(!/:::cursor_dev_propose/.test(parsed.content || ''), 'propose fence stripped')

const loose = parseProposeJsonLoose('{"requirement":"x","repo":"a/b","ref":"main"}')
assert(loose?.repo === 'a/b', 'loose json repo')

const hidden = hideCursorDevMachineBlocks(withPropose)
assert(!/:::cursor_dev/.test(hidden), 'hide machine blocks')

const opts = {
  groups: [
    { id: 'stack', label: '技术栈', options: [{ id: 'vue', label: 'Vue' }] },
    { id: 'scope', label: '范围', options: [{ id: 'login', label: '登录' }] },
  ],
  summary: 'x',
}
const stripped = stripLockedStackOptionGroups(opts, true)
assert(stripped.groups.length === 1 && stripped.groups[0].id === 'scope', 'strip locked stack')
assert(stripLockedStackOptionGroups(opts, false).groups.length === 2, 'keep when unlocked')

assert(/系统配置/.test(formatCursorDevAdminGuide('Key 无效')), 'admin guide')
assert(/重试写码/.test(formatCursorDevAdminGuide('并发已满')), 'quota guide')

console.log('SMOKE_OK chatCursorDevParse')
