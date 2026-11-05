# scan_ai_taste.py

中英文 AI 腔静态扫描。只用 Python 标准库（3.8+）；装了 PyYAML 就用它读 `patterns.yaml`，没装则用内置解析器读同一份文件。

这是 lint，不是 AI 检测器：扫描干净不代表写得好，有命中也不代表是 AI 写的。

## 用法

```bash
S=~/.agents/skills/write-docs/scripts/scan_ai_taste.py

python3 $S draft.md                              # 通用规则
python3 $S draft.md --profile all                   # 通用规则与可选画像规则
python3 $S docs/ --profile all                   # 目录，递归扫 .md/.txt/.mdx/.rst/.adoc
pbpaste | python3 $S -                           # 标准输入
python3 $S draft.md --json                       # 机器可读
python3 $S draft.md --show medium                # 只显示 medium 以上
python3 $S draft.md --fail-on medium             # medium 也算失败（CI 严格模式）
python3 $S draft.md --allow 说白了 --allow-file my_voice.txt   # 放行作者自己的用语
python3 $S draft.md --skip-quotes                # 跳过 > 引用块
python3 $S draft.md --no-structure               # 只跑词汇和句式规则
python3 $S corpus/ --ngrams 4 --top 40           # 找跨文件重复的短语（口癖库）
python3 $S --list-rules --profile all            # 列出全部规则
```

输出格式：`文件:行:列: 严重度 规则id 类别: 说明 「命中文本」`，下一行 `->` 是改法。
每个文件头部给出 `units`（中文字数 + 英文词数）、`score/1k`（每千单位加权分，high=5、medium=2、low=1）和 verdict（clean < 3 ≤ light < 8 ≤ moderate < 16 ≤ heavy）。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 没有达到 `--fail-on` 的命中（默认 high） |
| 1 | 至少一处达到 `--fail-on` |
| 2 | 用法错误、文件不存在、规则文件错误 |

## 跳过的内容

front matter、围栏代码块、缩进代码块（不含中文时）、行内代码、URL、链接目标、HTML 注释。
带 `ai-taste-ignore` 的行跳过；`<!-- ai-taste: off -->` 到 `<!-- ai-taste: on -->` 之间跳过（用于反例）。
`raw: true` 的规则（占位符、引用残留）扫描原文，包括代码和链接。

## 规则

id 前缀：Z 中文、E 英文、P 残留、S 结构统计；可选画像规则使用独立 profile。
`escalate_at: n` 表示同一规则在一篇文档中出现 n 次以上时整体升级为 `escalate_to`。这就是「看密度不看单个词」。

结构检查（S 系列）：句长变异系数、段长变异系数、连续「**标签**：」列表、标题/列表 emoji、单句成段比例、连续同开头、标题密度、英文 Title Case。

### 加规则

在 `patterns.yaml` 里追加，格式保持受限 YAML：一行一个 `key: value`，正则用单引号（单引号内 `''` 表示一个 `'`），列表写成 `[a, b]`。

```yaml
  - id: Z99
    pattern: '某个口癖'
    severity: low
    escalate_at: 3
    escalate_to: medium
    category: 个人口癖
    lang: zh
    profiles: [optional]
    message: 说明
    hint: 改法
```

`scope` 可选：`line`（默认）、`heading`（只看标题文本）、`bullet`、`para_start`（段首句，用 match）、`para_end`（段末句，段落至少两句）、`doc_start`。

改完跑自测：

```bash
cd ~/.agents/skills/write-docs/scripts
python3 scan_ai_taste.py samples/ai_zh.md;    echo $?   # 期望 1
python3 scan_ai_taste.py samples/ai_en.md --profile all; echo $?   # 期望 1
python3 scan_ai_taste.py samples/clean_zh.md --profile all; echo $?   # 期望 0
```

## 已知局限

- 只查词汇、句式和简单统计；内容空洞、没有证据这类问题查不出来。
- 「不是 X 而是 Y」在真实纠错时是正常用法，会误报；保留时说得出理由即可。
- 可选画像规则属于启发式，证据强度可能不同；请用 `--ngrams` 在自己的产出上校准。
- 中文分句按标点切分，引号嵌套和省略号可能影响句长统计。
