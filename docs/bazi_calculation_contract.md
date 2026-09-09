# GuanChen 八字排盘计算契约 (Bazi Calculation Contract)

本文档记录 Stage 2 冻结的排盘算法流派与溯源声明，确保所有推演具备确定的上下文。

## 1. 基础依赖 (Library)
- **核心算法库**：`lunar_python`
- **库版本**：
  - Stage 2 当前验证基线：`lunar_python 1.4.8`。
  - 实际运行结果由 Adapter 动态读取 runtime metadata version 并记录。
  - `uv.lock` 负责精确依赖解析与可复现性。

## 2. 输入约定 (Input Convention)
- 传入时间仅视作用户提供的当地民用时 (Gregorian local civil datetime)。
- 秒数固定为 `0`，不参与精度计算。

## 3. 晚子时规则 (Late-Zi Rule)
- 锁定参数：`late_zi_sect = 2`
- 规则：当时间处于 23:00 - 23:59 时，作为“晚子时”，日柱天干地支仍然归属**当天**。

## 4. 起运算法规则 (Yun Rule)
- 锁定参数：`yun_sect = 1`
- 规则：按天数与时辰数折算起运年龄（3天=1年，1天=4个月，1时辰=10天）。
- 性别映射：`Male -> 1`，`Female -> 0`，由计算库推导顺逆。

## 5. 地理位置策略 (Location Policy)
- 出生地仅保存原始文本 (`birth_place_text`) 供前端展示。
- 不进行地理编码 (Geocoding：地址文本 → 经纬度)。
- 不采用真太阳时修正 (`true_solar_time = False`)。

## 6. 大运映射策略 (DaYun Mapping Policy)
- 忽略第三方库输出的大运 `index = 0` (正式起运前的占位符)。
- GuanChen 的大运周期严格从 `index = 1`，且仅收录具备完整干支的对象开始录入。

## 7. 行为基准与测试验证 (Fixture Baseline)
- **Stage 2 验证基线**：锁定在 `lunar_python 1.4.8`。
- 系统包含一组硬编码的 Golden Fixtures（如 2005-12-23 08:37、1988-02-15 23:30 晚子时边界等）。这些用例直接承袭官方 Python Test，用于在未来依赖升级时，第一时间发现底层的“行为漂移 (Behavioral Drift)”。

## 8. 已知上游局限性 (Known Upstream Limitations)
- **巳支藏干顺序争议 (lunar_python Issue #28)**：
  - 当前官方库返回巳支藏干顺序为：`丙、庚、戊`。
  - 社区有反馈理论上应为 `丙、戊、庚`。
- **GuanChen v2.0 决定**：
  - 保持 `lunar_python 1.4.8` 原始返回顺序，不在 Adapter 层偷偷进行重排（Correction）。
  - 不将藏干列表的顺序在业务上解释为主气、中气、余气的权重排序或旺衰等级。
  - 若未来业务需要主气/余气/杂气的显式语义，需重新评估并专门记录架构决策 (ADR)。