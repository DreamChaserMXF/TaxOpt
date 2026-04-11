<template>
  <scroll-view scroll-y class="page">

    <!-- 方案提示 -->
    <view v-if="r.bonus !== undefined && r.monthly_salary !== undefined" class="tip-box">
      <text class="tip-label">最优拆分方案</text>
      <text class="tip-value">月薪 {{ fmt(r.monthly_salary) }} 元 × 12 ＋ 年终奖 {{ fmt(r.bonus) }} 元</text>
    </view>

    <!-- 8 张指标卡片（2列×4行） -->
    <view class="card">
      <text class="section-title">年度指标</text>
      <view class="cards-grid">
        <view v-for="card in metricCards" :key="card.label" class="metric-card">
          <text class="metric-label">{{ card.label }}</text>
          <text class="metric-value" :style="{ color: card.color }">{{ card.value }}</text>
          <text class="metric-sub">{{ card.sub }}</text>
        </view>
      </view>
    </view>

    <!-- 收入构成饼图 -->
    <!-- 需在 HBuilderX 插件市场安装「qiun-data-charts」后取消注释 -->
    <!--
    <view class="card">
      <text class="section-title">年度收入构成</text>
      <qiun-data-charts type="pie" :chartData="pieChartData" :opts="pieOpts" />
    </view>
    -->

    <!-- 月度到手柱状图 -->
    <!--
    <view class="card">
      <text class="section-title">月度到手趋势</text>
      <qiun-data-charts type="column" :chartData="barChartData" :opts="barOpts" />
    </view>
    -->

    <!-- 年终奖明细 -->
    <view v-if="r.bonus > 0" class="card">
      <text class="section-title">年终奖明细</text>
      <view class="bonus-grid">
        <view class="bonus-item">
          <text class="bonus-sub">税前</text>
          <text class="bonus-val">¥ {{ fmt(r.bonus) }}</text>
        </view>
        <view class="bonus-item">
          <text class="bonus-sub">税额</text>
          <text class="bonus-val" style="color: #dc2626">¥ {{ fmt(r.bonus_tax) }}</text>
        </view>
        <view class="bonus-item">
          <text class="bonus-sub">税后到手</text>
          <text class="bonus-val" style="color: #16a34a">¥ {{ fmt(r.bonus_after_tax) }}</text>
        </view>
      </view>
    </view>

    <!-- 月度明细表 -->
    <view class="card">
      <text class="section-title">月度明细</text>
      <scroll-view scroll-x class="table-wrap">
        <view class="table">
          <view class="tr thead">
            <text class="td">月份</text>
            <text class="td td-r">税前月薪</text>
            <text class="td td-r">个人三险</text>
            <text class="td td-r">公积金(个/司)</text>
            <text class="td td-r">当月税额</text>
            <text class="td td-r">税后到手</text>
          </view>
          <view
            v-for="row in r.monthly_details" :key="row.month"
            class="tr"
            :class="{ 'tr-alt': row.month % 2 === 0 }"
          >
            <text class="td">{{ row.month }}月</text>
            <text class="td td-r">{{ fmt(row.salary) }}</text>
            <text class="td td-r warn">{{ fmt(row.insurance.total) }}</text>
            <text class="td td-r info">{{ fmt(row.housing_fund.employee + row.housing_fund.employer) }}</text>
            <text class="td td-r danger">{{ fmt(row.tax) }}</text>
            <text class="td td-r success">{{ fmt(row.after_tax_salary) }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 返回按钮 -->
    <view class="btn-wrap">
      <button class="btn-back" @tap="uni.navigateBack()">返回修改</button>
    </view>

  </scroll-view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const r = ref({})

onMounted(() => {
  r.value = uni.getStorageSync('taxopt_result') || {}
})

// 数字格式化（整数，千分位）
function fmt(v) {
  if (v == null) return '—'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}
function fmtPct(v) {
  return (v * 100).toFixed(2) + '%'
}

// 8 张指标卡片
const metricCards = computed(() => {
  if (!r.value.net_take_home) return []
  const d = r.value
  const nominal = (d.annual_salary || 0) + (d.bonus || 0)
  return [
    { label: '名义收入',    value: '¥ ' + fmt(nominal),                               sub: '月薪×12 + 年终奖',         color: '#374151' },
    { label: '到手现金',    value: '¥ ' + fmt(d.net_take_home),                        sub: '扣除个税与三险一金',       color: '#16a34a' },
    { label: '公积金入账',  value: '¥ ' + fmt(d.annual_provident_fund),               sub: '个人 + 单位，按月×12',     color: '#2563eb' },
    { label: '现金+公积金', value: '¥ ' + fmt(d.net_take_home_including_provident_fund), sub: '含个人+单位公积金',      color: '#0d9488' },
    { label: '全年个税',    value: '¥ ' + fmt(d.total_tax),                           sub: '综合所得 + 年终奖',        color: '#dc2626' },
    { label: '税率',        value: fmtPct(d.effective_tax_rate),                       sub: '个税 / 名义收入',          color: '#e11d48' },
    { label: '个人社保',    value: '¥ ' + fmt(d.annual_insurance),                    sub: '养老 + 医疗 + 失业',       color: '#ea580c' },
    { label: '广义税率',    value: fmtPct(d.effective_burden_rate),                    sub: '（个税 + 社保）/ 名义收入', color: '#7c3aed' },
  ]
})

// 饼图数据（安装 qiun-data-charts 后启用）
const pieChartData = computed(() => {
  if (!r.value.net_take_home) return {}
  const d = r.value
  return {
    series: [{
      data: [
        { name: '到手现金', value: Math.round(d.net_take_home) },
        { name: '个税',     value: Math.round(d.total_tax) },
        { name: '个人三险', value: Math.round(d.annual_insurance) },
        { name: '个人公积金', value: Math.round(d.annual_housing_fund_employee) },
      ],
    }],
  }
})
const pieOpts = { legend: { show: true }, padding: [5, 5, 5, 5] }

// 柱状图数据（安装 qiun-data-charts 后启用）
const barChartData = computed(() => {
  if (!r.value.monthly_details) return {}
  return {
    categories: r.value.monthly_details.map(d => d.month + '月'),
    series: [{
      name: '税后到手',
      data: r.value.monthly_details.map(d => Math.round(d.after_tax_salary)),
    }],
  }
})
const barOpts = { legend: { show: false }, xAxis: { disableGrid: true } }
</script>

<style lang="scss" scoped>
.page {
  background: $bg-page;
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

// 最优拆分提示
.tip-box {
  background: #ede9fe;
  border: 1rpx solid #c4b5fd;
  border-radius: $radius;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
}
.tip-label { font-size: 22rpx; color: #6d28d9; font-weight: 600; display: block; margin-bottom: 6rpx; }
.tip-value  { font-size: 26rpx; color: #4c1d95; font-weight: 700; }

// 指标卡片网格
.cards-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}
.metric-card {
  background: #f9fafb;
  border-radius: 10rpx;
  padding: 20rpx 16rpx;
}
.metric-label { font-size: 22rpx; color: $text-muted; display: block; margin-bottom: 8rpx; }
.metric-value { font-size: 32rpx; font-weight: 700; display: block; margin-bottom: 4rpx; }
.metric-sub   { font-size: 20rpx; color: $text-muted; }

// 年终奖
.bonus-grid { display: flex; gap: 0; }
.bonus-item { flex: 1; text-align: center; }
.bonus-sub  { font-size: 22rpx; color: $text-muted; display: block; margin-bottom: 8rpx; }
.bonus-val  { font-size: 28rpx; font-weight: 600; }

// 月度明细表
.table-wrap { width: 100%; }
.table      { min-width: 900rpx; }
.tr {
  display: flex;
  border-bottom: 1rpx solid $border;
  &.thead .td { font-weight: 600; color: $text-muted; font-size: 22rpx; background: #f9fafb; }
  &.tr-alt    { background: #fafafa; }
}
.td {
  flex: 1;
  padding: 16rpx 8rpx;
  font-size: 24rpx;
  color: $text-base;
  min-width: 120rpx;
}
.td-r   { text-align: right; }
.warn   { color: #ea580c; }
.info   { color: #2563eb; }
.danger { color: #dc2626; }
.success{ color: #16a34a; }

// 按钮
.btn-wrap { padding: 8rpx 0 48rpx; }
.btn-back {
  width: 100%;
  height: 88rpx;
  background: #f3f4f6;
  color: $text-base;
  font-size: 28rpx;
  border-radius: 16rpx;
  border: 1rpx solid $border;
}
</style>
