<template>
  <scroll-view scroll-y class="page">

    <!-- 模式选择 -->
    <view class="card">
      <text class="section-title">计算模式</text>
      <view class="mode-tabs">
        <view
          v-for="m in modes" :key="m.value"
          class="mode-tab"
          :class="{ active: mode === m.value }"
          @tap="mode = m.value"
        >{{ m.label }}</view>
      </view>
    </view>

    <!-- 收入输入 -->
    <view class="card">
      <text class="section-title">收入（元）</text>
      <view v-if="mode !== 'both'" class="field">
        <text class="label">全年名义收入</text>
        <input class="input-field" type="digit" v-model.number="income.total" placeholder="如 300000" />
      </view>
      <view v-if="mode === 'salary' || mode === 'both'" class="field">
        <text class="label">月薪</text>
        <input class="input-field" type="digit" v-model.number="income.monthly" placeholder="如 20000" />
      </view>
      <view v-if="mode === 'bonus' || mode === 'both'" class="field">
        <text class="label">年终奖</text>
        <input class="input-field" type="digit" v-model.number="income.bonus" placeholder="如 60000" />
      </view>
      <view v-if="mode === 'optimize'" class="field">
        <text class="label">优化目标</text>
        <picker :range="objectives" range-key="label" :value="objectiveIndex" @change="onObjectiveChange">
          <view class="picker-row">
            <text>{{ objectives[objectiveIndex].label }}</text>
            <text class="picker-arrow">›</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 城市预设 -->
    <view class="card">
      <text class="section-title">城市 / 社保参数</text>
      <view class="field">
        <text class="label">城市预设</text>
        <picker :range="presetOptions" range-key="label" :value="presetIndex" @change="onPresetChange">
          <view class="picker-row">
            <text>{{ presetOptions[presetIndex]?.label || '加载中…' }}</text>
            <text class="picker-arrow">›</text>
          </view>
        </picker>
      </view>

      <!-- 展开/收起参数 -->
      <view class="expand-toggle" @tap="showParams = !showParams">
        <text class="expand-text">{{ showParams ? '收起参数 ∧' : '展开参数 ∨' }}</text>
      </view>

      <view v-if="showParams">
        <view class="divider" />
        <view class="field-row">
          <view class="field half">
            <text class="label">社保基数下限</text>
            <input class="input-field" type="digit" v-model.number="cfg.social_security_base_min" />
          </view>
          <view class="field half">
            <text class="label">社保基数上限</text>
            <input class="input-field" type="digit" v-model.number="cfg.social_security_base_limit" />
          </view>
        </view>
        <view class="field-row">
          <view class="field third">
            <text class="label">养老 %</text>
            <input class="input-field" type="digit" v-model.number="cfg.pension_rate" />
          </view>
          <view class="field third">
            <text class="label">医疗 %</text>
            <input class="input-field" type="digit" v-model.number="cfg.medical_rate" />
          </view>
          <view class="field third">
            <text class="label">失业 %</text>
            <input class="input-field" type="digit" v-model.number="cfg.unemployment_rate" />
          </view>
        </view>
        <view class="field-row">
          <view class="field half">
            <text class="label">公积金基数下限</text>
            <input class="input-field" type="digit" v-model.number="cfg.housing_fund_base_min" />
          </view>
          <view class="field half">
            <text class="label">公积金基数上限</text>
            <input class="input-field" type="digit" v-model.number="cfg.housing_fund_base_limit" />
          </view>
        </view>
        <view class="field-row">
          <view class="field half">
            <text class="label">个人公积金比例</text>
            <input class="input-field" type="digit" v-model.number="cfg.housing_fund_employee_rate" />
          </view>
          <view class="field half">
            <text class="label">单位公积金比例</text>
            <input class="input-field" type="digit" v-model.number="cfg.housing_fund_employer_rate" />
          </view>
        </view>
      </view>
    </view>

    <!-- 专项附加扣除 -->
    <view class="card">
      <text class="section-title">专项附加扣除（月）</text>
      <view v-for="d in deductions" :key="d.key" class="deduction-row">
        <text class="deduction-label">{{ d.label }}</text>
        <input class="input-field deduction-input" type="digit" v-model.number="cfg[d.key]" placeholder="0" />
      </view>
      <view class="deduction-row">
        <text class="deduction-label">其他年度扣除（全年）</text>
        <input class="input-field deduction-input" type="digit" v-model.number="cfg.annual_additional_deduction" placeholder="0" />
      </view>
    </view>

    <!-- 错误提示 -->
    <view v-if="error" class="error-box">
      <text>{{ error }}</text>
    </view>

    <!-- 计算按钮 -->
    <view class="btn-wrap">
      <button class="btn-primary" :loading="loading" :disabled="loading" @tap="calculate">
        {{ loading ? '计算中…' : '开始计算' }}
      </button>
    </view>

  </scroll-view>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '../../utils/api.js'

