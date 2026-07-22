import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'

/** 简易 ECharts 封装：返回 chartRef + setOption + dispose */
export function useEChart() {
  const elRef = ref(null)
  const chart = shallowRef(null)

  function init() {
    if (!elRef.value) return
    if (chart.value) chart.value.dispose()
    chart.value = echarts.init(elRef.value)
  }

  function setOption(option, notMerge = true) {
    if (!chart.value && elRef.value) init()
    chart.value?.setOption(option, notMerge)
  }

  function resize() {
    chart.value?.resize()
  }

  function dispose() {
    chart.value?.dispose()
    chart.value = null
  }

  onMounted(() => {
    init()
    window.addEventListener('resize', resize)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', resize)
    dispose()
  })

  return { elRef, chart, setOption, resize, dispose, init }
}

export function useEChartPair() {
  const a = useEChart()
  const b = useEChart()
  return { a, b }
}

export function idealLine(minV, maxV) {
  return {
    type: 'line',
    name: 'y=x',
    data: [[minV, minV], [maxV, maxV]],
    symbol: 'none',
    lineStyle: { color: 'rgba(16,185,129,.65)', type: 'dashed', width: 1.5 },
    tooltip: { show: false },
  }
}
