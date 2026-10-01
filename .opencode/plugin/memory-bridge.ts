/**
 * memory-bridge：opencode ↔ 记忆引擎 sidecar 的桥（只服务主 agent 会话）：
 *
 * - 生命周期：启动时拉起 `python -m hybrid_memory.server`，退出时 /save + kill
 * - 捕获：chat.message 与 session.idle 经稳定 request-id 把交互写入 L0；
 *   默认由持久的 Hauler → Selector 协议蒸馏，legacy 模式才使用单轮 candgen。
 * - 注入：按用户输入 /search，将候选记忆作为参考上下文注入。
 * - 默认主会话仅保留只读检索与日志工具，不开放直写/自动裁决入口；
 *   用户不满进入 Reviewer，冲突由独立的人审能力令牌批准。
 * - 内部 OpenCode worker 会话由 DYNAMICS_MEMORY_INTERNAL_AGENT 隔离。
 *
 * sidecar 端口默认 17872，可用 MEMORY_BRIDGE_PORT 覆盖。
 */
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { randomUUID } from "node:crypto"
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"

const PORT = Number(process.env.MEMORY_BRIDGE_PORT ?? 17872)
const BASE = `http://127.0.0.1:${PORT}`
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
  // Worker OpenCode sessions are internal protocol participants, not user turns.
  if (process.env.DYNAMICS_MEMORY_INTERNAL_AGENT === "1") return {} as any
  const trioMode = (process.env.MEMORY_PIPELINE ?? "opencode").toLowerCase() !== "legacy"
  const log = (msg: string) => console.error(`[memory-bridge] ${msg}`)

  // 鉴权令牌：每次现读 <project>/.opencode/memory/.memory-token
  // （重启/重生成不缓存脏值）。401 只告警一次——
  // 可能是端口被占位进程抢占或 token 轮换，静默重试会持续喂数据给错误对象
  const tokenFile = `${directory}/.opencode/memory/.memory-token`
  let warned401 = false
  let authDead = false
  const auth = async () => {
    const f = Bun.file(tokenFile)
    return (await f.exists()) ? (await f.text()).trim() : ""
  }
  const headers = async (): Promise<Record<string, string>> => {
    const h: Record<string, string> = { Authorization: `Bearer ${await auth()}` }
    return h
  }
  const check = (r: Response) => {
    if (r.status === 401) {
      if (!warned401) {
        warned401 = true
        log(`sidecar 401 鉴权失败（token=${tokenFile}）——端口被占位或 token 不匹配，停止发送数据`)
      }
      authDead = true // 请求体本身就是数据，401 后不再发
    }
    return r.ok
  }
  // 工具通道要把 4xx 的 error 文本原样给 agent（预算用尽/参数错都是它该看到的）
  type Res = { ok: boolean; status: number; data: any }
  const call = async (
    method: "GET" | "POST", path: string, body?: unknown,
    opts?: { timeoutMs?: number; requestId?: string },
  ): Promise<Res> => {
    if (authDead) return { ok: false, status: 401, data: { error: "sidecar 鉴权失败" } }
    try {
      const r = await fetch(BASE + path, {
        method,
        headers: {
          "Content-Type": "application/json", ...(await headers()),
          ...(opts?.requestId ? { "X-Request-Id": opts.requestId } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: opts?.timeoutMs ? AbortSignal.timeout(opts.timeoutMs) : undefined,
      })
      const ok = check(r)
      try {
        const data = await r.json()
        if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("expected object")
        return { ok, status: r.status, data }
      } catch {
        return { ok: false, status: r.status, data: { error: "sidecar 返回非法 JSON 对象" } }
      }
    } catch (e) {
      return { ok: false, status: 0, data: { error: `sidecar 不可达: ${String(e)}` } }
    }
  }
  const errText = (r: Res) => `（失败 ${r.status}: ${r.data?.error ?? "unknown"}）`

  // ---------------------------------------------------------------- 生命周期
  let proc: Bun.Subprocess<"ignore", "pipe", "pipe"> | undefined
  const health = await call("GET", "/health")
  let ready = health.ok && health.data?.ok === true
  // 已有 sidecar（用户手起 / 插件被加载多次）→ 直接复用，不重复拉起；
  // 只有自己拉起的进程才在 dispose 时杀掉
  if (ready) log(`sidecar already up on :${PORT}（复用，不重复拉起）`)
  // 只有连接失败才拉起；503/非法健康响应不能触发同端口的第二个进程。
  if (!ready && health.status === 0) {
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
      const probe = await call("GET", "/health")
      if (probe.ok && probe.data?.ok === true) {
        ready = true
        break
      }
      await Bun.sleep(250)
    }
  }
  log(ready ? `sidecar ready on :${PORT}` : `sidecar NOT reachable on :${PORT}`)

  // ---------------------------------------------------------------- 工具
  const fmtHits = (hits: Hit[]) =>
    hits.length
      ? hits.map((h) => `[unit ${h.unit_id} | t=${h.t}${h.scene ? ` | ${h.scene}` : ""}] ${h.snippet}`).join("\n")
      : "（无命中）"

  // 主 agent 用了日志工具 = 记忆没接住这个需求
  let lastMiss = ""
  const reportMiss = (query: string, hint: string) => {
    if (trioMode || !query || query === lastMiss) return
    void call("POST", "/miss", { query, hint, source: "agent_tool" }).then((r) => {
      if (r.ok) lastMiss = query
      else log(`缺失上报失败 ${errText(r)}`)
    })
  }

  const tools = {
    memory_search: tool({
      description: "检索长期记忆：按查询召回相关的项目事实、决策与待办",
      args: { query: tool.schema.string().describe("查询文本") },
      execute: async (args) => {
        const r = await call("POST", "/search", { query: args.query })
        return r.ok ? r.data.context || "（无相关记忆）" : `记忆检索失败 ${errText(r)}`
      },
    }),
    memory_conflicts: tool({
      description: "列出未裁决的记忆冲突（同实体新旧版本或矛盾条目）",
      args: {},
      execute: async () => {
        const r = await call("GET", "/conflicts")
        if (!r.ok) return `冲突查询失败 ${errText(r)}`
        if (!r.data.conflicts?.length) return "（无未决冲突）"
        return r.data.conflicts
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
        const r = await call("POST", "/propose", { proposals: args.proposals as Proposal[], origin: "agent" })
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


  // ---------------------------------------------------------------- main 钩子
  const pending = new Map<string, { user: string; retrievalId?: number }>()
  const textParts = new Map<string, { sessionID: string; messageID: string; text: string }>()
  const messageRoles = new Map<string, { sessionID: string; role: string }>()
  // 在途交付：opencode 不等待事件回调。回合在发送前写入 outbox，dispose
  // await 这条链后再 /save + kill。超时或进程退出后，下次加载用同一 request-id 重投。
  let inflight: Promise<unknown> = Promise.resolve()
  const outboxPath = join(directory, ".opencode", "memory", "bridge-outbox.json")
  const REQUEST_ID = /^[A-Za-z0-9._:-]{8,80}$/
  type CaptureTurn = {
    observe_id: string
    user_text: string
    assistant_text: string
    retrieval_id?: number
    feedback_id?: string
    observe_done: boolean
    feedback_done: boolean
    observe_terminal?: string
    feedback_terminal?: string
  }
  const captureTimeout = () => {
    const n = Number(process.env.MEMORY_BRIDGE_TIMEOUT_MS ?? 30_000)
    return Number.isFinite(n) && n > 0 ? n : 30_000
  }
  const captureAttempts = () => {
    const n = Number(process.env.MEMORY_BRIDGE_ATTEMPTS ?? 3)
    return Number.isFinite(n) && n >= 1 ? Math.floor(n) : 3
  }
  const captureBackoff = () => {
    const n = Number(process.env.MEMORY_BRIDGE_BACKOFF_MS ?? 200)
    return Number.isFinite(n) && n >= 0 ? n : 200
  }
  const newRequestId = (prefix: string) => {
    const id = `${prefix}-${randomUUID()}`
    if (!REQUEST_ID.test(id)) throw new Error(`request id rejected: ${id}`)
    return id
  }
  const isTurn = (value: unknown): value is CaptureTurn => {
    if (!value || typeof value !== "object") return false
    const t = value as CaptureTurn
    return REQUEST_ID.test(t.observe_id)
      && typeof t.user_text === "string" && typeof t.assistant_text === "string"
      && typeof t.observe_done === "boolean" && typeof t.feedback_done === "boolean"
      && (t.retrieval_id === undefined || typeof t.retrieval_id === "number")
      && (t.feedback_id === undefined || REQUEST_ID.test(t.feedback_id))
  }
  const retain = (t: CaptureTurn) =>
    Boolean(t.observe_terminal) || !t.observe_done || !(t.feedback_done || t.feedback_terminal)
  let turns: CaptureTurn[] = []
  const loadOutbox = (): CaptureTurn[] => {
    try {
      const parsed = JSON.parse(readFileSync(outboxPath, "utf8"))
      const raw = Array.isArray(parsed?.turns) ? parsed.turns : null
      if (!raw || raw.some((item: unknown) => !isTurn(item))) {
        throw new Error("outbox schema")
      }
      return raw
    } catch (e) {
      const err = e as NodeJS.ErrnoException
      if (err?.code === "ENOENT") return []
      log(`outbox 无法读取，已隔离且不重放：${String(e)}`)
      try { renameSync(outboxPath, `${outboxPath}.bad-${Date.now()}`) } catch { /* 留在原处，避免误删原文 */ }
      return []
    }
  }
  const persistOutbox = () => {
    const dir = dirname(outboxPath)
    mkdirSync(dir, { recursive: true })
    const gi = join(dir, ".gitignore")
    if (!existsSync(gi)) writeFileSync(gi, "*\n", { mode: 0o600 })
    const tmp = `${outboxPath}.tmp`
    writeFileSync(tmp, JSON.stringify({ version: 1, turns: turns.filter(retain) }), { mode: 0o600 })
    renameSync(tmp, outboxPath)
  }
  try { turns = loadOutbox() } catch (e) { log(`outbox 加载失败：${String(e)}`) }
  const schedule = (job: () => Promise<void>) => {
    inflight = inflight.then(job, job)
  }
  const observeAck = (r: Res): "acked" | "retry" | "stop" => {
    if (r.status === 401) return "stop"
    if (r.data?.accepted === true && typeof r.data.unit_id === "number") return "acked"
    if (r.ok && typeof r.data?.unit_id === "number") return "acked"
    if (r.status === 400 || r.status === 409) return "stop"
    return "retry"
  }
  const feedbackAck = (r: Res): "acked" | "retry" | "stop" => {
    if (r.status === 401) return "stop"
    if (r.data?.accepted === true || r.data?.replayed === true) return "acked"
    if (r.ok && typeof r.data?.n_useful === "number") return "acked"
    if (r.status === 409 && String(r.data?.error ?? "").includes("already")) return "acked"
    if (r.status === 400 || r.status === 404 || r.status === 409) return "stop"
    return "retry"
  }
  const attempt = async (path: "/observe" | "/feedback", body: Record<string, unknown>, requestId: string, judge: (r: Res) => "acked" | "retry" | "stop") => {
    let last: Res = { ok: false, status: 0, data: { error: "not sent" } }
    const attempts = captureAttempts()
    for (let i = 0; i < attempts; i++) {
      last = await call("POST", path, body, { timeoutMs: captureTimeout(), requestId })
      const kind = judge(last)
      log(`${path} ${requestId} → ${kind} ${last.status}`)
      if (kind !== "retry") return { kind, res: last }
      if (i + 1 < attempts && captureBackoff() > 0) await Bun.sleep(captureBackoff() * 2 ** i)
    }
    return { kind: "retry" as const, res: last }
  }
  let flushing = false
  let flushAgain = false
  let closing = false
  const deliver = async (turn: CaptureTurn) => {
    if (!turn.observe_done && !turn.observe_terminal) {
      const sent = await attempt("/observe", {
        user_text: turn.user_text, assistant_text: turn.assistant_text, request_id: turn.observe_id,
      }, turn.observe_id, observeAck)
      if (sent.kind === "acked") turn.observe_done = true
      else if (sent.kind === "stop" && sent.res.status !== 401) turn.observe_terminal = `observe ${sent.res.status}`
      persistOutbox()
      if (!turn.observe_done) return
    }
    if (turn.observe_terminal || turn.feedback_done || turn.feedback_terminal) return
    if (turn.retrieval_id === undefined) {
      turn.feedback_done = true
      persistOutbox()
      return
    }
    if (!turn.feedback_id) {
      turn.feedback_id = newRequestId("fb")
      persistOutbox()
    }
    const sent = await attempt("/feedback", {
      retrieval_id: turn.retrieval_id, question: turn.user_text, answer: turn.assistant_text,
      request_id: turn.feedback_id,
    }, turn.feedback_id, feedbackAck)
    if (sent.kind === "acked") turn.feedback_done = true
    else if (sent.kind === "stop" && sent.res.status !== 401) {
      // 检索已不在或正文被拒：L0 已在，不能换 id 再记一次，也不能热循环。
      turn.feedback_terminal = `feedback ${sent.res.status}`
      log(`feedback 无法交付 ${turn.feedback_id} retrieval=${turn.retrieval_id} ${sent.res.status}`)
    }
    persistOutbox()
  }
  const flushOutbox = async () => {
    if (!ready || authDead) return
    if (flushing) { flushAgain = true; return }
    flushing = true
    try {
      let blocked = false
      do {
        flushAgain = false
        blocked = false
        for (const turn of turns) {
          if (turn.observe_terminal || (turn.observe_done && (turn.feedback_done || turn.feedback_terminal))) continue
          await deliver(turn)
          const stuck = (!turn.observe_done && !turn.observe_terminal)
            || (turn.observe_done && !turn.feedback_done && !turn.feedback_terminal)
          if (stuck) { blocked = true; break }
        }
      } while (!blocked && (flushAgain || turns.some((turn) =>
        !turn.observe_terminal && !(turn.observe_done && (turn.feedback_done || turn.feedback_terminal)))))
      turns = turns.filter(retain)
      persistOutbox()
    } catch (e) {
      log(`flush 失败：${String(e)}`)
    } finally {
      flushing = false
    }
  }
  if (ready && turns.length) schedule(() => flushOutbox())

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
      const r = await call("POST", "/search", { query: p.user })
      if (!r.ok) {
        log(`记忆注入失败 ${errText(r)}`)
        return
      }
      p.retrievalId = r.data.retrieval_id
      const memo = r.data.context
        ? `<relevant-memories>\n以下是召回的相关记忆，不代表当前任务进程，仅作为参考：\n${r.data.context}\n</relevant-memories>`
        : `<relevant-memories>\n（本轮没有召回到相关记忆）\n</relevant-memories>`
      output.system.push(
        memo +
          "\n若上述记忆不足以回答且问题涉及项目历史（之前的决定、改过什么、某个值是多少），" +
          (trioMode
            ? "先用 log_search / log_timeline 查证再作答；不要直接写入长期记忆，后台 Hauler 和 Selector 会处理已保存的交互。"
            : "先用 log_search / log_timeline 查证再作答；查到的事实用 memory_propose 存下来。"),
      )
    },

    event: async ({ event }) => {
      if (process.env.MEMORY_BRIDGE_DEBUG) log(`event: ${event.type}`)
      if (!ready) return
      if (event.type === "message.updated") {
        const info = event.properties.info
        if (pending.has(info.sessionID)) {
          messageRoles.set(info.id, { sessionID: info.sessionID, role: info.role })
        }
        return
      }
      if (event.type === "message.part.updated") {
        const part = event.properties.part
        if (part.type === "text" && typeof part.text === "string" && pending.has(part.sessionID)) {
          textParts.set(part.id, {
            sessionID: part.sessionID, messageID: part.messageID, text: part.text,
          })
        }
        return
      }
      if (event.type === "session.idle") {
        const sid = event.properties.sessionID
        const p = pending.get(sid)
        if (!p) return
        const reply = [...textParts.values()]
          .filter((a) => a.sessionID === sid && a.text.trim() && messageRoles.get(a.messageID)?.role === "assistant")
          .map((a) => a.text)
          .join("\n\n")
        pending.delete(sid)
        for (const [id, a] of textParts) {
          if (a.sessionID === sid) textParts.delete(id)
        }
        for (const [id, info] of messageRoles) {
          if (info.sessionID === sid) messageRoles.delete(id)
        }
        if (!reply) {
          log(`idle: no reply captured for session ${sid}`)
          return
        }
        const turn: CaptureTurn = {
          observe_id: newRequestId("obs"),
          user_text: p.user,
          assistant_text: reply,
          retrieval_id: p.retrievalId,
          observe_done: false,
          feedback_done: false,
        }
        // 先落盘再入链。事件回调不被等待，不能等 inflight 才持久化。
        turns.push(turn)
        try { persistOutbox() } catch (e) { log(`outbox 写入失败，本进程仍会用同一 id 发送：${String(e)}`) }
        log(`idle: queued ${turn.observe_id} (user=${p.user.length}ch, reply=${reply.length}ch)`)
        // dispose 已开始后不再发新请求，避免 /save 期间被 kill 截断；原文已在 outbox。
        if (!closing) schedule(() => flushOutbox())
      }
    },

    tool: trioMode
      ? { memory_search: tools.memory_search, memory_conflicts: tools.memory_conflicts,
          log_search: tools.log_search, log_timeline: tools.log_timeline,
          log_stats: tools.log_stats, log_window: tools.log_window }
      : tools,

    dispose: async () => {
      closing = true
      await inflight // 等已排队的交付结束；每次尝试有超时，不会无限挂起
      await flushOutbox() // 排空 await 期间已落盘、尚未发送的回合
      const saved = await call("POST", "/save", {}, { timeoutMs: captureTimeout() })
      if (!saved.ok) log(`保存失败 ${errText(saved)}`)
      proc?.kill() // 只杀自己拉起的 sidecar；未确认回合留在 outbox
    },
  }
}) satisfies Plugin
