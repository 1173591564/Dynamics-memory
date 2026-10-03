/** Run: bun test tests/memory_bridge.test.ts
 * Real plugin hooks/HTTP adapter; only tool registration and external I/O are mocked.
 */
import { mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { afterEach, beforeEach, expect, mock, spyOn, test } from "bun:test"

const schema: any = new Proxy(() => schema, { get: () => schema })
mock.module("@opencode-ai/plugin", () => ({
  tool: Object.assign((definition: any) => definition, { schema }),
}))
const { default: bridge } = await import("../.opencode/plugin/memory-bridge.ts")

type Reply = { status: number; data?: unknown; raw?: string }
let replies: Map<string, Reply>
let requests: { path: string; body: any; requestId?: string }[]
let spawn: ReturnType<typeof spyOn>
let dir: string
const hooks = () => bridge({ directory: dir } as any) as Promise<any>
const ID = /^[A-Za-z0-9._:-]{8,80}$/

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "bridge-"))
  process.env.MEMORY_BRIDGE_BACKOFF_MS = "0"
  process.env.MEMORY_BRIDGE_ATTEMPTS = "3"
  delete process.env.MEMORY_BRIDGE_TIMEOUT_MS
  delete process.env.MEMORY_PIPELINE
  replies = new Map([
    ["/health", { status: 200, data: { ok: true } }],
    ["/search", { status: 200, data: { context: "", retrieval_id: 0 } }],
    ["/conflicts", { status: 200, data: { conflicts: [] } }],
    ["/miss", { status: 200, data: { queued: 1 } }],
    ["/log/search", { status: 200, data: { hits: [] } }],
    ["/observe", { status: 200, data: { unit_id: 0 } }],
    ["/feedback", { status: 200, data: { n_useful: 0 } }],
    ["/save", { status: 200, data: { saved: true } }],
  ])
  requests = []
  spyOn(console, "error").mockImplementation(() => {})
  spyOn(Bun, "file").mockImplementation(() => ({
    exists: async () => true, text: async () => "test-token",
  }) as any)
  spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname
    const headers = new Headers(init?.headers)
    requests.push({
      path,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      requestId: headers.get("X-Request-Id") ?? undefined,
    })
    const reply = replies.get(path)
    if (!reply) throw new Error(`unexpected request: ${path}`)
    return new Response(reply.raw ?? JSON.stringify(reply.data), { status: reply.status })
  })
  spawn = spyOn(Bun, "spawn").mockImplementation(() => {
    throw new Error("must not spawn a second sidecar")
  })
})
afterEach(() => mock.restore())

for (const status of [403, 429, 503]) {
  test(`memory tools surface HTTP ${status}, not an empty result`, async () => {
    const plugin = await hooks()
    replies.set("/search", { status, data: { error: "request rejected" } })
    replies.set("/conflicts", { status, data: { error: "request rejected" } })
    for (const output of [
      await plugin.tool.memory_search.execute({ query: "history" }),
      await plugin.tool.memory_conflicts.execute({}),
    ]) {
      expect(output).toContain(`失败 ${status}`)
      expect(output).toContain("request rejected")
    }
  })
}

test("successful empty responses remain empty, not failures", async () => {
  const plugin = await hooks()
  expect(await plugin.tool.memory_search.execute({ query: "q" })).toBe("（无相关记忆）")
  expect(await plugin.tool.memory_conflicts.execute({})).toBe("（无未决冲突）")
})

for (const reply of [
  { status: 503, data: { ok: false, checkpoint_fault: true } },
  { status: 200, data: { ok: false } },
  { status: 200, data: { unrelated: true } },
  { status: 200, data: null },
  { status: 200, raw: "not JSON" },
]) {
  test(`unhealthy probe ${JSON.stringify(reply)} is not readiness`, async () => {
    replies.set("/health", reply)
    const plugin = await hooks()
    await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
    const output = { system: [] }
    await plugin["experimental.chat.system.transform"]({ sessionID: "s" }, output)
    expect(output.system).toEqual([])
    expect(requests.map((r) => r.path)).toEqual(["/health"])
    expect(spawn).not.toHaveBeenCalled()
  })
}

