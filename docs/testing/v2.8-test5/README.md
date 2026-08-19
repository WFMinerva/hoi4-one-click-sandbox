# v2.8-test5 实机回归归档

> 轮次：v2.8-test5 ｜ 执行：2026-08-20（维护者实机＋AI 判读归档，半自动分工）｜ 判定：**PASS**

- **版本线**：v2.8-test5（descriptor.mod）；游戏版本 `a729d47bd`（code_revisions.log 绑定，2026-06-29 构建）。
- **测试包 SHA-256**：`e8df5bd4c98b6fae1f484608e7ab551a7fc1ebb8ba7b2c70620767d0524f495d`（修复轮重建，见问题清单①）。
- **判定**：见 `result.json`——check_logs 判读：`[OCS_TEST]`→`OCS_TEST` 标记 50 条＝用例清单 50 且全 PASS；白名单过滤后无新错误签名；text.log 0 字节（无本地化错误）；setup.log PRC_OCS 记录 9 条。
- **存档断言**：check_save 不存在（步骤4 存档断言暂缓，跳过）。
- **逐项清单**：见 `清单.md`（50 用例＋固定序列 7 项全部「通过」，证据＝game.log 标记与 result.json）。
- **问题清单**：
  1. **引擎消费消息串开头的 `[...]` 分组**（首跑实测发现）：`log = "[OCS_TEST] PASS <case>"` 写入 game.log 时 `[OCS_TEST]` 前缀被引擎替换为自己的 `[时间][日期][源]` 前缀，标记字面量丢失 → 判读工具 0 标记判 INVALID。修复：标记改为无方括号 `OCS_TEST PASS/FAIL <case>`（生成器/判读正则/单测/契约/文档同步），复跑验证标记完整存活（`game.log` 01:31:15 共 52 处 OCS_TEST 字面量）。历程见立项文档第九节「实机轮修正」。
  2. **中文存档名保存失败**（首跑实测发现）：`save v2.8test5判定` 的 _temp→正式名 rename 报 errno 2，判定档滞留 `_temp` 名。修复：判定档改名 ASCII `v2.8test5verdict.hoi4`（内容完整），制度与编排提示改为「判定档文件名必须 ASCII」。
  3. **归档脱敏漏正斜杠路径**（首跑 error.log 为证）：`C:/Users/...` 形态未被反斜杠版 USERPROFILE 替换覆盖。修复：`check_logs._redact_identity` 双分隔符覆盖＋`result.json` 的 `logs_dir` 输出即脱敏＋增单测（现 19 项）。
- **例外说明**：截图不适用（自动断言轮）；判定档 `v2.8test5verdict.hoi4` 留本机（二进制不入 git）；首跑日志副本见 `logs_首跑_旧标记格式/`。
- **结论**：本轮 50 用例全 PASS、日志洁净、版本绑定成立——**通过**，机主已签收（2026-08-20）；判定档 `v2.8test5verdict.hoi4` 经机主拍板登记为黄金存档（见 `docs/testing/黄金存档制度.md`）。
