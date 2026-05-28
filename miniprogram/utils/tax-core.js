const TAX_CONFIG_DEFAULTS = {
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
}

const TAX_CONFIG_KEYS = Object.keys(TAX_CONFIG_DEFAULTS)

export const COMPREHENSIVE_BRACKETS = [
  [0, 36000, 0.03, 0],
  [36000, 144000, 0.10, 2520],
  [144000, 300000, 0.20, 16920],
  [300000, 420000, 0.25, 31920],
  [420000, 660000, 0.30, 52920],
  [660000, 960000, 0.35, 85920],
  [960000, Infinity, 0.45, 181920],
]

export const BONUS_BRACKETS_MONTHLY = [
  [0, 3000, 0.03, 0],
  [3000, 12000, 0.10, 210],
  [12000, 25000, 0.20, 1410],
  [25000, 35000, 0.25, 2660],
  [35000, 55000, 0.30, 4410],
  [55000, 80000, 0.35, 7160],
  [80000, Infinity, 0.45, 15160],
]

export const BONUS_BRACKETS_ANNUAL = BONUS_BRACKETS_MONTHLY.map(
  ([lo, hi, rate, quick]) => [lo * 12, Number.isFinite(hi) ? hi * 12 : Infinity, rate, quick],
)

const COMPREHENSIVE_TAX_BREAKPOINTS = [
  0,
  ...COMPREHENSIVE_BRACKETS
    .map(([, hi]) => hi)
    .filter(Number.isFinite),
]

const BONUS_TAX_BREAKPOINTS = [
  0,
  ...BONUS_BRACKETS_ANNUAL
    .map(([, hi]) => hi)
    .filter(Number.isFinite),
]

