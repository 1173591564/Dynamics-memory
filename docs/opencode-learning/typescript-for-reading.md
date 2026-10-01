# 读 OpenCode 用的 TypeScript 语法

目标：**读懂** `packages/` 里的代码，不是先成为 TS 高手。  
按「出现频率」排；后面行为（B02+）会反复撞到这些写法。

配套：[`B01-metadata.md`](./B01-metadata.md) · [`behaviors.md`](./behaviors.md)

---

## 怎么用这份笔记

1. 先过 **A 档**（一天内）
2. 读 B01/B02 时对照 **B 档**
3. 读 `prompt.ts` / Effect 服务时再啃 **C 档**
4. **D 档** 遇到再查，不要预习

原则：看不懂类型参数时，先追「调用了谁、返回了什么、改没改状态」。

---

## A 档 — 每天都见（必须会）

### A1 文件怎么互相引用

```ts
import { Effect } from "effect"
import { Catalog } from "@opencode-ai/core/catalog"
import { Api } from "../api"
import type { Info } from "./session"
```

| 写法 | 意思 |
|---|---|
| `import { A } from "包名"` | 从包里拿**值** A |
| `import type { A } from "..."` | 只拿**类型**，运行时不存在 |
| `"../api"` | 相对路径：上一级目录的 `api` |
| `"@opencode-ai/core/..."` | monorepo 里的工作区包 |
| `"@/tool/task"` | 本包别名路径（常指向 `src/...`） |

```ts
export const HealthHandler = ...
export interface Interface { ... }
export type ID = string
export * as SessionPrompt from "./prompt"
```

| 写法 | 意思 |
|---|---|
| `export const/function/...` | 公开给别的文件 |
| `export interface` / `export type` | 公开类型 |
| `export * as Foo from "./x"` | 把模块收成命名空间 `Foo`（本仓库很常见） |

---

### A2 变量

```ts
const x = 1          // 不能重新赋值
let y = 1            // 可以重新赋值（仓库风格更少用）
y = 2
```

本仓库偏好：尽量 `const`；要变结果时用三元或早返回，而不是到处 `let`。

---

### A3 基本类型（读注释/签名时用）

| 写法 | 意思 |
|---|---|
| `string` / `number` / `boolean` | 文本 / 数字 / 真假 |
| `true` / `false` / `null` / `undefined` | 字面量；`undefined` ≈ 没给 |
| `string[]` 或 `Array<string>` | 字符串数组 |
| `Record<string, number>` | 「字符串键 → 数字值」的字典 |
| `unknown` | 未知，用前要收窄 |
| `any` | 任意（仓库规则：**尽量别用**） |
| `void` | 函数无有意义返回值 |
| `never` | 不可能有的值（穷尽分支时） |

```ts
const name: string = "build"
const ids: string[] = ["a", "b"]
```

冒号右边是**类型标注**。很多地方会省略，靠推断。

---

### A4 对象与可选字段

```ts
const user = {
  id: "msg_1",
  agent: "build",
}

user.agent              // 点号取值（仓库偏好，少解构）

type Msg = {
  id: string
  title?: string       // ? = 可以没有
}

const a: Msg = { id: "1" }
const b: Msg = { id: "1", title: "hi" }
```

```ts
// 展开：复制并覆盖
const next = { ...user, agent: "plan" }
```

---

### A5 数组常用方法（读逻辑极重要）

```ts
const xs = [1, 2, 3]
xs.map((x) => x * 2)           // 每个变一遍 → 新数组
xs.filter((x) => x > 1)        // 留下符合的
xs.find((x) => x === 2)        // 找第一个，可能 undefined
xs.some((x) => x > 2)          // 是否存在
xs.every((x) => x > 0)         // 是否全部
xs.flatMap((x) => [x, x])      // map 再拍平
xs.slice(-2)                   // 截取
```

箭头函数 `(x) => x * 2` =「接收 x，返回 x*2」。  
多行：

```ts
xs.map((x) => {
  const y = x + 1
  return y
})
```

