<template>
  <div
    class="analysis-dashboard-card"
    :class="{
      'adc-war': isWarRoom,
      'adc-dark': isDark,
    }"
  >
    <div class="adc-head">
      <span class="adc-badge">{{ isWarRoom ? '运营大屏' : '分析看板' }}</span>
      <span class="adc-title">{{ board.title || '运营看板' }}</span>
      <span class="adc-meta" v-if="metaText">{{ metaText }}</span>
    </div>

    <div class="adc-kpis" v-if="kpis.length">
      <div
        v-for="(k, i) in kpis"
        :key="k.id || i"
        class="adc-kpi"
        :style="{ animationDelay: `${i * 80}ms` }"
      >
        <div class="adc-kpi-label">{{ k.label }}</div>
        <div class="adc-kpi-value">
          <span class="adc-kpi-num">{{ k.value }}</span>
          <span class="adc-kpi-unit" v-if="k.unit">{{ k.unit }}</span>
        </div>
        <div class="adc-kpi-hint" v-if="k.hint">{{ k.hint }}</div>
      </div>
    </div>

    <div class="adc-body" :class="{ 'has-drill': !!drillOpen }">
      <div class="adc-grid" v-if="charts.length">
        <div
          v-for="(ch, i) in charts"
          :key="ch.id || ('adc-' + i)"
          class="adc-cell"
          :class="{ active: drillOpen && drillOpen.chartId === ch.id }"
        >
          <AnalysisChartCard
            :chart="ch"
            compact
            :war-room="isWarRoom"
            @point-click="(p) => onPointClick(ch, p)"
          />
        </div>
      </div>

      <aside class="adc-drill" v-if="drillOpen">
        <div class="adc-drill-head">
          <div>
            <div class="adc-drill-title">{{ drillOpen.title }}</div>
            <div class="adc-drill-sub">
              {{ drillOpen.category }}
              <template v-if="drillOpen.value != null">
                · {{ drillOpen.value }}
                <template v-if="drillOpen.percent != null">
                  （{{ drillOpen.percent }}%）
                </template>
              </template>
            </div>
          </div>
          <button type="button" class="adc-drill-close" @click="drillOpen = null">关闭</button>
        </div>
        <div class="adc-drill-empty" v-if="!drillRows.length">
          暂无明细行。可对话追问「{{ drillOpen.category }}」相关清单。
        </div>
        <div
          class="adc-drill-warn"
          v-else-if="drillOpen.fallbackAll"
        >
          未精确匹配到「{{ drillOpen.category }}」明细，下列为该图抽样行（请再对话按条件筛选）。
        </div>
        <div class="adc-drill-table-wrap" v-if="drillRows.length">
          <table class="adc-drill-table">
            <thead>
              <tr>
                <th v-for="h in drillHeaders" :key="h">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in drillRows" :key="ri">
                <td v-for="h in drillHeaders" :key="h">{{ row[h] ?? '' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="adc-drill-tip">点击图上其它类目可切换明细</div>
      </aside>
    </div>

    <ul class="adc-gaps" v-if="gaps.length">
      <li v-for="(g, i) in gaps" :key="g.id || i">
        <span class="adc-gap-title">{{ g.title || g.id || '缺口' }}</span>
        — {{ g.reason || '资料包未覆盖' }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import AnalysisChartCard from './AnalysisChartCard.vue'

const props = defineProps({
  board: {
    type: Object,
    required: true,
  },
})

const drillOpen = ref(null)

const charts = computed(() =>
  (props.board?.charts || []).filter((c) => c && c.option),
)

const gaps = computed(() =>
  (props.board?.gaps || []).filter((g) => g && (g.title || g.reason)),
)

const kpis = computed(() =>
  (props.board?.kpis || []).filter((k) => k && (k.label || k.value)),
)

const isWarRoom = computed(
  () =>
    props.board?.presentation === true ||
    props.board?.skin === 'ops_dark' ||
    kpis.value.length > 0,
)

const isDark = computed(
  () => (props.board?.skin || 'ops_dark') === 'ops_dark' && isWarRoom.value,
)

const metaText = computed(() => {
  const n = charts.value.length
  const g = gaps.value.length
  const parts = []
  if (n) parts.push(`${n} 图`)
  if (g) parts.push(`${g} 缺口`)
  if (isWarRoom.value) parts.push('可点图下钻')
  return parts.join(' · ')
})

const drillHeaders = computed(() => {
  const rows = drillRows.value
  if (!rows.length) return []
  return Object.keys(rows[0]).filter((k) => k !== '_group').slice(0, 8)
})

const drillRows = computed(() => {
  const d = drillOpen.value
  if (!d) return []
  return d.rows || []
})

function rowMatchesCategory(row, category, groupField) {
  if (!row || !category) return false
  const cat = String(category).trim()
  if (!cat) return false
  if (groupField && row[groupField] != null && String(row[groupField]).trim() === cat) {
    return true
  }
  if (row._group != null && String(row._group).trim() === cat) return true
  // 中文展示行：任意单元格等于类目名
  return Object.values(row).some((v) => String(v ?? '').trim() === cat)
}

function onPointClick(chart, point) {
  const drill = chart?.drill
  const category = String(point?.name || '').trim()
  if (!category) return
  const allRows = Array.isArray(drill?.rows) ? drill.rows : []
  const groupField = drill?.group_field || ''
  let rows = allRows.filter((r) => rowMatchesCategory(r, category, groupField))
  // 匹配不上时：若有 rows 仍展示全部并标注（避免空白翻车）
  let noteRows = rows
  if (!noteRows.length && allRows.length) {
    noteRows = allRows.slice(0, 12)
  }
  drillOpen.value = {
    chartId: chart.id,
    title: chart.title || drill?.title || '下钻明细',
    category,
    value: point?.value,
    percent: point?.percent,
    rows: noteRows,
    fallbackAll: rows.length === 0 && allRows.length > 0,
  }
}
</script>

<style scoped>
.analysis-dashboard-card {
  display: block;
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  margin: 10px 0 8px;
  padding: 12px 12px 14px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #f3f4f6 100%);
}
.adc-war {
  padding: 14px 14px 16px;
}
.adc-dark {
  border-color: #2a3038;
  background: linear-gradient(165deg, #151a20 0%, #1c232c 55%, #12161b 100%);
  color: #e8eef5;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.28);
}
.adc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.adc-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1e3a5f;
}
.adc-dark .adc-badge {
  background: rgba(62, 207, 142, 0.18);
  color: #7dffa8;
}
.adc-title {
  font-size: 16px;
  font-weight: 650;
  color: var(--text, #111827);
}
.adc-dark .adc-title {
  color: #f3f6fa;
  font-size: 17px;
  letter-spacing: 0.02em;
}
.adc-meta {
  font-size: 12px;
  color: #6b7280;
  margin-left: auto;
}
.adc-dark .adc-meta {
  color: #9aa6b5;
}

.adc-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.adc-kpi {
  padding: 12px 12px 10px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  animation: adc-kpi-in 0.45s ease both;
}
.adc-dark .adc-kpi {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.08);
}
.adc-kpi-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.adc-dark .adc-kpi-label {
  color: #9aa6b5;
}
.adc-kpi-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.adc-kpi-num {
  font-size: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #111827;
  line-height: 1.1;
}
.adc-dark .adc-kpi-num {
  color: #7dffa8;
  text-shadow: 0 0 24px rgba(62, 207, 142, 0.25);
}
.adc-kpi-unit {
  font-size: 13px;
  color: #6b7280;
}
.adc-dark .adc-kpi-unit {
  color: #9aa6b5;
}
.adc-kpi-hint {
  margin-top: 4px;
  font-size: 11px;
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
@keyframes adc-kpi-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.adc-body {
  display: block;
}
.adc-body.has-drill {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 32%);
  gap: 12px;
  align-items: stretch;
}
.adc-grid {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.adc-war .adc-grid {
  gap: 14px;
}
.adc-cell {
  min-width: 0;
  width: 100%;
  overflow: visible;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 4px 2px 2px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.adc-dark .adc-cell {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
}
.adc-cell.active {
  border-color: #3ecf8e;
  box-shadow: 0 0 0 1px rgba(62, 207, 142, 0.35);
}

.adc-drill {
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
  padding: 10px 12px;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.adc-dark .adc-drill {
  background: rgba(0, 0, 0, 0.28);
  border-color: rgba(255, 255, 255, 0.1);
}
.adc-drill-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
}
.adc-drill-title {
  font-size: 13px;
  font-weight: 650;
}
.adc-drill-sub {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}
.adc-dark .adc-drill-sub {
  color: #9aa6b5;
}
.adc-drill-close {
  border: 1px solid #d1d5db;
  background: transparent;
  border-radius: 6px;
  font-size: 12px;
  padding: 2px 8px;
  cursor: pointer;
  color: inherit;
}
.adc-dark .adc-drill-close {
  border-color: rgba(255, 255, 255, 0.2);
}
.adc-drill-empty {
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.45;
  padding: 8px 0;
}
.adc-drill-warn {
  font-size: 12px;
  color: #b45309;
  line-height: 1.45;
  padding: 4px 0 2px;
}
.adc-dark .adc-drill-warn {
  color: #fbbf24;
}
.adc-drill-table-wrap {
  overflow: auto;
  max-height: 360px;
  flex: 1;
}
.adc-drill-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
.adc-drill-table th,
.adc-drill-table td {
  border-bottom: 1px solid #e5e7eb;
  padding: 5px 6px;
  text-align: left;
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.adc-dark .adc-drill-table th,
.adc-dark .adc-drill-table td {
  border-bottom-color: rgba(255, 255, 255, 0.08);
}
.adc-drill-table th {
  color: #6b7280;
  font-weight: 600;
  position: sticky;
  top: 0;
  background: #fff;
}
.adc-dark .adc-drill-table th {
  background: #1a2028;
  color: #9aa6b5;
}
.adc-drill-tip {
  font-size: 11px;
  color: #9ca3af;
}

.adc-gaps {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: #9a3412;
  line-height: 1.45;
}
.adc-dark .adc-gaps {
  color: #fbbf24;
}
.adc-gap-title {
  font-weight: 600;
}

@media (max-width: 900px) {
  .adc-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .adc-body.has-drill {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .adc-grid {
    grid-template-columns: 1fr;
  }
  .adc-kpis {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
