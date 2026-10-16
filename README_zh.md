# TIRE

**基于可靠执行的自顶向下公式实例化**

![GitHub](https://img.shields.io/badge/GitHub-TIRE-181717?logo=github)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-TIRE-yellow)
![许可证](https://img.shields.io/badge/license-Apache%202.0-blue.svg)

[English](README.md) | **简体中文**

## 项目简介

TIRE 是一个从可复用物理公式构造物理推理数据的轻量流水线。它将公式转换为可执行程序，生成并运行单元测试，实例化数值参数，生成英文题面和教师解答，最后用独立执行得到的参考答案筛选结果。仓库用于展示可检查的最小数据构造流程。

## 主要特点

- **公式驱动生成**：支持直接输入公式，也支持从原题中提取公式。
- **执行校验**：在 `bubblewrap` 沙箱中运行程序和单测。
- **答案校验蒸馏**：教师模型看不到参考答案，错误、截断和格式不完整的回答会被筛除。
- **简单接口**：各阶段通过普通 Python 字典传递数据，可以独立检查和替换。



## 流程


| 阶段   | 作用                        |
| ---- | ------------------------- |
| 公式   | 提取并筛选物理关系                 |
| 程序   | 生成 Python 计算函数            |
| 单测   | 生成并执行合理测试参数               |
| 参数   | 生成数值及可选扰动                 |
| 参考答案 | 执行函数得到数值目标                |
| 题面   | 生成并规范化英文问题                |
| 蒸馏   | 调用教师模型解题                  |
| 校验   | 提取最后一个 `\\boxed{}` 并与目标比较 |
| 导出   | 输出 JSONL、SFT 和 GRPO 数据    |




## 数据发布

配套的 `TIRE-PHYSICS-2000` 数据与代码分开发布：


| 平台           | 链接                                                                       | 内容            |
| ------------ | ------------------------------------------------------------------------ | ------------- |
| Hugging Face | [ScienceOne-AI/TIRE](https://huggingface.co/datasets/ScienceOne-AI/TIRE) | 2,000 条英文物理问答 |


每条数据有 `question` 和 `answer` 字段。它是整理后的发布子集，不是完整 TIRE-19k 训练集，也不是评测集。

数据采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。可以这样读取：

```python
from datasets import load_dataset

dataset = load_dataset("ScienceOne-AI/TIRE", split="train")
```



## 安装

需要 Python 3.10+、Linux，以及支持用户命名空间的 `bubblewrap`。

```bash
python -m pip install -r requirements.txt
export TIRE_BASE_URL="https://your-endpoint/v1"
export TIRE_API_KEY="YOUR_API_KEY"
```

模型 ID 从 `config.example.json` 读取，请填写服务端支持的模型。当前客户端发送
带有 `enable_thinking: true` 的流式 OpenAI 兼容 Chat Completions 请求，并要求
返回的模型标识与配置中的 ID 一致。未认证的本地服务必须使用字面量
`TIRE_API_KEY=EMPTY`；当前客户端会发送 `Authorization: Bearer EMPTY`。

## 快速开始

示例直接提供电容公式，因此跳过公式提取：

```bash
python pipeline.py \
  --config config.example.json \
  --input examples/formulas.jsonl \
  --output outputs \
  --limit 1
```

输出目录包含通过样本、SFT/GRPO 文件、失败记录和 API 缓存。校验器提取最后一个完整的 `\\boxed{}` 表达式。最终数值答案与程序执行参考答案按 5% 相对误差校验。



## 代码结构

```text
pipeline.py              流水线入口
prompts.py               与附录 C.1 对齐的 prompt
client.py                API、重试和缓存
sandbox.py               隔离执行
steps/                   公式、程序、单测、参数、题面、蒸馏、校验和导出
```



## 许可证

代码使用 [Apache License 2.0](LICENSE)。数据集采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。
上游来源和运行依赖见 `THIRD_PARTY_NOTICES.md`。

## 引用

如果 TIRE 对你的研究有帮助，请引用：

```text
TIRE: Top-Down Formula Instantiation with Reliable Execution for Physics
Problem Synthesis.
```

正式引用格式将在论文公开版本发布后补充。