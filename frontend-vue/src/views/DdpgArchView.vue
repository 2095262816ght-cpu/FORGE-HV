<template>
  <div>
    <PageHeader
      sub="第 3 章 · 网络模型设计（论文图 1）"
      title="DDPG"
      em="模型架构"
      desc="深度确定性策略梯度（DDPG）基于 Actor-Critic 架构，适用于连续动作空间回归。状态 = 70 微结构 + 22 成分特征，动作 = 预测 HV，奖励 = 误差驱动反馈。"
    />
    <div class="page-card">
      <p style="color:var(--text-dim);margin-bottom:16px;line-height:1.7">
        深度确定性策略梯度（Deep Deterministic Policy Gradient）将 Actor-Critic 框架用于连续动作空间回归。
        在本项目中，动作输出被解释为合金维氏硬度（HV）的连续预测值，状态为成分/微结构特征向量。
      </p>
      <div class="arch-grid">
        <el-card shadow="never">
          <template #header><b>Actor 网络</b></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="输入">状态 s（成分 + 微结构特征）</el-descriptions-item>
            <el-descriptions-item label="结构">多层全连接 + ReLU</el-descriptions-item>
            <el-descriptions-item label="输出">确定性动作 a = μ(s|θμ) → 预测 HV</el-descriptions-item>
            <el-descriptions-item label="目标网络">μ'(s|θμ') 软更新</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never">
          <template #header><b>Critic 网络</b></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="输入">状态-动作对 (s, a)</el-descriptions-item>
            <el-descriptions-item label="结构">多层全连接 + ReLU</el-descriptions-item>
            <el-descriptions-item label="输出">Q(s, a|θQ) 价值估计</el-descriptions-item>
            <el-descriptions-item label="目标网络">Q'(s, a|θQ') 软更新</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never">
          <template #header><b>优先经验回放 PER</b></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="动机">缓解样本稀疏、聚焦高 TD-error 转移</el-descriptions-item>
            <el-descriptions-item label="优先级">p_i ∝ |δ_i| + ε</el-descriptions-item>
            <el-descriptions-item label="采样">P(i) = p_i^α / Σ p_k^α</el-descriptions-item>
            <el-descriptions-item label="修正">重要性采样权重 w_i</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card shadow="never">
          <template #header><b>奖励设计</b></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="目标">缩小预测 HV 与真实 HV 的误差</el-descriptions-item>
            <el-descriptions-item label="形式">r = −|ŷ − y| 或基于 RMSE/MAE 的塑形奖励</el-descriptions-item>
            <el-descriptions-item label="评估">R² / RMSE / MAE / MAPE（论文 5.2）</el-descriptions-item>
            <el-descriptions-item label="早停">验证集 R² 停滞时触发</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </div>
    </div>

    <div class="page-card">
      <h3>训练流程概览</h3>
      <el-steps :active="4" align-center finish-status="success">
        <el-step title="采样" description="从 PER 取出 batch" />
        <el-step title="Critic 更新" description="最小化 TD 误差" />
        <el-step title="Actor 更新" description="策略梯度提升 Q" />
        <el-step title="软更新" description="目标网络缓慢跟踪" />
      </el-steps>
    </div>
  </div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
</script>
