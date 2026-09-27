/**
 * memory-bridge：opencode ↔ 记忆引擎 sidecar 的桥。两种角色，同一份代码：
 *
 * main（默认）——主 agent 的会话：
 * - 生命周期：启动时拉起 `python -m hybrid_memory.server`，退出时 /save + kill
 * - 捕获：chat.message 记用户输入；session.idle 时把 (user, assistant) 一轮
 *   交互 POST /observe（sidecar 先落 L0 日志、触发扫描，再 candgen 蒸馏）
 * - 注入：experimental.chat.system.transform 时按当前用户输入 /search，
 *   结果以 <relevant-memories> 块注入（明确标注"不代表当前任务进程"）
 * - 记账：注入时记下 retrieval_id，回答完成后 POST /feedback 走 recognizer
 * - 工具：memory_* + log_*（主 agent 主动通道）。主 agent 一旦用 log_* 去翻
 *   日志，就说明注入的记忆没接住——插件顺手 POST /miss，后台调查员拿大预算
 *   系统性修复。这是衔尾蛇的一半：消费者的行为反过来驱动生产。
 *
 * worker（MEMORY_BRIDGE_ROLE=worker）——sidecar 拉起的调查员会话：
 * - 只注册工具，不挂任何捕获/注入钩子（火墙：调查员自己的会话绝不能被
 *   observe，否则会长出"我检索了日志"这类自指记忆并无限递归）
 * - token 从 MEMORY_BRIDGE_TOKEN 读（调查员的 --dir 是本仓库，不是用户项目，
 *   文件路径对不上）；每个请求带 X-Signal-Id（MEMORY_BRIDGE_SIGNAL），
 *   服务端按信号计量工具调用/回展预算并施加因果上界
 * - 不拉起 sidecar：它就是被 sidecar 拉起来的
 *
 * sidecar 端口默认 17872，可用 MEMORY_BRIDGE_PORT 覆盖；judge 类无工具角色仍
 * 走 --pure（插件不加载）。
 */
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { resolve } from "node:path"

const PORT = Number(process.env.MEMORY_BRIDGE_PORT ?? 17872)
const BASE = `http://127.0.0.1:${PORT}`
const ROLE = process.env.MEMORY_BRIDGE_ROLE === "worker" ? "worker" : "main"
const SIGNAL = process.env.MEMORY_BRIDGE_SIGNAL ?? ""
// sidecar 的包根：插件文件在 <repo>/.opencode/plugin/ 下——spawn 的 cwd
// 固定到这里而不是目标项目目录，防项目内同名 hybrid_memory 模块遮蔽劫持
const REPO_ROOT = resolve(import.meta.dir, "../..")

type Hit = { unit_id: number; t: number; scene: string; snippet: string }
type Conflict = { left: number; right: number; left_text: string; right_text: string }
type Proposal = {
  text: string
  kind?: string
  salience?: number
  source_unit_ids: number[]
  entity_key?: string
  supersedes?: number[]
}

