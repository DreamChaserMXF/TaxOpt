<template>
  <scroll-view scroll-y class="page">

    <!-- 方案提示 -->
    <view v-if="r.bonus !== undefined && r.monthly_salary !== undefined" class="tip-box">
      <text class="tip-label">{{ r._mode === 'optimize' ? '最优拆分方案' : '薪酬方案' }}</text>
      <text class="tip-sub">全年名义收入 ¥ {{ fmt(r.nominal_income || ((r.annual_salary || 0) + (r.bonus || 0))) }}</text>
      <text class="tip-value">月薪 {{ fmt(r.monthly_salary) }} 元 × 12 ＋ 年终奖 {{ fmt(r.bonus) }} 元</text>
      <text v-if="r.extra_income > 0" class="tip-note">＋ 额外激励 {{ fmt(r.extra_income) }} 元</text>
      <text v-if="r.stock_grants && r.stock_grants.length > 0" class="tip-note">＋ 股票激励 {{ r.stock_grants.length }} 笔，合计 {{ fmt((r.stock_grants || []).reduce((sum, item) => sum + item, 0)) }} 元</text>
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

    <!-- 分项结果 -->
    <view v-if="resultSections.length > 0" class="card">
      <text class="section-title">分项结果</text>
      <view v-for="item in resultSections" :key="item.key" class="result-row">
        <view>
          <text class="result-label">{{ item.label }}</text>
          <text v-if="item.sub" class="result-sub">{{ item.sub }}</text>
        </view>
        <text class="result-value" :style="{ color: item.color || '#0f172a' }">¥ {{ fmt(item.value) }}</text>
      </view>
    </view>

    <!-- 收入与税额构成 -->
    <view v-if="incomeRows.length > 0" class="card">
      <text class="section-title">收入与税额构成</text>
      <view class="compose-table">
        <view class="compose-row compose-head">
          <text class="compose-item compose-name">收入项目</text>
          <text class="compose-item compose-num">税前</text>
          <text class="compose-item compose-num">税额</text>
          <text class="compose-item compose-num">税后</text>
        </view>
        <view v-for="row in incomeRows" :key="row.key" class="compose-row" :class="{ 'compose-total': row.total }">
          <text class="compose-item compose-name">{{ row.label }}</text>
          <text class="compose-item compose-num">{{ fmt(row.gross) }}</text>
          <text class="compose-item compose-num tax">{{ row.taxableNote || fmt(row.tax) }}</text>
          <text class="compose-item compose-num take">{{ row.takeNote || fmt(row.take) }}</text>
        </view>
      </view>
    </view>

    <!-- 年度收入构成 -->
    <view v-if="annualBreakdown.length > 0" class="card">
      <text class="section-title">年度收入构成</text>
      <view class="stack-bar">
        <view
          v-for="item in annualBreakdown"
          :key="item.key"
          class="stack-segment"
          :style="{ width: item.width, background: item.color }"
        />
      </view>
      <view class="legend-list">
        <view v-for="item in annualBreakdown" :key="item.key" class="legend-row">
          <view class="legend-left">
            <text class="legend-dot" :style="{ background: item.color }"></text>
            <text class="legend-label">{{ item.label }}</text>
          </view>
          <view class="legend-right">
            <text class="legend-value">¥ {{ fmt(item.value) }}</text>
            <text class="legend-rate">{{ item.rate }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 月度到手趋势 -->
    <view v-if="monthlyTrend.length > 0" class="card">
      <text class="section-title">月度到手趋势</text>
      <view class="trend-chart">
        <view v-for="item in monthlyTrend" :key="item.month" class="trend-col">
          <view class="trend-track">
            <view class="trend-bar" :style="{ height: item.height }"></view>
          </view>
          <text class="trend-month">{{ item.month }}</text>
          <text class="trend-value">¥{{ item.short }}</text>
        </view>
      </view>
    </view>

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

    <!-- 股票明细 -->
    <view v-if="(r.stock_grants || []).length > 0" class="card">
      <text class="section-title">股票明细</text>
      <view v-for="row in stockRows" :key="row.key" class="stock-card">
        <view class="stock-top">
          <text class="stock-title">{{ row.label }}</text>
          <text class="stock-gross">¥ {{ fmt(row.gross) }}</text>
        </view>
        <view class="stock-meta">
          <text class="stock-tax">税额 ¥ {{ fmt(row.tax) }}</text>
          <text class="stock-take">税后 ¥ {{ fmt(row.take) }}</text>
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
      <button class="btn-save" @tap="savePoster">保存长图</button>
      <button class="btn-back" @tap="uni.navigateBack()">返回修改</button>
    </view>

    <canvas
      canvas-id="resultPoster"
      id="resultPoster"
      class="poster-canvas"
      :style="{ width: posterWidth + 'px', height: posterHeight + 'px' }"
    />

  </scroll-view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const r = ref({})
const posterWidth = 1125
const posterHeight = computed(() => {
  const resultBlockHeight = 180 + Math.min(resultSections.value.length, 6) * 64
  const composeBlockHeight = 180 + Math.min(incomeRows.value.length, 6) * 54
  const extraLines = [
    (r.value.extra_income || 0) > 0,
    ((r.value.stock_grants || []).length > 0),
    (r.value.total_tax || 0) > 0,
  ].filter(Boolean).length
  const extraBlockHeight = 120 + Math.max(extraLines, 1) * 44
  return 220 + 32 + 220 + 32 + resultBlockHeight + 32 + composeBlockHeight + 32 + extraBlockHeight + 160
})

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
  const nominal = d.nominal_income || (d.annual_salary || 0) + (d.bonus || 0)
  const hasExtra = d.extra_income > 0 || (d.stock_grants && d.stock_grants.length > 0)
  return [
    { label: '名义收入',    value: '¥ ' + fmt(nominal),                               sub: hasExtra ? '月薪×12 + 奖金 + 其他' : '月薪×12 + 年终奖', color: '#374151' },
    { label: '到手现金',    value: '¥ ' + fmt(d.net_take_home),                        sub: '扣除个税与三险一金',       color: '#16a34a' },
    { label: '公积金入账',  value: '¥ ' + fmt(d.annual_provident_fund),               sub: '个人 + 单位，按月×12',     color: '#2563eb' },
    { label: '现金+公积金', value: '¥ ' + fmt(d.net_take_home_including_provident_fund), sub: '含个人+单位公积金',      color: '#0d9488' },
    { label: '全年个税',    value: '¥ ' + fmt(d.total_tax),                           sub: '综合所得 + 年终奖',        color: '#dc2626' },
    { label: '税率',        value: fmtPct(d.effective_tax_rate),                       sub: '个税 / 名义收入',          color: '#e11d48' },
    { label: '个人社保',    value: '¥ ' + fmt(d.annual_insurance),                    sub: '养老 + 医疗 + 失业',       color: '#ea580c' },
    { label: '广义税率',    value: fmtPct(d.effective_burden_rate),                    sub: '（个税 + 社保）/ 名义收入', color: '#7c3aed' },
  ]
})

