# TaxOpt

**个人所得税税筹与测算（示意工具）**：给定**全年名义收入**（12 个月工资 + 年终奖），在「月薪全年一致、年终奖单独计税、年终奖不计五险一金」等假设下，可**遍历**搜索使**全年到手**最高的拆分（`optimize` 下由 `--objective` 选择优化**现金**或**现金+公积金**），或**固定**月薪/年终奖之一后推算全年到手。

> 税率表与政策时点以代码为准；**不构成税务或法律建议**。

## 项目结构


| 文件                                | 作用                                                                    |
| --------------------------------- | --------------------------------------------------------------------- |
| `main.py`                         | `TaxConfig`、`load_tax_config_from_json`、`validate_tax_config`、计税与 CLI |
| `config.json`                     | **默认**计税参数（与 `main.py` 同目录；未指定 `-c` 时使用）                              |
| `config.example.json`             | 配置模板（当前示例为 **浙江社保 + 杭州市区公积金** 常见 2025 口径，见下文说明）；可复制为 `config.json` 或 `-c` 指定   |
| `presets/`                        | **直辖市 + 一二线城市** 等 **42** 套预设 JSON，命名 **`省拼音-市拼音`**（默认市区口径）；索引见 `presets/README.md`        |


## 环境

- Python 3.8+，**标准库**（`argparse`、`json` 等）。

## 配置文件（JSON）

- **默认路径**：与 `main.py` 同目录下的 `**config.json`**。未传 `-c` 且未传 `--preset` 时自动读取该文件。
- **自定义路径**：`python main.py -c /path/to/my.json ...` 或 `--config`。
- **城市预设**：`python main.py --preset zhejiang-hangzhou ...` 加载 `presets/zhejiang-hangzhou.json`（可省略 `.json`）。`python main.py --list-presets` 列出全部预设名。若**同时**指定 `-c` 与 `--preset`，**仅以 `-c` 为准**（stderr 会提示警告）。杭州区县公积金见 `zhejiang-hangzhou-counties`。
- **规则**：根节点为 JSON 对象；**键名须与 `TaxConfig` 字段完全一致**；**不允许未知字段**（拼写错误会直接报错）；**未写的键**使用程序内 `TaxConfig` 的默认值，并在 **stderr** 输出**警告**列出缺省字段名（建议复制 `config.example.json` 填全）。
- 加载成功后会在 **stderr** 打印一行 `已加载配置：<绝对路径>`，便于确认使用的文件。
- 个人敏感参数可放在未入库的 `config.local.json`（见 `.gitignore`），运行时 `-c config.local.json`。

### 政策时间窗口（社保 vs 公积金）

- **企业职工基本养老保险等（浙江省统一缴费基数）**：上下限多按 **自然年** 调整，例如 2025 年度标准常见表述为 **2025-01-01 起** 执行（以浙人社发〔2025〕52 号等正式文件为准）。
- **杭州住房公积金**：缴存基数上下限多按 **住房公积金年度** 调整，常见为 **当年 7 月 1 日起至次年 6 月 30 日**（以杭州住房公积金管理中心当年通知为准）。
- 因此存在 **自然年与公积金年度不一致**：同一年内可能前半段与后半段适用不同年度的公积金基数文件，而社保基数已按新年执行。本工具对全年只用 **一组固定基数** 近似，**跨年或跨 7 月调整节点**时请以单位实际申报为准，或自行拆分时段（本程序未建模分段基数）。

### 示例配置数值来源（`config.example.json` / 默认 `config.json`）

- **社保基数**：浙江省 2025 年企业职工社会保险缴费基数 **下限 4986 元/月、上限 25299 元/月**（与杭州执行省定标准一致）；个人比例按养老 8%、医疗 2%、失业 0.5% 填写（简化模型，以参保地最新比例为准）。
- **公积金基数**：**杭州市区** 2025 年度常见 **下限 2490 元/月、上限 40694 元/月**；**桐庐、建德、淳安** 下限多为 **2260** 元/月，若适用请改 `housing_fund_base_min`。
- **公积金比例**：`housing_fund_employee_rate` / `housing_fund_employer_rate` 取 **0.12** 仅作演示；个人比例单位多在 **5%–12%** 内选择，公司比例可与个人不同，请按实际修改。若 JSON 未写 `housing_fund_employer_rate`，默认与个人比例相同。

