# 来源、许可与证据边界

采集与核对日期：2026-09-08。本页不保存学习状态。

## 参考词表及署名

原始词表作者 Jonathan Waller，Tanos JLPT Resources。

- [N3资料与估计方法](https://www.tanos.co.uk/jlpt/jlpt3/)明确说明N3没有官方清单。历史语料频率不能当成当前真题频率。
- [作者许可](https://www.tanos.co.uk/jlpt/sharing/)允许非售卖资料按 Creative Commons BY 使用并署名；该网页未指定版本，本项目不擅自补版本。
- 机器可读来源为 [stephenmk/yomitan-jlpt-vocab](https://github.com/stephenmk/yomitan-jlpt-vocab)，固定提交 `b062d4e38c4bdd0950ae1d4ec55f04b176182e03` 的 `original_data/n3.csv`、`n4.csv`、`n5.csv`。
- 整理者添加了JMdict ID。本库仅用来源提供的ID作索引，未联网核验每个ID的当前状态。镜像与Waller原表属于同一来源链，不能当独立多源计票。
- [上游README原文快照](../tasks/002-vocabulary-library/assets/upstream/README.txt)、[CC-BY-SA-4.0许可原文](../tasks/002-vocabulary-library/assets/upstream/LICENSE.txt)、[固定URL/字节数/哈希](../tasks/002-vocabulary-library/assets/upstream/retrieval.json)均保留。README以txt保存原文，避免将其上游相对链接误认成本项目导航。

本库的词表整理和教师学习释义以CC-BY-SA-4.0共享，署名Jonathan Waller/Tanos、stephenmk及本项目整理工作，保留许可证与改动说明。此声明不为项目中无关文件设定许可证，也不改变官方试卷及第三方内容本身的权利。

## 官方证据

[JLPT FAQ](https://www.jlpt.jp/e/faq/)说明不再发布包含词汇、汉字和语法列表的Test Content Specifications。[官方练习册入口](https://www.jlpt.jp/e/samples/sampleindex.html)说明两册含改革后考试所选题目，不代表历年完整题库。

| 来源 | 已核对目标题号 | PDF物理页 | 印刷页 |
| --- | --- | --- | --- |
| [2012 N3词汇册](https://www.jlpt.jp/samples/sample2012/pdf/N3V.pdf) | 1–14、24–33 | 3、4、6、7 | 5、6、8、9 |
| [2018 N3词汇册](https://www.jlpt.jp/samples/sample2018/pdf/N3V.pdf) | 1–14、26–35 | 3、4、6、7 | 1、2、4、5 |

48个目标来自页面视觉核对，不含干扰选项。词条officialEvidence记录网址、题号、双页码、题型和目标词形。屈折形式/假名归一及中英释义由教师整理，不是官方译文。横断禁止保留为表达，原下划线目标含句尾です。

13个目标未匹配到三张参考表中的相同词形/读音组合，其中也含完整表达；不等于其组成部分全部缺失，也不推断官方级别。未统计历年出现率，未清点两册第3大题、语法、阅读或听力。

[核对说明与PDF来源哈希](../tasks/002-vocabulary-library/assets/official-review.json)可用于重新定位。PDF仅作本地临时审阅，词库不分发完整PDF、题干、选项、答案或截图，只保存词头、必要目标形式和位置事实。

## 数据处理

完整读取三表，保留原始CSV字节。以来源ID整理重复/变体，每个原始行、词形、读音、英文、级别均保留。展示字段只作NFKC和首尾空白处理，不按假名相同合并不同词。

重点词头与读音完全匹配才挂接来源ID；未匹配则建立本地条目，不猜ID或补N3标签。原表英文留作证据，在重点层纠正已发现问题，如数值以上/以下、単語和急/速い。

未完成全库中文翻译和独立词典校审。全量导入不等于全量语言审校；数据数量也不代表学习者能力。
