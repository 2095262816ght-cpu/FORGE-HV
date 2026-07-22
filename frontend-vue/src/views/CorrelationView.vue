<template>
  <div>
    <PageHeader
      sub="第 2 章 · 22 种元素成分关系"
      title="元素"
      em="相关性"
      desc="22 种合金元素成分（Al/W/Ta/Ti/Cr 等）间的相关性矩阵。Pearson / Spearman / Kendall 三种方法，自动列出 |r|≥0.7 的高耦合元素对。"
    />

    <div class="card" style="margin-bottom:20px">
      <div class="card-head">
        <div class="card-title"><span class="num">A</span>相关性矩阵</div>
        <div class="chips">
          <span
            v-for="m in CORR_METHODS"
            :key="m.value"
            class="chip"
            :class="{ on: method === m.value }"
            @click="load(m.value)"
          >{{ m.label }}</span>
        </div>
      </div>
      <div class="card-body">
        <div class="corr-legend">
          <span><i class="corr-dot pos"></i>蓝 = 正相关</span>
          <span><i class="corr-dot neg"></i>青 = 负相关</span>
          <span>气泡大小 = |r|</span>
        </div>
        <div v-loading="loading" ref="chartEl" class="chart-box tall corr-chart"></div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-title"><span class="num">B</span>高耦合元素对（|r| ≥ 0.7）</div>
        <span class="tag tag-ember">{{ pairs.length }} 对</span>
      </div>
      <div class="card-body">
        <div class="table-wrap" style="max-height:280px">
          <table class="data">
            <thead>
              <tr>
                <th>#</th>
                <th>元素 A</th>
                <th>元素 B</th>
                <th>相关系数 r</th>
                <th>强度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!pairs.length">
                <td colspan="5" style="text-align:center;color:var(--text-faint);padding:24px">
                  {{ loading ? '计算中…' : '✓ 无 |r|≥0.7 的高耦合对' }}
                </td>
              </tr>
              <tr v-for="(p, i) in pairs" :key="`${p.a}-${p.b}`">
                <td class="idx">{{ i + 1 }}</td>
                <td class="tgt">{{ p.a }}</td>
                <td class="tgt">{{ p.b }}</td>
                <td :style="{ color: p.r >= 0 ? 'var(--ember-hot)' : 'var(--copper)', fontWeight: 600 }">
                  {{ p.r > 0 ? '+' : '' }}{{ (+p.r).toFixed(3) }}
                </td>
                <td><span class="tag" :class="strengthTag(p.r)">{{ strength(p.r) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { get } from '@/api/http'
import { CORR_METHODS } from '@/utils/constants'
import { useEChart } from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'

const method = ref('pearson')
const loading = ref(false)
const pairs = ref([])
const { elRef: chartEl, setOption } = useEChart()

function strength(r) {
  const a = Math.abs(r)
  if (a >= 0.9) return '极强'
  if (a >= 0.8) return '强'
  return '中'
}

function strengthTag(r) {
  const a = Math.abs(r)
  if (a >= 0.9) return 'tag-danger'
  if (a >= 0.8) return 'tag-ember'
  return 'tag-warn'
}

function bubbleColor(v) {
  const a = Math.abs(v)
  const alpha = Math.min(0.15 + a * 0.8, 0.95)
  return v >= 0
    ? `rgba(37, 99, 235, ${alpha})`
    : `rgba(2, 132, 199, ${alpha})`
}

function renderBubbleMatrix(cols, matrix) {
  const N = cols.length
  if (!N) {
    setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#94A3B8', fontSize: 14 } } })
    return
  }

  const data = []
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const v = +matrix[i][j]
      data.push({
        value: [j, N - 1 - i, v],
        itemStyle: {
          color: bubbleColor(v),
          borderColor: v >= 0 ? '#2563EB' : '#0284C7',
          borderWidth: Math.abs(v) >= 0.7 ? 1.5 : 0.6,
          shadowBlur: Math.abs(v) >= 0.85 ? 8 : 0,
          shadowColor: v >= 0 ? 'rgba(37,99,235,.3)' : 'rgba(2,132,199,.3)',
        },
      })
    }
  }

  const maxBubble = Math.min(22, Math.max(12, Math.floor(420 / N)))

  setOption({
    animationDuration: 450,
    title: {
      text: '元素相关性矩阵（蓝=正相关 · 青=负相关 · 气泡大小=|r|）',
      left: 0,
      top: 0,
      textStyle: {
        fontSize: 13,
        fontWeight: 500,
        color: '#0F172A',
        fontFamily: 'Source Sans 3, sans-serif',
      },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,.98)',
      borderColor: 'rgba(15,23,42,.08)',
      borderWidth: 1,
      textStyle: { color: '#0F172A', fontSize: 12 },
      formatter: (p) => {
        const [x, y, v] = p.value
        const a = cols[N - 1 - y]
        const b = cols[x]
        const sign = v > 0 ? '+' : ''
        return `<b>${a}</b> ↔ <b>${b}</b><br/>r = <span style="color:${v >= 0 ? '#2563EB' : '#0284C7'};font-weight:600">${sign}${v.toFixed(3)}</span>`
      },
    },
    grid: {
      left: 48,
      right: 24,
      top: 44,
      bottom: 48,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: cols,
      position: 'bottom',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: 'rgba(15,23,42,.06)' } },
      axisLabel: {
        color: '#64748B',
        fontSize: 11,
        fontFamily: 'IBM Plex Mono, monospace',
        interval: 0,
        rotate: N > 14 ? 45 : 0,
      },
    },
    yAxis: {
      type: 'category',
      data: [...cols].reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: true, lineStyle: { color: 'rgba(15,23,42,.06)' } },
      axisLabel: {
        color: '#64748B',
        fontSize: 11,
        fontFamily: 'IBM Plex Mono, monospace',
      },
    },
    series: [{
      type: 'scatter',
      data,
      symbol: 'circle',
      symbolSize: (val) => {
        const a = Math.abs(val[2])
        return Math.max(4, a * maxBubble)
      },
      emphasis: {
        scale: 1.25,
        itemStyle: {
          shadowBlur: 12,
          shadowColor: 'rgba(15,23,42,.2)',
        },
      },
      z: 2,
    }],
  })
}

async function load(m = method.value) {
  method.value = m
  loading.value = true
  const res = await get('/api/correlation/matrix', { method: m })
  loading.value = false
  if (res.error) {
    ElMessage.error(res.error)
    return
  }
  pairs.value = res.high_pairs || []
  renderBubbleMatrix(res.columns || [], res.matrix || [])
  ElMessage.success(`${m} 矩阵已加载 · 高耦合 ${pairs.value.length} 对`)
}

onMounted(() => load('pearson'))
</script>

<style scoped>
.corr-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text-dim);
}
.corr-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: -1px;
}
.corr-dot.pos {
  background: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
}
.corr-dot.neg {
  background: #0284C7;
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.18);
}
.corr-chart {
  height: 480px;
  min-height: 420px;
}
</style>
