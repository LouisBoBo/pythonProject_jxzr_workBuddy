<template>
  <div class="analysis-chart-card" :class="{ compact, 'war-room': warRoom }" :style="cardStyle">
    <div class="acc-head">
      <span class="acc-badge" v-if="!compact">分析图</span>
      <span class="acc-title">{{ chart.title || '分析图' }}</span>
      <span class="acc-type" v-if="displayType">{{ displayType }}</span>
      <span class="acc-drill-hint" v-if="compact && chart.drill?.enabled">点击下钻</span>
    </div>
    <p class="acc-def" v-if="chart.definition && !compact">{{ chart.definition }}</p>
    <ul class="acc-caveats" v-if="caveats.length && !compact">
      <li v-for="(c, i) in caveats" :key="i">{{ c }}</li>
    </ul>
    <div ref="el" class="acc-chart" role="img" :aria-label="chart.title || '分析图'" />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const PIE_TOP_N = 8
const CART_HORIZONTAL_N = 8
const CART_HORIZONTAL_LEN = 8
const CART_ZOOM_N = 12
const LABEL_SHOW_MAX = 10

const props = defineProps({
  chart: {
    type: Object,
    required: true,
  },
  compact: {
    type: Boolean,
    default: false,
  },
  warRoom: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['point-click'])

const el = ref(null)
let chartInst = null
let ro = null
let clickHandler = null

const caveats = computed(() =>
  (props.chart?.caveats || []).map((c) => String(c || '').trim()).filter(Boolean).slice(0, 5),
)

const displayType = computed(() => {
  const series = props.chart?.option?.series
  const fromSeries = Array.isArray(series)
    ? series.find((s) => s && (s.type === 'pie' || s.type === 'bar' || s.type === 'line'))?.type
    : null
  return String(fromSeries || props.chart?.chart_type || '').toLowerCase()
})

const layoutMeta = computed(() => {
  const opt = props.chart?.option || {}
  return props.chart?.layout || opt._wb_layout || {}
})

const chartHeight = computed(() => {
  if (props.warRoom) {
    const hint = Number(layoutMeta.value?.height_hint)
    if (Number.isFinite(hint) && hint >= 200) return Math.min(340, Math.max(280, hint))
    return 300
  }
  if (props.compact) {
    const hint = Number(layoutMeta.value?.height_hint)
    // 看板格：控制在 240～300，宽扁好看
    if (Number.isFinite(hint) && hint >= 200) return Math.min(300, Math.max(240, hint))
    return 260
  }
  const hint = Number(layoutMeta.value?.height_hint)
  if (Number.isFinite(hint) && hint >= 280) return Math.min(720, hint)
  return 360
})

const cardStyle = computed(() => ({
  '--acc-chart-h': `${chartHeight.value}px`,
}))

function pieLabelWidth(data) {
  const maxLen = (data || []).reduce((m, d) => Math.max(m, String(d?.name ?? '').length), 0)
  if (maxLen >= 16) return 120
  if (maxLen >= 10) return 100
  return 80
}

function aggregatePieData(data) {
  if (!Array.isArray(data) || data.length <= PIE_TOP_N) return data
  const paired = data
    .map((d) => ({
      name: String(d?.name ?? ''),
      value: Number(d?.value) || 0,
    }))
    .sort((a, b) => b.value - a.value)
  const keep = paired.slice(0, PIE_TOP_N)
  const rest = paired.slice(PIE_TOP_N)
  const other = rest.reduce((s, x) => s + x.value, 0)
  return [...keep, { name: '其他', value: other }]
}

function normalizePieOption(option, { compact = false } = {}) {
  const series = option.series
  if (!Array.isArray(series)) return option
  const pieIdx = series.findIndex((s) => s && s.type === 'pie')
  if (pieIdx < 0) return option

  let data = Array.isArray(series[pieIdx].data) ? series[pieIdx].data : []
  data = aggregatePieData(data)
  const n = data.length
  const dense = n >= 6
  const labelW = pieLabelWidth(data)

  option.tooltip = {
    trigger: 'item',
    formatter: '{b}<br/>{c}（{d}%）',
    ...(option.tooltip || {}),
  }

  // 看板格：保留名称+百分比；缩小环半径给外标留空；勿裁切
  if (compact) {
    const label = {
      show: true,
      formatter: '{b} {d}%',
      fontSize: dense ? 10 : 11,
      lineHeight: 14,
      overflow: 'truncate',
      width: Math.min(labelW, dense ? 72 : 88),
      ellipsis: '…',
      alignTo: 'labelLine',
      bleedMargin: 2,
      distanceToLabelLine: 2,
    }
    const labelLine = {
      show: true,
      length: dense ? 8 : 10,
      length2: dense ? 8 : 10,
      smooth: 0.2,
    }
    option.legend = dense
      ? {
          type: 'scroll',
          orient: 'horizontal',
          bottom: 0,
          left: 'center',
          width: '96%',
          itemWidth: 10,
          itemHeight: 8,
          textStyle: { fontSize: 10 },
          pageIconSize: 10,
        }
      : { show: false }
    option.series[pieIdx] = {
      ...series[pieIdx],
      data,
      radius: dense ? ['26%', '42%'] : ['30%', '50%'],
      center: dense ? ['50%', '46%'] : ['50%', '50%'],
      avoidLabelOverlap: true,
      minShowLabelAngle: 3,
      stillShowZeroSum: false,
      label,
      labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' },
      labelLine,
      emphasis: {
        ...(series[pieIdx].emphasis || {}),
        label: {
          show: true,
          fontSize: 12,
          fontWeight: 'bold',
          width: labelW + 12,
          overflow: 'none',
        },
        labelLine: { show: true },
      },
    }
    // 压矮：宽扁比例，避免「又窄又长」
    option._wb_layout = {
      mode: dense ? 'pie_compact_labeled' : 'pie_compact',
      height_hint: dense ? 280 : 260,
      category_count: n,
    }
    return option
  }

  const label = {
    show: true,
    formatter: '{b}\n{d}%',
    fontSize: dense ? 10 : 11,
    lineHeight: 14,
    overflow: 'truncate',
    width: labelW,
    ellipsis: '…',
    alignTo: 'labelLine',
    bleedMargin: 4,
    distanceToLabelLine: 4,
  }
  const labelLine = {
    show: true,
    length: dense ? 14 : 12,
    length2: dense ? 12 : 10,
    smooth: 0.2,
  }

  if (dense) {
    option.legend = {
      type: 'scroll',
      orient: 'horizontal',
      bottom: 2,
      left: 'center',
      width: '94%',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 10 },
      pageIconSize: 10,
    }
  } else {
    option.legend = { show: false }
  }

  option.series[pieIdx] = {
    ...series[pieIdx],
    data,
    radius: dense ? ['28%', '48%'] : ['34%', '58%'],
    center: dense ? ['50%', '48%'] : ['50%', '52%'],
    avoidLabelOverlap: true,
    minShowLabelAngle: 2,
    stillShowZeroSum: false,
    label,
    labelLayout: { hideOverlap: false, moveOverlap: 'shiftY' },
    labelLine,
    emphasis: {
      ...(series[pieIdx].emphasis || {}),
      label: {
        show: true,
        fontSize: 12,
        fontWeight: 'bold',
        width: labelW + 20,
        overflow: 'none',
      },
      labelLine: { show: true },
    },
  }
  option._wb_layout = {
    mode: dense ? 'pie_labeled' : 'pie',
    height_hint: dense ? 520 : 400,
    category_count: n,
  }
  return option
}

