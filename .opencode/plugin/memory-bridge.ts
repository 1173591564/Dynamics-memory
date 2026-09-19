/**
 * memory-bridge：opencode ↔ 记忆引擎 sidecar 的桥。
 *
 * - 生命周期：启动时拉起 `python -m hybrid_memory.server`，退出时 /save + kill
 * - 捕获：chat.message 记用户输入；session.idle 时把 (user, assistant) 一轮
 *   交互 POST /observe（引擎内部先 candgen 蒸馏，只有蒸馏产物进池）
 * - 注入：experimental.chat.system.transform 时按当前用户输入 /recall，
 *   结果以 <relevant-memories> 块注入（明确标注"不代表当前任务进程"）
 * - 记账：注入时记下 retrieval_id，回答完成后 POST /feedback 走 recognizer
 * - 工具：memory_search / memory_conflicts / memory_resolve（agent 主动通道）
 *
 * sidecar 端口默认 17872，可用 MEMORY_BRIDGE_PORT 覆盖；judge 类调用走
 * --pure（插件不加载），不会与本插件互相触发。
 */
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"

const PORT = Number(process.env.MEMORY_BRIDGE_PORT ?? 17872)
const BASE = `http://127.0.0.1:${PORT}`

export default (async ({ directory }) => {
  const log = (msg: string) => console.error(`[memory-bridge] ${msg}`)

  const get = async (path: string) => {
    try {
      const r = await fetch(BASE + path)
      return r.ok ? await r.json() : null
    } catch {
      return null
    }
  }
  const post = async (path: string, body: unknown) => {
    try {
      const r = await fetch(BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      return r.ok ? await r.json() : null
    } catch {
      return null
    }
  }

  // 已有 sidecar（用户手起 / 插件被加载多次）→ 直接复用，不重复拉起；
  // 只有自己拉起的进程才在 dispose 时杀掉
  let proc: Bun.Subprocess<"ignore", "pipe", "pipe"> | undefined
  let ready = !!(await get("/health"))
  if (ready) log(`sidecar already up on :${PORT}（复用，不重复拉起）`)
  if (!ready) {
    proc = Bun.spawn(
      ["python", "-m", "hybrid_memory.server", "--port", String(PORT), "--project", directory],
      { cwd: directory, env: process.env, stdout: "pipe", stderr: "pipe" },
    )
    const drain = async (stream: ReadableStream<Uint8Array> | undefined, tag: string) => {
      if (!stream) return
      const decoder = new TextDecoder()
      for await (const chunk of stream) log(`${tag}: ${decoder.decode(chunk).trimEnd()}`)
    }
    void drain(proc.stdout as ReadableStream<Uint8Array>, "sidecar")
    void drain(proc.stderr as ReadableStream<Uint8Array>, "sidecar!")
    for (let i = 0; i < 40; i++) {
      if (await get("/health")) {
        ready = true
        break
      }
      await Bun.sleep(250)
    }
  }
  log(ready ? `sidecar ready on :${PORT}` : `sidecar NOT reachable on :${PORT}`)

  const pending = new Map<string, { user: string; retrievalId?: number }>()
  const assistantText = new Map<string, { sessionID: string; text: string }>()
  // 在途的 observe/feedback：opencode 不等待事件回调，进程退出会掐断请求；
  // dispose 必须先 await 它再 /save + kill
  let inflight: Promise<unknown> = Promise.resolve()

  return {
    "chat.message": async ({ sessionID }, { parts }) => {
      const text = parts
        .filter((p) => p.type === "text")
        .map((p) => ("text" in p ? p.text : ""))
        .join("\n")
      if (text.trim()) pending.set(sessionID, { user: text })
    },

    "experimental.chat.system.transform": async ({ sessionID }, output) => {
      if (!ready || !sessionID) return
      const p = pending.get(sessionID)
      if (!p) return
      const rec = await get(`/recall?q=${encodeURIComponent(p.user)}`)
      if (!rec?.context) return
      p.retrievalId = rec.retrieval_id
      output.system.push(
        `<relevant-memories>\n以下是召回的相关记忆，不代表当前任务进程，仅作为参考：\n${rec.context}\n</relevant-memories>`,
      )
    },

    event: async ({ event }) => {
      if (process.env.MEMORY_BRIDGE_DEBUG) log(`event: ${event.type}`)
      if (!ready) return
      if (event.type === "message.part.updated") {
        const part = event.properties.part
        if (part.type === "text" && typeof part.text === "string" && part.text) {
          assistantText.set(part.messageID, {
            sessionID: part.sessionID,
            text: part.text,
          })
        }
        return
      }
      if (event.type === "session.idle") {
        const sid = event.properties.sessionID
        const p = pending.get(sid)
        if (!p) return
        const reply = [...assistantText.values()]
          .filter((a) => a.sessionID === sid)
          .map((a) => a.text)
          .join("\n\n")
        pending.delete(sid)
        for (const [mid, a] of assistantText) {
          if (a.sessionID === sid) assistantText.delete(mid)
        }
        if (!reply) {
          log(`idle: no reply captured for session ${sid}`)
          return
        }
        const retrievalId = p.retrievalId
        inflight = (async () => {
          log(`idle: observe turn (user=${p.user.length}ch, reply=${reply.length}ch)`)
          const obs = await post("/observe", { user_text: p.user, assistant_text: reply })
          log(`idle: observe → ${JSON.stringify(obs)}`)
          if (retrievalId !== undefined) {
            const fb = await post("/feedback", {
              retrieval_id: retrievalId,
              question: p.user,
              answer: reply,
            })
            log(`idle: feedback → ${JSON.stringify(fb)}`)
          }
        })()
      }
    },

    tool: {
      memory_search: tool({
        description: "检索长期记忆：按查询召回相关的项目事实、决策与待办",
        args: { query: tool.schema.string().describe("查询文本") },
        execute: async (args) => {
          const rec = await post("/search", { query: args.query })
          return rec?.context || "（无相关记忆）"
        },
      }),
      memory_conflicts: tool({
        description: "列出未裁决的记忆冲突（同实体新旧版本或矛盾条目）",
        args: {},
        execute: async () => {
          const out = await get("/conflicts")
          if (!out?.conflicts?.length) return "（无未决冲突）"
          return out.conflicts
            .map((c: { left: number; right: number; left_text: string; right_text: string }) =>
              `[${c.left} vs ${c.right}] ${c.left_text} ⚔ ${c.right_text}`)
            .join("\n")
        },
      }),
      memory_resolve: tool({
        description:
          "裁决一组记忆冲突：synonym（同义合并）/ update（新替旧）/ contradiction（矛盾保留并降权）/ collision（无关都留）/ pending（暂不裁决）",
        args: {
          left: tool.schema.number().describe("冲突左侧记忆 id"),
          right: tool.schema.number().describe("冲突右侧记忆 id"),
          verdict: tool.schema
            .string()
            .describe("synonym | update | contradiction | collision | pending"),
        },
        execute: async (args) => {
          const out = await post("/resolve", {
            left: args.left,
            right: args.right,
            verdict: args.verdict,
          })
          return out ? `已裁决 ${out.resolved} 条` : "裁决失败（sidecar 不可达）"
        },
      }),
    },

    dispose: async () => {
      await inflight // 等捕获回路落地，再存盘收尾
      await post("/save", {})
      proc?.kill()   // 只杀自己拉起的 sidecar
    },
  }
}) satisfies Plugin
