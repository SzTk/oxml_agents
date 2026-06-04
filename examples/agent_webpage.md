# agent_webpage — Example Output

Agent that visits a URL and summarises the page content.

**Query:** `What is the post at https://aittalam.github.io/posts/2025-06-17-vibe-reversing/ about?`

```
uv run agent_webpage.py
```

## Output

```text
╭─────────────────────────────────────────────────────────────────────────── CALL_LLM: Qwen2.5-7B-Instruct-Q8_0 ───────────────────────────────────────────────────────────────────────────╮
│ ╭─ INPUT ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ [                                                                                                                                                                                    │ │
│ │   {"role": "system", "content": "You must use the available tools to find an answer."},                                                                                              │ │
│ │   {"role": "user",   "content": "\nWhat is the post at https://aittalam.github.io/posts/2025-06-17-vibe-reversing/ about?\n"}                                                        │ │
│ │ ]                                                                                                                                                                                    │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│ ╭─ OUTPUT ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ [{"tool.name": "visit_webpage", "tool.args": "{\"url\": \"https://aittalam.github.io/posts/2025-06-17-vibe-reversing/\", \"timeout\": \"10\"}"}]                                      │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────────────────────────────────────────────── EXECUTE_TOOL: visit_webpage ───────────────────────────────────────────────────────────────────────────────╮
│ ╭─ Input ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ {"url": "https://aittalam.github.io/posts/2025-06-17-vibe-reversing/", "timeout": 10}                                                                                               │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│ ╭─ OUTPUT ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ On Vibe Reversing | mala::notes                                                                                                                                                      │ │
│ │                                                                                                                                                                                      │ │
│ │ Among the PowerBrowsing tools I developed in the past, there was one I actually used a lot myself: a tiny Perl script that crawled live timetables from our national train           │ │
│ │ company's bloated website and returned the information I needed as plain text. [...] Last week I decided to check if and how a modern LLM tool could help someone perform a          │ │
│ │ similar task. This post describes what I learned from my experiment.                                                                                                                 │ │
│ │ [full page content retrieved and passed to the model]                                                                                                                               │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────────────────────────────────────────────────────── CALL_LLM: Qwen2.5-7B-Instruct-Q8_0 ───────────────────────────────────────────────────────────────────────────╮
│ ╭─ OUTPUT ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ The post discusses the author's experience in using Claude, an AI language model, to reverse engineer the API of a website that provides train timetables for Italy (Viaggiatreno).  │ │
│ │ The author compares the process of reverse engineering the API 20 years ago (manual Perl scripts) with today's experience of using AI to assist in the process.                     │ │
│ │                                                                                                                                                                                      │ │
│ │ Key points:                                                                                                                                                                          │ │
│ │  • Past: manual reverse-engineering, writing Perl scripts, learning HTTP/regex from scratch.                                                                                         │ │
│ │  • Today: replicated in <30 min using plain-English prompts and screenshots; no code written by hand.                                                                               │ │
│ │  • Concerns: illusion of "no experience needed", risk of vendor lock-in, loss of the deep meta-learning process.                                                                    │ │
│ │  • Conclusion: "vibe reversing" is a useful tool especially for adversarial interoperability, but awareness of its pitfalls is essential.                                            │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│ ╭─ USAGE ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ {"input_tokens": 3898, "output_tokens": 426}                                                                                                                                        │ │
│ ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