function axisLabelTruncate(maxLen) {
  const width = maxLen >= 12 ? 88 : maxLen >= 8 ? 72 : 56
  return {
    interval: 0,
    fontSize: 11,
    hideOverlap: true,
    overflow: 'truncate',
    width,
    ellipsis: '…',
  }
}

function categoryAxisData(option) {
  const x = option.xAxis
  if (Array.isArray(x?.data)) return x.data
  if (Array.isArray(x?.[0]?.data)) return x[0].data
  const y = option.yAxis
  if (y?.type === 'category' && Array.isArray(y.data)) return y.data
  if (Array.isArray(y?.[0]?.data) && y[0]?.type === 'category') return y[0].data
  return []
}

function seriesType(option) {
  const s = (option.series || []).find((x) => x && (x.type === 'bar' || x.type === 'line'))
  return s?.type || 'bar'
}

function normalizeBarLineOption(option, { compact = false } = {}) {
  const cats = categoryAxisData(option).map((c) => String(c ?? ''))
  if (!cats.length) return option

  const n = cats.length
  const maxLen = cats.reduce((m, c) => Math.max(m, c.length), 0)
  const ctype = seriesType(option)
  const alreadyHorizontal =
    option.yAxis?.type === 'category' ||
    (Array.isArray(option.yAxis) && option.yAxis[0]?.type === 'category') ||
    option._wb_layout?.mode === 'horizontal'

  const useHorizontal =
    alreadyHorizontal ||
    (ctype === 'bar' && (n >= CART_HORIZONTAL_N || maxLen >= CART_HORIZONTAL_LEN))
  const showValueLabel = compact ? n <= 5 : n <= LABEL_SHOW_MAX
  const needZoom = n >= CART_ZOOM_N
  const titleText = option.title?.text || option.title?.[0]?.text
  const title = {
    text: titleText || '分析图',
    left: 'center',
    top: 4,
    textStyle: { fontSize: compact ? 13 : 14 },
  }
  const tooltip = {
    trigger: 'axis',
    axisPointer: { type: ctype === 'bar' ? 'shadow' : 'line' },
  }
  const name =
    (option.series || []).find((s) => s && (s.type === 'bar' || s.type === 'line'))?.name || '数量'
  const vals = (option.series || []).find((s) => s && (s.type === 'bar' || s.type === 'line'))?.data

  if (useHorizontal) {
    const heightHint = compact
      ? Math.min(280, Math.max(240, 36 + Math.min(n, 6) * 30))
      : Math.min(720, Math.max(360, 48 + n * 28))
    option.title = compact ? { show: false } : title
    option.tooltip = tooltip
    option.grid = {
      left: '4%',
      right: showValueLabel ? '12%' : '6%',
      top: compact ? '8%' : '14%',
      bottom: needZoom || (compact && n > 6) ? '14%' : '6%',
      containLabel: true,
    }
    option.xAxis = { type: 'value', minInterval: 1, splitNumber: 4 }
    option.yAxis = {
      type: 'category',
      data: cats,
      inverse: true,
      axisTick: { alignWithLabel: true },
      axisLabel: { ...axisLabelTruncate(maxLen), margin: 10 },
    }
    option.series = (option.series || []).map((s) => {
      if (!s || (s.type && s.type !== 'bar' && s.type !== 'line')) return s
      return {
        ...s,
        name: s.name || name,
        type: s.type || ctype,
        data: Array.isArray(s.data) ? s.data : vals,
        barMaxWidth: compact ? 16 : 22,
        barCategoryGap: '35%',
        label: { show: showValueLabel, position: 'right', fontSize: 11 },
      }
    })
    if (needZoom || (compact && n > 6)) {
      option.dataZoom = [
        {
          type: 'slider',
          yAxisIndex: 0,
          width: 12,
          right: 2,
          start: 0,
          end: Math.max(18, (100 * Math.min(6, n)) / n),
          brushSelect: false,
        },
        {
          type: 'inside',
          yAxisIndex: 0,
          zoomOnMouseWheel: false,
          moveOnMouseWheel: true,
        },
      ]
    } else {
      delete option.dataZoom
    }
    option._wb_layout = {
      mode: 'horizontal',
      height_hint: heightHint,
      category_count: n,
    }
    return option
  }

  const needTilt = maxLen >= 6 || n >= 4
  const rotate = needTilt && maxLen >= 8 ? 45 : needTilt ? 35 : 0
  const bottom = needZoom ? '28%' : rotate >= 40 ? '24%' : rotate ? '16%' : '10%'
  option.title = compact ? { show: false } : title
  option.tooltip = tooltip
  option.grid = {
    left: '8%',
    right: '6%',
    top: compact ? '10%' : '16%',
    bottom,
    containLabel: true,
  }
  option.xAxis = {
    type: 'category',
    boundaryGap: ctype !== 'line',
    data: cats,
    axisTick: { alignWithLabel: true },
    axisLabel: {
      ...axisLabelTruncate(maxLen),
      rotate,
      margin: 14,
      hideOverlap: true,
    },
  }
  // 保留后端良率轴（0～100）与 areaStyle，勿覆盖成默认轴
  const prevY = option.yAxis
  const keepY =
    prevY &&
    typeof prevY === 'object' &&
    !Array.isArray(prevY) &&
    (prevY.min != null || prevY.max != null || ctype === 'line')
  option.yAxis = keepY
    ? {
        ...prevY,
        type: 'value',
        splitNumber: prevY.splitNumber ?? 4,
      }
    : { type: 'value', minInterval: 1, splitNumber: 4 }
  option.series = (option.series || []).map((s) => {
    if (!s || (s.type && s.type !== 'bar' && s.type !== 'line')) return s
    const isLine = (s.type || ctype) === 'line'
    const next = {
      ...s,
      smooth: isLine ? (s.smooth ?? true) : s.smooth,
      barMaxWidth: s.barMaxWidth ?? (n <= 8 ? 48 : 36),
      barCategoryGap: s.barCategoryGap ?? (n <= 6 ? '42%' : '28%'),
      label: {
        show: showValueLabel && (!isLine || s.label?.show),
        position: 'top',
        fontSize: 11,
        ...(s.label && typeof s.label === 'object' ? { color: s.label.color } : {}),
      },
    }
    if (isLine && s.areaStyle) {
      next.areaStyle = s.areaStyle
      next.lineStyle = s.lineStyle || next.lineStyle
      next.itemStyle = s.itemStyle || next.itemStyle
      next.symbol = s.symbol || 'circle'
      next.symbolSize = s.symbolSize ?? 8
      next.showSymbol = s.showSymbol !== false
    }
    return next
  })
  if (needZoom) {
    option.dataZoom = [
      {
        type: 'slider',
        xAxisIndex: 0,
        height: 18,
        bottom: 6,
        start: 0,
        end: Math.max(18, (100 * Math.min(10, n)) / n),
        brushSelect: false,
      },
      { type: 'inside', xAxisIndex: 0 },
    ]
  } else {
    delete option.dataZoom
  }
  option._wb_layout = {
    mode: 'vertical',
    height_hint: compact ? 260 : needZoom || rotate ? 400 : 360,
    category_count: n,
  }
  return option
}

