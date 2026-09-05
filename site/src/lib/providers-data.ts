export interface Provider {
  name: string
  url: string
  requiresApiKey: boolean
  description: string
  local: boolean
}

export const providers: Provider[] = [
  {
    name: 'LM Studio',
    url: 'http://127.0.0.1:1234/v1',
    requiresApiKey: false,
    description: 'Local model serving with a beautiful UI. Load and run models offline.',
    local: true,
  },
  {
    name: 'Ollama',
    url: 'http://127.0.0.1:11434/v1',
    requiresApiKey: false,
    description: 'Lightweight local model runner. Pull and run models with a single command.',
    local: true,
  },
  {
    name: 'OpenAI',
    url: 'https://api.openai.com/v1',
    requiresApiKey: true,
    description: 'GPT-4o, GPT-4, GPT-3.5-turbo. Cloud-based with pay-per-token pricing.',
    local: false,
  },
  {
    name: 'OpenRouter',
    url: 'https://openrouter.ai/api/v1',
    requiresApiKey: true,
    description: 'Unified gateway to 200+ models from OpenAI, Anthropic, Meta, and more.',
    local: false,
  },
  {
    name: 'Groq',
    url: 'https://api.groq.com/openai/v1',
    requiresApiKey: true,
    description: 'Ultra-fast inference on Groq LPU hardware. Lowest latency for supported models.',
    local: false,
  },
  {
    name: 'DeepSeek',
    url: 'https://api.deepseek.com/v1',
    requiresApiKey: true,
    description: 'DeepSeek-V3, DeepSeek-R1. Strong reasoning and coding at competitive pricing.',
    local: false,
  },
  {
    name: 'AIMLAPI',
    url: 'https://api.aimlapi.com/v1',
    requiresApiKey: true,
    description: 'Access to 300+ AI models through a single OpenAI-compatible API.',
    local: false,
  },
  {
    name: 'SiliconFlow',
    url: 'https://api.siliconflow.cn/v1',
    requiresApiKey: true,
    description: 'Fast inference for open-source models. Free tier available.',
    local: false,
  },
]
