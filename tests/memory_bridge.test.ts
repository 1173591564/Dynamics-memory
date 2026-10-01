/** Run: bun test tests/memory_bridge.test.ts
 * Real plugin hooks/HTTP adapter; only tool registration and external I/O are mocked.
 */
import { afterEach, beforeEach, expect, mock, spyOn, test } from "bun:test"

const schema: any = new Proxy(() => schema, { get: () => schema })
mock.module("@opencode-ai/plugin", () => ({
  tool: Object.assign((definition: any) => definition, { schema }),
}))
process.env.MEMORY_BRIDGE_ROLE = "main"
process.env.MEMORY_BRIDGE_TOKEN = "test-token"
const { default: bridge } = await import("../.opencode/plugin/memory-bridge.ts")

type Reply = { status: number; data?: unknown; raw?: string }
let replies: Map<string, Reply>
let requests: { path: string; body: any }[]
let spawn: ReturnType<typeof spyOn>
const hooks = () => bridge({ directory: "/unused-test-project" } as any) as Promise<any>

beforeEach(() => {
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
  spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = new URL(String(input)).pathname
    requests.push({ path, body: init?.body ? JSON.parse(String(init.body)) : undefined })
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
    expect(requests.filter((r) => r.path === "/observe").map((r) => r.body)).toEqual([
      { user_text: "q", assistant_text: "answer" },
    ])
    expect(requests.filter((r) => r.path === "/feedback")).toHaveLength(status === 200 ? 1 : 0)
    expect(requests.at(-1)?.path).toBe("/save")
  })
}

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
    expect(requests.filter((r) => r.path === "/observe").map((r) => r.body)).toEqual(
      role === "assistant" ? [{ user_text: "q", assistant_text: "first\n\nsecond" }] : [],
    )
  })
}