function applyWarRoomTheme(option) {
  if (!props.warRoom || !option || typeof option !== 'object') return option
  const axisLabel = { color: '#9aa6b5' }
  const axisLine = { lineStyle: { color: 'rgba(255,255,255,0.12)' } }
  const splitLine = { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
  const patchAxis = (axis) => {
    if (!axis) return axis
    if (Array.isArray(axis)) return axis.map((a) => patchAxis(a))
    return {
      ...axis,
      axisLabel: { ...(axis.axisLabel || {}), ...axisLabel },
      axisLine: { ...(axis.axisLine || {}), ...axisLine },
      splitLine: { ...(axis.splitLine || {}), ...splitLine },
    }
  }
  option.xAxis = patchAxis(option.xAxis)
  option.yAxis = patchAxis(option.yAxis)
  if (option.legend && typeof option.legend === 'object') {
    option.legend = {
      ...option.legend,
      textStyle: { ...(option.legend.textStyle || {}), color: '#c5ced8', fontSize: 10 },
      pageTextStyle: { color: '#9aa6b5' },
    }
  }
  // 饼图外标颜色
  const series = option.series
  if (Array.isArray(series)) {
    option.series = series.map((s) => {
      if (!s || s.type !== 'pie') return s
      return {
        ...s,
        label: {
          ...(s.label || {}),
          color: '#d7dee8',
        },
      }
    })
  }
  return option
}

function normalizeOption(raw) {
  if (!raw || typeof raw !== 'object') return raw
  const option = JSON.parse(JSON.stringify(raw))
  const compact = !!props.compact
  const hasPie = (option.series || []).some((s) => s && s.type === 'pie')
  let next
  if (hasPie) next = normalizePieOption(option, { compact })
  else {
    const isBarOrLine = (option.series || []).some(
      (s) => s && (s.type === 'bar' || s.type === 'line' || !s.type),
    )
    next = isBarOrLine ? normalizeBarLineOption(option, { compact }) : option
  }
  return applyWarRoomTheme(next)
}

function applyLayoutHeight(option) {
  if (!el.value) return
  if (props.compact) {
    el.value.style.height = `${chartHeight.value}px`
    return
  }
  const hint = Number(option?._wb_layout?.height_hint)
  if (Number.isFinite(hint) && hint >= 280) {
    el.value.style.height = `${Math.min(720, hint)}px`
  }
}

function bindClick() {
  if (!chartInst) return
  if (clickHandler) {
    chartInst.off('click', clickHandler)
    clickHandler = null
  }
  clickHandler = (params) => {
    if (!params) return
    const name =
      params.name != null && String(params.name)
        ? String(params.name)
        : Array.isArray(params.value)
          ? String(params.value[0] ?? '')
          : ''
    if (!name) return
    let value = params.value
    if (typeof value === 'object' && value && 'value' in value) value = value.value
    if (Array.isArray(value)) value = value[value.length - 1]
    const percent =
      params.percent != null
        ? Number(params.percent)
        : params.data?.percent != null
          ? Number(params.data.percent)
          : null
    emit('point-click', {
      name,
      value: value != null ? Number(value) : null,
      percent: Number.isFinite(percent) ? Math.round(percent * 10) / 10 : null,
      dataIndex: params.dataIndex,
      seriesType: params.seriesType,
    })
  }
  chartInst.on('click', clickHandler)
  try {
    chartInst.getZr()?.setCursorStyle?.('pointer')
  } catch (_) {
    /* ignore */
  }
}

function render() {
  if (!el.value) return
  const option = normalizeOption(props.chart?.option)
  if (!option || typeof option !== 'object') return
  applyLayoutHeight(option)
  if (!chartInst) {
    chartInst = echarts.init(el.value, undefined, { renderer: 'canvas' })
  }
  chartInst.setOption(option, true)
  chartInst.resize()
  bindClick()
}

onMounted(() => {
  render()
  if (typeof ResizeObserver !== 'undefined' && el.value) {
    ro = new ResizeObserver(() => {
      chartInst?.resize()
    })
    ro.observe(el.value)
  }
})

watch(
  () => [props.chart?.option, props.chart?.layout, props.warRoom],
  () => render(),
  { deep: true },
)

onUnmounted(() => {
  ro?.disconnect()
  ro = null
  if (chartInst && clickHandler) {
    chartInst.off('click', clickHandler)
  }
  clickHandler = null
  chartInst?.dispose()
  chartInst = null
})
</script>

<style scoped>
.analysis-chart-card {
  margin: 10px 0 4px;
  padding: 12px 14px 10px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 10px;
  background: var(--surface, #fafafa);
}
.acc-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.acc-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e8eef7;
  color: #1e3a5f;
}
.acc-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text, #111827);
}
.acc-type {
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
}
.acc-def {
  margin: 0 0 6px;
  font-size: 12px;
  color: #4b5563;
  line-height: 1.45;
}
.acc-caveats {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 12px;
  color: #9a3412;
}
.acc-chart {
  width: 100%;
  height: var(--acc-chart-h, 360px);
  min-height: 280px;
}
.analysis-chart-card.compact {
  margin: 0;
  padding: 8px 10px 6px;
  height: 100%;
  background: #fff;
}
.analysis-chart-card.compact .acc-title {
  font-size: 13px;
}
.analysis-chart-card.compact .acc-chart {
  min-height: 240px;
  height: var(--acc-chart-h, 260px);
}
.analysis-chart-card.war-room {
  background: transparent;
  border: none;
  padding: 6px 8px 4px;
}
.analysis-chart-card.war-room .acc-title {
  color: #e8eef5;
  font-size: 13px;
}
.analysis-chart-card.war-room .acc-type {
  color: #8b98a8;
}
.analysis-chart-card.war-room .acc-chart {
  min-height: 280px;
  height: var(--acc-chart-h, 300px);
}
.acc-drill-hint {
  margin-left: auto;
  font-size: 10px;
  color: #3ecf8e;
  opacity: 0.85;
}
</style>