for (const raw of ["not JSON", "null", "[]"]) {
  test(`malformed successful response ${raw} is a visible failure`, async () => {
    const plugin = await hooks()
    replies.set("/search", { status: 200, raw })
    expect(await plugin.tool.memory_search.execute({ query: "q" })).toContain("非法 JSON 对象")
  })
}

test("connection failure spawns once and waits for a healthy probe", async () => {
  let probes = 0
  spyOn(globalThis, "fetch").mockImplementation(async () => {
    probes++
    if (probes === 1) throw new Error("connection refused")
    return new Response(JSON.stringify({ ok: probes >= 3 }), { status: probes >= 3 ? 200 : 503 })
  })
  spawn.mockImplementation(() => ({ stdout: undefined, stderr: undefined, kill: mock(() => {}) }))
  spyOn(Bun, "sleep").mockImplementation(async () => {})
  await hooks()
  expect(spawn).toHaveBeenCalledTimes(1)
  expect(probes).toBe(3)
})

test("401 stops subsequent data transmission", async () => {
  const plugin = await hooks()
  replies.set("/search", { status: 401, data: { error: "unauthorized" } })
  expect(await plugin.tool.memory_search.execute({ query: "q" })).toContain("失败 401")
  expect(await plugin.tool.memory_conflicts.execute({})).toContain("失败 401")
  expect(requests.map((r) => r.path)).toEqual(["/health", "/search"])
})

test("failed miss reports do not mark the query as successfully reported", async () => {
  process.env.MEMORY_PIPELINE = "legacy"
  const plugin = await hooks()
  replies.set("/miss", { status: 503, data: { error: "queue full" } })
  await plugin.tool.log_search.execute({ query: "q" })
  await new Promise(setImmediate)
  replies.set("/miss", { status: 200, data: { queued: 1 } })
  await plugin.tool.log_search.execute({ query: "q" })
  await new Promise(setImmediate)
  await plugin.tool.log_search.execute({ query: "q" })
  expect(requests.filter((r) => r.path === "/miss")).toHaveLength(2)
})

for (const status of [200, 503]) {
  test(`capture feedback requires an acknowledged observe (${status})`, async () => {
    const plugin = await hooks()
    replies.set("/observe", { status, data: status === 200 ? { unit_id: 0 } : { error: "unavailable" } })
    replies.set("/search", { status: 200, data: { context: "project fact", retrieval_id: 0 } })
    await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
    const output = { system: [] as string[] }
    await plugin["experimental.chat.system.transform"]({ sessionID: "s" }, output)
    expect(output.system[0]).toContain("project fact")
    await plugin.event({ event: { type: "message.updated", properties: {
      info: { id: "m", role: "assistant", sessionID: "s" },
    } } })
    await plugin.event({ event: { type: "message.part.updated", properties: {
      part: { id: "p", type: "text", text: "answer", sessionID: "s", messageID: "m" },
    } } })
    await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
    await plugin.dispose()
    const observed = requests.filter((r) => r.path === "/observe")
    if (status === 200) {
      expect(observed).toHaveLength(1)
      expect(observed[0].body.user_text).toBe("q")
      expect(observed[0].body.assistant_text).toBe("answer")
      expect(observed[0].body.request_id).toMatch(ID)
      expect(observed[0].requestId).toBe(observed[0].body.request_id)
      expect(requests.filter((r) => r.path === "/feedback")).toHaveLength(1)
      expect(requests.filter((r) => r.path === "/feedback")[0].body.request_id).toMatch(ID)
    } else {
      expect(observed.length).toBeGreaterThan(1)
      expect(new Set(observed.map((r) => r.body.request_id)).size).toBe(1)
      expect(observed.every((r) => r.body.user_text === "q" && r.body.assistant_text === "answer")).toBe(true)
      expect(requests.filter((r) => r.path === "/feedback")).toHaveLength(0)
    }
    expect(requests.at(-1)?.path).toBe("/save")
  })
}

