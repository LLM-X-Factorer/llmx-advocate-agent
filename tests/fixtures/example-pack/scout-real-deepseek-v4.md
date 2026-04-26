---
schema_version: '1.0'
pack_id: reddit-2026-04-26-1sw3stb
created_at: '2026-04-26T14:33:52.020169Z'
created_by: llmx-scout-agent@0.1.0
source:
  platform: reddit
  primary_url: https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/
  original_url: https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/
  title: llama.cpp DeepSeek v4 Flash experimental inference
  author: antirez
  published_at: '2026-04-26T10:20:32Z'
  language: en
metrics:
  hn_score: null
  hn_comments: null
  github_stars: null
  github_stars_today: null
  reddit_upvotes: 25
  reddit_comments: 27
  x_likes: null
  x_reposts: null
scout_analysis:
  matched_keywords:
  - Llama
  - DeepSeek
  - Qwen
  - inference
  llm_score: 7.7
  llm_reasoning: 作者把 2-bit MoE 跑上高端消费机包装成『可用』，但量化策略（路由 2-bit + 共享 Q8）暴露了『算力省下却被 KV
    与路由吃掉』的二阶事实；评论区对内存需求与速度的撕裂让争议成立，且 repo + GGUF 提供复现素材，适合做深度拆解而非事件搬运。
  judgment_seed: 表面是『128GB 跑 2-bit MoE 进消费级可行区』的硬件胜利，但其实是在暴露『稀疏化红利正在撞上内存墙，量化收益被 KV
    Cache 与路由开销吃掉』的架构真相。
  suggested_layer: 留存层
  controversy_signals:
  - type: counterintuitive_data
    evidence: 2-bit 量化路由专家后仍声称强于 Qwen-3.6-27B，与『越大量化越弱』的直觉相悖；评论区对 86GB vs 128GB 的分歧显示对『可行区』定义存在争议
    url: https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/
  - type: practical_contradiction
    evidence: 作者『17 t/s 在 M3 Max 可用』与评论『Blackwell 6000 才能稳』形成设备层级错位，揭示理论吞吐与用户体验的断层
    url: https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/
  notes: null
harvest:
  harvested_at: '2026-04-26T14:33:52.020169Z'
  fulltext_extracted: true
  fulltext_method: api
  fulltext_external_file: null
  comments_count_fetched: 5
  warnings: []
---

# llama.cpp DeepSeek v4 Flash experimental inference

## 来源元信息

- **平台**：reddit（[primary](https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/)）
- **原文**：https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/
- **作者**：antirez · 2026-04-26
- **热度**：reddit upvotes 25, reddit comments 27

## Scout 的预判

> ⚠️ 以下为 scout 阶段的初步判断，下游 advocate-agent 应当校验、深化或推翻，不可直接采用。

**判断种子**：表面是『128GB 跑 2-bit MoE 进消费级可行区』的硬件胜利，但其实是在暴露『稀疏化红利正在撞上内存墙，量化收益被 KV Cache 与路由开销吃掉』的架构真相。

**建议层级**：留存层

**争议信号**：
- counterintuitive_data：2-bit 量化路由专家后仍声称强于 Qwen-3.6-27B，与『越大量化越弱』的直觉相悖；评论区对 86GB vs 128GB 的分歧显示对『可行区』定义存在争议（[来源](https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/)）
- practical_contradiction：作者『17 t/s 在 M3 Max 可用』与评论『Blackwell 6000 才能稳』形成设备层级错位，揭示理论吞吐与用户体验的断层（[来源](https://reddit.com/r/LocalLLaMA/comments/1sw3stb/llamacpp_deepseek_v4_flash_experimental_inference/)）

## 原文正文

Hi, [here you can find](https://github.com/antirez/llama.cpp-deepseek-v4-flash) experimental llama.cpp support for DeepSeek v4, and [here](https://huggingface.co/antirez/deepseek-v4-gguf) there is the GGUF you can use to run the inference with "just" (lol) 128GB of RAM. The model, even quantized at 2 bit, looks very solid in my limited testing, and the speed of 17 t/s in my MacBook M3 Max is quite interesting, I would say we are into the usable zone.

What I did was to heavily quantize the routed experts to 2 bits using two different 2 bit quants to balance error and size. All the rest of the model, including the shared expert for each layer, is Q8: it is not worth it to play with the most sensible parts of the model if the bulk of the weights are in the routed experts.

I have the feeling that even 2 bit quantized this will prove to be a stronger model than Qwen 3.6 27B, but this is only a feeling based on the quality of the replies I get chatting with it. There is to experiment more and run benchmarks.

**EDIT** sorry for the CMake error, I produced the GGUF using a tool that I decided not to ship (not ready for prime time..., mostly a hack) instead of using the standard quantizer of llama.cpp. Now the problem is fixed. Also the inference in Metal is now 21 token/sec after some optimization.

**EDIT2** also fixed the long context bug.

## 评论区精华

### @antirez（3 分）

For the first time, even with this selective 2 bit quantization, I feel like I have a frontier model running on my computer. The quality of the replies is incredible, and its mental order, the fact that it thinks the right amount of time based on the question complexity. The language used. Incredibly cool.

### @Monkey_1505（2 分）

Huh, 86gb. Could run that entirely on a blackwell 6000 and get solid speeds at near full context.  Mind you it's  a13b so you probably could offload some of the expert to CPU instead, and use a slightly higher quant. 

Interesting. I didn't think it would fit this small.

### @LegacyRemaster（2 分）

CMake Error at tools/CMakeLists.txt:22 (add\_subdirectory):

  add\_subdirectory given source "deepseek4-quantize" which is not an existing

  directory.

\---------- added dir---------&gt;  



CMake Error at tools/CMakeLists.txt:22 (add\_subdirectory):

  The source directory

C:/llm/llama.cpp-deepseek-v4-flash/tools/deepseek4-quantize

  does not contain a CMakeLists.txt file.

### @tarruda（2 分）

Have you considered trying IQ3_XXS? It might also fit in 128G

### @markole（2 分）

Omg, it's the Redis guy. Thanks!