const resultSections = computed(() => {
  if (!r.value || !r.value.net_take_home) return []
  const list = [
    {
      key: 'salary_take_home',
      label: '工资薪金到手',
      sub: (r.value.extra_income || 0) > 0 ? '已含额外激励，并扣综合所得个税与个人五险一金' : '扣综合所得个税与个人五险一金',
      value: (Number(r.value.salary_take_home) || 0) + (Number(r.value.extra_income) || 0),
      color: '#16a34a',
    },
  ]

  if ((r.value.bonus_after_tax || 0) > 0) {
    list.push({
      key: 'bonus_after_tax',
      label: '年终奖到手',
      sub: '年终奖单独计税后',
      value: Number(r.value.bonus_after_tax) || 0,
      color: '#16a34a',
    })
  }

  if ((r.value.stock_grants || []).length > 0) {
    list.push({
      key: 'stock_take_home',
      label: '股票到手',
      sub: '股票激励逐笔计税后',
      value: (r.value.stock_grants || []).reduce((sum, item) => sum + item, 0) - ((Number(r.value.total_stock_tax) || 0)),
      color: '#0d9488',
    })
  }

  list.push({
    key: 'provident',
    label: '公积金入账',
    sub: '个人 + 单位，按月计入',
    value: Number(r.value.annual_provident_fund) || 0,
    color: '#2563eb',
  })

  list.push({
    key: 'total_cash',
    label: '全年现金到手',
    sub: '名义收入 - 个税 - 个人五险一金',
    value: Number(r.value.net_take_home) || 0,
    color: '#16a34a',
  })

  list.push({
    key: 'total_with_pf',
    label: '现金 + 公积金',
    sub: '含个人与单位公积金',
    value: Number(r.value.net_take_home_including_provident_fund) || 0,
    color: '#4f46e5',
  })

  return list
})