// ── 模式 ──────────────────────────────────────
const modes = [
  { value: 'optimize', label: '优化' },
  { value: 'salary',   label: '月薪' },
  { value: 'bonus',    label: '年终奖' },
  { value: 'both',     label: '自定义' },
]
const mode = ref('optimize')

const objectives = [
  { value: 'cash',                   label: '最大化到手现金' },
  { value: 'cash_plus_provident_fund', label: '最大化现金+公积金' },
]
const objectiveIndex = ref(0)
const onObjectiveChange = (e) => { objectiveIndex.value = e.detail.value }

// ── 收入 ──────────────────────────────────────
const income = reactive({ total: null, monthly: null, bonus: null })

// ── 城市预设 ──────────────────────────────────
const presets = ref([])
const presetOptions = ref([{ slug: '', label: '自定义参数' }])
const presetIndex = ref(0)

onMounted(async () => {
  try {
    const list = await api.getPresets()
    presets.value = list
    presetOptions.value = [
      { slug: '', label: '自定义参数' },
      ...list.map(p => ({ slug: p.slug, label: p.label })),
    ]
  } catch (e) {
    // 加载失败时保留"自定义参数"选项，不阻断使用
  }
})

const onPresetChange = async (e) => {
  presetIndex.value = e.detail.value
  const selected = presetOptions.value[e.detail.value]
  if (!selected?.slug) return
  try {
    const data = await api.getPreset(selected.slug)
    Object.assign(cfg, data)
    showParams.value = true
  } catch (e) {
    uni.showToast({ title: '预设加载失败', icon: 'none' })
  }
}

// ── 参数配置 ───────────────────────────────────
const showParams = ref(false)
const cfg = reactive({
  basic_deduction: 60000,
  social_security_base_min: 0,
  social_security_base_limit: 0,
  pension_rate: 0.08,
  medical_rate: 0.02,
  unemployment_rate: 0.005,
  housing_fund_base_min: 0,
  housing_fund_base_limit: 0,
  housing_fund_employee_rate: 0.12,
  housing_fund_employer_rate: 0.12,
  children_education: 0,
  continuing_education: 0,
  serious_illness: 0,
  housing_loan_interest: 0,
  housing_rent: 0,
  elderly_support: 0,
  annual_additional_deduction: 0,
})

const deductions = [
  { key: 'children_education',   label: '子女教育' },
  { key: 'continuing_education', label: '继续教育' },
  { key: 'serious_illness',      label: '大病医疗' },
  { key: 'housing_loan_interest', label: '住房贷款利息' },
  { key: 'housing_rent',         label: '住房租金' },
  { key: 'elderly_support',      label: '赡养老人' },
]

// ── 计算 ──────────────────────────────────────
const loading = ref(false)
const error = ref('')

async function calculate() {
  error.value = ''
  const payload = {
    mode: mode.value,
    objective: objectives[objectiveIndex.value].value,
    config: { ...cfg },
  }
  if (mode.value !== 'both') payload.total = income.total
  if (mode.value === 'salary' || mode.value === 'both') payload.monthly = income.monthly
  if (mode.value === 'bonus'  || mode.value === 'both') payload.bonus   = income.bonus

  loading.value = true
  try {
    const result = await api.calculate(payload)
    uni.setStorageSync('taxopt_result', result)
    uni.navigateTo({ url: '/pages/result/result' })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.page {
  background: $bg-page;
  min-height: 100vh;
  padding: 24rpx;
  box-sizing: border-box;
}

.mode-tabs {
  display: flex;
  background: #f3f4f6;
  border-radius: 10rpx;
  padding: 6rpx;
  gap: 4rpx;
}
.mode-tab {
  flex: 1;
  text-align: center;
  padding: 12rpx 0;
  font-size: 26rpx;
  color: $text-muted;
  border-radius: 8rpx;
  &.active {
    background: #fff;
    color: $primary;
    font-weight: 600;
    box-shadow: 0 1rpx 4rpx rgba(0,0,0,.08);
  }
}

.field { margin-bottom: 20rpx; }
.field-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.half  { flex: 1; }
.third { flex: 1; }

.picker-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 72rpx;
  border: 1rpx solid $border;
  border-radius: 8rpx;
  padding: 0 16rpx;
  background: #f9fafb;
  font-size: 28rpx;
  color: $text-base;
}
.picker-arrow { color: $text-muted; font-size: 36rpx; }

.expand-toggle { margin-top: 16rpx; }
.expand-text { font-size: 24rpx; color: $primary; }

.deduction-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.deduction-label { font-size: 26rpx; color: $text-base; flex: 1; }
.deduction-input { width: 200rpx !important; flex: none; text-align: right; }

.error-box {
  background: #fef2f2;
  border: 1rpx solid #fca5a5;
  border-radius: 8rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  font-size: 26rpx;
  color: #dc2626;
}

.btn-wrap { padding: 0 0 48rpx; }
.btn-primary {
  width: 100%;
  height: 88rpx;
  background: $primary;
  color: #fff;
  font-size: 30rpx;
  font-weight: 600;
  border-radius: 16rpx;
  border: none;
  &[disabled] { background: #a5b4fc; }
}
</style>
