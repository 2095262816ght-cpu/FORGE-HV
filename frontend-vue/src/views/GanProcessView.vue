<template>
  <div>
    <PageHeader
      sub="第 5.4 节 · 数据扩充过程"
      title="数据"
      em="扩充过程"
      desc="原始数据仅 149 条，各模型严重过拟合。引入生成对抗网络（GAN）生成 10000 条符合原始分布的合成样本，扩充训练集至 10149 条，显著提升泛化性能。"
    />
    <div class="page-card">
      <p style="color:var(--text-dim);line-height:1.7;margin-bottom:14px">
        生成对抗网络（GAN）由生成器 G 与判别器 D 对抗训练：G 从噪声 z 生成合金成分/特征样本，
        D 区分真实样本与生成样本。收敛后用 G 扩充训练集，再与原始数据对比 DDPG / LR / PR / SVR 表现。
      </p>
      <div class="arch-grid">
        <el-card shadow="never">
          <template #header><b>Generator G</b></template>
          <p style="color:var(--text-dim);font-size:12px;line-height:1.7">
            输入潜在噪声 z ∼ N(0, I)，经全连接网络映射到与真实特征同维的合成样本 x̂ = G(z)。
            目标是最大化 D(G(z))，使生成分布逼近真实数据分布。
          </p>
        </el-card>
        <el-card shadow="never">
          <template #header><b>Discriminator D</b></template>
          <p style="color:var(--text-dim);font-size:12px;line-height:1.7">
            输入真实或生成样本，输出真伪概率。目标是正确分类真实数据与伪数据，
            训练损失在均衡点附近收敛至 ln 2 ≈ 0.693。
          </p>
        </el-card>
        <el-card shadow="never">
          <template #header><b>数据扩充用途</b></template>
          <p style="color:var(--text-dim);font-size:12px;line-height:1.7">
            在小样本高温合金数据集上，GAN 合成样本用于缓解过拟合，
            对应实验对比页「5.4 数据扩充比较」。
          </p>
        </el-card>
      </div>
    </div>

    <div class="page-card">
      <h3>对抗训练损失曲线（示意）</h3>
      <p style="color:var(--text-dim);font-size:12px;margin:0 0 12px;line-height:1.6">
        本图为论文原理示意，非本次会话实时训练日志。真实 GAN 扩充数据请在「5.4 GAN 数据扩充对比」中运行实验查看指标。
      </p>
      <div ref="chartEl" class="chart-box"></div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useEChart } from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'

const { elRef: chartEl, setOption } = useEChart()

onMounted(() => {
  const epochs = 200
  const gLoss = []
  const dLoss = []
  for (let i = 0; i < epochs; i++) {
    const gBase = 3.5 * Math.exp(-i / 80) + 1.0
    gLoss.push([i, gBase + (Math.random() - 0.5) * 0.4])
    const dBase = 0.2 + (0.69 - 0.2) * (1 - Math.exp(-i / 60))
    dLoss.push([i, dBase + (Math.random() - 0.5) * 0.25])
  }
  setOption({
    title: { text: 'GAN 对抗训练损失曲线（论文原理示意）', left: 0, textStyle: { fontSize: 13, color: '#F5F5F7' } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { color: 'rgba(235,235,245,0.6)' } },
    grid: { left: 50, right: 20, top: 40, bottom: 50 },
    xAxis: { type: 'value', name: 'Epoch', splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } } },
    yAxis: { type: 'value', name: 'Loss', splitLine: { lineStyle: { color: 'rgba(255,255,255,.06)' } } },
    series: [
      {
        name: 'Generator Loss (G)',
        type: 'line',
        data: gLoss,
        showSymbol: false,
        areaStyle: { color: 'rgba(10,132,255,.12)' },
        lineStyle: { color: '#0A84FF', width: 2 },
      },
      {
        name: 'Discriminator Loss (D)',
        type: 'line',
        data: dLoss,
        showSymbol: false,
        areaStyle: { color: 'rgba(191,90,242,.12)' },
        lineStyle: { color: '#BF5AF2', width: 2 },
      },
    ],
  })
})
</script>
