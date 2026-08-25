/**
 * smoke: chatAnalysisChartParse.js
 * 用法：node apps/web/scripts/smoke_chat_analysis_chart_parse.mjs
 */
import {
  chartFingerprint,
  mergeUniqueCharts,
  parseAnalysisChartFences,
} from '../src/chatAnalysisChartParse.js'

function ok(name) {
  console.log('OK  ', name)
}

function fail(name, detail) {
  console.error('FAIL', name, detail || '')
  process.exitCode = 1
}

const fence = `看图：
:::analysis_chart
{"title":"状态分布","chart_type":"pie","option":{"series":[{"type":"pie","data":[{"name":"A","value":1}]}]}}
:::
正文续`
const parsed = parseAnalysisChartFences(fence)
if (parsed.charts.length === 1 && parsed.charts[0].title === '状态分布' && parsed.content.includes('正文续')) {
  ok('parse analysis_chart fence')
} else {
  fail('parse analysis_chart fence', JSON.stringify(parsed))
}

const bad = parseAnalysisChartFences(':::analysis_chart\n{not json}\n:::')
if (bad.charts.length === 0 && bad.content.includes(':::analysis_chart')) {
  ok('keep invalid fence')
} else {
  fail('keep invalid fence', JSON.stringify(bad))
}

const a = { title: 'T', chart_type: 'bar', option: { xAxis: { data: [1] }, series: [{ data: [2] }] } }
const b = { title: 'T', chart_type: 'bar', option: { xAxis: { data: [1] }, series: [{ data: [2] }] } }
const c = { title: 'U', chart_type: 'bar', option: { xAxis: { data: [9] }, series: [{ data: [8] }] } }
if (chartFingerprint(a) === chartFingerprint(b) && chartFingerprint(a) !== chartFingerprint(c)) {
  ok('fingerprint')
} else {
  fail('fingerprint')
}

const merged = mergeUniqueCharts([a], [b, c])
if (merged.length === 2 && merged[0].title === 'T' && merged[1].title === 'U') {
  ok('merge unique')
} else {
  fail('merge unique', merged)
}

if (!process.exitCode) {
  console.log('SMOKE_OK chatAnalysisChartParse')
}
