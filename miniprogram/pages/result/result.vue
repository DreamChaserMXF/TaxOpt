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
            <text class="td td-month">月份</text>
            <text class="td td-salary td-r">税前月薪</text>
            <text class="td td-take td-r">税后到手</text>
            <text class="td td-r">个人三险</text>
            <text class="td td-r">公积金(个/司)</text>
            <text class="td td-r">当月税额</text>
          </view>
          <view
            v-for="row in r.monthly_details" :key="row.month"
            class="tr"
            :class="{ 'tr-alt': row.month % 2 === 0 }"
          >
            <text class="td td-month">{{ row.month }}月</text>
            <text class="td td-salary td-r">{{ fmt(row.salary) }}</text>
            <text class="td td-take td-r success">{{ fmt(row.after_tax_salary) }}</text>
            <text class="td td-r warn">{{ fmt(row.insurance.total) }}</text>
            <text class="td td-r info">{{ fmt(row.housing_fund.employee + row.housing_fund.employer) }}</text>
            <text class="td td-r danger">{{ fmt(row.tax) }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 返回按钮 -->
    <view class="btn-wrap">
      <button class="btn-save" @tap="savePoster">保存长图</button>
      <button class="btn-back" @tap="goBack">返回修改</button>
    </view>

    <canvas
      canvas-id="resultPoster"
      id="resultPoster"
      class="poster-canvas"
      :style="{ width: posterWidth + 'px', height: posterHeight + 'px' }"
    />

  </scroll-view>
</template>

<script>
import { ref, computed, onMounted } from '@vue/composition-api'
export default {
  setup() {
    const r = ref({})
    const posterWidth = 1125

    function fmt(v) {
      if (v == null) return '—'
      return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
    }

    function fmtPct(v) {
      return (v * 100).toFixed(2) + '%'
    }

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
          value: (r.value.stock_grants || []).reduce((sum, item) => sum + item, 0) - (Number(r.value.total_stock_tax) || 0),
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

    const incomeRows = computed(() => {
      if (!r.value || !r.value.net_take_home) return []
      const rows = [
        {
          key: 'salary',
          label: '工资薪金',
          gross: r.value.annual_salary || 0,
          tax: r.value.comprehensive_annual_tax || 0,
          take: (Number(r.value.salary_take_home) || 0) + (Number(r.value.extra_income) || 0),
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

    const metricCards = computed(() => {
      if (!r.value.net_take_home) return []
      const d = r.value
      const nominal = d.nominal_income || (d.annual_salary || 0) + (d.bonus || 0)
      const hasExtra = d.extra_income > 0 || (d.stock_grants && d.stock_grants.length > 0)
      return [
        { label: '名义收入', value: '¥ ' + fmt(nominal), sub: hasExtra ? '月薪×12 + 奖金 + 其他' : '月薪×12 + 年终奖', color: '#374151' },
        { label: '到手现金', value: '¥ ' + fmt(d.net_take_home), sub: '扣除个税与三险一金', color: '#16a34a' },
        { label: '公积金入账', value: '¥ ' + fmt(d.annual_provident_fund), sub: '个人 + 单位，按月×12', color: '#2563eb' },
        { label: '现金+公积金', value: '¥ ' + fmt(d.net_take_home_including_provident_fund), sub: '含个人+单位公积金', color: '#0d9488' },
        { label: '全年个税', value: '¥ ' + fmt(d.total_tax), sub: '综合所得 + 年终奖', color: '#dc2626' },
        { label: '税率', value: fmtPct(d.effective_tax_rate), sub: '个税 / 名义收入', color: '#e11d48' },
        { label: '个人社保', value: '¥ ' + fmt(d.annual_insurance), sub: '养老 + 医疗 + 失业', color: '#ea580c' },
        { label: '广义税率', value: fmtPct(d.effective_burden_rate), sub: '（个税 + 社保）/ 名义收入', color: '#7c3aed' },
      ]
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

    const posterData = computed(() => {
      const monthlyRows = (r.value.monthly_details || []).map(item => ({
        month: `${item.month}月`,
        salary: fmt(item.salary),
        take: fmt(item.after_tax_salary),
        insurance: fmt(item.insurance.total),
        housing: fmt(item.housing_fund.employee + item.housing_fund.employer),
        tax: fmt(item.tax),
      }))

      const extraNotes = []
      if ((r.value.extra_income || 0) > 0) {
        extraNotes.push(`额外激励 ¥ ${fmt(r.value.extra_income)}`)
      }
      if ((r.value.stock_grants || []).length > 0) {
        const stockTotal = (r.value.stock_grants || []).reduce((sum, item) => sum + item, 0)
        extraNotes.push(`股票激励 ${r.value.stock_grants.length} 笔，合计 ¥ ${fmt(stockTotal)}`)
      }

      let height = 260
      height += 32 + 356
      height += 32 + (96 + resultSections.value.length * 78)
      height += 32 + (112 + incomeRows.value.length * 60)
      if (annualBreakdown.value.length > 0) {
        height += 32 + (150 + annualBreakdown.value.length * 42)
      }
      if (monthlyTrend.value.length > 0) {
        height += 32 + 304
      }
      if ((r.value.bonus || 0) > 0) {
        height += 32 + 148
      }
      if (stockRows.value.length > 0) {
        height += 32 + (92 + stockRows.value.length * 68)
      }
      if (monthlyRows.length > 0) {
        height += 32 + (108 + (monthlyRows.length + 1) * 48)
      }
      height += 88

      return {
        title: r.value._mode === 'optimize' ? 'TaxOpt 税筹优化结果' : 'TaxOpt 收入计算结果',
        nominal: fmt(r.value.nominal_income || ((r.value.annual_salary || 0) + (r.value.bonus || 0))),
        salaryLine: `月薪 ${fmt(r.value.monthly_salary)} × 12 ＋ 年终奖 ${fmt(r.value.bonus)}`,
        extraNotes,
        metrics: metricCards.value,
        resultRows: resultSections.value,
        composeRows: incomeRows.value,
        annualRows: annualBreakdown.value,
        trendRows: monthlyTrend.value,
        bonusVisible: (r.value.bonus || 0) > 0,
        stockRows: stockRows.value,
        monthlyRows,
        height,
      }
    })

    const posterHeight = computed(() => posterData.value.height)

    onMounted(() => {
      r.value = uni.getStorageSync('taxopt_result') || {}
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

    function setText(ctx, { size, color, align = 'left' }) {
      ctx.setFontSize(size)
      ctx.setFillStyle(color)
      ctx.setTextAlign(align)
    }

    function drawCard(ctx, x, y, w, h, title) {
      drawRoundedRect(ctx, x, y, w, h, 28, '#ffffff')
      setText(ctx, { size: 24, color: '#64748b' })
      ctx.fillText(title, x + 32, y + 42)
      return y + 78
    }

    function drawRightText(ctx, text, x, y, size, color) {
      setText(ctx, { size, color, align: 'right' })
      ctx.fillText(text, x, y)
      ctx.setTextAlign('left')
    }

    function splitLines(text, maxChars, maxLines = 2) {
      if (!text) return []
      const lines = []
      let current = ''
      Array.from(String(text)).forEach((char) => {
        if (current.length >= maxChars) {
          lines.push(current)
          current = char
          return
        }
        current += char
      })
      if (current) lines.push(current)
      if (lines.length <= maxLines) return lines
      const clipped = lines.slice(0, maxLines)
      clipped[maxLines - 1] = `${clipped[maxLines - 1].slice(0, Math.max(maxChars - 1, 1))}…`
      return clipped
    }

    function drawWrappedText(ctx, text, x, y, options = {}) {
      const {
        maxChars = 18,
        maxLines = 2,
        lineHeight = 28,
        size = 20,
        color = '#64748b',
      } = options
      const lines = splitLines(text, maxChars, maxLines)
      setText(ctx, { size, color })
      lines.forEach((line, index) => {
        ctx.fillText(line, x, y + index * lineHeight)
      })
      return lines.length
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
        const current = settingRes.authSetting && settingRes.authSetting['scope.writePhotosAlbum']

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
        return !!(openRes.authSetting && openRes.authSetting['scope.writePhotosAlbum'])
      } catch (error) {
        return false
      }
    }

    function pad2(value) {
      return String(value).padStart(2, '0')
    }

    function buildPosterFileBase(date = new Date()) {
      const y = date.getFullYear()
      const m = pad2(date.getMonth() + 1)
      const d = pad2(date.getDate())
      const hh = pad2(date.getHours())
      const mm = pad2(date.getMinutes())
      const ss = pad2(date.getSeconds())
      return `TaxOpt_${y}${m}${d}_${hh}${mm}${ss}`
    }

    function getMiniProgramFs() {
      if (typeof wx !== 'undefined' && wx.getFileSystemManager) {
        return wx.getFileSystemManager()
      }
      if (typeof uni !== 'undefined' && uni.getFileSystemManager) {
        return uni.getFileSystemManager()
      }
      return null
    }

    function getUserDataPath() {
      if (typeof wx !== 'undefined' && wx.env && wx.env.USER_DATA_PATH) {
        return wx.env.USER_DATA_PATH
      }
      return ''
    }

    function fileExists(fs, filePath) {
      return new Promise((resolve) => {
        if (!fs || !fs.access) {
          resolve(false)
          return
        }
        fs.access({
          path: filePath,
          success: () => resolve(true),
          fail: () => resolve(false),
        })
      })
    }

    function copyFile(fs, srcPath, destPath) {
      return new Promise((resolve, reject) => {
        if (!fs || !fs.copyFile) {
          reject(new Error('copyFile unavailable'))
          return
        }
        fs.copyFile({
          srcPath,
          destPath,
          success: resolve,
          fail: reject,
        })
      })
    }

    async function buildPosterTargetPath() {
      const fs = getMiniProgramFs()
      const userDataPath = getUserDataPath()
      if (!fs || !userDataPath) return ''

      const baseName = buildPosterFileBase()
      let idx = 0
      while (idx < 1000) {
        const suffix = idx === 0 ? '' : `_${idx}`
        const filePath = `${userDataPath}/${baseName}${suffix}.png`
        const exists = await fileExists(fs, filePath)
        if (!exists) return filePath
        idx += 1
      }
      return `${userDataPath}/${baseName}_${Date.now()}.png`
    }

    async function persistPosterFile(tempFilePath) {
      const fs = getMiniProgramFs()
      const targetPath = await buildPosterTargetPath()
      if (!fs || !targetPath) {
        return tempFilePath
      }
      await copyFile(fs, tempFilePath, targetPath)
      return targetPath
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
      const poster = posterData.value
      const height = poster.height

      ctx.setFillStyle('#f5f7fb')
      ctx.fillRect(0, 0, width, height)

      ctx.setFillStyle('#4f46e5')
      ctx.fillRect(0, 0, width, 232)

      setText(ctx, { size: 46, color: '#ffffff' })
      ctx.fillText(poster.title, 64, 88)
      setText(ctx, { size: 28, color: '#eef2ff' })
      ctx.fillText(`全年名义收入 ¥ ${poster.nominal}`, 64, 142)
      ctx.fillText(poster.salaryLine, 64, 184)
      poster.extraNotes.forEach((line, index) => {
        ctx.fillText(line, 64, 226 + index * 34)
      })

      let y = 264

      const metricCardTop = drawCard(ctx, 40, y, width - 80, 356, '年度指标')
      const metricBoxWidth = (width - 80 - 32 * 3) / 2
      const metricBoxHeight = 58
      poster.metrics.forEach((item, index) => {
        const col = index % 2
        const row = Math.floor(index / 2)
        const boxX = 72 + col * (metricBoxWidth + 32)
        const boxY = metricCardTop + row * 64
        drawRoundedRect(ctx, boxX, boxY, metricBoxWidth, metricBoxHeight, 18, '#f8fafc')
        setText(ctx, { size: 20, color: '#64748b' })
        ctx.fillText(item.label, boxX + 18, boxY + 22)
        drawRightText(ctx, item.value, boxX + metricBoxWidth - 18, boxY + 36, 26, item.color)
        setText(ctx, { size: 18, color: '#94a3b8' })
        ctx.fillText(item.sub, boxX + 18, boxY + 46)
      })

      y += 388

      const resultHeight = 96 + poster.resultRows.length * 78
      let sectionTop = drawCard(ctx, 40, y, width - 80, resultHeight, '分项结果')
      poster.resultRows.forEach((item, index) => {
        const rowTop = sectionTop + index * 78
        setText(ctx, { size: 26, color: '#0f172a' })
        ctx.fillText(item.label, 72, rowTop + 8)
        if (item.sub) {
          drawWrappedText(ctx, item.sub, 72, rowTop + 32, { size: 18, color: '#94a3b8', maxChars: 26, lineHeight: 24 })
        }
        drawRightText(ctx, `¥ ${fmt(item.value)}`, width - 72, rowTop + 12, 28, item.color || '#0f172a')
      })

      y += resultHeight + 32

      const composeHeight = 112 + poster.composeRows.length * 60
      sectionTop = drawCard(ctx, 40, y, width - 80, composeHeight, '收入与税额构成')
      setText(ctx, { size: 20, color: '#94a3b8' })
      ctx.fillText('收入项目', 72, sectionTop)
      drawRightText(ctx, '税前', 520, sectionTop, 20, '#94a3b8')
      drawRightText(ctx, '税额', 760, sectionTop, 20, '#94a3b8')
      drawRightText(ctx, '税后', width - 72, sectionTop, 20, '#94a3b8')
      poster.composeRows.forEach((row, index) => {
        const rowTop = sectionTop + 34 + index * 60
        setText(ctx, { size: 24, color: row.total ? '#111827' : '#334155' })
        ctx.fillText(row.label, 72, rowTop)
        drawRightText(ctx, fmt(row.gross), 520, rowTop, 24, '#334155')
        drawRightText(ctx, row.taxableNote || fmt(row.tax), 760, rowTop, 24, '#dc2626')
        drawRightText(ctx, row.takeNote || fmt(row.take), width - 72, rowTop, 24, '#16a34a')
      })

      y += composeHeight + 32

      if (poster.annualRows.length > 0) {
        const annualHeight = 150 + poster.annualRows.length * 42
        sectionTop = drawCard(ctx, 40, y, width - 80, annualHeight, '年度收入构成')
        drawRoundedRect(ctx, 72, sectionTop + 8, width - 144, 18, 999, '#e2e8f0')
        let offsetX = 72
        poster.annualRows.forEach((item, index) => {
          const segmentWidth = (width - 144) * (parseFloat(item.width) / 100)
          const radius = index === 0 || index === poster.annualRows.length - 1 ? 9 : 0
          drawRoundedRect(ctx, offsetX, sectionTop + 8, segmentWidth, 18, radius, item.color)
          offsetX += segmentWidth
        })
        poster.annualRows.forEach((item, index) => {
          const rowTop = sectionTop + 56 + index * 42
          setText(ctx, { size: 22, color: item.color })
          ctx.fillText(`● ${item.label}`, 72, rowTop)
          drawRightText(ctx, `¥ ${fmt(item.value)}`, width - 160, rowTop, 22, '#334155')
          drawRightText(ctx, item.rate, width - 72, rowTop, 20, '#94a3b8')
        })
        y += annualHeight + 32
      }

      if (poster.trendRows.length > 0) {
        const trendHeight = 304
        sectionTop = drawCard(ctx, 40, y, width - 80, trendHeight, '月度到手趋势')
        const chartBottom = y + trendHeight - 46
        const chartHeight = 130
        const maxValue = Math.max(...poster.trendRows.map(item => item.value), 1)
        const barGap = 10
        const barWidth = ((width - 144) - (poster.trendRows.length - 1) * barGap) / poster.trendRows.length
        poster.trendRows.forEach((item, index) => {
          const barX = 72 + index * (barWidth + barGap)
          const barHeight = Math.max((item.value / maxValue) * chartHeight, 10)
          drawRoundedRect(ctx, barX, chartBottom - barHeight - 38, barWidth, barHeight, 12, '#6366f1')
          setText(ctx, { size: 18, color: '#64748b', align: 'center' })
          ctx.fillText(item.month.replace('月', ''), barX + barWidth / 2, chartBottom)
          ctx.fillText(item.short, barX + barWidth / 2, chartBottom - barHeight - 50)
        })
        ctx.setTextAlign('left')
        y += trendHeight + 32
      }

      if (poster.bonusVisible) {
        const bonusHeight = 148
        sectionTop = drawCard(ctx, 40, y, width - 80, bonusHeight, '年终奖明细')
        const columnWidth = (width - 80 - 64) / 3
        const bonusItems = [
          { label: '税前', value: fmt(r.value.bonus), color: '#0f172a' },
          { label: '税额', value: fmt(r.value.bonus_tax), color: '#dc2626' },
          { label: '税后到手', value: fmt(r.value.bonus_after_tax), color: '#16a34a' },
        ]
        bonusItems.forEach((item, index) => {
          const itemX = 72 + index * columnWidth
          setText(ctx, { size: 20, color: '#94a3b8', align: 'center' })
          ctx.fillText(item.label, itemX + columnWidth / 2, sectionTop + 10)
          ctx.fillText(`¥ ${item.value}`, itemX + columnWidth / 2, sectionTop + 54)
        })
        ctx.setTextAlign('left')
        y += bonusHeight + 32
      }

      if (poster.stockRows.length > 0) {
        const stockHeight = 92 + poster.stockRows.length * 68
        sectionTop = drawCard(ctx, 40, y, width - 80, stockHeight, '股票明细')
        poster.stockRows.forEach((row, index) => {
          const rowTop = sectionTop + index * 68
          drawRoundedRect(ctx, 72, rowTop - 18, width - 144, 54, 16, '#f8fafc')
          setText(ctx, { size: 22, color: '#0f172a' })
          ctx.fillText(row.label, 92, rowTop + 4)
          setText(ctx, { size: 18, color: '#94a3b8' })
          ctx.fillText(`税额 ¥ ${fmt(row.tax)}`, 92, rowTop + 28)
          drawRightText(ctx, `税后 ¥ ${fmt(row.take)}`, width - 92, rowTop + 18, 22, '#16a34a')
        })
        y += stockHeight + 32
      }

      if (poster.monthlyRows.length > 0) {
        const monthlyHeight = 108 + (poster.monthlyRows.length + 1) * 48
        sectionTop = drawCard(ctx, 40, y, width - 80, monthlyHeight, '月度明细')
        setText(ctx, { size: 18, color: '#94a3b8' })
        ctx.fillText('月份', 72, sectionTop)
        drawRightText(ctx, '税前月薪', 360, sectionTop, 18, '#94a3b8')
        drawRightText(ctx, '税后到手', 560, sectionTop, 18, '#94a3b8')
        drawRightText(ctx, '个人三险', 740, sectionTop, 18, '#94a3b8')
        drawRightText(ctx, '税额', width - 72, sectionTop, 18, '#94a3b8')
        poster.monthlyRows.forEach((row, index) => {
          const rowTop = sectionTop + 34 + index * 48
          setText(ctx, { size: 20, color: '#334155' })
          ctx.fillText(row.month, 72, rowTop)
          drawRightText(ctx, row.salary, 360, rowTop, 20, '#334155')
          drawRightText(ctx, row.take, 560, rowTop, 20, '#16a34a')
          drawRightText(ctx, row.insurance, 740, rowTop, 20, '#ea580c')
          drawRightText(ctx, row.tax, width - 72, rowTop, 20, '#dc2626')
        })
        y += monthlyHeight + 32
      }

      setText(ctx, { size: 22, color: '#94a3b8' })
      ctx.fillText('TaxOpt 微信小程序 · 结果长图', 72, height - 40)

      ctx.draw(false, () => {
        uni.canvasToTempFilePath({
          canvasId: 'resultPoster',
          success: async ({ tempFilePath }) => {
            try {
              const filePath = await persistPosterFile(tempFilePath)
              uni.saveImageToPhotosAlbum({
                filePath,
                success: () => {
                  uni.hideLoading()
                  uni.showToast({ title: '长图已保存', icon: 'success' })
                },
                fail: () => {
                  uni.hideLoading()
                  uni.showToast({ title: '保存失败，请检查相册权限', icon: 'none' })
                },
              })
            } catch (error) {
              uni.hideLoading()
              uni.showToast({ title: '保存失败，请稍后重试', icon: 'none' })
            }
          },
          fail: () => {
            uni.hideLoading()
            uni.showToast({ title: '生成长图失败', icon: 'none' })
          },
        })
      })
    }

    function goBack() {
      uni.navigateBack()
    }

    return {
      r,
      posterWidth,
      posterHeight,
      fmt,
      metricCards,
      resultSections,
      incomeRows,
      annualBreakdown,
      monthlyTrend,
      stockRows,
      savePoster,
      goBack,
    }
  },
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
.table      { min-width: 940rpx; }
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
.td-month {
  flex: none;
  width: 68rpx;
  min-width: 68rpx;
}
.td-salary,
.td-take {
  min-width: 150rpx;
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
  padding: 0;
  line-height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $primary;
  color: #fff;
  font-size: 28rpx;
  border-radius: 16rpx;
  border: none;
}
.btn-back {
  width: 100%;
  height: 88rpx;
  padding: 0;
  line-height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
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
