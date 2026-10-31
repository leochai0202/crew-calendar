# PR #58：全机场主语省略与运行动作校验

基线：`037c79fd74332a4246335d05848376c3cf6f06a8`。继续同一 Draft PR，未修改 main，未触发生产。

**MERGE_READY=false。中英文实际渲染稿仍是 FAILED_SAFE 诊断预览，不能发送或发布。**

## 生成正文的主语省略

规则只在 `chinese_fact_output` / `english_fact_output` 输出层执行。`BilingualFact`、手册原文、原始来源字段、来源页、版本、事实身份、筛选结果不因省略规则改变。

- 中文仅省略明确处于主语位置的“机组/飞行机组”，保留必须、不得、不要、应当、可以及完整条件、数字和动作。“请机组注意”成为“请注意”；长条件“机组在发现引导有疑问时，应当……”成为“在发现引导有疑问时，应当……”。
- 不删除“通知机组”“ATC要求机组”等宾语，不删除“机组的职责”等所有格，不删除 ATC、机务、机场等其他主体。
- typical/history 类保持事件原文主体；责任认定、曾发生事件及含义不明确的事实叙述保留主体，不为省略而抹去责任。
- 英文不留下不完整的 `must/should + verb` 碎句。仅对明确操作要求作语法等价的无人员主语表达：should → recommended，must → mandatory，shall → required；否定、副词、完整操作内容和条件原样保留。
- may 只有在来源明确授权/许可且动词为操作许可行为时才对应 permitted；`may experience`、`may not` 或无可靠许可依据的 may 保留原句，不能把可能性改成许可。
- 后续 they/their/themselves 等可能依赖该主体的句子保留原文，不编造代词先行词。`must have` 等认识判断不当作操作要求改写。

这不是用英语事实模板替代手册内容，也没有重译机场事实。语法前缀之外的动作、限制、风险和运行数据保留来源。

## 原文与实际渲染示例

以下为输出层规则/真实来源的核对，不代表整份稿已通过安全校验。

中文规则正例：

> 机组必须遵守速度限制。 → 必须遵守速度限制。
>
> 机组不得擅自转向五边。 → 不得擅自转向五边。
>
> 机组如未收到ATC许可，不得进入08号跑道。 → 如未收到ATC许可，不得进入08号跑道。

英文规则正例：

> Flight crew must maintain 3000ft. → It is mandatory to maintain 3000ft.
>
> Crews should not accept an unstable approach. → It is recommended not to accept an unstable approach.
>
> When authorized by ATC, crews may use T1. → When authorized by ATC, it is permitted to use T1.

真实渲染片段（中文587页；英文1368页，同一机坪运行记录）：

> 机坪有时给推出开车指令，有时候给推出到位报告指令，注意识别并遵守指令。

> Apron control may issue push-back and start-up clearance, or instruction to report push-back complete. It is required to identify and comply with relevant clearances.

机坪/Apron control 主体仍在；只省略对应操作要求中的机组主体，shall 强度以 required 保留。原始中英文仍可在 audit JSON 的同一 fact ID 下核对。

反例均保留：历史事件中机组的行为/责任；`ATC must issue clearance`；`Maintenance crews must check the engine`；`ATC要求机组保持3000ft`；`The crew may not see the runway`；`The crew must stop. They must notify ATC`。

## 通用配对与动作校验

1. 在原有顺序配对后，对仍空缺的完整英文记录允许进行保守的异序恢复。要求同机场章节内、同类别/阶段、至少两个完整运行锚点及两个概念、否定/义务一致、候选双方唯一，且英文段落未被其他事实占用。任一语种含季节、昼夜、如果/除非及先后时序条件时不进入该恢复路径：数字和名词相同不足以证明条件等价。只返回完整英文来源，不替换已绑定的源冲突，不借同 token 的后续记录，不拆条件父段补造对应。
2. 合成测试证明逆序段落可以恢复，重复中文、已占用英文、错误阶段、改变高度、仅共享一个 token 都不能恢复。
3. 当前重点真实样本没有因这条保守恢复增加新的英文对应，**未宣称剩余 A/B 问题已全部修复**。长条件父记录、无可靠语义锚点、某些无编号和不同排列仍可能保留 gap。
4. 新增通用 takeoff_roll / landing_roll 动作概念。起飞许可、起飞简令或 taxiing 不能证明起飞滑跑；takeoff roll / take-off run / commence takeoff 的可靠等价接受，关键数字和其他程序仍独立严格校验。