---

### A6 函数

```ts
// 普通函数
function add(a: number, b: number): number {
  return a + b
}

// 箭头函数（赋值给变量）
const add2 = (a: number, b: number) => a + b

// 可选参数、默认值
function f(x?: string, y = 1) {}

// 返回类型可省略（靠推断）
const g = () => ({ healthy: true as const })
```

`as const`：把值锁成最窄字面量类型。  
例：`true as const` 的类型是 `true`，不是 `boolean`。B01 health 里见过。

---

### A7 控制流（仓库风格）

```ts
// 早返回（偏好）
function foo(x: number) {
  if (x < 0) return 0
  return x * 2
}

// 三元（偏好，代替 let 赋值）
const label = ok ? "yes" : "no"

// switch
switch (part.type) {
  case "text":
    return part.text
  case "tool":
    return part.tool
  default:
    return ""
}
```

尽量少写 `else`；条件不满足就往下走。

---

### A8 字符串

```ts
const id = "opencode-go"
const msg = `Provider not found: ${id}`   // 模板字符串，${} 插值
```

---

## B 档 — 读 API / Schema / 服务接口时必会

### B1 `type` 与 `interface`

```ts
type ID = string

type Result = "stop" | "continue" | "compact"   // 联合类型：三选一

interface Interface {
  readonly prompt: (input: PromptInput) => Effect.Effect<...>
  readonly cancel: (sessionID: SessionID) => Effect.Effect<void>
}
```

| 概念 | 人话 |
|---|---|
| `type` | 给类型起别名 |
| `interface` | 描述对象有哪些字段/方法 |
| `readonly` | 只读，别改这个字段 |
| `"a" \| "b"` | 只能是 a 或 b |

读代码时：`interface` 常表示「这个 Service 对外提供哪些方法」。

---

### B2 可选链与空值合并

```ts
const name = session.agent?.name      // session.agent 为空则整体 undefined，不报错
const n = count ?? 0                 // count 是 null/undefined 时用 0
const x = flag || "default"          // flag 假值（0、""、false）也会落到默认——和 ?? 不同
```

---

### B3 类型断言与收窄

```ts
// 断言：程序员告诉编译器「相信我」
const part = value as SessionV1.ToolPart

// 类型守卫：在 filter/if 里收窄
parts.filter((p): p is SessionV1.SubtaskPart => p.type === "subtask")

if (msg.info.role === "user") {
  // 这里面 TS 知道是 user 分支
}
```

`p is Xxx` = 这个函数若返回 true，则 p 就是 Xxx 类型。

---

### B4 `satisfies`

```ts
const ops = {
  cancel,
  prompt,
} satisfies TaskPromptOps
```

意思：这个对象**必须符合** `TaskPromptOps` 的形状，但仍保留更具体的推断。  
当成「带检查的对象字面量」即可。

---

### B5 泛型（先混个眼熟）

```ts
function first<T>(xs: T[]): T | undefined {
  return xs[0]
}

Effect.Effect<成功值, 错误, 依赖>
Schema.Schema.Type<typeof Info>    // 从 Schema 推出的 TS 类型
```

`<T>` =「这里有一个可填的类型坑」。  
读的时候：把 `T` 想成「某种具体类型的占位符」，不必会自己写复杂泛型。

看到巨长的：

```ts
Effect.Effect<SessionV1.WithParts, Image.Error>
```

读成：**成功得到 WithParts；可能失败 Image.Error**。

---

### B6 模块命名空间用法（本仓库特色）

```ts
import { Session } from "@/session/session"
import { AgentV2 } from "@opencode-ai/core/agent"

Session.Service
Session.create(...)
AgentV2.Service.use((agent) => agent.all())
```

文件末尾常见：

```ts
export * as Session from "./session"
```

所以 `Session.xxx` 不是「一个叫 Session 的 class 的静态方法」这么简单，而经常是**模块命名空间**。

---

### B7 Schema（合同，不是业务）

来自 `effect` 的 Schema，用来描述/校验数据形状。