function numeric(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

export function createTaxConfig(raw = {}) {
  const config = {}
  TAX_CONFIG_KEYS.forEach((key) => {
    config[key] = numeric(raw[key], TAX_CONFIG_DEFAULTS[key])
  })
  return config
}

export function validateTaxConfig(config) {
  const c = createTaxConfig(config)
  if (c.basic_deduction < 0) {
    throw new Error('basic_deduction 不能为负数')
  }

  ;[
    ['pension_rate', c.pension_rate],
    ['medical_rate', c.medical_rate],
    ['unemployment_rate', c.unemployment_rate],
    ['housing_fund_employee_rate', c.housing_fund_employee_rate],
    ['housing_fund_employer_rate', c.housing_fund_employer_rate],
  ].forEach(([name, rate]) => {
    if (rate < 0 || rate > 1) {
      throw new Error(`${name} 须在 [0, 1] 区间内，当前为 ${rate}`)
    }
  })

  if (
    c.social_security_base_min > 0 &&
    c.social_security_base_limit > 0 &&
    c.social_security_base_min > c.social_security_base_limit
  ) {
    throw new Error(
      `社保基数下限不能大于上限：social_security_base_min=${c.social_security_base_min}, social_security_base_limit=${c.social_security_base_limit}`,
    )
  }

  if (
    c.housing_fund_base_min > 0 &&
    c.housing_fund_base_limit > 0 &&
    c.housing_fund_base_min > c.housing_fund_base_limit
  ) {
    throw new Error(
      `公积金基数下限不能大于上限：housing_fund_base_min=${c.housing_fund_base_min}, housing_fund_base_limit=${c.housing_fund_base_limit}`,
    )
  }

  ;[
    ['children_education', c.children_education],
    ['continuing_education', c.continuing_education],
    ['serious_illness', c.serious_illness],
    ['housing_loan_interest', c.housing_loan_interest],
    ['housing_rent', c.housing_rent],
    ['elderly_support', c.elderly_support],
    ['annual_additional_deduction', c.annual_additional_deduction],
  ].forEach(([name, value]) => {
    if (value < 0) {
      throw new Error(`${name} 不能为负数，当前为 ${value}`)
    }
  })
}

export function progressiveTax(taxable, brackets) {
  const value = numeric(taxable)
  if (value <= 0) return 0

  for (let i = 0; i < brackets.length; i += 1) {
    const [lo, hi, rate, quick] = brackets[i]
    if (lo < value && value <= hi) {
      return value * rate - quick
    }
  }
  return 0
}

export class TaxCalculator {
  constructor(config) {
    this.c = createTaxConfig(config)
  }

  monthlySpecialAdditional() {
    const c = this.c
    return (
      c.children_education +
      c.continuing_education +
      c.serious_illness +
      c.housing_loan_interest +
      c.housing_rent +
      c.elderly_support
    )
  }

  annualAdditionalTotal() {
    return this.monthlySpecialAdditional() * 12 + this.c.annual_additional_deduction
  }

  monthlyInsurance(monthlySalary) {
    const c = this.c
    let base = numeric(monthlySalary)
    if (c.social_security_base_limit > 0) {
      base = Math.min(base, c.social_security_base_limit)
    }
    if (c.social_security_base_min > 0) {
      base = Math.max(base, c.social_security_base_min)
    }

    const pension = base * c.pension_rate
    const medical = base * c.medical_rate
    const unemployment = base * c.unemployment_rate
    return {
      pension,
      medical,
      unemployment,
      total: pension + medical + unemployment,
    }
  }

  monthlyHousingFund(monthlySalary) {
    const c = this.c
    let base = numeric(monthlySalary)
    if (c.housing_fund_base_limit > 0) {
      base = Math.min(base, c.housing_fund_base_limit)
    }
    if (c.housing_fund_base_min > 0) {
      base = Math.max(base, c.housing_fund_base_min)
    }

    return {
      employee: base * c.housing_fund_employee_rate,
      employer: base * c.housing_fund_employer_rate,
    }
  }

  bonusTax(bonus) {
    const value = numeric(bonus)
    if (value <= 0) return 0
    return progressiveTax(value, BONUS_BRACKETS_ANNUAL)
  }

  calcAnnualTax(monthlySalary, bonus, extraIncome = 0) {
    const salary = numeric(monthlySalary)
    const extra = numeric(extraIncome)
    const ins = this.monthlyInsurance(salary)
    const hf = this.monthlyHousingFund(salary)
    const annualPersonalDeduction = (ins.total + hf.employee) * 12
    const annualProvidentFundTotal = (hf.employee + hf.employer) * 12

    const taxable = (
      salary * 12 +
      extra -
      this.c.basic_deduction -
      this.annualAdditionalTotal() -
      annualPersonalDeduction
    )

    return {
      comprehensiveTax: progressiveTax(taxable, COMPREHENSIVE_BRACKETS),
      bonusTax: this.bonusTax(bonus),
      annualPersonalDeduction,
      annualProvidentFundTotal,
      ins,
      hf,
    }
  }

  monthlyDetails(monthlySalary, insMonthly = null, hfMonthly = null) {
    const salary = numeric(monthlySalary)
    const ins = insMonthly || this.monthlyInsurance(salary)
    const hf = hfMonthly || this.monthlyHousingFund(salary)
    const monthlyPersonalDeduction = ins.total + hf.employee
    const addM = this.monthlySpecialAdditional()
    const basicM = this.c.basic_deduction / 12
    let prevCumTax = 0
    const rows = []

    for (let month = 1; month <= 12; month += 1) {
      const cumIncome = salary * month
      const cumBasic = basicM * month
      const cumDeduction = monthlyPersonalDeduction * month
      const cumAdd = addM * month + this.c.annual_additional_deduction
      const cumTaxable = cumIncome - cumBasic - cumDeduction - cumAdd
      const cumTax = progressiveTax(cumTaxable, COMPREHENSIVE_BRACKETS)
      const monthTax = cumTax - prevCumTax
      prevCumTax = cumTax

      rows.push({
        month,
        salary,
        insurance: ins,
        housing_fund: hf,
        tax: monthTax,
        after_tax_salary: salary - monthlyPersonalDeduction - monthTax,
        after_tax_including_provident_fund: (
          salary - monthlyPersonalDeduction - monthTax + hf.employee + hf.employer
        ),
        cumulative_taxable_income: cumTaxable,
        cumulative_tax: cumTax,
      })
    }

    return rows
  }
}

function enrichResultWithProvidentFund(result) {
  const apf = numeric(result.annual_provident_fund)
  result.net_take_home_including_provident_fund = result.net_take_home + apf
  result.salary_take_home_including_provident_fund = result.salary_take_home + apf
}

export class TaxOptimizer {
  constructor(calc) {
    this.calc = calc
  }

  alignFloorToStep(value, step) {
    if (value <= 0) return 0
    return Math.floor((value + 1e-9) / step) * step
  }

  alignCeilToStep(value, step) {
    if (value <= 0) return 0
    return Math.ceil((value - 1e-9) / step) * step
  }

  piecewiseComponentLinear(sampleSalary, baseMin, baseLimit, annualRate) {
    if (annualRate === 0) return [0, 0]
    if (baseLimit > 0 && sampleSalary >= baseLimit) {
      return [0, baseLimit * annualRate]
    }
    if (baseMin > 0 && sampleSalary <= baseMin) {
      return [0, baseMin * annualRate]
    }
    return [annualRate, 0]
  }

  annualPersonalDeductionLinear(sampleSalary) {
    const c = this.calc.c
    const insuranceAnnualRate = 12 * (
      c.pension_rate +
      c.medical_rate +
      c.unemployment_rate
    )
    const [insuranceSlope, insuranceIntercept] = this.piecewiseComponentLinear(
      sampleSalary,
      c.social_security_base_min,
      c.social_security_base_limit,
      insuranceAnnualRate,
    )
    const [housingFundSlope, housingFundIntercept] = this.piecewiseComponentLinear(
      sampleSalary,
      c.housing_fund_base_min,
      c.housing_fund_base_limit,
      12 * c.housing_fund_employee_rate,
    )
    return [
      insuranceSlope + housingFundSlope,
      insuranceIntercept + housingFundIntercept,
    ]
  }

  salaryAxisBreakpoints(salaryBonusPool) {
    const capReal = Math.max(0, numeric(salaryBonusPool) / 12)
    const thresholds = [0, capReal]
    ;[
      this.calc.c.social_security_base_min,
      this.calc.c.social_security_base_limit,
      this.calc.c.housing_fund_base_min,
      this.calc.c.housing_fund_base_limit,
    ].forEach((value) => {
      if (value > 0 && value < capReal) {
        thresholds.push(value)
      }
    })
    return [...new Set(thresholds)].sort((a, b) => a - b)
  }

  candidateMonthlySalaries(salaryBonusPool, step, extraIncome = 0) {
    const pool = numeric(salaryBonusPool)
    if (pool < 0) return []

    const capReal = pool / 12
    const maxMonthlySalary = this.alignFloorToStep(capReal, step)
    const candidates = new Set([0, maxMonthlySalary])

    const addNeighborPoints = (point) => {
      if (point < 0 || point > capReal + 1e-9) return
      ;[
        this.alignFloorToStep(point, step),
        this.alignCeilToStep(point, step),
      ].forEach((candidate) => {
        if (candidate >= 0 && candidate <= maxMonthlySalary) {
          candidates.add(candidate)
        }
      })
    }

    const salaryBreakpoints = this.salaryAxisBreakpoints(pool)
    salaryBreakpoints.forEach(addNeighborPoints)

    const baseTaxableIntercept = (
      numeric(extraIncome) -
      this.calc.c.basic_deduction -
      this.calc.annualAdditionalTotal()
    )

    for (let i = 0; i < salaryBreakpoints.length - 1; i += 1) {
      const lo = salaryBreakpoints[i]
      const hi = salaryBreakpoints[i + 1]
      if (hi - lo <= 1e-9) continue

      const sampleSalary = (lo + hi) / 2
      const [deductionSlope, deductionIntercept] = this.annualPersonalDeductionLinear(sampleSalary)
      const taxableSlope = 12 - deductionSlope
      const taxableIntercept = baseTaxableIntercept - deductionIntercept
      if (Math.abs(taxableSlope) <= 1e-12) continue

      COMPREHENSIVE_TAX_BREAKPOINTS.forEach((boundary) => {
        const point = (boundary - taxableIntercept) / taxableSlope
        if (lo - 1e-9 <= point && point <= hi + 1e-9) {
          addNeighborPoints(point)
        }
      })
    }

    BONUS_TAX_BREAKPOINTS.forEach((boundary) => {
      addNeighborPoints((pool - boundary) / 12)
    })

    return [...candidates].sort((a, b) => a - b)
  }

  optimize(
    totalAnnual,
    step = 1,
    objective = 'cash',
    extraIncome = 0,
    stockGrants = [],
  ) {
    validateTaxConfig(this.calc.c)
    const total = numeric(totalAnnual)
    const extra = numeric(extraIncome)
    const grants = (stockGrants || []).map((item) => numeric(item))

    if (step <= 0) {
      throw new Error(`遍历步长 step 须为正整数，当前为 ${step}`)
    }
    if (total < 0) {
      throw new Error('全年工资总额不能为负数')
    }
    if (extra < 0) {
      throw new Error('额外激励不能为负数')
    }
    if (grants.some((grant) => grant < 0)) {
      throw new Error('股票激励金额不能为负数')
    }

    const stockGrantsTotal = grants.reduce((sum, grant) => sum + grant, 0)
    let salaryBonusPool = total - extra - stockGrantsTotal
    if (salaryBonusPool < -0.01) {
      throw new Error('额外激励与股票激励之和不能超过全年名义收入')
    }
    if (salaryBonusPool < 0) {
      salaryBonusPool = 0
    }

    let best = null
    let bestNet = -Infinity
    let bestTaxAtNet = Infinity
    const totalStockTax = grants.reduce((sum, grant) => sum + this.calc.bonusTax(grant), 0)
    const usePfObjective = objective === 'cash_plus_provident_fund'

    this.candidateMonthlySalaries(salaryBonusPool, step, extra).forEach((monthlySalary) => {
      const bonus = salaryBonusPool - monthlySalary * 12
      if (bonus < 0) return

      const annual = this.calc.calcAnnualTax(monthlySalary, bonus, extra)
      const tax = annual.comprehensiveTax + annual.bonusTax + totalStockTax
      const net = total - tax - annual.annualPersonalDeduction
      const score = usePfObjective ? net + annual.annualProvidentFundTotal : net

      if (score > bestNet || (score === bestNet && tax < bestTaxAtNet)) {
        bestNet = score
        bestTaxAtNet = tax
        best = { monthlySalary, bonus }
      }
    })

    if (!best) return {}

    return resultFromSalaryBonusSplit(
      this.calc,
      salaryBonusPool,
      best.monthlySalary,
      best.bonus,
      extra,
      grants,
    )
  }
}

export function adaptiveSearchStep(totalIncome) {
  return Math.max(1, Math.trunc(numeric(totalIncome) / 1000000))
}

function isClose(a, b, absTol = 0.01) {
  return Math.abs(a - b) <= absTol
}

export function resultFromSalaryBonusSplit(
  calc,
  totalAnnual,
  monthlySalary,
  bonus,
  extraIncome = 0,
  stockGrants = [],
) {
  const total = numeric(totalAnnual)
  const salary = numeric(monthlySalary)
  const bonusValue = numeric(bonus)
  const extra = numeric(extraIncome)
  const grants = (stockGrants || []).map((item) => numeric(item))

  if (total < 0) {
    throw new Error('全年收入不能为负数')
  }
  if (salary < 0 || bonusValue < 0) {
    throw new Error('月薪、年终奖不能为负数')
  }
  if (extra < 0) {
    throw new Error('额外激励不能为负数')
  }
  if (grants.some((grant) => grant < 0)) {
    throw new Error('股票激励金额不能为负数')
  }
  if (!isClose(salary * 12 + bonusValue, total, 0.01)) {
    throw new Error(
      `拆分不一致：月薪×12 + 年终奖 = ${(salary * 12 + bonusValue).toFixed(2)}，与全年收入 ${total.toFixed(2)} 不符（允许误差 0.01 元）`,
    )
  }

  const annual = calc.calcAnnualTax(salary, bonusValue, extra)
  const stockGrantsTax = grants.map((grant) => calc.bonusTax(grant))
  const totalStockTax = stockGrantsTax.reduce((sum, tax) => sum + tax, 0)
  const nominalIncome = total + extra + grants.reduce((sum, grant) => sum + grant, 0)
  const tax = annual.comprehensiveTax + annual.bonusTax + totalStockTax
  const net = nominalIncome - tax - annual.annualPersonalDeduction
  const salaryTake = salary * 12 - annual.comprehensiveTax - annual.annualPersonalDeduction

  const out = {
    monthly_salary: salary,
    annual_salary: salary * 12,
    bonus: bonusValue,
    extra_income: extra,
    stock_grants: grants,
    stock_grants_tax: stockGrantsTax,
    total_stock_tax: totalStockTax,
    comprehensive_annual_tax: annual.comprehensiveTax,
    bonus_tax: annual.bonusTax,
    total_tax: tax,
    annual_social_security: annual.annualPersonalDeduction,
    annual_insurance: annual.ins.total * 12,
    annual_housing_fund_employee: annual.hf.employee * 12,
    annual_provident_fund: annual.annualProvidentFundTotal,
    salary_take_home: salaryTake,
    net_take_home: net,
    nominal_income: nominalIncome,
    effective_tax_rate: nominalIncome ? tax / nominalIncome : 0,
    effective_social_security_rate: nominalIncome ? annual.annualPersonalDeduction / nominalIncome : 0,
    effective_burden_rate: nominalIncome ? (tax + annual.annualPersonalDeduction) / nominalIncome : 0,
    bonus_after_tax: bonusValue - annual.bonusTax,
    monthly_details: calc.monthlyDetails(salary, annual.ins, annual.hf),
  }
  enrichResultWithProvidentFund(out)
  return out
}

export function calculateWithConfig(payload, config) {
  const mode = payload && payload.mode
  if (mode !== 'optimize' && mode !== 'calc') {
    throw new Error('mode 必须为 optimize 或 calc')
  }

  const cfg = createTaxConfig(config)
  validateTaxConfig(cfg)
  const calc = new TaxCalculator(cfg)

  if (mode === 'optimize') {
    if (payload.total == null) {
      throw new Error('optimize 模式需要 total')
    }
    const total = numeric(payload.total)
    const result = new TaxOptimizer(calc).optimize(
      total,
      adaptiveSearchStep(total),
      payload.objective || 'cash',
      numeric(payload.extra_income),
      payload.stock_grants || [],
    )
    if (!result || Object.keys(result).length === 0) {
      throw new Error('未找到优化方案')
    }
    return result
  }

  if (payload.monthly == null || payload.bonus == null) {
    throw new Error('calc 模式需要 monthly 和 bonus')
  }
  const monthly = numeric(payload.monthly)
  const bonus = numeric(payload.bonus)
  return resultFromSalaryBonusSplit(
    calc,
    monthly * 12 + bonus,
    monthly,
    bonus,
    numeric(payload.extra_income),
    payload.stock_grants || [],
  )
}
