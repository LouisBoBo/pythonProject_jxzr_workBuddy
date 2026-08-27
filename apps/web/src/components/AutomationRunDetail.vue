<template>
  <div class="run-detail">
    <div v-if="parsed.kind !== 'empty'" class="run-detail-toolbar">
      <el-button
        size="small"
        :type="copied ? 'success' : 'default'"
        :loading="copying"
        @click="onCopy"
      >
        {{ copied ? '已复制' : '一键复制' }}
      </el-button>
    </div>

    <div class="morning-banner">
      <span class="morning-banner-deco">— —</span>
      <span class="morning-banner-title">📰 {{ bannerTitle }} 📰</span>
      <span class="morning-banner-deco">— —</span>
    </div>

    <template v-if="parsed.kind === 'news'">
      <p v-if="parsed.intro" class="run-intro">{{ parsed.intro }}</p>

      <article v-for="item in parsed.items" :key="item.index" class="news-item">
        <div class="news-item-head">
          <span class="news-check" aria-hidden="true">✅</span>
          <span class="news-emoji" aria-hidden="true">{{ item.emoji }}</span>
          <h4 class="news-title">{{ item.title }}</h4>
        </div>
        <p v-if="item.points" class="news-body">
          <span class="news-tag">要点</span>
          {{ item.points }}
        </p>
        <p v-if="item.source || item.link" class="news-source-line">
          <span class="news-tag">{{ item.sourceLabel || '来源' }}</span>
          <a
            v-if="item.link"
            class="news-link"
            :href="item.link"
            target="_blank"
            rel="noopener noreferrer"
          >
            戳 👉 {{ linkLabel(item) }}
          </a>
          <span v-else>{{ item.source }}</span>
        </p>
      </article>
    </template>

    <template v-else-if="parsed.kind === 'report'">
      <p v-if="parsed.intro" class="run-intro">{{ parsed.intro }}</p>

      <section v-for="(sec, si) in parsed.sections" :key="si" class="report-section">
        <h4 class="report-section-title">{{ sec.title }}</h4>
        <ul v-if="sec.type === 'numbered'" class="report-list report-list--numbered">
          <li v-for="row in sec.items" :key="row.index" class="report-line">
            <span class="report-line-num">{{ row.index }}、</span>
            <span class="report-line-text">{{ row.text }}</span>
          </li>
        </ul>
        <ul v-else-if="sec.type === 'bullets'" class="report-list report-list--bullets">
          <li v-for="(row, bi) in sec.items" :key="bi" class="report-line report-line--bullet">
            <span class="report-bullet" aria-hidden="true">•</span>
            <span class="report-line-text">{{ row.text }}</span>
          </li>
        </ul>
        <p v-else class="report-para">{{ sec.items[0]?.text }}</p>
      </section>
    </template>

    <template v-else-if="parsed.kind === 'plain'">
      <p v-for="(para, idx) in parsed.paragraphs" :key="idx" class="run-para run-para--multiline">{{ para }}</p>
    </template>

    <p v-else class="run-empty">暂无摘要内容</p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { formatRunSummaryForCopy, isProductionDailyReport, parseRunSummary } from '../automationRunSummary.js'

const props = defineProps({
  summary: { type: String, default: '' },
  automationName: { type: String, default: '运行详情' },
})

const parsed = computed(() => parseRunSummary(props.summary))
const copied = ref(false)
const copying = ref(false)
let copiedTimer = null

const bannerTitle = computed(() => {
  if (isProductionDailyReport(props.summary, props.automationName)) return '生产日报'
  if (parsed.value.kind === 'news') return '今日精选'
  if (parsed.value.kind === 'report') return '本周简报'
  const name = String(props.automationName || '').trim()
  return name || '任务摘要'
})

function linkLabel(item) {
  if (item.source && item.source.length <= 48) return item.source
  try {
    const u = new URL(item.link)
    return u.hostname.replace(/^www\./, '')
  } catch {
    return '查看原文'
  }
}

async function copyTextToClipboard(text) {
  const value = text || ''
  if (!value) return false
  try {
    await navigator.clipboard.writeText(value)
    return true
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = value
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      return true
    } catch {
      return false
    }
  }
}

async function onCopy() {
  const text = formatRunSummaryForCopy(props.summary, props.automationName)
  if (!text) {
    ElMessage.warning('暂无可复制内容')
    return
  }
  copying.value = true
  const ok = await copyTextToClipboard(text)
  copying.value = false
  if (!ok) {
    ElMessage.error('复制失败，请手动选中内容复制')
    return
  }
  copied.value = true
  ElMessage.success('已复制到剪贴板')
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copied.value = false
  }, 2000)
}
</script>

<style scoped>
.run-detail {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-primary);
}

.run-detail-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.morning-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin-bottom: 18px;
  padding: 10px 8px;
  text-align: center;
}

.morning-banner-deco {
  color: var(--text-tertiary);
  font-size: 13px;
  letter-spacing: 2px;
}

.morning-banner-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.run-intro {
  margin: 0 0 20px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-left: 3px solid #e8eef5;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.65;
}

.news-item {
  margin-bottom: 22px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f1f5f9;
}

.news-item:last-of-type {
  border-bottom: none;
  margin-bottom: 8px;
  padding-bottom: 0;
}

.news-item-head {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 10px;
}

.news-check {
  flex-shrink: 0;
  font-size: 15px;
  line-height: 1.5;
}

.news-emoji {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 1.5;
}

.news-title {
  margin: 0;
  flex: 1;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.55;
  color: var(--text-primary);
}

.news-body,
.news-source-line {
  margin: 0 0 8px;
  padding-left: 28px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.news-source-line {
  margin-bottom: 0;
  color: var(--text-tertiary);
  font-size: 13px;
}

.news-tag {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 7px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  vertical-align: 0.05em;
}

.news-link {
  color: #2563eb;
  text-decoration: none;
  word-break: break-all;
}

.news-link:hover {
  text-decoration: underline;
}

.run-para {
  margin: 0 0 14px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.run-para--multiline {
  white-space: pre-line;
}

.report-section {
  margin-bottom: 22px;
}

.report-section:last-child {
  margin-bottom: 0;
}

.report-section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.5;
}

.report-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.report-line {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.report-line:last-child {
  margin-bottom: 0;
}

.report-line-num {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 1.6em;
}

.report-line-text {
  flex: 1;
  min-width: 0;
}

.report-bullet {
  flex-shrink: 0;
  color: var(--brand);
  line-height: 1.75;
  width: 1em;
}

.report-para {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-secondary);
}

.run-para:last-child {
  margin-bottom: 0;
}

.run-empty {
  margin: 0;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 24px 0;
}
</style>