```ts
Schema.Struct({
  healthy: Schema.Literal(true),
  name: Schema.String,
  count: Schema.Number,
  nested: Schema.optional(Schema.String),
})

Schema.Array(Model.Info)
Schema.Literals(["steer", "queue"])
```

| 写法 | 人话 |
|---|---|
| `Schema.Struct({...})` | 对象形状 |
| `Schema.Literal(true)` | 必须等于这个字面量 |
| `Schema.optional(...)` | 字段可有可无（编码时常省略 undefined） |
| `Schema.Array(...)` | 数组 |
| `Schema.Literals([...])` | 枚举字符串 |

**读 protocol 时：Schema = 响应/请求长什么样。**

---

## C 档 — Effect（本仓库心脏，B01 起就会见）

把 Effect 先当成：**可组合的异步函数 + 依赖注入 + 类型化错误**。

### C1 三种基础形态

```ts
Effect.succeed(value)     // 立刻成功
Effect.fail(error)        // 立刻失败
Effect.void               // 成功但无值（代替 succeed(undefined)）
```

---

### C2 `Effect.gen` + `yield*`（当成 async/await）

```ts
Effect.gen(function* () {
  const catalog = yield* Catalog.Service
  const models = yield* catalog.model.available()
  return models
})
```

对照心理模型：

```ts
// 假想的 async 写法（不是真代码）
async function () {
  const catalog = await get(Catalog.Service)
  const models = await catalog.model.available()
  return models
}
```

| 语法 | 人话 |
|---|---|
| `function*` | 生成器函数，可在中间暂停 |
| `yield* X` | 执行 Effect X，拿出成功值；失败则整段失败 |
| `yield* Some.Service` | 从环境取出服务（DI） |

---

### C3 `Effect.fn("名字")`

```ts
const available = Effect.fn("CatalogV2.model.available")(function* () {
  ...
})
```

= 定义一个 Effect 函数，并带上追踪名 `"CatalogV2.model.available"`。  
调试/日志里会看到这个名字。逻辑上仍是「可 yield 的函数」。

`Effect.fnUntraced` = 同样，但不怎么打点。

---

### C4 `.pipe(...)` 链式加工

```ts
effect.pipe(
  Effect.map((x) => x + 1),
  Effect.catch(() => Effect.succeed(0)),
  Effect.orDie,
)
```

从左到右把值传过一串变换。类似：

```ts
f(g(h(effect)))  // 但 pipe 更易读
```

常见操作（先认名字）：

| API | 人话 |
|---|---|
| `Effect.map` | 成功值变形 |
| `Effect.flatMap` | 成功后再接另一个 Effect |
| `Effect.catch` / `catchCause` | 捕获错误 |
| `Effect.orDie` | 错误变成缺陷（别对外抛业务错时用） |
| `Effect.ignore` | 忽略结果/错误（小心用） |
| `Effect.forkIn(scope)` | 丢到后台跑 |
| `Effect.provideService` | 手动注入某个服务 |

---

### C5 Service / Layer（依赖注入）

```ts
export class Service extends Context.Service<Service, Interface>()("@opencode/v2/Agent") {}

const catalog = yield* Catalog.Service
AgentV2.Service.use((agent) => agent.all())
```

| 概念 | 人话 |
|---|---|
| `Service` | 一种可注入的能力（Catalog、Session…） |
| `Layer` | 怎么**制造**这些服务、它们依赖谁 |
| `yield* X.Service` | 我要 X |
| `Service.use(f)` | 拿到 X 后执行 f |

读业务时：看到 `yield* Foo.Service` 就去找 `Foo` 的 `Interface` 有哪些方法。

---

### C6 HttpApi 三件套（B01 核心）

```ts
// 合同（protocol）
HttpApiEndpoint.get("health.get", "/api/health", {
  success: Schema.Struct({ healthy: Schema.Literal(true) }),
})

HttpApiGroup.make("server.health").add(endpoint)

// 实现（server）
HttpApiBuilder.group(Api, "server.health", (handlers) =>
  handlers.handle("health.get", () => Effect.succeed({ healthy: true as const })),
)
```

