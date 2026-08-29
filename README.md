# sansan-report

> 把一段时间里多份诊断存档，合并成一份带日期、索引、每条都能溯源的可交付 Markdown 报告。

## 这是什么

`sansan-save` 三件套的最后一块：**只做汇总，不做新诊断**。把同一项目下的存档按时间合并、去重、分类，生成一份能发给合伙人、留档复盘、跟外部顾问对账的报告。

## 解决什么问题

- 诊断结论散在一次次对话/存档里，想整体回顾或对外分享得自己拼；
- 需要一份「关注点怎么演进、确认了什么、否决了什么、还差什么、下一步」的完整快照；
- 要保证报告里每句话都能追溯到当时确认过的存档，而不是 AI 现编。

## 怎么工作

收集与路径生成由零依赖脚本 `archive.py` 完成（与 save/restore 同一份、规则一致），语义合并由 Agent 完成：

```bash
A=~/.agents/skills/sansan-report/scripts/archive.py

python3 "$A" collect --json                 # 当前项目全部存档（含正文，按时间正序）
python3 "$A" collect --since 2026-08-01 --json
python3 "$A" collect --slug proj --json
python3 "$A" report-path --json             # 生成 reports/项目/时间戳-项目.md，永不覆盖
```

## 报告结构（六段）

1. 用户主诉的演进（唯一允许简短总结的一段，只描述关注点变化）
2. 已确认的结论（去重、新的在前、被修正的新旧并列标注）
3. 已否决的方向（含否决理由与出处）
4. 当前未解决的问题（进行中的假设 + 从未处理的早期方向）
5. 推荐下一步（一段话，按优先级）
6. 附录：存档索引表（日期/标题/状态/来源/文件）

输出到 `{存档根}/reports/{项目}/{时间戳}-{项目}.md`，**每次新建、绝不覆盖**，可对比不同时点。

## 怎么用

```text
/sansan-report                          # 合并当前项目全部存档
/sansan-report --since 2026-08-01       # 只汇总某天之后
/sansan-report --slug proj-a            # 指定项目
出报告 / 打包 / 给合伙人看的              # 等价于默认命令
```

只有 1 份存档时会先提示「单份无需合并」，你确认后才强制生成；0 份则不生成空报告。

## 边界

- 只生成 Markdown，不主动转 PDF/HTML；
- 存档里的敏感信息原样保留、不脱敏（脱敏在 save 阶段做）；
- 只读当前配置对应的存档目录，不跨目录搜私人文件；
- 除「主诉演进」外不发挥、不补写，所有结论必须有存档出处。

## 配套技能

- `sansan-save`：写入存档；
- `sansan-restore`：恢复/搜索单份存档。

三件套各自带一份相同的 `archive.py`，可独立安装且路径规则一致。报告若要发公众号，可配合 `sansan-wechat-html` 转成微信粘贴版。

## 安装

```bash
npx -y skills add sansan19900801/sansan-report -g --all
```

## 作者与支持

- 作者：sansan（[GitHub 主页](https://github.com/sansan19900801)）
- 如需加入付费答疑群，可扫码或打开[答疑群说明](https://mp.weixin.qq.com/s/3wporFEz1cGNWslmZsgPKw)

![付费答疑群二维码](assets/support-qr.jpg)

## 许可证

MIT
