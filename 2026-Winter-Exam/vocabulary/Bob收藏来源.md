# Bob 收藏来源（只读）

这是你用翻译软件自行查询并收藏的词句来源，与原有 N3/N4/N5 参考词库并列使用。用户于 2026-10-07 授权只读接入，禁止改动 Bob 数据库。

## 本机位置

目录：`~/Library/Containers/com.hezongyidev.Bob/Data/Documents/`

数据库：`bob-core.sqlite`。Finder 中按 **⌘⇧G**，粘贴上面的目录即可打开位置。

[来源配置](bob-source.json) 保存定位与只读约定。2026-10-07 实际查询收藏表 `translate_translate_favorite` 为 **133 条**；这是当次数量，之后运行工具读取实时数量。收藏包含词句，不等于 133 个已学日语单词。

## 查询入口

在项目根目录运行，无额外依赖，不联网：

```bash
python3 tools/bob_favorites.py stats
python3 tools/bob_favorites.py recent --limit 5
python3 tools/bob_favorites.py search '关键词' --limit 10
```

`recent` 按收藏记录 `localId` 从大到小显示；`search` 在原文和第一个翻译服务的译文中作字面子串搜索。返回原文、第一服务译文、服务名、收藏记录 ID 和原始时间字段。保留译文的 Markdown 原格式；不把时间字段猜成时区或学习日期。

原文来自 `queryText`，第一服务译文来自 `resultTuple0` JSON 的 `result.content.text`。第一服务没有结果或格式不支持时，返回空值和提示，不拿别的服务冒充。默认不展示或读取其他服务的译文，也不读取历史表。

数据库以 SQLite `mode=ro` 打开，额外启用 `query_only` 和权限限制；工具只有统计、最近收藏、搜索三种动作，无修改和导出命令。缺少数据库或结构变化时明确报错，不创建替代数据库。

## 教学如何使用

教师可按当前能力从收藏选一个合适的词句，核对译文后用于学习；来源记录为 `bob-favorite-<localId>`。实际教过的内容才进入统一学习索引，真实回应才进入能力观察。

Bob 数据库与整批收藏全文保留在原目录，不复制到项目或 GitHub。项目中的配置、规则和查询工具不包含收藏全文。执行约束见 [只读规则](../../.ai/instructions/bob-source.md)。