const stockRows = computed(() => {
  const grants = r.value.stock_grants || []
  const taxes = r.value.stock_grants_tax || []
  return grants.map((gross, idx) => ({
    key: `stock-${idx}`,
    label: `股票激励 #${idx + 1}`,
    gross,
    tax: taxes[idx] || 0,
    take: gross - (taxes[idx] || 0),
  }))
})

const incomeRows = computed(() => {
  if (!r.value || !r.value.net_take_home) return []
  const rows = [
    {
      key: 'salary',
      label: '工资薪金',
      gross: r.value.annual_salary || 0,
      tax: r.value.comprehensive_annual_tax || 0,
      take: r.value.salary_take_home || 0,
    },
  ]

  if ((r.value.extra_income || 0) > 0) {
    rows.push({
      key: 'extra',
      label: '额外激励',
      gross: r.value.extra_income || 0,
      tax: 0,
      take: 0,
      taxableNote: '并入上行',
      takeNote: '并入上行',
    })
  }

  if ((r.value.bonus || 0) > 0) {
    rows.push({
      key: 'bonus',
      label: '年终奖',
      gross: r.value.bonus || 0,
      tax: r.value.bonus_tax || 0,
      take: r.value.bonus_after_tax || 0,
    })
  }

  stockRows.value.forEach((row) => rows.push(row))

  rows.push({
    key: 'total',
    label: '合计',
    gross: r.value.nominal_income || ((r.value.annual_salary || 0) + (r.value.bonus || 0)),
    tax: r.value.total_tax || 0,
    take: r.value.net_take_home || 0,
    total: true,
  })

  return rows
})

const annualBreakdown = computed(() => {
  if (!r.value || !r.value.net_take_home) return []
  const d = r.value
  const segments = [
    { key: 'cash', label: '到手现金', value: Number(d.net_take_home) || 0, color: '#22c55e' },
    { key: 'tax', label: '个税', value: Number(d.total_tax) || 0, color: '#ef4444' },
    { key: 'insurance', label: '个人三险', value: Number(d.annual_insurance) || 0, color: '#f97316' },
    { key: 'housing', label: '个人公积金', value: Number(d.annual_housing_fund_employee) || 0, color: '#3b82f6' },
  ].filter(item => item.value > 0)

  const total = segments.reduce((sum, item) => sum + item.value, 0) || 1
  return segments.map(item => ({
    ...item,
    width: `${(item.value / total) * 100}%`,
    rate: `${((item.value / total) * 100).toFixed(1)}%`,
  }))
})

const monthlyTrend = computed(() => {
  const details = r.value.monthly_details || []
  if (!details.length) return []
  const values = details.map(item => Number(item.after_tax_salary) || 0)
  const maxValue = Math.max(...values, 1)
  return details.map(item => {
    const value = Number(item.after_tax_salary) || 0
    return {
      month: `${item.month}月`,
      value,
      height: `${Math.max((value / maxValue) * 160, 12)}rpx`,
      short: (value / 1000).toFixed(1).replace(/\.0$/, '') + 'k',
    }
  })
})

