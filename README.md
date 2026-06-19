# TaxOpt

TaxOpt 是一个个人所得税测算与税筹优化工具。它支持在全年名义收入固定时，优化「月薪 × 12 + 年终奖」拆分，也支持按已知月薪与年终奖直接测算全年到手、个税、社保公积金、年终奖税后、股票激励税后等结果。

> 本项目用于个人学习、测算和方案推演，不构成税务、法律或投资建议。正式申报和薪酬筹划请以官方政策、单位实际申报口径和专业意见为准。

## 1. 使用说明

### 1.1 小程序

小程序适合移动端随手测算，计算逻辑与城市预设已经打包到小程序内，核心计算不依赖服务端。

主要功能：

- `税筹优化`：输入全年名义收入，自动寻找月薪与年终奖拆分方案。
- `收入计算`：输入固定月薪和固定年终奖，测算该方案全年结果。
- 优化目标：支持最大化现金到手，或最大化「现金 + 个人/单位公积金」。
- 其他收入：支持额外激励，并入综合所得；支持多笔股票激励，每笔按年终奖口径单独计税。
- 城市与参数：支持 42 个城市预设，也可以展开并手动修改社保、公积金参数。
- 专项附加扣除：支持子女教育、继续教育、大病医疗、住房贷款利息、住房租金、赡养老人和全年一次性附加扣除。
- 结果页：展示年度指标、分项结果、收入与税额构成、年终奖明细、股票明细、月度明细和趋势图。
- 历史记录：支持保存、恢复、删除历史测算记录。
- 分享导出：当前支持保存结果长图；小程序版不要求 Excel 导出。

使用方式：

1. 打开小程序。
2. 选择 `税筹优化` 或 `收入计算`。
3. 填写收入、城市预设、专项扣除和其他收入。
4. 点击 `开始计算` 查看结果。
5. 需要复用结果时，可从历史记录恢复。

### 1.2 Web

Web 版适合在桌面浏览器中进行较完整的参数录入、结果查看和调试。Web 页面由 FastAPI 服务托管，计算逻辑复用 Python 核心模块。

主要功能：

- 支持 `optimize` 和 `calc` 两种模式。
- 支持城市预设和自定义配置。
- 支持额外激励、股票激励、专项附加扣除。
- 展示年度汇总、月度明细、税额与到手结果。
- 提供 `/api/*` 接口，便于前端或外部系统调用。
- Web/API 服务端保留 Excel 导出接口；小程序端可以不使用该能力。

本地使用：

```bash
pip install -r requirements.txt
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- Web 页面：`http://127.0.0.1:8000/`
- API 文档：`http://127.0.0.1:8000/docs`

### 1.3 命令行

命令行适合快速测算、批量验证和开发调试。入口为 `main.py`。

常用命令：

```bash
# 查看帮助
python main.py --help

# 列出城市预设
python main.py --list-presets

# 使用默认 config.json 做税筹优化
python main.py optimize --total 500000

# 使用城市预设做税筹优化
python main.py --preset jiangsu-suzhou optimize --total 500000

# 优化目标改为“现金 + 公积金”
python main.py --preset zhejiang-hangzhou optimize \
  --total 500000 \
  --objective cash_plus_provident_fund

# 加入额外激励和多笔股票激励
python main.py optimize \
  --total 800000 \
  --extra-income 60000 \
  --stock-grant 30000 \
  --stock-grant 120000

# 固定月薪 + 年终奖测算
python main.py calc --monthly 20000 --bonus 80000

# 使用自定义配置文件
python main.py -c config.local.json calc --monthly 20000 --bonus 80000
```

命令行输出包括收入结构、到手收入、个税与社保公积金、12 个月累计预扣明细、年终奖明细和股票激励明细。

## 2. 部署说明

### 2.1 Python 环境

建议部署和测试时使用项目专用环境，避免污染全局 Python：

```bash
conda create -n TaxOpt python=3.11
conda activate TaxOpt
pip install -r requirements.txt
```

如果本机已经有 `TaxOpt` 环境，可直接：