test("accepted 503 is delivery, not a second observe, and still sends feedback", async () => {
  const plugin = await hooks()
  replies.set("/observe", { status: 503, data: { error: "容量", accepted: true, unit_id: 4, pending: true } })
  replies.set("/search", { status: 200, data: { context: "fact", retrieval_id: 9 } })
  await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
  await plugin["experimental.chat.system.transform"]({ sessionID: "s" }, { system: [] })
  await plugin.event({ event: { type: "message.updated", properties: {
    info: { id: "m", role: "assistant", sessionID: "s" },
  } } })
  await plugin.event({ event: { type: "message.part.updated", properties: {
    part: { id: "p", type: "text", text: "answer", sessionID: "s", messageID: "m" },
  } } })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
  await plugin.dispose()
  const observed = requests.filter((r) => r.path === "/observe")
  expect(observed).toHaveLength(1)
  expect(observed[0].body.request_id).toMatch(ID)
  const feedback = requests.filter((r) => r.path === "/feedback")
  expect(feedback).toHaveLength(1)
  expect(feedback[0].body).toMatchObject({ retrieval_id: 9, question: "q", answer: "answer" })
  expect(feedback[0].body.request_id).toMatch(ID)
  expect(feedback[0].requestId).toBe(feedback[0].body.request_id)
})

test("timeout retries the same observe id and does not mint another", async () => {
  process.env.MEMORY_BRIDGE_TIMEOUT_MS = "30"
  process.env.MEMORY_BRIDGE_ATTEMPTS = "2"
  let observes = 0
  spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname
    const headers = new Headers(init?.headers)
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    requests.push({ path, body, requestId: headers.get("X-Request-Id") ?? undefined })
    if (path === "/health") return new Response(JSON.stringify({ ok: true }), { status: 200 })
    if (path === "/observe" && observes++ === 0) {
      // 以 TimeoutError 直接拒绝来模拟客户端超时中止。不依赖
      // AbortSignal.timeout：Bun-Windows 上 mock fetch 挂起时其定时器
      // 不触发（真实 fetch 的超时路径已用本地静默服务器验证正常）。
      // 断言意图不变：超时 → 以同一 request_id 重试。
      throw new DOMException("The operation timed out.", "TimeoutError")
    }
    if (path === "/save") return new Response(JSON.stringify({ saved: true }), { status: 200 })
    return new Response(JSON.stringify({ accepted: true, unit_id: 1, pending: true }), { status: 200 })
  })
  const plugin = await hooks()
  await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
  await plugin.event({ event: { type: "message.updated", properties: {
    info: { id: "m", role: "assistant", sessionID: "s" },
  } } })
  await plugin.event({ event: { type: "message.part.updated", properties: {
    part: { id: "p", type: "text", text: "answer", sessionID: "s", messageID: "m" },
  } } })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
  await plugin.dispose()
  const observed = requests.filter((r) => r.path === "/observe")
  expect(observed).toHaveLength(2)
  expect(observed[0].body.request_id).toBe(observed[1].body.request_id)
  expect(observed[0].requestId).toBe(observed[0].body.request_id)
})

test("fingerprint 409 does not mint another observe id or send feedback", async () => {
  process.env.MEMORY_BRIDGE_ATTEMPTS = "2"
  replies.set("/observe", { status: 409, data: { error: "request_id already bound" } })
  const plugin = await hooks()
  await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
  await plugin.event({ event: { type: "message.updated", properties: {
    info: { id: "m", role: "assistant", sessionID: "s" },
  } } })
  await plugin.event({ event: { type: "message.part.updated", properties: {
    part: { id: "p", type: "text", text: "answer", sessionID: "s", messageID: "m" },
  } } })
  await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
  await plugin.dispose()
  const observed = requests.filter((r) => r.path === "/observe")
  expect(observed).toHaveLength(1)
  expect(observed[0].body.request_id).toMatch(ID)
  expect(requests.filter((r) => r.path === "/feedback")).toHaveLength(0)
  const second = await hooks()
  await second.dispose()
  expect(requests.filter((r) => r.path === "/observe")).toHaveLength(1)
})