function drawRoundedRect(ctx, x, y, w, h, rds, fill) {
  const radius = Math.min(rds, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.lineTo(x + w - radius, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius)
  ctx.lineTo(x + w, y + h - radius)
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h)
  ctx.lineTo(x + radius, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius)
  ctx.lineTo(x, y + radius)
  ctx.quadraticCurveTo(x, y, x + radius, y)
  ctx.closePath()
  ctx.setFillStyle(fill)
  ctx.fill()
}

function callAsync(apiName, options = {}) {
  return new Promise((resolve, reject) => {
    uni[apiName]({
      ...options,
      success: resolve,
      fail: reject,
    })
  })
}

async function ensureAlbumPermission() {
  try {
    const settingRes = await callAsync('getSetting')
    const current = settingRes.authSetting?.['scope.writePhotosAlbum']

    if (current === true) return true

    if (current === undefined) {
      await callAsync('authorize', { scope: 'scope.writePhotosAlbum' })
      return true
    }

    const modalRes = await callAsync('showModal', {
      title: '需要相册权限',
      content: '保存长图需要写入系统相册，请在设置中允许保存到相册。',
      confirmText: '去设置',
    })

    if (!modalRes.confirm) return false

    const openRes = await callAsync('openSetting')
    return !!openRes.authSetting?.['scope.writePhotosAlbum']
  } catch (error) {
    return false
  }
}