口诀：**Endpoint 声明 → Group 打包 → Builder 实现。**

---

## D 档 — 遇到再查（先别系统学）

### D1 解构（仓库不偏好，但别人代码有）

```ts
const { a, b } = obj          // 本仓库风格指南：尽量改写成 obj.a
const [first, ...rest] = arr
```

---

### D2 class

```ts
export class Service extends Context.Service<...>()("名字") {}
export class NotFoundError extends Schema.TaggedErrorClass<...>()("NotFound", { ... }) {}
```

这里的 class 常常是 **带品牌的错误/服务标签**，不是传统 OOP 业务对象。  
见到 `new ProviderNotFoundError({...})` = 构造一个类型化错误。

---

### D3 `readonly` 数组 / const 类型参数

```ts
readonly string[]
as const
```

表示「别改我 / 类型尽量窄」。读懂「不可变意图」即可。

---

### D4 条件类型、infer、映射类型

```ts
type X = T extends string ? A : B
type Y = Schema.Schema.Type<typeof Info>
```

属于高级类型体操。  
**学习行为链路时跳过**；需要改公共 API 再学。

---

### D5 `try/catch`

仓库风格：**尽量少用**；Effect 路径用 `catch` / 类型化错误。  
若看到裸 `try/catch`，多半是边界（原生回调、第三方 SDK）。

---

### D6 装饰器、命名空间合并、枚举 `enum`

OpenCode 热路径上很少作为阅读重点。见到再搜。

---

## E. 对照表：JS/Python 经验怎么映射

| 你熟悉的 | TS/本仓库 |
|---|---|
| Python dict | 对象 `{ k: v }` |
| Python list | `T[]` |
| Python `Optional[T]` | `T \| undefined` 或 `T?` 字段 |
| `async/await` | `Effect.gen` + `yield*` |
| 依赖注入容器 | `yield* Foo.Service` / Layer |
| JSON Schema | `Schema.Struct...` |
| REST 路由定义 | `HttpApiEndpoint` |
| REST 控制器 | `HttpApiBuilder.group` + `handle` |
| 接口/Protocol | `interface Interface` |
| 包/模块 | `export * as Foo` |

---

## F. 读一段真实代码的练习模板

拿到任意函数，按顺序问：

1. **名字是什么？**（`Effect.fn("...")` 或函数名）
2. **入参有哪些字段？**（看第一个参数的类型/对象）
3. **yield\* 了哪些 Service？**（依赖谁）
4. **中间有没有写库/发事件/改文件？**（副作用）
5. **最后 return 什么？**（成功值）
6. **哪些 if 会提前失败/返回？**（错误与早退）

类型一时看不懂，先把 1–6 写在纸上；这就是「按行为读代码」。

---

## G. 建议学习顺序（和 behaviors 对齐）

| 阶段 | 语法重点 | 对着练 |
|---|---|---|
| 现在 | A 全套 + B7 Schema + C6 HttpApi + C2 gen | B01 |
| 下一步 | B1 接口、B5 泛型读法、C5 Service | B02 Session |
| 然后 | C3/C4 pipe、数组 A5、联合类型 B1 | B06 prompt/processor |
| 以后 | D 档按需 | 改 API / 写测试 |

---

## H. 一页速查（打印/置顶）

```
import / export / export * as
const · 对象 · 数组 map/filter/find
() => · function · ? · ?? · ?.
type · interface · "a"|"b" · readonly
as const · satisfies · p is T
Schema.Struct / optional / Array / Literal
Effect.succeed · Effect.gen · yield* · Effect.fn
Service · Layer · .pipe
HttpApiEndpoint · HttpApiGroup · HttpApiBuilder.handle
```

---

**记住：这份笔记是「阅读眼镜」，不是语法全书。**  
能靠它读完 B01–B06 的主路径，就算达标；写代码时再回头补细节。
