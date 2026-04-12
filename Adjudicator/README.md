# 🤖 Adjudicator (Agent B) 核心推理模块

这是本项目的“审判长”模块（前身为早期实验性的神经符号模型 `src/model/agents/critic.ts`，现已被完全重构并迁移至本独立目录）。

## 💡 它的职责是什么？
在这个自动阅读 ArXiv 论文的系统中，大多数 RAG 系统只能对文献进行“表面摘要”。但是，**Adjudicator（仲裁官）**专门负责扮演学术界最令人头疼的 “Reviewer 2（审稿人）” 角色。它不致力于总结论文的优点，而是使用批判性思维系统地寻找论文的**逻辑断裂点**和**适用领域的错配**。

当它找到文献的痛点后，它会自动连接本地的 **Pinecone 向量数据库**，寻找其他论文中能够完美弥补该缺陷的 3 条强力破局方案。

## 🏗️ 核心重构与升级迭代 (What's New?)

经历过初代的报错和格式污染后，我们在本模块实现了以下重磅技术突破：

### 1. 放弃手写规则，拥抱 Gemini 原生 Schema 约束
我们彻底弃用了早期臃肿、难以干预的 TypeScript 硬编码抓错规则（Neuro-Symbolic）。
现在通过传递精密的 `ResponseSchema`，我们直接在底层 API 强迫 Gemini 必须生成高度结构化的 JSON，从而实现：
*   **论文逻辑三段论拆解**：提取 `premises` (前提), `processes` (过程), `conclusions` (结论)
*   **深层次图谱匹配短路诊断**：例如诊断出 `Domain Mismatch` 或是推导出的 `Broken Edge` 等致命伤。

### 2. 双子星模型解耦 (Schema vs PlainText)
在之前迭代中，曾经发生过因为强制全量 JSON 输出保护，导致让模型额外输出“推荐短句”时遭到污染直接输出整坨 JSON 乱码的灾难。
**终极解法：**我们使用了一个双层模型请求。
*   `gemini-2.5-pro` (带 Schema 锁)：负责剥离学术外衣进行深层逻辑缺陷侦别。
*   `plainTextModel` (无拘束)：负责为 Pinecone 搜索出的外援文献量身定做 **30字 以内的干练中文人类可读评价**（`recommendation_reason` 字段）。

### 3. 多端自适应分发
Adjudicator 不仅把它的分析写入到了 Supabase 数据库的 `adjudicator_data` 字段供本地 `localhost:3000` 及云端 Cloud Run 调用，其数据流现在还被深度埋点到了：
*   ✅ **NextJS 渲染组件**：在 `PaperDisplay.tsx` 中增加条件式绚丽玫瑰红色 UI 渲染。
*   ✅ **Brevo 每日邮箱投递**：在 `email.ts` 中完成了自适应的纯 HTML 原生编译发送，让你每天早起都能收到高信息密度的前沿战报。

## ⚙️ 目录结构
*   `index.ts` - 主函数入口，包含大双子模型的调用钩子和 Pinecone 查询映射。
*   `schemas.ts` - TypeScript 类型定义及传给 Gemini 的严格 Zod 标准（保障输出 100% 可预测）。

## 🚀 Future To Do's
1. 将这个分析环节无缝整合进批量流水线（注意防范 OOM）
2. 接入更多元维度的 Prompt 体系供用户自由选择（温和模式 / 暴击模式）
