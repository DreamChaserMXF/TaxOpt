"""
个人所得税税筹：给定全年工资总额，遍历月薪/年终奖拆分，使「到手收入」最大
（已扣个税与个人五险一金；年终奖按模型不计五险一金）。

可选：将个人与公司公积金按月缴存合计计入「广义到手」；个人/公司缴存比例可分别配置。
optimize 模式的优化目标由命令行 `--objective` 指定（现金最大或现金+公积金最大）。

命令行：python main.py [-c 配置文件 | --preset 省-市] [optimize|salary|bonus|both] ...
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
    basic_deduction: int = 60000  # 基本减除费用（年，5000/月×12=60000）

    social_security_base_min: float = 0  # 社保缴费基数下限（月，0 表示不启用下限）
    social_security_base_limit: float = 0  # 社保缴费基数上限（月，0 表示不启用上限）
    pension_rate: float = 0.08  # 养老保险个人比例
    medical_rate: float = 0.02  # 医疗保险个人比例
    unemployment_rate: float = 0.005  # 失业保险个人比例

    housing_fund_base_min: float = 0  # 公积金缴费基数下限（月）
    housing_fund_base_limit: float = 0  # 公积金缴费基数上限（月）
    housing_fund_employee_rate: float = 0.12  # 公积金个人缴存比例
    housing_fund_employer_rate: float = 0.12  # 公积金公司缴存比例（JSON 未写时默认与个人相同）

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

    if "housing_fund_employer_rate" not in raw:
        kwargs["housing_fund_employer_rate"] = kwargs["housing_fund_employee_rate"]

    try:
        return TaxConfig(**kwargs)
    except TypeError as e:
        raise ValueError(f"配置字段类型与 TaxConfig 不符：{e}") from e


def validate_tax_config(c: TaxConfig) -> None:
    """配置不合法时抛出 ValueError，不进行税筹计算。"""
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

COMPREHENSIVE_BRACKETS = [
    (0, 36000, 0.03, 0),
    (36000, 144000, 0.10, 2520),
    (144000, 300000, 0.20, 16920),
    (300000, 420000, 0.25, 31920),
    (420000, 660000, 0.30, 52920),
    (660000, 960000, 0.35, 85920),
    (960000, float("inf"), 0.45, 181920),
]

# 年终奖单独计税：月均口径
BONUS_BRACKETS_MONTHLY: List[Tuple[float, float, float, float]] = [
    (0, 3000, 0.03, 0),
    (3000, 12000, 0.10, 210),
    (12000, 25000, 0.20, 1410),
    (25000, 35000, 0.25, 2660),
    (35000, 55000, 0.30, 4410),
    (55000, 80000, 0.35, 7160),
    (80000, float("inf"), 0.45, 15160),
]

# 年终奖单独计税：年均口径。速算扣除数要使用每月的口径做全年扣除
BONUS_BRACKETS_ANNUAL: List[Tuple[float, float, float, float]] = [
    (lo * 12, hi * 12, rate, quick) for lo, hi, rate, quick in BONUS_BRACKETS_MONTHLY
]


def _progressive_tax(taxable: float, brackets: List[tuple]) -> float:
    if taxable <= 0:
        return 0.0
    for lo, hi, rate, quick in brackets:
        if lo < taxable <= hi:
            return taxable * rate - quick
    return 0.0


class TaxCalculator:
    def __init__(self, config: TaxConfig):
        self.c = config

    def _monthly_special_additional(self) -> float:
        return (
            self.c.children_education
            + self.c.continuing_education
            + self.c.serious_illness
            + self.c.housing_loan_interest
            + self.c.housing_rent
            + self.c.elderly_support
        )

    def annual_additional_total(self) -> float:
        return self._monthly_special_additional() * 12 + self.c.annual_additional_deduction

    def monthly_social_security(self, monthly_salary: float) -> Dict[str, float]:
        s = monthly_salary
        social = s
        if self.c.social_security_base_limit > 0:
            social = min(social, self.c.social_security_base_limit)
        if self.c.social_security_base_min > 0:
            social = max(social, self.c.social_security_base_min)

        housing = s
        if self.c.housing_fund_base_limit > 0:
            housing = min(housing, self.c.housing_fund_base_limit)
        if self.c.housing_fund_base_min > 0:
            housing = max(housing, self.c.housing_fund_base_min)

        pension = social * self.c.pension_rate
        medical = social * self.c.medical_rate
        unemployment = social * self.c.unemployment_rate
        fund_e = housing * self.c.housing_fund_employee_rate
        fund_u = housing * self.c.housing_fund_employer_rate
        total = pension + medical + unemployment + fund_e
        return {
            "pension": pension,
            "medical": medical,
            "unemployment": unemployment,
            "housing_fund_employee": fund_e,
            "housing_fund_employer": fund_u,
            "total": total,
        }

    def annual_social_security_total(self, monthly_salary: float) -> float:
        return self.monthly_social_security(monthly_salary)["total"] * 12



    def bonus_tax(self, bonus: float) -> float:
        if bonus <= 0:
            return 0.0
        return _progressive_tax(bonus, BONUS_BRACKETS_ANNUAL)

    def total_tax_and_social_security(
        self, monthly_salary: float, bonus: float
    ) -> Tuple[float, float, float, float, Dict[str, float]]:
        """
        单月 monthly_social_security 只算一次。
        返回 (综合所得年度个税, 年终奖个税, 全年个人五险一金, 全年个人+公司公积金, 单月五险一金分项)。
        """
        ss = self.monthly_social_security(monthly_salary)
        annual_social_security = ss["total"] * 12
        annual_pf = 12 * (ss["housing_fund_employee"] + ss["housing_fund_employer"])
        annual_salary = monthly_salary * 12
        additional = self.annual_additional_total()
        taxable = annual_salary - self.c.basic_deduction - additional - annual_social_security
        comprehensive_tax = _progressive_tax(taxable, COMPREHENSIVE_BRACKETS)
        b_tax = self.bonus_tax(bonus)
        return comprehensive_tax, b_tax, annual_social_security, annual_pf, ss

    def monthly_details(
        self, monthly_salary: float, ss_monthly: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        ss = ss_monthly if ss_monthly is not None else self.monthly_social_security(monthly_salary)
        ss_m = ss["total"]
        add_m = self._monthly_special_additional()
        basic_m = self.c.basic_deduction / 12
        prev_cum_tax = 0.0
        rows: List[Dict[str, Any]] = []

        for month in range(1, 13):
            cum_income = monthly_salary * month
            cum_basic = basic_m * month
            cum_ss = ss_m * month
            cum_add = add_m * month + self.c.annual_additional_deduction
            cum_taxable = cum_income - cum_basic - cum_ss - cum_add
            cum_tax = _progressive_tax(cum_taxable, COMPREHENSIVE_BRACKETS)
            month_tax = cum_tax - prev_cum_tax
            prev_cum_tax = cum_tax
            rows.append(
                {
                    "month": month,
                    "salary": monthly_salary,
                    "social_security": ss,
                    "tax": month_tax,
                    "after_tax_salary": monthly_salary - ss_m - month_tax,
                    "after_tax_including_provident_fund": monthly_salary
                    - ss_m
                    - month_tax
                    + ss["housing_fund_employee"]
                    + ss["housing_fund_employer"],
                    "cumulative_taxable_income": cum_taxable,
                    "cumulative_tax": cum_tax,
                }
            )
        return rows


def enrich_result_with_provident_fund(result: Dict[str, Any]) -> None:
    """根据 result['annual_provident_fund'] 写入广义到手字段（不改变个税与现金到手）。"""
    apf = float(result["annual_provident_fund"])
    result["net_take_home_including_provident_fund"] = result["net_take_home"] + apf
    result["salary_take_home_including_provident_fund"] = result["salary_take_home"] + apf


class TaxOptimizer:
    def __init__(self, calc: TaxCalculator):
        self.calc = calc

    def optimize(
        self, total_annual: float, step: int = 1, objective: str = "cash"
    ) -> Dict[str, Any]:
        validate_tax_config(self.calc.c)
        if step <= 0:
            raise ValueError(f"遍历步长 step 须为正整数，当前为 {step}")
        if total_annual < 0:
            raise ValueError("全年工资总额不能为负数")

        best: Optional[Dict[str, Any]] = None
        best_net = float("-inf")
        best_tax_at_net = float("inf")
        cap = int(total_annual // 12)

        use_pf_objective = objective == "cash_plus_provident_fund"

        for m in range(0, cap + 1, step):
            bonus = total_annual - m * 12
            if bonus < 0:
                continue
            comp_tax, b_tax, annual_ss, annual_pf, _ss = self.calc.total_tax_and_social_security(
                m, bonus
            )
            tax = comp_tax + b_tax
            net = total_annual - tax - annual_ss
            salary_take = m * 12 - comp_tax - annual_ss
            score = net + annual_pf if use_pf_objective else net
            if score > best_net or (score == best_net and tax < best_tax_at_net):
                best_net = score
                best_tax_at_net = tax
                best = {
                    "monthly_salary": m,
                    "annual_salary": m * 12,
                    "bonus": bonus,
                    "comprehensive_annual_tax": comp_tax,
                    "bonus_tax": b_tax,
                    "total_tax": tax,
                    "annual_social_security": annual_ss,
                    "annual_provident_fund": annual_pf,
                    "salary_take_home": salary_take,
                    "net_take_home": net,
                    "effective_tax_rate": tax / total_annual if total_annual else 0.0,
                    "effective_social_security_rate": annual_ss / total_annual if total_annual else 0.0,
                    "effective_burden_rate": (tax + annual_ss) / total_annual if total_annual else 0.0,
                }

        if not best:
            return {}

        enrich_result_with_provident_fund(best)
        b = best["bonus"]
        best["monthly_details"] = self.calc.monthly_details(best["monthly_salary"])
        best["bonus_after_tax"] = b - best["bonus_tax"]
        return best

def adaptive_search_step(total_income: float) -> int:
    step = max(1, int(total_income / 1_000_000))
    return step


def result_from_salary_bonus_split(
    calc: TaxCalculator,
    total_annual: float,
    monthly_salary: float,
    bonus: float,
) -> Dict[str, Any]:
    """
    已知月薪、年终奖与全年名义收入，复用计税函数得到与 optimize 相同结构的结果字典。
    要求：12*月薪 + 年终奖 ≈ 全年收入（允许 0.01 元浮点误差）。
    """
    if total_annual < 0:
        raise ValueError("全年收入不能为负数")
    if monthly_salary < 0 or bonus < 0:
        raise ValueError("月薪、年终奖不能为负数")
    if not math.isclose(monthly_salary * 12 + bonus, total_annual, rel_tol=0, abs_tol=0.01):
        raise ValueError(
            f"拆分不一致：月薪×12 + 年终奖 = {monthly_salary * 12 + bonus:,.2f}，"
            f"与全年收入 {total_annual:,.2f} 不符（允许误差 0.01 元）"
        )

    comp_tax, b_tax, annual_ss, annual_pf, ss = calc.total_tax_and_social_security(
        monthly_salary, bonus
    )
    tax = comp_tax + b_tax
    net = total_annual - tax - annual_ss
    salary_take = monthly_salary * 12 - comp_tax - annual_ss
    out = {
        "monthly_salary": monthly_salary,
        "annual_salary": monthly_salary * 12,
        "bonus": bonus,
        "comprehensive_annual_tax": comp_tax,
        "bonus_tax": b_tax,
        "total_tax": tax,
        "annual_social_security": annual_ss,
        "annual_provident_fund": annual_pf,
        "salary_take_home": salary_take,
        "net_take_home": net,
        "effective_tax_rate": tax / total_annual if total_annual else 0.0,
        "effective_social_security_rate": annual_ss / total_annual if total_annual else 0.0,
        "effective_burden_rate": (tax + annual_ss) / total_annual if total_annual else 0.0,
        "bonus_after_tax": bonus - b_tax,
        "monthly_details": calc.monthly_details(monthly_salary, ss),
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
    pf_mode = recommend_wording and optimize_objective == "cash_plus_provident_fund"
    default_title = (
        "个人所得税税筹规划结果（目标：全年广义到手最多，含个人与公司公积金）"
        if pf_mode
        else "个人所得税税筹规划结果（目标：全年到手最多）"
    )
    print("=" * 100)
    print(title or default_title)
    print("=" * 100)
    # 月薪、年终分配详情
    print(f"\n全年工资总额: {total_income:,.2f} 元")
    prefix_m = "推荐月薪" if recommend_wording else "月薪"
    prefix_b = "推荐年终奖" if recommend_wording else "年终奖"
    print(
        f"{prefix_m}: {result.get('monthly_salary', 0):,.2f} 元/月，"
        f"12个月税前总额: {result.get('annual_salary', 0):,.2f} 元"
    )
    print(f"{prefix_b}: {result.get('bonus', 0):,.2f} 元")
    print("-" * 80)
    # 工资和年终奖到手收入
    print(
        f"工资薪金部分到手（12个月税前 − 综合所得个税 − 全年个人五险一金）: "
        f"{result.get('salary_take_home', 0):,.2f} 元"
    )
    print(
        f"年终奖到手（年终奖 − 年终奖个税）: "
        f"{result.get('bonus_after_tax', 0):,.2f} 元"
    )
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
    # 税额
    print(f"综合所得（工资薪金）个税: {result.get('comprehensive_annual_tax', 0):,.2f} 元")
    print(f"年终奖个税: {result.get('bonus_tax', 0):,.2f} 元")
    print(f"全年总税额: {result.get('total_tax', 0):,.2f} 元")
    print(f"全年个人五险一金: {result.get('annual_social_security', 0):,.2f} 元")
    print(f"个税占名义收入: {result.get('effective_tax_rate', 0) * 100:.2f}%")
    print(f"个人五险一金占名义收入: {result.get('effective_social_security_rate', 0) * 100:.2f}%")
    print(f"个税+个人五险一金占名义收入: {result.get('effective_burden_rate', 0) * 100:.2f}%")
    if apf > 0 and total_income:
        print(
            f"公积金(个人+公司)占名义收入: {apf / total_income * 100:.2f}%"
        )
        ntip = float(result.get("net_take_home_including_provident_fund", 0))
        print(f"（现金+公积金）到手占名义收入: {ntip / total_income * 100:.2f}%")

    # 月度明细
    print("\n" + "-" * 100)
    print("月度明细")
    print("-" * 100)
    print(
        f"{'月份':<6} {'月薪':<8} {'个人三险一金':<8} {'公司+个人公积金':<12} "
        f"{'税额':<8} {'税后工资':<12} {'广义税后':<12}"
    )
    print("-" * 100)
    for d in result.get("monthly_details", []):
        ss = d["social_security"]
        pf_pc = ss["housing_fund_employee"] + ss["housing_fund_employer"]
        print(
            f"{d['month']:<6} {d['salary']:>6,.2f} "
            f"{ss['total']:>14,.2f} {pf_pc:>14,.2f} "
            f"{d['tax']:>14,.2f} {d['after_tax_salary']:>12,.2f} "
            f"{d['after_tax_including_provident_fund']:>14,.2f}"
        )

    print("\n" + "-" * 100)
    print("年终奖明细")
    print("-" * 100)
    bonus = result.get("bonus", 0)
    print(f"年终奖金额: {bonus:,.2f} 元")
    print(f"年终奖税额: {result.get('bonus_tax', 0):,.2f} 元")
    print(f"年终奖税后金额: {result.get('bonus_after_tax', 0):,.2f} 元")

    print("=" * 100)


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent / DEFAULT_CONFIG_FILENAME


def _resolve_preset_config_path(slug: str) -> Path:
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
    parser = argparse.ArgumentParser(
        description=(
            "个人所得税：税筹优化或按给定拆分计算全年到手（扣个税与个人五险一金）；"
            "optimize 可用 --objective 选择以现金或「现金+公积金」最大为目标。"
        )
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="optimize",
        choices=("optimize", "salary", "bonus", "both"),
        help=(
            "optimize=遍历最优拆分；salary=全年+月薪；bonus=全年+年终奖；"
            "both=月薪+年终奖（默认 optimize）"
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
        help="月薪（salary 必填；both 与 --bonus 同时必填）",
    )
    parser.add_argument(
        "--bonus",
        "-b",
        type=float,
        default=None,
        help="年终奖（bonus 必填；both 与 --monthly 同时必填）",
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
    args = parser.parse_args()

    if args.list_presets:
        list_presets()
        return

    if args.config and args.preset:
        print(
            "警告：同时指定 -c 与 --preset，将仅使用 -c 指定的配置文件。",
            file=sys.stderr,
        )

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
            result = TaxOptimizer(calc).optimize(total_income, step, objective=args.objective)
            if result:
                print_result(
                    result,
                    total_income,
                    optimize_objective=args.objective,
                )
            else:
                print("未找到优化方案")

        elif args.mode == "salary":
            if args.total is None or args.monthly is None:
                parser.error("salary 模式需要 --total/-t 与 --monthly/-m")
            total_income = args.total
            monthly = args.monthly
            bonus = total_income - monthly * 12
            if bonus < -0.01:
                parser.error("月薪×12 超过全年收入，无法拆分")
            if bonus < 0:
                bonus = 0.0  # 浮点误差范围内视为 0 年终奖
            result = result_from_salary_bonus_split(calc, total_income, monthly, bonus)
            print_result(
                result,
                total_income,
                title="给定全年收入与月薪：全年税后所得（扣个税与五险一金）",
                recommend_wording=False,
            )

        elif args.mode == "bonus":
            if args.total is None or args.bonus is None:
                parser.error("bonus 模式需要 --total/-t 与 --bonus/-b")
            total_income = args.total
            bonus = args.bonus
            monthly = (total_income - bonus) / 12.0
            if monthly < -0.01:
                parser.error("年终奖超过全年收入，无法拆分")
            if monthly < 0:
                monthly = 0.0  # 浮点误差范围内视为无月薪部分
            result = result_from_salary_bonus_split(calc, total_income, monthly, bonus)
            print_result(
                result,
                total_income,
                title="给定全年收入与年终奖：全年税后所得（扣个税与五险一金）",
                recommend_wording=False,
            )

        else:  # both
            if args.monthly is None or args.bonus is None:
                parser.error("both 模式需要 --monthly/-m 与 --bonus/-b（全年收入=月薪×12+年终奖）")
            monthly = args.monthly
            bonus = args.bonus
            if monthly < 0 or bonus < 0:
                parser.error("月薪、年终奖不能为负数")
            total_income = monthly * 12 + bonus
            result = result_from_salary_bonus_split(calc, total_income, monthly, bonus)
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
