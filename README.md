# consumed-ai

Universal software execution engine. Execute any API via natural language from WhatsApp, Telegram, Discord, Slack, or your terminal.

## Quick Start

```bash
pip install consumed-ai
consumed-ai start
```

## What It Does

- **18 channel connectors** — Telegram, Discord, Slack, WhatsApp, Signal, iMessage, Email, SMS, Teams, and more
- **Agent mesh** — spawn AI agents with tools, inter-agent communication, and persistent memory
- **Grammar fast path** — known API patterns execute in 5-15ms at zero LLM cost
- **BYOK** — bring your own LLM key (Anthropic, OpenAI, Groq, Google)
- **Environment scanner** — auto-detects installed tools, packages, credentials, and Docker containers
- **Local-first** — runs on your machine, optionally connects to consumed.ai cloud for 27,000+ API patterns

## CLI Commands

```bash
consumed-ai start                    # Start local daemon (port 9190)
consumed-ai scan                     # Scan your environment
consumed-ai connect telegram         # Connect a messaging channel
consumed-ai chat                     # Interactive terminal chat
consumed-ai status                   # Check daemon status
consumed-ai key store openai         # Store an LLM API key
consumed-ai key list                 # List stored keys
```

## Channel Connectors

| Channel | How | Requires |
|---------|-----|----------|
| Telegram | Bot API long-polling | Bot token |
| Discord | discord.py gateway | Bot token |
| Slack | Socket Mode | App token + bot token |
| WhatsApp | Meta Business API | Cloud token + phone ID |
| Signal | signal-cli REST | Phone number + signal-cli running |
| iMessage | BlueBubbles REST | BlueBubbles server |
| Email | IMAP/SMTP | Email + password |
| SMS | Twilio API | Account SID + auth token |
| WebChat | Local WebSocket | Nothing (always on) |

## BYOK Model Tiers

```bash
consumed-ai key store openai         # Store your OpenAI key
consumed-ai key store anthropic      # Or Anthropic
consumed-ai key store groq           # Or Groq (fastest)
```

The system recommends models by outcome, not name:

| Need | Recommended |
|------|-------------|
| Fast and cheap | Groq LLaMA, Claude Haiku, Gemini Flash |
| Balanced | Claude Sonnet, GPT-4o mini, Gemini Pro |
| Maximum intelligence | Claude Opus, GPT-4o, Gemini Ultra |
| Coding | Claude Sonnet, GPT-4o, DeepSeek Coder |

## Cloud Connection (Optional)

Connect to consumed.ai for access to:
- 27,000+ grammar patterns (instant API matching)
- 739,000+ tool wrappers (auto-discovered APIs)
- HashiCorp Vault credential management
- Self-expanding pipeline (new APIs discovered automatically)

```bash
consumed-ai start --cloud-url https://api.consumed.ai
```

Without cloud: local grammar parsing + your own LLM key. Still useful, just fewer patterns.

## License

Apache 2.0 — see [LICENSE](LICENSE)