test("a new plugin instance replays an unacked outbox id instead of creating another", async () => {
  process.env.MEMORY_BRIDGE_ATTEMPTS = "1"
  replies.set("/observe", { status: 0, data: { error: "down" } })
  const first = await hooks()
  await first["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
  await first.event({ event: { type: "message.updated", properties: {
    info: { id: "m", role: "assistant", sessionID: "s" },
  } } })
  await first.event({ event: { type: "message.part.updated", properties: {
    part: { id: "p", type: "text", text: "answer", sessionID: "s", messageID: "m" },
  } } })
  await first.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
  await first.dispose()
  const firstIds = requests.filter((r) => r.path === "/observe").map((r) => r.body.request_id)
  expect(new Set(firstIds).size).toBe(1)
  const firstId = firstIds[0]
  const before = requests.length
  replies.set("/observe", { status: 200, data: { accepted: true, unit_id: 3, pending: true } })
  const second = await hooks()
  await second.dispose()
  const replayed = requests.slice(before).filter((r) => r.path === "/observe")
  expect(replayed.length).toBeGreaterThan(0)
  expect(replayed.every((r) => r.body.request_id === firstId)).toBe(true)
  expect(replayed[0].body).toMatchObject({ user_text: "q", assistant_text: "answer" })
})

for (const role of ["assistant", "user", "unknown"]) {
  test(`capture keeps latest parts but only confirmed assistant text (${role})`, async () => {
    const plugin = await hooks()
    await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "q" }] })
    // Parts may precede role metadata; same part updates replace, different parts coexist.
    for (const [id, text] of [["a", "draft"], ["b", "second"], ["a", "first"], ["cleared", "stale"], ["cleared", ""]]) {
      await plugin.event({ event: { type: "message.part.updated", properties: {
        part: { id, type: "text", text, sessionID: "s", messageID: "m" },
      } } })
    }
    if (role !== "unknown") {
      await plugin.event({ event: { type: "message.updated", properties: {
        info: { id: "m", role, sessionID: "s" },
      } } })
    }
    await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
    // A late update after idle must not contaminate the next turn.
    await plugin.event({ event: { type: "message.part.updated", properties: {
      part: { id: "late", type: "text", text: "stale", sessionID: "s", messageID: "m" },
    } } })
    await plugin["chat.message"]({ sessionID: "s" }, { parts: [{ type: "text", text: "next" }] })
    await plugin.event({ event: { type: "session.idle", properties: { sessionID: "s" } } })
    await plugin.dispose()
    const observed = requests.filter((r) => r.path === "/observe")
    if (role === "assistant") {
      expect(observed).toHaveLength(1)
      expect(observed[0].body.user_text).toBe("q")
      expect(observed[0].body.assistant_text).toBe("first\n\nsecond")
      expect(observed[0].body.request_id).toMatch(ID)
    } else {
      expect(observed).toHaveLength(0)
    }
  })
}

test("internal OpenCode agent sessions do not initialize the memory bridge", async () => {
  process.env.DYNAMICS_MEMORY_INTERNAL_AGENT = "1"
  try {
    const plugin = await hooks()
    expect(plugin).toEqual({})
    expect(requests).toEqual([])
    expect(spawn).not.toHaveBeenCalled()
  } finally {
    delete process.env.DYNAMICS_MEMORY_INTERNAL_AGENT
  }
})


test("trio main-session tools cannot bypass Selector or human review", async () => {
  const plugin = await hooks()
  expect(plugin.tool.memory_propose).toBeUndefined()
  expect(plugin.tool.memory_resolve).toBeUndefined()
  expect(plugin.tool.memory_diagnose).toBeUndefined()
  await plugin.tool.log_search.execute({ query: "port" })
  expect(requests.some((r) => r.path === "/miss")).toBe(false)
})