## 权威输入和全机场复核

- 20261019 手册未改，SHA256 `e231f10d01fe6379c2d0bfcef821a731033ccfecb1f2797ea66bd67848317cc8`。
- 177 个中文章节、83 个可靠英文入口、82 个中文章节按 ICAO 精确绑定；范围与角色审计重新执行，结构数量未变。此结果不等于全部机场已双语通过。
- 两天实际任务仍只读使用 `26e9391e6053c7223386346f0e90be2dbc5b6644` 的 ICS 复制件，保持与上一轮相同输入；不改生产排班/ICS。
- 包含不同格式的 WIII、ZYTL、ZYCC、ZSNJ、ZSAM 等扩展回归，没有机场/日期/航班专用生产判断。

## 两天真实隔离验收

| 日期 | 上轮自动错误 | 本轮自动错误 | selected实例 | source-backed | gap | 结果 |
|---|---:|---:|---:|---:|---:|---|
| 2026-10-26 | 13 | 14 | 86 | 82 | 4 | FAILED_SAFE |
| 2026-10-28 | 18 | 19 | 93 | 85 | 8 | FAILED_SAFE |

两天都多检出一条已知真实源冲突：中文315页“收到起飞许可后立即开始起飞滑跑”，英文1171页原文却为 `begin taxiing immediately upon receiving the takeoff clearance`。这是加强保护，不是新增错误配对；没有把 taxiing 擅改成 takeoff roll。

26日分类：C=3、D=9、派生parity=2。28日：B=1、C=7、D=10、派生parity=1。重复航班组中的同一来源问题按错误实例统计，并非各自都是独立来源缺陷。

两天 approved override / concept fallback / 生成翻译均0；`.success=false`，新正式输出为0；中英文 dated/latest 四个 last-good 哨兵逐项保持不变。每个不连续航班组都进入双语校验，没有发布半套内容。

## 仍未解决的问题

- **A/B：** ZPLJ 英文章节尚未可靠定位；WIII 部分长条件、进场/滑行父项和异序来源仍不能可靠配对；ZGGG 自动脱波/联系进近的英文含义仍不可靠。没有将解析器空结果当作手册不存在英文。
- **C/D：** OLPAB/OBLAP、速度/距离单位、跑道分配、单发程序、PAPI关联、STAR跑道证实、特殊机位/推出限制缺口、TCAS启停时序、AMBOY程序代号及起飞滑跑/taxiing冲突仍在。逐项源页和原文差异保留，需权威手册对应来源/修订，不能自行翻译或猜改。
- **正文质量：** 人工检查的实际渲染稿仍有来源错误英语和OCR连词等问题。主语规则没有掩盖五边、时序、航路点或数据冲突。不能宣称整份中英文稿已无条件遗漏/数据问题，不具备真实发布条件。

## 完整证据与正文样稿

- [26日逐错表](pr58-round5-20261026-review.md) / [全部候选与源序JSON](pr58-round5-20261026-review.json)。
- [28日逐错表](pr58-round5-20261028-review.md) / [全部候选与源序JSON](pr58-round5-20261028-review.json)。
- [26日真实中英文渲染全文](source-only-manual-audit.md)。
- [28日及额外机场、进离场样稿](source-only-20261028-audit.md)。
- [来源分类及确切页码](pr58-source-issue-rules.json)；[全机场结构扫描](all-manual-chapter-structure.json)。

定向测试、完整 pytest、diff 检查和本次新 HEAD 的两项 CI 最终结果记录在 PR 最新验收段，不复用上一提交的788 passed。

**继续 Draft，不合并、不上线、不触发正式航前、日历、认证或OTP。没有修改 main、ICS、调度或发布基础设施。**