```bash
conda activate TaxOpt
pip install -r requirements.txt
```

### 2.2 Web/API 服务

开发环境启动：

```bash
conda activate TaxOpt
uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

也可以使用仓库内脚本：

```bash
./start_server.sh
```

生产或服务器环境可使用 Docker Compose：

```bash
cd deploy
docker compose up -d --build
```

当前 Compose 配置包含：

- `taxopt`：FastAPI 应用容器，内部监听 `8000`。
- `nginx`：反向代理容器，监听 `80` 和 `443`，证书目录默认挂载 `/etc/letsencrypt`。

部署工程师需要根据实际域名修改 `deploy/nginx.conf`，并准备 HTTPS 证书。Web/API 若用于公网访问，建议放在反向代理后并启用 HTTPS。

### 2.3 小程序

小程序源码位于 `miniprogram/`，是 UniApp 项目。它不能直接把源码目录作为最终微信小程序产物使用，需要先通过 HBuilderX 编译。

部署/联调流程：

1. 安装 HBuilderX 和微信开发者工具。
2. 用 HBuilderX 打开 `miniprogram/` 目录。
3. 在 HBuilderX 中选择 `运行` 或 `发行` 到 `微信小程序`。
4. HBuilderX 会生成微信小程序产物，常见目录为：

```text
miniprogram/unpackage/dist/dev/mp-weixin/
```

或发行构建目录：

```text
miniprogram/unpackage/dist/build/mp-weixin/
```

5. 打开微信开发者工具，选择 `导入项目`。
6. 项目目录选择 HBuilderX 生成的 `mp-weixin` 产物目录，而不是仓库根目录。
7. AppID 使用项目配置中的 AppID，或替换为自己的小程序 AppID。
8. 编译并预览。

小程序计算和城市预设已离线化，不需要为计算功能配置 request 合法域名，也不需要启动 FastAPI 后端。只有在未来新增远程同步、在线更新、服务端导出等能力时，才需要配置 HTTPS 服务和微信小程序后台合法域名。

### 2.4 命令行部署

命令行不需要启动服务，只需要 Python 环境和配置文件：

```bash
conda activate TaxOpt
python main.py --preset zhejiang-hangzhou optimize --total 500000
```

部署为定时任务或内部脚本时，建议显式指定 `--preset` 或 `-c /absolute/path/to/config.json`，避免因工作目录不同而读取到非预期配置。

## 3. 开发说明

### 3.1 项目结构

| 路径 | 作用 |
| --- | --- |
| `main.py` | Python 核心计算模块与 CLI 入口，包含 `TaxConfig`、`TaxCalculator`、`TaxOptimizer`、结果组装和配置校验 |
| `api.py` | FastAPI 服务，托管 `web/` 静态页面，并提供计算、预设、Excel 导出等接口 |
| `web/` | Web 前端静态页面 |
| `miniprogram/` | UniApp 小程序源码 |
| `miniprogram/utils/tax-core.js` | 小程序本地计算核心，是 `main.py` 的等价 JS 实现 |
| `miniprogram/utils/presets-data.js` | 小程序内置城市预设数据 |
| `miniprogram/utils/api.js` | 小程序本地 API 兼容层，保持 `getPresets`、`getPreset`、`calculate` 调用方式 |
| `presets/` | 42 套城市预设 JSON，命名规则为 `省拼音-市拼音.json` |
| `config.json` | 默认配置文件，未指定 `-c` 或 `--preset` 时由 CLI 使用 |
| `config.example.json` | 配置模板 |
| `tests/` | Python 核心、API、小程序离线一致性测试 |
| `deploy/` | Dockerfile、Docker Compose、Nginx 示例配置 |
| `docs/` | 小程序计划、状态和验收 checklist |

### 3.2 核心模型

核心计算假设：

- 全年名义收入可以包含月薪、年终奖、额外激励和股票激励。
- `optimize` 模式会把可拆分收入池分配到「月薪 × 12」与「年终奖」。
- 额外激励并入综合所得计税，但不参与月薪/年终奖拆分。
- 股票激励按多笔独立奖金处理，每笔使用年终奖单独计税口径。
- 年终奖和股票激励不计入社保、公积金缴费基数。
- 社保、公积金缴费基数按月薪和配置上下限进行 clamp。
- 全年只使用一组固定社保/公积金参数，未建模跨自然年或跨公积金年度的分段基数。

优化目标：

- `cash`：最大化全年现金到手。
- `cash_plus_provident_fund`：最大化全年现金到手 + 个人/单位公积金入账。

### 3.3 配置与预设

配置字段与 `TaxConfig` 对齐。JSON 根节点必须是对象；未知字段会报错；缺失字段使用程序内默认值。

常用配置字段：

| 字段 | 含义 |
| --- | --- |
| `basic_deduction` | 基本减除费用，年口径，通常为 `60000` |
| `social_security_base_min` / `social_security_base_limit` | 社保缴费基数下限/上限，月口径 |
| `pension_rate` / `medical_rate` / `unemployment_rate` | 养老、医疗、失业个人比例 |
| `housing_fund_base_min` / `housing_fund_base_limit` | 公积金缴存基数下限/上限，月口径 |
| `housing_fund_employee_rate` / `housing_fund_employer_rate` | 个人/单位公积金比例 |
| `children_education` | 子女教育专项附加扣除，月口径 |
| `continuing_education` | 继续教育专项附加扣除，月口径 |
| `serious_illness` | 大病医疗等扣除，按填写的月度额度处理 |
| `housing_loan_interest` | 住房贷款利息专项附加扣除，月口径 |
| `housing_rent` | 住房租金专项附加扣除，月口径 |
| `elderly_support` | 赡养老人专项附加扣除，月口径 |
| `annual_additional_deduction` | 全年一次性附加扣除 |

城市预设位于 `presets/`，索引见 `presets/README.md`。小程序端的 `miniprogram/utils/presets-data.js` 由这些 JSON 生成；如果更新 `presets/`，需要同步更新小程序内置数据，并运行一致性测试。

个人敏感配置不要提交到仓库。可使用未入库的 `config.local.json`：

```bash
python main.py -c config.local.json optimize --total 500000
```

### 3.4 数据来源与政策口径

仓库内示例和预设用于测算近似，不保证覆盖各地全部细则。默认示例主要参考：

- 浙江省 2025 年企业职工社会保险缴费基数上下限，杭州执行省定标准。
- 杭州市区 2025 年度住房公积金常见上下限。
- 个人比例按常见养老 8%、医疗 2%、失业 0.5% 以及公积金 5% 到 12% 区间中的示例比例配置。

注意社保和公积金的时间窗口可能不同：社保基数常按自然年调整，公积金基数常按住房公积金年度调整。本工具对全年只使用一组固定参数，跨年或跨 7 月调整节点时请按实际申报口径自行拆分测算。

### 3.5 测试

建议开发前后都在 `TaxOpt` conda 环境中运行测试：

```bash
conda activate TaxOpt
pip install pytest  # 如果当前环境尚未安装
pytest tests/ -q
```

常用测试：

```bash
# 核心算法
pytest tests/test_calculator.py -q

# FastAPI 接口
pytest tests/test_api.py -q

# 小程序 JS 与 Python 核心一致性
pytest tests/test_miniprogram_offline.py -q
```

`tests/test_miniprogram_offline.py` 会用 Node 执行小程序端 JS，并与 Python `main.py` 的输出逐字段比较。修改 `main.py`、`miniprogram/utils/tax-core.js` 或预设数据时，应重点运行这组测试。

### 3.6 开发约定

- Python 核心以 `main.py` 为真相源。
- 小程序端 `tax-core.js` 需要与 `main.py` 保持等价。
- API 返回字段应尽量稳定，因为 Web、小程序、历史记录和测试都会读取这些字段。
- 新增税种、收入类型或结果字段时，需要同步更新 CLI、API、小程序展示和测试。
- 配置文件字段变更时，需要同步更新 `TaxConfig`、预设 JSON、README 和相关测试。
