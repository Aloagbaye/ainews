---
layout: post
title: "AI News Digest — August 02, 2026"
date: 2026-08-02
description: "This week in AI centered on open frontier models becoming deployable systems, with major moves in agent security, inference efficiency, and sovereign-scale compute."
categories: [digest, ai-news]
---

This week in AI centered on open frontier models becoming deployable systems, with major moves in agent security, inference efficiency, and sovereign-scale compute.

---

### Moonshot releases open-weight Kimi K3 frontier model `Research & Methodology`

Moonshot’s Kimi K3 was the week’s standout model release: a 2.8T-parameter Mixture-of-Experts model with native vision, a 1M-token context window, Kimi Delta Attention, Attention Residuals, and 16-of-896 expert activation. The technical report says full Kimi K3 weights were released for research and broader deployment, making it a notable open-weight frontier-scale release.

[Source](https://www.kimi.com/blog/kimi-k3)

### vLLM ships day-0 serving support for Kimi K3 `Systems Design`

The vLLM team added Kimi K3 support with a hybrid cache manager for recurrent KDA state and paged full-attention KV blocks, plus prefill/decode disaggregation, tool calling, structured output, and speculative decoding. Their reported serving path reached 118 tokens/s without speculation and 370 tokens/s with DSpark on 16 NVIDIA GB300 NVL72 GPUs, highlighting the systems work needed to serve frontier open-weight models.

[Source](https://vllm-project.github.io/2026/07/27/k3.html)

### vLLM and Red Hat advance parallel speculative decoding `Cost & Efficiency`

vLLM and Red Hat AI highlighted open-source support for parallel drafting algorithms including P-EAGLE, DFlash, and DSpark. The approach generates candidate token blocks in one forward pass, aiming to improve throughput and reduce tuning burden while preserving verifier-model output quality.

[Source](https://vllm-project.github.io/2026/07/28/speculators-parallel-drafting.html)

### NVIDIA launches Open Secure AI Alliance for agent-era security `News`

NVIDIA announced the Open Secure AI Alliance with partners across cloud, cybersecurity, enterprise AI, and open-source infrastructure, including Hugging Face, GitHub, Microsoft, IBM, Cloudflare, LangChain, Mistral, and vLLM. The alliance aims to build and share open technologies, models, techniques, and tools for securing software and AI agents.

[Source](https://blogs.nvidia.com/blog/open-secure-ai-alliance/)

### AWS plans up to $50B in U.S. government AI and supercomputing infrastructure `Systems Design`

Amazon said AWS will invest up to $50 billion to expand AI and high-performance computing infrastructure for U.S. government customers, adding nearly 1.3 GW of capacity across AWS Top Secret, Secret, and GovCloud regions. The buildout will give agencies access to services and hardware including SageMaker AI, Bedrock, Nova, Anthropic Claude, open-weight models, Trainium, and NVIDIA infrastructure.

[Source](https://www.aboutamazon.com/news/company-news/amazon-ai-investment-us-federal-agencies)

## What to watch

Watch whether Kimi K3’s open-weight release sparks a new wave of production-grade serving work, and whether agent security plus inference cost become the next major competitive battlegrounds.

---

*Generated every Sunday by [OpenAI (gpt-5.5)](https://openai.com) with web search.*
