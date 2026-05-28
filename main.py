"""
个人所得税税筹核心模块。

本文件既是命令行入口，也是 API 层复用的计算内核。读代码时可以按下面的顺序看：

1. TaxConfig：保存社保、公积金、专项附加扣除等城市/个人参数。
2. TaxCalculator：只负责「给定月薪、年终奖、额外激励」时怎么算税和月度明细。
3. TaxOptimizer：在总收入固定时，寻找月薪/年终奖拆分，使目标到手收入最大。
4. result_from_salary_bonus_split：把一次计算包装成前端、API、CLI 都能消费的结果字典。
5. main：命令行参数解析和输出。

收入口径：
- total_annual 在 optimize 模式表示全年名义收入，包含工资、年终奖、额外激励、股票激励。
- salary_bonus_pool 表示可在「月薪×12」和「年终奖」之间拆分的部分。
- extra_income 表示额外激励，并入综合所得计税，但不参与月薪/年终奖拆分。
- stock_grants 表示股票激励，每笔按年终奖方式单独计税，也不参与月薪/年终奖拆分。

可选：将个人与公司公积金按月缴存合计计入「广义到手」；个人/公司缴存比例可分别配置。
optimize 模式的优化目标由命令行 `--objective` 指定（现金最大或现金+公积金最大）。

命令行：python main.py [-c 配置文件 | --preset 省-市] [optimize|calc] ...
未指定 -c 且未指定 --preset 时，读取与 main.py 同目录下的 config.json。
预设位于 presets/ 目录，命名：省拼音-市拼音（默认各城「市区」主流口径，见 presets/README.md）。
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# ---------- 配置 ----------


@dataclass
class TaxConfig:
    """
    计税参数集合。

    命名约定：
    - *_rate 使用小数，例如 0.12 表示 12%。
    - base_min/base_limit 是月度缴费基数的上下限；0 表示不启用该限制。
    - 专项附加扣除默认按月填写，annual_additional_deduction 是额外的一次性全年扣除。
    """

    basic_deduction: int = 60000  # 基本减除费用（年，5000/月×12=60000）

    social_security_base_min: float = 0  # 社保缴费基数下限（月，0 表示不启用下限）
    social_security_base_limit: float = 0  # 社保缴费基数上限（月，0 表示不启用上限）
    pension_rate: float = 0.08  # 养老保险个人比例
    medical_rate: float = 0.02  # 医疗保险个人比例
    unemployment_rate: float = 0.005  # 失业保险个人比例

    housing_fund_base_min: float = 0  # 公积金缴费基数下限（月）
    housing_fund_base_limit: float = 0  # 公积金缴费基数上限（月）
    housing_fund_employee_rate: float = 0.12  # 公积金个人缴存比例
    housing_fund_employer_rate: float = 0.12  # 公积金公司缴存比例（load_tax_config_from_json 未写时取与个人相同值）

    children_education: float = 0  # 子女教育专项附加扣除（月）
    continuing_education: float = 0  # 继续教育专项附加扣除（月）
    serious_illness: float = 0  # 大病医疗等（月，按你填写的月度额度）
    housing_loan_interest: float = 0  # 住房贷款利息专项附加扣除（月）
    housing_rent: float = 0  # 住房租金专项附加扣除（月）
    elderly_support: float = 0  # 赡养老人专项附加扣除（月）
    annual_additional_deduction: float = 0  # 全年一次性附加扣除（累计预扣从首月全额扣）


DEFAULT_CONFIG_FILENAME = "config.json"
PRESETS_DIR = Path(__file__).resolve().parent / "presets"


def load_tax_config_from_json(path: Union[str, Path]) -> TaxConfig:
    """
    从 JSON 文件构造 TaxConfig。根节点须为对象；不允许出现未知字段（避免拼写错误静默忽略）；
    未出现的键使用 TaxConfig 字段默认值，并在 stderr 输出警告列出缺省字段名。
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with path.open(encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败（{path}）：{e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"配置文件根节点必须是 JSON 对象：{path}")

    # 配置文件是用户手写/维护的地方，字段名拼错最容易造成安静的错误。
    # 因此这里采用严格模式：未知字段直接报错，缺失字段才回落到默认值。
    field_names = {f.name for f in fields(TaxConfig)}
    unknown = set(raw.keys()) - field_names
    if unknown:
        raise ValueError(
            "配置文件含有未知字段（请检查拼写，或与 TaxConfig 字段对齐）："
            + ", ".join(sorted(unknown))
        )

    missing = sorted(field_names - set(raw.keys()))
    if missing:
        print(
            "警告：配置文件未包含以下字段，将使用程序内默认值："
            + ", ".join(missing),
            file=sys.stderr,
        )

    kwargs: Dict[str, Any] = {}
    for f in fields(TaxConfig):
        if f.name in raw:
            kwargs[f.name] = raw[f.name]
        else:
            kwargs[f.name] = f.default

    # 兼容旧配置：如果没有单独写单位公积金比例，就沿用个人比例。
    if "housing_fund_employer_rate" not in raw:
        kwargs["housing_fund_employer_rate"] = kwargs["housing_fund_employee_rate"]

    try:
        return TaxConfig(**kwargs)
    except TypeError as e:
        raise ValueError(f"配置字段类型与 TaxConfig 不符：{e}") from e


def validate_tax_config(c: TaxConfig) -> None:
    """
    对 TaxConfig 做业务层校验。

    这里不尝试修正配置，只负责尽早失败。这样 CLI/API/测试都能复用同一套错误口径，
    避免不同入口出现「一个允许、一个拒绝」的情况。
    """
    if c.basic_deduction < 0:
        raise ValueError("basic_deduction 不能为负数")

    for name, r in (
        ("pension_rate", c.pension_rate),
        ("medical_rate", c.medical_rate),
        ("unemployment_rate", c.unemployment_rate),
        ("housing_fund_employee_rate", c.housing_fund_employee_rate),
        ("housing_fund_employer_rate", c.housing_fund_employer_rate),
    ):
        if not 0 <= r <= 1:
            raise ValueError(f"{name} 须在 [0, 1] 区间内，当前为 {r}")

    if c.social_security_base_min > 0 and c.social_security_base_limit > 0:
        if c.social_security_base_min > c.social_security_base_limit:
            raise ValueError(
                "社保基数下限不能大于上限："
                f"social_security_base_min={c.social_security_base_min}, "
                f"social_security_base_limit={c.social_security_base_limit}"
            )

    if c.housing_fund_base_min > 0 and c.housing_fund_base_limit > 0:
        if c.housing_fund_base_min > c.housing_fund_base_limit:
            raise ValueError(
                "公积金基数下限不能大于上限："
                f"housing_fund_base_min={c.housing_fund_base_min}, "
                f"housing_fund_base_limit={c.housing_fund_base_limit}"
            )

    for name, v in (
        ("children_education", c.children_education),
        ("continuing_education", c.continuing_education),
        ("serious_illness", c.serious_illness),
        ("housing_loan_interest", c.housing_loan_interest),
        ("housing_rent", c.housing_rent),
        ("elderly_support", c.elderly_support),
        ("annual_additional_deduction", c.annual_additional_deduction),
    ):
        if v < 0:
            raise ValueError(f"{name} 不能为负数，当前为 {v}")


# ---------- 计税 ----------

# 综合所得年度税率表。每个元组为：
# (本档应纳税所得额下界, 上界, 税率, 速算扣除数)。
# _progressive_tax 会使用「应纳税所得额 × 税率 − 速算扣除数」直接得到全年税额。
COMPREHENSIVE_BRACKETS = [
    (0, 36000, 0.03, 0),
    (36000, 144000, 0.10, 2520),
    (144000, 300000, 0.20, 16920),
    (300000, 420000, 0.25, 31920),
    (420000, 660000, 0.30, 52920),
    (660000, 960000, 0.35, 85920),
    (960000, float("inf"), 0.45, 181920),
]

# 年终奖单独计税：月均口径。
# 年终奖政策通常先把全年奖金除以 12 找月度税档；这里保留月度表作为来源数据。
BONUS_BRACKETS_MONTHLY: List[Tuple[float, float, float, float]] = [
    (0, 3000, 0.03, 0),
    (3000, 12000, 0.10, 210),
    (12000, 25000, 0.20, 1410),
    (25000, 35000, 0.25, 2660),
    (35000, 55000, 0.30, 4410),
    (55000, 80000, 0.35, 7160),
    (80000, float("inf"), 0.45, 15160),
]

# 年终奖单独计税：年化口径。
# 注意速算扣除数仍使用月度表中的数值，不乘以 12；税率区间才乘以 12。
BONUS_BRACKETS_ANNUAL: List[Tuple[float, float, float, float]] = [
    (lo * 12, hi * 12, rate, quick) for lo, hi, rate, quick in BONUS_BRACKETS_MONTHLY
]

# 优化器用到的税档断点。
# 当月薪变化时，综合所得和年终奖只会在这些边界附近改变边际税率；
# 因此后面的 TaxOptimizer 可以只检查断点两侧的候选月薪，而不是扫描每一个整数。
# 综合所得应纳税所得额的税档上界列表，用于反解「月薪落在哪里会跨综合所得税档」。
COMPREHENSIVE_TAX_BREAKPOINTS = [
    0.0,
    *[hi for _lo, hi, _rate, _quick in COMPREHENSIVE_BRACKETS if math.isfinite(hi)],
]
# 年终奖税档的年度上界列表，用于反解「月薪变化后年终奖落在哪里会跨税档」。
BONUS_TAX_BREAKPOINTS = [
    0.0,
    *[hi for _lo, hi, _rate, _quick in BONUS_BRACKETS_ANNUAL if math.isfinite(hi)],
]


def _progressive_tax(taxable: float, brackets: List[tuple]) -> float:
    """
    按累进税率表计算税额。

    taxable 是已经扣除基本减除费用、专项附加扣除、三险一金后的应纳税所得额。
    brackets 的速算扣除数已与该 taxable 的口径匹配，因此不需要逐档累加。
    """
    if taxable <= 0:
        return 0.0
    for lo, hi, rate, quick in brackets:
        if lo < taxable <= hi:
            return taxable * rate - quick
    return 0.0


class TaxCalculator:
    """
    给定一个 TaxConfig 后的纯计算器。

    这个类不负责寻找最优拆分，也不处理命令行参数；它只回答：
    - 指定月薪时，每月三险和公积金怎么缴？
    - 指定月薪、年终奖、额外激励时，年度税额是多少？
    - 工资薪金的 12 个月累计预扣明细是什么？
    """

    def __init__(self, config: TaxConfig):
        self.c = config

    def _monthly_special_additional(self) -> float:
        """把按月填写的专项附加扣除合成月度总额。"""
        return (
            self.c.children_education
            + self.c.continuing_education
            + self.c.serious_illness
            + self.c.housing_loan_interest
            + self.c.housing_rent
            + self.c.elderly_support
        )

    def annual_additional_total(self) -> float:
        """全年专项附加扣除总额：月度项目 × 12 + 一次性全年扣除。"""
        return self._monthly_special_additional() * 12 + self.c.annual_additional_deduction

    def monthly_insurance(self, monthly_salary: float) -> Dict[str, float]:
        """
        三险（养老、医疗、失业）个人月度缴纳明细及合计。

        社保基数按「先套上限，再套下限」处理：
        - 上限大于 0 时，工资超过上限也只按上限缴。
        - 下限大于 0 时，工资低于下限也按下限缴。
        """
        base = monthly_salary  # 缴费基数，后续按当地上下限 clamp。
        if self.c.social_security_base_limit > 0:
            base = min(base, self.c.social_security_base_limit)
        if self.c.social_security_base_min > 0:
            base = max(base, self.c.social_security_base_min)
        # 三险各自按同一个社保缴费基数乘以个人比例。
        pension = base * self.c.pension_rate
        medical = base * self.c.medical_rate
        unemployment = base * self.c.unemployment_rate
        return {
            "pension": pension,
            "medical": medical,
            "unemployment": unemployment,
            "total": pension + medical + unemployment,
        }

    def monthly_housing_fund(self, monthly_salary: float) -> Dict[str, float]:
        """
        公积金月度缴存：个人与单位部分。

        公积金基数的上下限逻辑与社保相同，但个人和单位比例可不同。
        """
        base = monthly_salary  # 公积金缴存基数，独立于社保基数上下限。
        if self.c.housing_fund_base_limit > 0:
            base = min(base, self.c.housing_fund_base_limit)
        if self.c.housing_fund_base_min > 0:
            base = max(base, self.c.housing_fund_base_min)
        return {
            "employee": base * self.c.housing_fund_employee_rate,
            "employer": base * self.c.housing_fund_employer_rate,
        }

    def bonus_tax(self, bonus: float) -> float:
        """按年终奖单独计税口径计算一笔奖金/股票激励的税额。"""
        if bonus <= 0:
            return 0.0
        return _progressive_tax(bonus, BONUS_BRACKETS_ANNUAL)

    def _calc_annual_tax(
        self, monthly_salary: float, bonus: float, extra_income: float = 0.0
    ) -> Tuple[float, float, float, float, Dict[str, float], Dict[str, float]]:
        """
        计算年度税额与缴纳金额，单月险费只算一次。

        这个函数是整个模块的年度计算核心：
        - 月薪部分按综合所得累计到全年；
        - extra_income 也并入综合所得；
        - bonus 按年终奖单独计税；
        - 年终奖和股票激励不参与三险一金基数，三险一金只由 monthly_salary 决定。

        extra_income 为额外激励，并入综合所得一起计税。
        返回 (综合所得年税, 年终奖税, 年度个人三险一金合计, 年度公积金个人+公司合计,
              月度三险分项, 月度公积金分项)。
        """
        ins = self.monthly_insurance(monthly_salary)  # 月度个人三险明细。
        hf = self.monthly_housing_fund(monthly_salary)  # 月度个人/单位公积金明细。
        annual_personal_deduction = (ins["total"] + hf["employee"]) * 12  # 年度个人三险一金，用于税前扣除。
        annual_provident_fund_total = (hf["employee"] + hf["employer"]) * 12  # 年度个人+单位公积金入账额。

        # 综合所得应纳税所得额 =
        # 工资薪金全年收入 + 额外激励 - 基本减除费用 - 专项附加扣除 - 个人三险一金。
        # 年终奖不放进这里，因为本模型使用年终奖单独计税。
        taxable = (
            monthly_salary * 12
            + extra_income
            - self.c.basic_deduction
            - self.annual_additional_total()
            - annual_personal_deduction
        )
        comprehensive_tax = _progressive_tax(taxable, COMPREHENSIVE_BRACKETS)  # 工资+额外激励的全年个税。
        bonus_tax = self.bonus_tax(bonus)  # 年终奖单独计税税额。
        return comprehensive_tax, bonus_tax, annual_personal_deduction, annual_provident_fund_total, ins, hf

    def monthly_details(
        self,
        monthly_salary: float,
        ins_monthly: Optional[Dict[str, float]] = None,
        hf_monthly: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        生成工资薪金部分的 12 个月累计预扣明细。

        这里模拟的是工资按月发放时的累计预扣法：每个月先算截至当月的累计应纳税额，
        再减去上月累计税额，得到本月应扣税。额外激励、年终奖、股票激励不拆进月度明细；
        它们在年度汇总层面体现。

        ins_monthly/hf_monthly 可选传入，是为了优化器已经算过最优月薪的缴费明细时避免重复计算。
        """
        ins = ins_monthly if ins_monthly is not None else self.monthly_insurance(monthly_salary)  # 月度三险明细。
        hf = hf_monthly if hf_monthly is not None else self.monthly_housing_fund(monthly_salary)  # 月度公积金明细。
        monthly_personal_deduction = ins["total"] + hf["employee"]  # 三险一金个人月度合计
        add_m = self._monthly_special_additional()  # 每月专项附加扣除合计。
        basic_m = self.c.basic_deduction / 12  # 基本减除费用折算到每月。
        prev_cum_tax = 0.0  # 上月为止已累计预扣的综合所得个税。
        rows: List[Dict[str, Any]] = []  # 返回给 CLI/API/前端的 12 个月明细。

        for month in range(1, 13):
            # 累计预扣法：每个月都用「截至当月累计收入/扣除」重算累计税额。
            # 当月税额 = 本月累计税额 - 上月累计税额。
            cum_income = monthly_salary * month  # 截至当月累计工资收入。
            cum_basic = basic_m * month  # 截至当月累计基本减除费用。
            cum_deduction = monthly_personal_deduction * month  # 截至当月累计个人三险一金扣除。
            cum_add = add_m * month + self.c.annual_additional_deduction  # 截至当月累计专项附加扣除。
            cum_taxable = cum_income - cum_basic - cum_deduction - cum_add  # 截至当月累计应纳税所得额。
            cum_tax = _progressive_tax(cum_taxable, COMPREHENSIVE_BRACKETS)  # 截至当月应累计缴纳的税额。
            month_tax = cum_tax - prev_cum_tax  # 本月应扣税额。
            prev_cum_tax = cum_tax
            rows.append(
                {
                    "month": month,
                    "salary": monthly_salary,
                    "insurance": ins,
                    "housing_fund": hf,
                    "tax": month_tax,
                    "after_tax_salary": monthly_salary - monthly_personal_deduction - month_tax,
                    "after_tax_including_provident_fund": (
                        monthly_salary - monthly_personal_deduction - month_tax
                        + hf["employee"] + hf["employer"]
                    ),
                    "cumulative_taxable_income": cum_taxable,
                    "cumulative_tax": cum_tax,
                }
            )
        return rows


def enrich_result_with_provident_fund(result: Dict[str, Any]) -> None:
    """
    根据 result['annual_provident_fund'] 写入广义到手字段。

    现金到手不包含单位公积金；「现金+公积金」是另一个展示/优化口径，
    所以这里追加字段而不改写 net_take_home。
    """
    apf = float(result["annual_provident_fund"])  # annual provident fund，年度个人+单位公积金总额。
    result["net_take_home_including_provident_fund"] = result["net_take_home"] + apf
    result["salary_take_home_including_provident_fund"] = result["salary_take_home"] + apf


class TaxOptimizer:
    """
    在总收入固定时寻找最优月薪/年终奖拆分。

    朴素做法是从 0 到 total_annual/12 按 step 枚举所有月薪，但高收入时会很慢。
    当前实现利用税率和缴费基数的「分段线性」特征，只枚举可能改变目标函数斜率的断点附近：
    - 社保/公积金基数上下限；
    - 综合所得跨税档位置；
    - 年终奖跨税档位置；
    - 每个断点按 step 对齐后的左右候选值。

    只要目标函数在每个分段内是线性的，最优点就会出现在分段端点或网格端点附近。
    这也是 _candidate_monthly_salaries 可以显著减少搜索量的原因。
    """

    def __init__(self, calc: TaxCalculator):
        self.calc = calc

    @staticmethod
    def _align_floor_to_step(value: float, step: int) -> int:
        """把真实断点向下吸附到 step 网格，作为可枚举的月薪候选值。"""
        if value <= 0:
            return 0
        return int(math.floor((value + 1e-9) / step)) * step

    @staticmethod
    def _align_ceil_to_step(value: float, step: int) -> int:
        """把真实断点向上吸附到 step 网格，避免错过断点右侧的候选值。"""
        if value <= 0:
            return 0
        return int(math.ceil((value - 1e-9) / step)) * step

    @staticmethod
    def _piecewise_component_linear(
        sample_salary: float,
        base_min: float,
        base_limit: float,
        annual_rate: float,
    ) -> Tuple[float, float]:
        """
        在给定的月薪线性区间内，返回 annual_component = slope * salary + intercept。
        该函数用于把社保/公积金 clamp 后的年化个人扣除表示为分段线性函数。

        举例：
        - 工资低于基数下限时，缴费按下限算，annual_component 是常数，slope=0。
        - 工资高于基数上限时，缴费按上限算，也是常数，slope=0。
        - 工资在上下限之间时，缴费随工资线性变化，slope=annual_rate。
        """
        if annual_rate == 0:
            return 0.0, 0.0
        if base_limit > 0 and sample_salary >= base_limit:
            return 0.0, base_limit * annual_rate
        if base_min > 0 and sample_salary <= base_min:
            return 0.0, base_min * annual_rate
        return annual_rate, 0.0

    def _annual_personal_deduction_linear(self, sample_salary: float) -> Tuple[float, float]:
        """
        返回 sample_salary 所在小区间内「年度个人税前扣除」关于月薪的线性表达式：

            annual_personal_deduction = slope * monthly_salary + intercept

        这里的年度个人税前扣除只包含个人三险和个人公积金。它会从综合所得中扣除，
        因而影响 comprehensive taxable income；单位公积金不会降低个税，只影响
        「现金+公积金」展示/优化目标，所以不放进这个函数。

        为什么可以线性化：
        - 社保和公积金缴费基数都按 clamp(monthly_salary, base_min, base_limit) 计算。
        - clamp 函数在每个基数断点之间都是线性的，可能是常数，也可能等于 monthly_salary。
        - 调用方 _candidate_monthly_salaries 已经用 _salary_axis_breakpoints 把月薪轴按
          社保/公积金上下限切开，并传入区间中点 sample_salary。
        - 因此在 sample_salary 所在区间内，个人三险和个人公积金都可以分别写成
          component_slope * monthly_salary + component_intercept。

        返回的 slope/intercept 是两个扣除项的合并结果：
        - slope 表示月薪每增加 1 元，年度个人税前扣除增加多少元。
        - intercept 表示因基数上下限锁定后形成的年度固定扣除额。

        例子：
        - 月薪低于社保下限时，个人三险按下限缴，三险部分 slope=0，intercept=下限*12*三险费率。
        - 月薪在社保上下限之间时，个人三险随月薪变，三险部分 slope=12*三险费率，intercept=0。
        - 月薪高于社保上限时，个人三险按上限缴，三险部分 slope=0，intercept=上限*12*三险费率。
        公积金部分同理，只是使用公积金自己的上下限和个人缴存比例。
        """
        insurance_annual_rate = 12 * (  # 月薪在基数区间内时，个人三险对年扣除额的斜率。
            self.calc.c.pension_rate
            + self.calc.c.medical_rate
            + self.calc.c.unemployment_rate
        )

        # 个人三险年扣除额在当前月薪区间内的线性形式。
        # _piecewise_component_linear 会根据 sample_salary 判断当前区间处于
        # 「低于下限 / 上下限之间 / 高于上限」三种状态中的哪一种。
        insurance_slope, insurance_intercept = self._piecewise_component_linear(
            sample_salary,
            self.calc.c.social_security_base_min,
            self.calc.c.social_security_base_limit,
            insurance_annual_rate,
        )

        # 个人公积金也按相同方式线性化，但使用公积金自己的基数上下限。
        # 注意这里使用 employee_rate；employer_rate 是单位缴存，不属于个人税前扣除。
        housing_fund_slope, housing_fund_intercept = self._piecewise_component_linear(
            sample_salary,
            self.calc.c.housing_fund_base_min,
            self.calc.c.housing_fund_base_limit,
            12 * self.calc.c.housing_fund_employee_rate,
        )

        # 年度个人税前扣除 = 个人三险 + 个人公积金。
        # 两个分段线性函数相加后仍然是线性的，因此直接相加 slope 和 intercept。
        return (
            insurance_slope + housing_fund_slope,
            insurance_intercept + housing_fund_intercept,
        )

    def _salary_axis_breakpoints(self, salary_bonus_pool: float) -> List[float]:
        """
        找出月薪轴上的社保公积金缴费基数断点。

        salary_bonus_pool 是可拆分为月薪和年终奖的收入池，所以月薪理论上不能超过
        salary_bonus_pool / 12。社保/公积金上下限只有落在这个区间内才可能影响最优解。
        """
        cap_real = max(0.0, salary_bonus_pool / 12.0)  # 月薪理论上限：收入池全部发成 12 个月工资。
        thresholds = [0.0, cap_real]  # 候选区间端点，后续再加入缴费基数上下限。
        for value in (
            self.calc.c.social_security_base_min,
            self.calc.c.social_security_base_limit,
            self.calc.c.housing_fund_base_min,
            self.calc.c.housing_fund_base_limit,
        ):  # value 是某一个社保/公积金缴费基数断点。
            if 0 < value < cap_real:
                thresholds.append(float(value))
        return sorted(set(thresholds))

    def _candidate_monthly_salaries(
        self,
        salary_bonus_pool: float,
        step: int,
        extra_income: float = 0.0,
    ) -> List[int]:
        """
        断点搜索候选集：
        1. 社保/公积金基数 clamp 的斜率切换点；
        2. 综合所得应纳税所得额跨税档的反解点；
        3. 年终奖金额跨税档的反解点；
        4. 上述所有真实断点在步长网格上的左右端点。

        返回值是已经按 step 对齐的整数月薪列表。列表会包含 0 和最大可行月薪，
        因此即使没有任何税档/基数断点，也能覆盖纯年终奖和纯月薪两个边界方案。
        """
        if salary_bonus_pool < 0:
            return []

        cap_real = salary_bonus_pool / 12.0  # 不考虑 step 时的真实月薪上限。
        max_monthly_salary = self._align_floor_to_step(cap_real, step)  # step 网格上的最大可行月薪。
        candidates = {0, max_monthly_salary}  # 月薪候选集合，先放入纯年终奖和近似纯月薪边界。

        def add_neighbor_points(point: float) -> None:
            """把一个真实断点转换成 step 网格上的左右候选点。"""
            if point < 0 or point > cap_real + 1e-9:
                return
            for candidate in (  # candidate 是真实断点吸附到 step 网格后的月薪值。
                self._align_floor_to_step(point, step),
                self._align_ceil_to_step(point, step),
            ):
                if 0 <= candidate <= max_monthly_salary:
                    candidates.add(candidate)

        salary_breakpoints = self._salary_axis_breakpoints(salary_bonus_pool)  # 月薪轴上社保公积金缴费基数造成的分段端点。
        for point in salary_breakpoints:
            add_neighbor_points(point)

        base_taxable_intercept = (  # 不含月薪和个人三险一金时，综合所得 taxable 的常数部分。
            extra_income
            - self.calc.c.basic_deduction
            - self.calc.annual_additional_total()
        )
        for lo, hi in zip(salary_breakpoints, salary_breakpoints[1:]):
            if hi - lo <= 1e-9:
                continue
            sample_salary = (lo + hi) / 2  # 当前缴费基数分段内的任意代表点，用来判断斜率。
            deduction_slope, deduction_intercept = self._annual_personal_deduction_linear(sample_salary)
            taxable_slope = 12.0 - deduction_slope  # 月薪每增加 1 元时，综合所得 taxable 增加多少。
            taxable_intercept = base_taxable_intercept - deduction_intercept  # 当前分段内 taxable 的常数项。
            if abs(taxable_slope) <= 1e-12:
                continue

            # 在一个缴费基数分段内：
            #   taxable = taxable_slope * monthly_salary + taxable_intercept
            # 所以每个综合所得税档边界都可以反解出一个月薪断点。
            for boundary in COMPREHENSIVE_TAX_BREAKPOINTS:  # boundary 是综合所得应纳税所得额的税档上界。
                point = (boundary - taxable_intercept) / taxable_slope  # 反解出的跨档月薪。
                if lo - 1e-9 <= point <= hi + 1e-9:
                    add_neighbor_points(point)

        # 年终奖金额 = salary_bonus_pool - monthly_salary * 12。
        # 年终奖跨税档时，同样反解回月薪轴，加入断点左右候选。
        for boundary in BONUS_TAX_BREAKPOINTS:  # boundary 是年终奖金额的税档上界。
            add_neighbor_points((salary_bonus_pool - boundary) / 12.0)  # 反解出的年终奖跨档月薪。

        return sorted(candidates)

    def optimize(
        self,
        total_annual: float,
        step: int = 1,
        objective: str = "cash",
        extra_income: float = 0.0,
        stock_grants: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        返回给定全年名义收入下的最优拆分结果。

        total_annual 是用户看到的全年名义收入总额。进入搜索前会先扣出不能拆分的收入：
        - extra_income：并入综合所得，但不是月薪，也不是年终奖；
        - stock_grants：每笔单独按年终奖方式计税，也不进入月薪/年终奖池。

        剩下的 salary_bonus_pool 才在「月薪×12」与「年终奖」之间分配。
        objective 决定比较候选方案时看现金到手，还是现金到手加个人/单位公积金。
        """
        validate_tax_config(self.calc.c)
        if stock_grants is None:
            stock_grants = []
        if step <= 0:
            raise ValueError(f"遍历步长 step 须为正整数，当前为 {step}")
        if total_annual < 0:
            raise ValueError("全年工资总额不能为负数")
        if extra_income < 0:
            raise ValueError("额外激励不能为负数")
        if any(g < 0 for g in stock_grants):
            raise ValueError("股票激励金额不能为负数")

        stock_grants_total = sum(stock_grants)  # 股票激励总额，单独计税且不进入月薪/年终奖拆分。
        salary_bonus_pool = total_annual - extra_income - stock_grants_total  # 可在月薪和年终奖之间分配的收入池。
        if salary_bonus_pool < -0.01:
            raise ValueError("额外激励与股票激励之和不能超过全年名义收入")
        if salary_bonus_pool < 0:
            # 允许 0.01 元内的浮点误差，但进入搜索时归零，避免出现负年终奖/月薪。
            salary_bonus_pool = 0.0

        best: Optional[Dict[str, Any]] = None  # 当前最优方案，只保存月薪和年终奖，最终统一组装结果。
        best_net = float("-inf")  # 当前最优目标值；cash 模式为现金到手，pf 模式为现金+公积金。
        best_tax_at_net = float("inf")  # 目标值相同时用于稳定排序的最低税额。
        total_stock_tax = sum(self.calc.bonus_tax(g) for g in stock_grants)  # 所有股票激励的单独计税合计。

        use_pf_objective = objective == "cash_plus_provident_fund"  # 是否以现金+个人/单位公积金作为优化目标。

        # 逐个评估断点候选月薪。给定月薪 m 后，年终奖由收入池剩余部分唯一确定。
        for m in self._candidate_monthly_salaries(
            salary_bonus_pool,
            step=step,
            extra_income=extra_income,
        ):
            bonus = salary_bonus_pool - m * 12  # 当前月薪 m 对应的年终奖余额。
            if bonus < 0:
                continue
            comp_tax, bonus_tax, annual_personal_deduction, annual_provident_fund_total, _ins, _hf = (
                self.calc._calc_annual_tax(m, bonus, extra_income)
            )  # 当前拆分下的综合所得税、年终奖税、个人扣除、公积金等年度指标。
            tax = comp_tax + bonus_tax + total_stock_tax  # 当前方案全年总个税。
            net = total_annual - tax - annual_personal_deduction  # 当前方案全年现金到手。
            score = net + annual_provident_fund_total if use_pf_objective else net  # 用于比较优劣的目标值。

            # 主排序看目标值；目标值完全相同则选税额更低的方案，保证结果稳定。
            if score > best_net or (score == best_net and tax < best_tax_at_net):
                best_net = score
                best_tax_at_net = tax
                best = {
                    "monthly_salary": m,
                    "bonus": bonus,
                }

        if not best:
            return {}

        # 复用统一的结果组装函数，确保 optimize 和 calc 两种入口返回字段一致。
        return result_from_salary_bonus_split(
            self.calc,
            salary_bonus_pool,
            best["monthly_salary"],
            best["bonus"],
            extra_income=extra_income,
            stock_grants=stock_grants,
        )


def adaptive_search_step(total_income: float) -> int:
    """
    根据收入规模选择默认搜索步长。

    断点搜索已经很稀疏；这个步长主要决定候选点吸附到多粗的月薪网格。
    例如 2,010,000 元收入会得到 2 元步长，低收入至少使用 1 元步长。
    """
    step = max(1, int(total_income / 1_000_000))  # 默认月薪网格步长，收入越高允许略粗的搜索粒度。
    return step


def result_from_salary_bonus_split(
    calc: TaxCalculator,
    total_annual: float,
    monthly_salary: float,
    bonus: float,
    extra_income: float = 0.0,
    stock_grants: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    已知月薪、年终奖与全年名义收入（月薪×12+年终奖部分），复用计税函数得到结果字典。

    这个函数是「结果字典」的唯一组装点：
    - CLI 打印、FastAPI 返回、网页前端展示都依赖这里的字段；
    - optimize 找到最佳拆分后也会回到这里；
    - calc 模式则直接使用用户给定的 monthly_salary/bonus 进入这里。

    extra_income 并入综合所得计税；stock_grants 中每笔独立按年终奖方式单独计税。
    要求：12*月薪 + 年终奖 ≈ total_annual（允许 0.01 元浮点误差）。
    """
    if stock_grants is None:
        stock_grants = []
    if total_annual < 0:
        raise ValueError("全年收入不能为负数")
    if monthly_salary < 0 or bonus < 0:
        raise ValueError("月薪、年终奖不能为负数")
    if extra_income < 0:
        raise ValueError("额外激励不能为负数")
    if any(g < 0 for g in stock_grants):
        raise ValueError("股票激励金额不能为负数")
    if not math.isclose(monthly_salary * 12 + bonus, total_annual, rel_tol=0, abs_tol=0.01):
        raise ValueError(
            f"拆分不一致：月薪×12 + 年终奖 = {monthly_salary * 12 + bonus:,.2f}，"
            f"与全年收入 {total_annual:,.2f} 不符（允许误差 0.01 元）"
        )

    comp_tax, bonus_tax, annual_personal_deduction, annual_provident_fund_total, ins, hf = (
        calc._calc_annual_tax(monthly_salary, bonus, extra_income)
    )  # 给定拆分下的年度税额、扣除和月度缴费明细。

    stock_grants_tax = [calc.bonus_tax(g) for g in stock_grants]  # 每笔股票激励按年终奖口径单独计税的税额。
    total_stock_tax = sum(stock_grants_tax)  # 股票激励个税合计。

    nominal_income = total_annual + extra_income + sum(stock_grants)  # 对外展示的全年名义收入总额。
    tax = comp_tax + bonus_tax + total_stock_tax  # 综合所得、年终奖、股票激励三类个税合计。
    net = nominal_income - tax - annual_personal_deduction  # 扣除个税和个人三险一金后的现金到手。

    # salary_take_home 只扣综合所得个税和个人三险一金。
    # extra_income 的税已经包含在 comp_tax 里，但 extra_income 本金单独保留在 extra_income 字段；
    # 展示层如需「工资薪金+额外激励到手」会再把 extra_income 加回去。
    salary_take = monthly_salary * 12 - comp_tax - annual_personal_deduction

    # 字段命名尽量保持 API 稳定：已有前端和测试直接读取这些 key。
    out = {
        "monthly_salary": monthly_salary,
        "annual_salary": monthly_salary * 12,
        "bonus": bonus,
        "extra_income": extra_income,
        "stock_grants": stock_grants,
        "stock_grants_tax": stock_grants_tax,
        "total_stock_tax": total_stock_tax,
        "comprehensive_annual_tax": comp_tax,
        "bonus_tax": bonus_tax,
        "total_tax": tax,
        "annual_social_security": annual_personal_deduction,
        "annual_insurance": ins["total"] * 12,
        "annual_housing_fund_employee": hf["employee"] * 12,
        "annual_provident_fund": annual_provident_fund_total,
        "salary_take_home": salary_take,
        "net_take_home": net,
        "nominal_income": nominal_income,
        "effective_tax_rate": tax / nominal_income if nominal_income else 0.0,
        "effective_social_security_rate": annual_personal_deduction / nominal_income if nominal_income else 0.0,
        "effective_burden_rate": (tax + annual_personal_deduction) / nominal_income if nominal_income else 0.0,
        "bonus_after_tax": bonus - bonus_tax,
        "monthly_details": calc.monthly_details(monthly_salary, ins, hf),
    }
    enrich_result_with_provident_fund(out)
    return out


def print_result(
    result: Dict[str, Any],
    total_income: float,
    title: Optional[str] = None,
    *,
    recommend_wording: bool = True,
    optimize_objective: Optional[str] = None,
) -> None:
    """
    把结果字典打印成命令行可读的报告。

    这里不参与计算，只负责展示口径：
    - recommend_wording=True 时使用「推荐月薪/推荐年终奖」，适合 optimize 模式。
    - recommend_wording=False 时使用「月薪/年终奖」，适合 calc 模式。
    - optimize_objective 用来在广义到手目标下调整标题和说明。
    """
    pf_mode = recommend_wording and optimize_objective == "cash_plus_provident_fund"
    default_title = (
        "个人所得税税筹规划结果（目标：全年广义到手最多，含个人与公司公积金）"
        if pf_mode
        else "个人所得税税筹规划结果（目标：全年到手最多）"
    )
    nominal_income = float(result.get("nominal_income", total_income))
    extra_income = float(result.get("extra_income", 0))
    stock_grants = result.get("stock_grants") or []
    stock_grants_tax = result.get("stock_grants_tax") or []
    stock_take_home = sum(stock_grants) - float(result.get("total_stock_tax", 0))
    salary_plus_extra_take_home = float(result.get("salary_take_home", 0)) + extra_income
    annual_insurance = float(result.get("annual_insurance", 0))
    annual_housing_fund_employee = float(result.get("annual_housing_fund_employee", 0))
    tax_plus_insurance_rate = (
        (float(result.get("total_tax", 0)) + annual_insurance) / nominal_income
        if nominal_income else 0.0
    )
    print("=" * 100)
    print(title or default_title)
    print("=" * 100)
    print("\n【收入结构】")
    print(f"全年名义收入: {nominal_income:,.2f} 元")
    prefix_m = "推荐月薪" if recommend_wording else "月薪"
    prefix_b = "推荐年终奖" if recommend_wording else "年终奖"
    print(
        f"{prefix_m}: {result.get('monthly_salary', 0):,.2f} 元/月，"
        f"12个月税前总额: {result.get('annual_salary', 0):,.2f} 元"
    )
    print(f"{prefix_b}: {result.get('bonus', 0):,.2f} 元")
    if extra_income > 0:
        print(f"额外激励（并入综合所得）: {extra_income:,.2f} 元")
    if stock_grants:
        print(
            f"股票激励: 共 {len(stock_grants)} 笔，合计 {sum(stock_grants):,.2f} 元"
        )
    print("-" * 80)
    print("【到手收入】")
    print(
        f"工资薪金部分到手（含额外激励，并扣综合所得个税与个人五险一金）: "
        f"{salary_plus_extra_take_home:,.2f} 元"
    )
    print(
        f"年终奖到手（年终奖 − 年终奖个税）: "
        f"{result.get('bonus_after_tax', 0):,.2f} 元"
    )
    if stock_grants:
        print(f"股票到手（股票激励 − 股票个税）: {stock_take_home:,.2f} 元")
    print(f"全年现金到手（名义收入 − 个税 − 个人五险一金）: {result.get('net_take_home', 0):,.2f} 元")
    apf = float(result.get("annual_provident_fund", 0))
    if apf > 0:
        print(
            f"全年公积金入账（个人+公司，按月×12，年终奖不计）: {apf:,.2f} 元"
        )
        print(
            f"全年到手（现金+公积金）: "
            f"{result.get('net_take_home_including_provident_fund', result.get('net_take_home', 0)):,.2f} 元"
        )
        if pf_mode:
            print("（以「现金+公积金」最大为目标）")
    print("-" * 80)
    print("【社保+个税】")
    print(f"综合所得（工资+额外激励）个税: {result.get('comprehensive_annual_tax', 0):,.2f} 元")
    print(f"年终奖个税: {result.get('bonus_tax', 0):,.2f} 元")
    if stock_grants:
        print(f"股票激励个税合计: {result.get('total_stock_tax', 0):,.2f} 元")
    print(f"全年总税额: {result.get('total_tax', 0):,.2f} 元")
    print(f"全年个人社保（三险）: {annual_insurance:,.2f} 元")
    print(f"全年个人公积金: {annual_housing_fund_employee:,.2f} 元")
    print(f"个税占名义收入: {result.get('effective_tax_rate', 0) * 100:.2f}%")
    print(f"个税+社保占名义收入: {tax_plus_insurance_rate * 100:.2f}%")
    if apf > 0 and nominal_income:
        print(
            f"公积金(个人+公司)占名义收入: {apf / nominal_income * 100:.2f}%"
        )
        ntip = float(result.get("net_take_home_including_provident_fund", 0))
        print(f"（现金+公积金）到手占名义收入: {ntip / nominal_income * 100:.2f}%")

    # 月度明细
    print("\n" + "-" * 100)
    print("【月度明细】")
    print("月度明细（月薪部分）")
    print("-" * 100)
    print(
        f"{'月份':<6} {'月薪':<8} {'个人三险一金':<8} {'公司+个人公积金':<12} "
        f"{'税额':<8} {'税后工资':<12} {'广义税后':<12}"
    )
    print("-" * 100)
    for d in result.get("monthly_details", []):
        ins = d["insurance"]
        hf = d["housing_fund"]
        monthly_personal_deduction = ins["total"] + hf["employee"]  # 三险一金个人月度合计
        pf_total = hf["employee"] + hf["employer"]  # 个人+单位公积金月度合计
        print(
            f"{d['month']:<6} {d['salary']:>6,.2f} "
            f"{monthly_personal_deduction:>14,.2f} {pf_total:>14,.2f} "
            f"{d['tax']:>14,.2f} {d['after_tax_salary']:>12,.2f} "
            f"{d['after_tax_including_provident_fund']:>14,.2f}"
        )

    print("\n" + "-" * 100)
    print("【年终奖明细】")
    print("年终奖明细")
    print("-" * 100)
    bonus = result.get("bonus", 0)
    print(f"年终奖金额: {bonus:,.2f} 元")
    print(f"年终奖税额: {result.get('bonus_tax', 0):,.2f} 元")
    print(f"年终奖税后金额: {result.get('bonus_after_tax', 0):,.2f} 元")

    if stock_grants:
        print("\n" + "-" * 100)
        print("【股票明细】")
        print("股票明细")
        print("-" * 100)
        for i, (g, gt) in enumerate(zip(stock_grants, stock_grants_tax), 1):
            print(
                f"第 {i} 笔: 税前 {g:,.2f} 元，税额 {gt:,.2f} 元，税后 {g - gt:,.2f} 元"
            )

    print("=" * 100)


def _default_config_path() -> Path:
    """默认配置文件路径：与 main.py 同目录的 config.json。"""
    return Path(__file__).resolve().parent / DEFAULT_CONFIG_FILENAME


def _resolve_preset_config_path(slug: str) -> Path:
    """把命令行传入的预设名解析为 presets/<slug>.json 的绝对路径。"""
    stem = slug.strip()
    if stem.endswith(".json"):
        stem = stem[: -len(".json")]
    return (PRESETS_DIR / f"{stem}.json").resolve()


def list_presets() -> None:
    """打印 presets 目录下可用预设名（不含 .json），一行一个。"""
    if not PRESETS_DIR.is_dir():
        print("presets 目录不存在。", file=sys.stderr)
        return
    names = sorted(p.stem for p in PRESETS_DIR.glob("*.json"))
    for name in names:
        print(name)


def main() -> None:
    """
    命令行入口。

    CLI 的职责是把参数翻译成计算调用：
    - optimize：给定全年名义收入，调用 TaxOptimizer 找最优拆分。
    - calc：给定月薪和年终奖，直接计算该方案。
    """
    parser = argparse.ArgumentParser(
        description=(
            "个人所得税：税筹优化或按给定月薪+年终奖计算全年到手（扣个税与个人五险一金）；"
            "optimize 可用 --objective 选择以现金或「现金+公积金」最大为目标。"
        )
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="optimize",
        choices=("optimize", "calc"),
        help=(
            "optimize=遍历最优拆分；calc=月薪+年终奖（默认 optimize）"
        ),
    )
    parser.add_argument(
        "--total",
        "-t",
        type=float,
        default=None,
        help="全年名义收入（工资12个月+年终奖）",
    )
    parser.add_argument(
        "--monthly",
        "-m",
        type=float,
        default=None,
        help="月薪（calc 与 --bonus 同时必填）",
    )
    parser.add_argument(
        "--bonus",
        "-b",
        type=float,
        default=None,
        help="年终奖（calc 与 --monthly 同时必填）",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="optimize 模式下月薪搜索步长；默认按收入自适应",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help=f"TaxConfig 的 JSON 文件路径；与 --preset 同时指定时以本选项为准；"
        f"均未指定时使用程序目录下的 {DEFAULT_CONFIG_FILENAME}",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default=None,
        metavar="省-市",
        help="使用 presets/<省-市>.json（可省略 .json）；见 presets/README.md。与 -c 同时指定时忽略本项",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="列出 presets 下可用预设文件名并退出",
    )
    parser.add_argument(
        "--objective",
        choices=("cash", "cash_plus_provident_fund"),
        default="cash",
        help=(
            "仅 optimize：cash=全年现金到手最大；"
            "cash_plus_provident_fund=现金+全年个人与公司公积金最大"
        ),
    )
    parser.add_argument(
        "--extra-income",
        type=float,
        default=0.0,
        metavar="金额",
        help="额外激励金额，并入综合所得计税（optimize/calc 模式有效）",
    )
    parser.add_argument(
        "--stock-grant",
        type=float,
        action="append",
        default=None,
        dest="stock_grants",
        metavar="金额",
        help="股票激励金额，每笔单独按年终奖方式计税；可多次指定（optimize/calc 模式有效）",
    )
    args = parser.parse_args()
    stock_grants = args.stock_grants or []

    # --list-presets 是一个独立查询动作，不需要读取默认配置。
    if args.list_presets:
        list_presets()
        return

    if args.config and args.preset:
        print(
            "警告：同时指定 -c 与 --preset，将仅使用 -c 指定的配置文件。",
            file=sys.stderr,
        )

    # 配置来源优先级：显式 -c/--config > --preset > 默认 config.json。
    if args.config:
        config_path = Path(args.config).expanduser().resolve()
    elif args.preset:
        config_path = _resolve_preset_config_path(args.preset)
        if not config_path.is_file():
            print(f"未知预设：{args.preset}", file=sys.stderr)
            print(f"预期文件不存在：{config_path}", file=sys.stderr)
            print("可用预设：python main.py --list-presets", file=sys.stderr)
            return
    else:
        config_path = _default_config_path()

    # CLI optimize 未传 --total 时的示例默认值；API 层不会使用这个默认值。
    default_total = 2_010_000

    try:
        config = load_tax_config_from_json(config_path)
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"读取配置失败：{e}", file=sys.stderr)
        return

    print(f"已加载配置：{config_path}", file=sys.stderr)

    try:
        validate_tax_config(config)
    except ValueError as e:
        print(f"配置校验失败：{e}", file=sys.stderr)
        return

    calc = TaxCalculator(config)

    try:
        if args.mode == "optimize":
            total_income = args.total if args.total is not None else default_total
            step = args.step if args.step is not None else adaptive_search_step(total_income)
            print(f"每月工资搜索步长: {step}")
            result = TaxOptimizer(calc).optimize(
                total_income,
                step,
                objective=args.objective,
                extra_income=args.extra_income,
                stock_grants=stock_grants,
            )
            if result:
                print_result(
                    result,
                    total_income,
                    optimize_objective=args.objective,
                )
            else:
                print("未找到优化方案")

        else:  # calc
            # calc 模式不做优化，只校验用户给定拆分并生成同样结构的结果。
            if args.monthly is None or args.bonus is None:
                parser.error("calc 模式需要 --monthly/-m 与 --bonus/-b（全年收入=月薪×12+年终奖）")
            monthly = args.monthly
            bonus = args.bonus
            if monthly < 0 or bonus < 0:
                parser.error("月薪、年终奖不能为负数")
            total_income = monthly * 12 + bonus
            result = result_from_salary_bonus_split(
                calc, total_income, monthly, bonus,
                extra_income=args.extra_income, stock_grants=stock_grants,
            )
            print_result(
                result,
                total_income,
                title="给定月薪与年终奖：全年税后所得（扣个税与五险一金）",
                recommend_wording=False,
            )

    except ValueError as e:
        print(f"计算错误：{e}")


if __name__ == "__main__":
    main()