async function savePoster() {
  if (!r.value || !r.value.net_take_home) return

  const allowed = await ensureAlbumPermission()
  if (!allowed) {
    uni.showToast({ title: '未获得相册权限', icon: 'none' })
    return
  }

  uni.showLoading({ title: '生成长图中…', mask: true })

  const ctx = uni.createCanvasContext('resultPoster')
  const width = posterWidth
  const height = posterHeight.value
  const title = r.value._mode === 'optimize' ? 'TaxOpt 税筹优化结果' : 'TaxOpt 收入计算结果'
  const nominal = r.value.nominal_income || ((r.value.annual_salary || 0) + (r.value.bonus || 0))
  const stockTotal = (r.value.stock_grants || []).reduce((sum, item) => sum + item, 0)
  const posterSections = resultSections.value.slice(0, 6)
  const posterIncomeRows = incomeRows.value.slice(0, 6)

  ctx.setFillStyle('#f8fafc')
  ctx.fillRect(0, 0, width, height)

  ctx.setFillStyle('#4f46e5')
  ctx.fillRect(0, 0, width, 220)

  ctx.setFillStyle('#ffffff')
  ctx.setFontSize(44)
  ctx.fillText(title, 64, 88)
  ctx.setFontSize(28)
  ctx.fillText(`全年名义收入 ¥ ${fmt(nominal)}`, 64, 142)
  ctx.fillText(`月薪 ${fmt(r.value.monthly_salary)} × 12  +  年终奖 ${fmt(r.value.bonus)}`, 64, 184)

  let y = 252
  drawRoundedRect(ctx, 40, y, width - 80, 220, 28, '#ffffff')
  ctx.setFillStyle('#64748b')
  ctx.setFontSize(24)
  ctx.fillText('核心结果', 72, y + 44)
  ctx.setFillStyle('#0f172a')
  ctx.setFontSize(34)
  ctx.fillText(`到手现金 ¥ ${fmt(r.value.net_take_home)}`, 72, y + 100)
  ctx.setFillStyle('#2563eb')
  ctx.fillText(`公积金入账 ¥ ${fmt(r.value.annual_provident_fund)}`, 72, y + 154)
  ctx.setFillStyle('#4f46e5')
  ctx.fillText(`现金+公积金 ¥ ${fmt(r.value.net_take_home_including_provident_fund)}`, 72, y + 208)

  y += 252
  const resultBlockHeight = 140 + posterSections.length * 64
  drawRoundedRect(ctx, 40, y, width - 80, resultBlockHeight, 28, '#ffffff')
  ctx.setFillStyle('#64748b')
  ctx.setFontSize(24)
  ctx.fillText('分项结果', 72, y + 44)

  let rowY = y + 92
  posterSections.forEach((item) => {
    ctx.setFillStyle('#0f172a')
    ctx.setFontSize(28)
    ctx.fillText(item.label, 72, rowY)
    ctx.setFillStyle('#64748b')
    ctx.setFontSize(20)
    if (item.sub) ctx.fillText(item.sub, 72, rowY + 30)
    ctx.setFillStyle(item.color || '#0f172a')
    ctx.setFontSize(28)
    ctx.fillText(`¥ ${fmt(item.value)}`, 760, rowY)
    rowY += 64
  })

  y += resultBlockHeight + 32
  const composeBlockHeight = 140 + posterIncomeRows.length * 54
  drawRoundedRect(ctx, 40, y, width - 80, composeBlockHeight, 28, '#ffffff')
  ctx.setFillStyle('#64748b')
  ctx.setFontSize(24)
  ctx.fillText('收入与税额构成', 72, y + 44)

  let composeY = y + 92
  posterIncomeRows.forEach((row) => {
    ctx.setFillStyle('#0f172a')
    ctx.setFontSize(26)
    ctx.fillText(row.label, 72, composeY)
    ctx.setFillStyle('#475569')
    ctx.setFontSize(22)
    ctx.fillText(`税前 ¥ ${fmt(row.gross)}`, 72, composeY + 30)
    const taxText = row.taxableNote ? `税额 ${row.taxableNote}` : `税额 ¥ ${fmt(row.tax)}`
    const takeText = row.takeNote ? `税后 ${row.takeNote}` : `税后 ¥ ${fmt(row.take)}`
    ctx.fillText(taxText, 360, composeY + 30)
    ctx.fillText(takeText, 700, composeY + 30)
    composeY += 54
  })

  y += composeBlockHeight + 32
  const extraLines = [
    (r.value.extra_income || 0) > 0,
    stockTotal > 0,
    (r.value.total_tax || 0) > 0,
  ].filter(Boolean).length
  const extraBlockHeight = 92 + Math.max(extraLines, 1) * 44
  drawRoundedRect(ctx, 40, y, width - 80, extraBlockHeight, 28, '#ffffff')
  ctx.setFillStyle('#64748b')
  ctx.setFontSize(24)
  ctx.fillText('补充信息', 72, y + 44)
  ctx.setFillStyle('#0f172a')
  ctx.setFontSize(24)
  let extraY = y + 96
  if ((r.value.extra_income || 0) > 0) {
    ctx.fillText(`额外激励 ¥ ${fmt(r.value.extra_income)}`, 72, extraY)
    extraY += 44
  }
  if (stockTotal > 0) {
    ctx.fillText(`股票激励 ${r.value.stock_grants.length} 笔，合计 ¥ ${fmt(stockTotal)}`, 72, extraY)
    extraY += 44
  }
  ctx.fillText(`全年个税 ¥ ${fmt(r.value.total_tax)}`, 72, extraY)

  ctx.setFillStyle('#94a3b8')
  ctx.setFontSize(22)
  ctx.fillText('TaxOpt 微信小程序 · 结果长图', 72, height - 48)

  ctx.draw(false, () => {
    uni.canvasToTempFilePath({
      canvasId: 'resultPoster',
      success: ({ tempFilePath }) => {
        uni.saveImageToPhotosAlbum({
          filePath: tempFilePath,
          success: () => {
            uni.hideLoading()
            uni.showToast({ title: '长图已保存', icon: 'success' })
          },
          fail: () => {
            uni.hideLoading()
            uni.showToast({ title: '保存失败，请检查相册权限', icon: 'none' })
          },
        })
      },
      fail: () => {
        uni.hideLoading()
        uni.showToast({ title: '生成长图失败', icon: 'none' })
      },
    })
  })
}
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
.tip-sub    { font-size: 22rpx; color: #4338ca; display: block; margin-bottom: 8rpx; }
.tip-value  { font-size: 26rpx; color: #4c1d95; font-weight: 700; display: block; }
.tip-note   { font-size: 22rpx; color: #6366f1; display: block; margin-top: 6rpx; }

.stack-bar {
  display: flex;
  width: 100%;
  height: 20rpx;
  overflow: hidden;
  border-radius: 999rpx;
  background: #e2e8f0;
  margin-bottom: 20rpx;
}
.stack-segment {
  height: 100%;
}
.legend-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.legend-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}
.legend-left,
.legend-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.legend-dot {
  width: 18rpx;
  height: 18rpx;
  border-radius: 999rpx;
  flex: none;
}
.legend-label {
  font-size: 24rpx;
  color: $text-base;
}
.legend-value {
  font-size: 24rpx;
  color: #334155;
}
.legend-rate {
  font-size: 22rpx;
  color: $text-muted;
  min-width: 72rpx;
  text-align: right;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 10rpx;
  height: 260rpx;
  padding-top: 20rpx;
}
.trend-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
}
.trend-track {
  width: 100%;
  max-width: 34rpx;
  height: 170rpx;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: #eef2ff;
  border-radius: 999rpx;
  overflow: hidden;
}
.trend-bar {
  width: 100%;
  background: linear-gradient(180deg, #818cf8 0%, #4f46e5 100%);
  border-radius: 999rpx;
}
.trend-month {
  font-size: 20rpx;
  color: $text-muted;
}
.trend-value {
  font-size: 18rpx;
  color: #64748b;
}

.result-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  padding: 18rpx 0;
  border-bottom: 1rpx solid $border;
}
.result-row:last-child {
  border-bottom: none;
}
.result-label {
  display: block;
  font-size: 24rpx;
  color: $text-base;
  font-weight: 600;
}
.result-sub {
  display: block;
  margin-top: 6rpx;
  font-size: 20rpx;
  color: $text-muted;
}
.result-value {
  font-size: 26rpx;
  font-weight: 700;
  text-align: right;
}

.compose-table {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.compose-row {
  display: flex;
  align-items: center;
  padding: 18rpx 0;
  border-bottom: 1rpx solid $border;
}
.compose-head {
  padding-top: 0;
  color: $text-muted;
  font-size: 22rpx;
  font-weight: 600;
}
.compose-total {
  background: #f8fafc;
  margin: 8rpx -16rpx -8rpx;
  padding: 18rpx 16rpx;
  border-bottom: none;
  border-radius: 12rpx;
  font-weight: 600;
}
.compose-item {
  font-size: 24rpx;
}
.compose-name {
  flex: 1.3;
  color: $text-base;
}
.compose-num {
  flex: 1;
  text-align: right;
}
.tax {
  color: #dc2626;
}
.take {
  color: #16a34a;
}

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

.stock-card {
  background: #f8fafc;
  border-radius: 12rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 14rpx;
}
.stock-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 10rpx;
}
.stock-title {
  font-size: 24rpx;
  color: $text-base;
  font-weight: 600;
}
.stock-gross {
  font-size: 24rpx;
  color: #334155;
}
.stock-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}
.stock-tax {
  font-size: 22rpx;
  color: #dc2626;
}
.stock-take {
  font-size: 22rpx;
  color: #16a34a;
}

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
.btn-wrap {
  padding: 8rpx 0 48rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.btn-save {
  width: 100%;
  height: 88rpx;
  background: $primary;
  color: #fff;
  font-size: 28rpx;
  border-radius: 16rpx;
  border: none;
}
.btn-back {
  width: 100%;
  height: 88rpx;
  background: #f3f4f6;
  color: $text-base;
  font-size: 28rpx;
  border-radius: 16rpx;
  border: 1rpx solid $border;
}

.poster-canvas {
  position: fixed;
  left: -9999px;
  top: -9999px;
  opacity: 0;
  pointer-events: none;
}
</style>