export default (async ({ directory }) => {
  const log = (msg: string) => console.error(`[memory-bridge:${ROLE}] ${msg}`)

  // 鉴权令牌：main 角色每次现读 <project>/.opencode/memory/.memory-token
  // （重启/重生成不缓存脏值）；worker 角色用环境变量。401 只告警一次——
  // 可能是端口被占位进程抢占或 token 轮换，静默重试会持续喂数据给错误对象
  const tokenFile = `${directory}/.opencode/memory/.memory-token`
  let warned401 = false
  let authDead = false
  const auth = async () => {
    if (process.env.MEMORY_BRIDGE_TOKEN) return process.env.MEMORY_BRIDGE_TOKEN
    const f = Bun.file(tokenFile)
    return (await f.exists()) ? (await f.text()).trim() : ""
  }
  const headers = async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = { Authorization: `Bearer ${await auth()}` }
    if (SIGNAL) h["X-Signal-Id"] = SIGNAL
    return h
  }
  const check = (r: Response) => {
    if (r.status === 401) {
      if (!warned401) {
        warned401 = true
        log(`sidecar 401 鉴权失败（token=${process.env.MEMORY_BRIDGE_TOKEN ? "env" : tokenFile}）——端口被占位或 token 不匹配，停止发送数据`)
      }
      authDead = true // 请求体本身就是数据，401 后不再发
    }
    return r.ok
  }
  // 工具通道要把 4xx 的 error 文本原样给 agent（预算用尽/参数错都是它该看到的）
  type Res = { ok: boolean; status: number; data: any }
  const call = async (method: "GET" | "POST", path: string, body?: unknown): Promise<Res> => {
    if (authDead) return { ok: false, status: 401, data: { error: "sidecar 鉴权失败" } }
    try {
      const r = await fetch(BASE + path, {
        method,
        headers: { "Content-Type": "application/json", ...(await headers()) },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      const ok = check(r)
      let data: any = null
      try {
        data = await r.json()
      } catch {
        data = null
      }
      return { ok, status: r.status, data }
    } catch (e) {
      return { ok: false, status: 0, data: { error: `sidecar 不可达: ${String(e)}` } }
    }
  }
  const get = async (path: string) => (await call("GET", path)).data
  const post = async (path: string, body: unknown) => {
    const r = await call("POST", path, body)
    return r.ok ? r.data : null
  }
  const errText = (r: Res) => `（失败 ${r.status}: ${r.data?.error ?? "unknown"}）`

  // ---------------------------------------------------------------- 生命周期
  let proc: Bun.Subprocess<"ignore", "pipe", "pipe"> | undefined
  let ready = !!(await get("/health"))
  if (ROLE === "worker") {
    if (!ready) log(`sidecar NOT reachable on :${PORT}（worker 角色不拉起）`)
  } else {
    // 已有 sidecar（用户手起 / 插件被加载多次）→ 直接复用，不重复拉起；
    // 只有自己拉起的进程才在 dispose 时杀掉
    if (ready) log(`sidecar already up on :${PORT}（复用，不重复拉起）`)
    if (!ready) {
      proc = Bun.spawn(
        ["python", "-m", "hybrid_memory.server", "--port", String(PORT), "--project", directory],
        { cwd: REPO_ROOT, env: process.env, stdout: "pipe", stderr: "pipe" },
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
  }

  // ---------------------------------------------------------------- 工具
  const fmtHits = (hits: Hit[]) =>
    hits.length
      ? hits.map((h) => `[unit ${h.unit_id} | t=${h.t}${h.scene ? ` | ${h.scene}` : ""}] ${h.snippet}`).join("\n")
      : "（无命中）"

  // 主 agent 用了日志工具 = 记忆没接住这个需求；worker 自己就是修复者，不上报
  let lastMiss = ""
  const reportMiss = (query: string, hint: string) => {
    if (ROLE !== "main" || !query || query === lastMiss) return
    lastMiss = query
    void post("/miss", { query, hint, source: "agent_tool" })
  }

  const tools = {
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
          .map((c: Conflict) => `[${c.left} vs ${c.right}] ${c.left_text} ⚔ ${c.right_text}`)
          .join("\n")
      },
    }),
    memory_resolve: tool({
      description:
        "裁决一组记忆冲突：synonym（同义合并）/ update（新替旧）/ contradiction（矛盾保留并降权）/ collision（无关都留）/ pending（暂不裁决）。可附 entity_key 标注这对记忆讲的是哪个实体。",
      args: {
        left: tool.schema.number().describe("冲突左侧记忆 id"),
        right: tool.schema.number().describe("冲突右侧记忆 id"),
        verdict: tool.schema.string().describe("synonym | update | contradiction | collision | pending"),
        entity_key: tool.schema.string().optional().describe("实体键，如 proxy/handler.ts 或 hermes"),
      },
      execute: async (args) => {
        const r = await call("POST", "/resolve", {
          left: args.left,
          right: args.right,
          verdict: args.verdict,
          entity_key: args.entity_key ?? "",
          ensure_tension: true,
        })
        return r.ok ? `已裁决 ${r.data.resolved} 条` : `裁决失败 ${errText(r)}`
      },
    }),
    log_search: tool({
      description:
        "在原始交互日志里检索（词法+向量，只返回片段）。记忆里没有、但项目历史里可能有的事实用它找；再用 log_window 回展原文。",
      args: {
        query: tool.schema.string().describe("查询文本；PR 号/文件名/标识符命中最准"),
        before: tool.schema.number().optional().describe("只看时间步 < before 的日志"),
        scene: tool.schema.string().optional().describe("限定情境名"),
        k: tool.schema.number().optional().describe("返回条数，默认 8"),
      },
      execute: async (args) => {
        reportMiss(args.query, "log_search")
        const r = await call("POST", "/log/search", {
          query: args.query,
          before: args.before,
          scene: args.scene,
          k: args.k,
        })
        return r.ok ? fmtHits(r.data.hits) : `日志检索失败 ${errText(r)}`
      },
    }),
    log_timeline: tool({
      description: "某个实体（文件路径/PR#/commit/标识符/概念）在日志里的全部提及，按时间排列——看它是怎么演化的",
      args: {
        entity: tool.schema.string().describe("实体，如 handler.ts、#42、deepseek-v4-flash"),
        before: tool.schema.number().optional().describe("只看时间步 < before 的日志"),
        limit: tool.schema.number().optional().describe("最多条数，默认 30"),
      },
      execute: async (args) => {
        reportMiss(args.entity, "log_timeline")
        const r = await call("POST", "/log/timeline", {
          entity: args.entity,
          before: args.before,
          limit: args.limit,
        })
        return r.ok ? `${args.entity} 时间线（${r.data.n} 处）：\n${fmtHits(r.data.timeline)}` : `时间线失败 ${errText(r)}`
      },
    }),
    log_stats: tool({
      description: "日志聚合统计（不含原文）：按情境 / 实体 / 周计数——先看全貌再决定下钻哪里",
      args: {
        group_by: tool.schema.string().describe("scene | entity | week"),
        before: tool.schema.number().optional(),
        limit: tool.schema.number().optional(),
      },
      execute: async (args) => {
        const r = await call("POST", "/log/stats", {
          group_by: args.group_by,
          before: args.before,
          limit: args.limit,
        })
        if (!r.ok) return `统计失败 ${errText(r)}`
        const rows: Record<string, unknown>[] = r.data.rows ?? []
        return `共 ${r.data.units_total} 个单元\n` + rows.map((row) => JSON.stringify(row)).join("\n")
      },
    }),
    log_window: tool({
      description:
        "回展指定日志单元的原文（唯一能看到全文的通道，按字符预算截断）。先用 log_search/log_timeline 定位 unit_id，再回展。",
      args: {
        unit_ids: tool.schema.array(tool.schema.number()).describe("要回展的 unit id 列表（≤20）"),
        max_chars: tool.schema.number().optional().describe("本次最多字符数"),
      },
      execute: async (args) => {
        const r = await call("POST", "/log/window", { unit_ids: args.unit_ids, max_chars: args.max_chars })
        if (!r.ok) return `回展失败 ${errText(r)}`
        const parts = (r.data.units ?? []).map(
          (u: { unit_id: number; t: number; scene: string; user_text: string; assistant_text: string; truncated: boolean }) =>
            `### unit ${u.unit_id} (t=${u.t}${u.scene ? ` | ${u.scene}` : ""})${u.truncated ? " [已截断]" : ""}\n[user]\n${u.user_text}\n\n[assistant]\n${u.assistant_text}`,
        )
        const tail: string[] = []
        if (r.data.missing?.length) tail.push(`不存在/越界: ${r.data.missing.join(",")}`)
        if (r.data.omitted?.length) tail.push(`预算不足未回展: ${r.data.omitted.join(",")}`)
        if (typeof r.data.budget_left === "number") tail.push(`剩余回展预算: ${r.data.budget_left} 字`)
        return parts.join("\n\n") + (tail.length ? `\n\n（${tail.join("；")}）` : "")
      },
    }),
    memory_propose: tool({
      description:
        "把从日志里核实到的事实写入长期记忆。每条必须带 source_unit_ids（你在 log_* 结果里实际看到过的 unit）；服务端会校验溯源、脱敏并拒绝自指内容。",
      args: {
        proposals: tool.schema
          .array(
            tool.schema.object({
              text: tool.schema.string().describe("自包含的一句话事实/决策/待办"),
              kind: tool.schema.string().optional().describe("work_fact | work_task | work_method | work_artifact | preference"),
              salience: tool.schema.number().optional().describe("0–1，缺失时的预期损失"),
              source_unit_ids: tool.schema.array(tool.schema.number()).describe("来源 unit id"),
              entity_key: tool.schema.string().optional().describe("实体键"),
              supersedes: tool.schema.array(tool.schema.number()).optional().describe("被此条取代的旧记忆 id"),
            }),
          )
          .describe("提议列表"),
      },
      execute: async (args) => {
        const r = await call("POST", "/propose", { proposals: args.proposals as Proposal[], origin: ROLE === "worker" ? "repair" : "agent" })
        if (!r.ok) return `写入失败 ${errText(r)}`
        const rej = (r.data.rejected ?? []) as { index: number; reason: string }[]
        return (
          `已接收 ${r.data.accepted} 条（新建 ${r.data.new_ids?.length ?? 0}，合并 ${r.data.merged ?? 0}）` +
          (rej.length ? `；拒绝 ${rej.length} 条: ${rej.map((x) => `#${x.index} ${x.reason}`).join("; ")}` : "")
        )
      },
    }),
    memory_diagnose: tool({
      description:
        "记录一次记忆缺失的诊断（调查完成后调用）：not_in_window | dropped_by_candgen | too_coarse | wrong_scene | never_logged | no_miss",
      args: {
        miss_type: tool.schema.string().describe("缺失类型"),
        note: tool.schema.string().optional().describe("一句话说明"),
      },
      execute: async (args) => {
        const r = await call("POST", "/diagnose", { miss_type: args.miss_type, note: args.note ?? "" })
        return r.ok ? `已记录：${JSON.stringify(r.data.miss_counts)}` : `记录失败 ${errText(r)}`
      },
    }),
  }

  // worker 角色：只有工具，没有钩子——这就是火墙
  if (ROLE === "worker") return { tool: tools }

  // ---------------------------------------------------------------- main 钩子
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
      // 走 POST /search：长 CJK 输入放 query string 会 ×3 URL 编码后
      // 超 request-line 上限（recall 静默失败）；/search 与 /recall 返回同构
      const rec = await post("/search", { query: p.user })
      if (!rec) return
      p.retrievalId = rec.retrieval_id
      const memo = rec.context
        ? `<relevant-memories>\n以下是召回的相关记忆，不代表当前任务进程，仅作为参考：\n${rec.context}\n</relevant-memories>`
        : `<relevant-memories>\n（本轮没有召回到相关记忆）\n</relevant-memories>`
      output.system.push(
        memo +
          "\n若上述记忆不足以回答且问题涉及项目历史（之前的决定、改过什么、某个值是多少），" +
          "先用 log_search / log_timeline 查证再作答；查到的事实用 memory_propose 存下来。",
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
        // 链式而非覆写：dispose await inflight 必须等到最后一个在途回路，
        // 否则提前 idle 的 observe/feedback 会被 proc.kill 截断丢数据
        inflight = inflight.then(async () => {
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
        })
      }
    },

    tool: tools,

    dispose: async () => {
      await inflight // 等捕获回路落地，再存盘收尾
      await post("/save", {})
      proc?.kill() // 只杀自己拉起的 sidecar
    },
  }
}) satisfies Plugin