### 字段说明与示例（带注释）

标准 JSON **不支持** `//` 注释，下表对应 `config.json` 里每个键的含义；可复制 `config.example.json` 再改数值。


| 键名                            | 含义                               |
| ----------------------------- | -------------------------------- |
| `basic_deduction`             | 基本减除费用（**年**，通常 60000）           |
| `social_security_base_min`    | 社保缴费基数**下限**（月）；`0` 表示没有下限，下同    |
| `social_security_base_limit`  | 社保缴费基数**上限**（月）；`0` 表示不按上限封顶，下同  |
| `pension_rate`                | 养老保险个人比例，如 `0.08`                |
| `medical_rate`                | 医疗保险个人比例                         |
| `unemployment_rate`           | 失业保险个人比例                         |
| `housing_fund_base_min`       | 公积金缴费基数下限（月）                     |
| `housing_fund_base_limit`     | 公积金缴费基数上限（月）                     |
| `housing_fund_employee_rate`  | 公积金**个人**缴存比例                    |
| `housing_fund_employer_rate`| 公积金**公司**缴存比例；省略时默认等于个人比例       |
| `children_education`          | 子女教育专项附加扣除（**月**）                |
| `continuing_education`        | 继续教育专项附加扣除（**月**）                |
| `serious_illness`             | 大病医疗等（**月**，按你折算的月度额度）           |
| `housing_loan_interest`       | 住房贷款利息专项附加扣除（**月**）              |
| `housing_rent`                | 住房租金专项附加扣除（**月**）                |
| `elderly_support`             | 赡养老人专项附加扣除（**月**）                |
| `annual_additional_deduction` | **全年**一次性附加扣除（如个人养老金。累计预扣从首月全额扣） |


**示例（与仓库内 `config.example.json` 一致，浙江社保 + 杭州市区公积金 2025 常见口径）：**

```json
{
  "basic_deduction": 60000,
  "social_security_base_min": 4986,
  "social_security_base_limit": 25299,
  "pension_rate": 0.08,
  "medical_rate": 0.02,
  "unemployment_rate": 0.005,
  "housing_fund_base_min": 2490,
  "housing_fund_base_limit": 40694,
  "housing_fund_employee_rate": 0.12,
  "housing_fund_employer_rate": 0.12,
  "children_education": 0,
  "continuing_education": 0,
  "serious_illness": 0,
  "housing_loan_interest": 0,
  "housing_rent": 0,
  "elderly_support": 0,
  "annual_additional_deduction": 0
}
```

## 使用方法

1. 编辑 `**config.json**`（或自建 JSON 并用 `-c` 指定）。保存后运行；`**validate_tax_config**` 会在计算前校验（比例区间、基数上下限关系、非负等）。
2. 命令行模式（`python main.py --help` 查看参数）：

```bash
# 指定配置文件（可选；省略则使用程序目录下 config.json）
python main.py -c config.json optimize -t 500000

# 按城市预设（文件名规则：省-市，见 presets/README.md）
python main.py --list-presets
python main.py --preset jiangsu-suzhou both -m 20000 -b 80000

# 税筹：遍历月薪/年终奖（默认；未传 -t 时使用代码内默认全年收入）
python main.py optimize [--total 全年收入]
# 税筹目标为「现金+全年公积金」最大（默认 --objective cash 为纯现金到手最大）
python main.py optimize -t 500000 --objective cash_plus_provident_fund

# 已知全年收入 + 月薪 → 反推年终奖并算全年到手
python main.py salary --total 全年收入 --monthly 月薪

# 已知全年收入 + 年终奖 → 反推月薪并算全年到手
python main.py bonus --total 全年收入 --bonus 年终奖

# 已知月薪 + 年终奖 → 全年名义收入=月薪×12+年终奖，再算全年到手
python main.py both --monthly 月薪 --bonus 年终奖
```

3. 输出税筹结果或测算结果：汇总（到手、税额、五险一金、占比）、**12 个月**明细、年终奖税额与税后。


## 免责声明

本仓库用于个人学习与方案推演，不保证与各地细则完全一致。正式筹划请咨询专业人士并以官方政策为准。