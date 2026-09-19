# B01：列/读元数据（health、provider、model、agent）

> 目标：不懂 TypeScript 也能看懂这条行为在干什么。  
> 状态：`[ ]` 未学 / `[~]` 跟过 / `[x]` 能复述

---

## 0. 先忘掉语法，用生活类比

把 OpenCode 想成一家餐厅：

| 概念 | 类比 |
|---|---|
| **客户端**（TUI / 网页 / 桌面） | 顾客 |
| **HTTP API** | 点餐窗口上的菜单牌 |
| **protocol 包** | 「菜单上必须印什么」的规定（合同） |
| **server 包** | 窗口服务员（接到单，去后厨拿） |
| **core 包**（Catalog / Agent） | 后厨库存本 |
| **B01** | 顾客问：「店开着吗？今天有哪些供应商菜、哪些菜品、哪些厨师岗位？」 |

B01 **不会做菜**（不跑 AI 对话），只是 **查菜单和营业状态**。

---

## 1. B01 到底包含哪几件事

| 序号 | 顾客问的话 | 网址（HTTP） | 大概回答 |
|---|---|---|---|
| 1 | 店开着吗？ | `GET /api/health` | `{ "healthy": true }` |
| 2 | 有哪些 AI 供应商？ | `GET /api/provider` | 供应商列表 |
| 3 | 某一个供应商详情？ | `GET /api/provider/openai` 这类 | 单个供应商 |
| 4 | 有哪些模型？ | `GET /api/model` | 模型列表（Kimi、GPT…） |
| 5 | 有哪些代理角色？ | `GET /api/agent` | build / plan / explore… |

你在界面上看到的模型下拉、代理下拉，数据就来自这里（或等价内部调用）。

---

## 2. 读代码前必懂的 8 个 TypeScript / 本仓库用语

完整语法笔记见 [`typescript-for-reading.md`](./typescript-for-reading.md)（按 A/B/C/D 档）。  
下面这些会反复出现。先当「单词表」。

### 2.1 `import ... from "..."`

= 从别的文件把东西拿过来用。

```ts
import { Effect } from "effect"
```

意思：从 `effect` 这个库里拿 `Effect` 这个工具。

### 2.2 `export`

= 把这个文件里的东西公开给别人用。

```ts
export const HealthGroup = ...
```

别的文件可以 `import { HealthGroup } from "..."`。

### 2.3 `const 名字 = 值`

= 定义一个不能再改绑的名字（常量）。

### 2.4 对象 `{ key: value }`

= 一包带名字的数据，类似 Python 的 dict / JSON。

```ts
{ healthy: true }
```

### 2.5 函数 `() => 结果` 或 `function () { ... }`

= 一段可调用的逻辑。  
`() => Effect.succeed(...)` =「无参数，返回后面那个东西」。

### 2.6 `Schema`（本仓库很常见）

= **数据形状说明书**：规定「成功响应必须长什么样」。  
不是业务逻辑，是合同。

```ts
Schema.Struct({ healthy: Schema.Literal(true) })
```

意思：必须是一个对象，且 `healthy` 字段只能是字面量 `true`。

### 2.7 `Effect`（本仓库最核心的运行时风格）

把「可能异步、可能失败、可能依赖服务」的计算，写成一种可组合的描述。

你暂时只需记住三句：

| 写法 | 人话 |
|---|---|
| `Effect.succeed(x)` | 立刻成功，结果是 `x` |
| `yield* 某个Service` | 向系统「要」一个服务实例（像依赖注入） |
| `Effect.gen(function* () { ... })` | 用「可暂停的函数」把多步 Effect 串起来 |

看到 `function*` 和 `yield*` 先别慌：把它读成 **async/await 的亲戚**。

- `function*` ≈ 这个函数里可以一步步暂停
- `yield*` ≈ 等待这一步完成，拿到结果

### 2.8 `HttpApiGroup` / `HttpApiEndpoint` / `HttpApiBuilder`

| 名字 | 人话 |
|---|---|
| `HttpApiEndpoint.get("名字", "/路径", { success: ... })` | 声明一条 GET 接口 |
| `HttpApiGroup.make("组名").add(端点)` | 把多条接口收成一组 |
| `HttpApiBuilder.group(..., "组名", ...)` | **实现** 这一组接口的处理函数 |

记住分工：

- **protocol** = 只声明「有什么接口、返回什么形状」
- **server handlers** = 真正接到请求后干什么

---

## 3. 总链路（一张图记牢）

```
UI / CLI
   │  HTTP GET
   ▼
packages/protocol   ← 合同：路径 + 成功/失败形状
   │
   ▼
packages/server/handlers  ← 服务员：handle("xxx")
   │
   ├─ health     → 直接返回 { healthy: true }
   ├─ provider   → Catalog.provider.available() / get()
   ├─ model      → Catalog.model.available()
   └─ agent      → AgentV2.all()
   │
   ▼
packages/core     ← 库存：Catalog / Agent 内存状态
   │
   ▼
JSON 响应（多数还包一层 location + data）
```

---

## 4. 逐文件精读（带「这行在干嘛」）

### 4.1 Health 合同 — `packages/protocol/src/groups/health.ts`

```ts
export const HealthGroup = HttpApiGroup.make("server.health").add(
  HttpApiEndpoint.get("health.get", "/api/health", {
    success: Schema.Struct({ healthy: Schema.Literal(true) }),
  }).annotateMerge(
    OpenApi.annotations({
      identifier: "v2.health.get",
      summary: "Check server health",
      description: "Check whether the API server is ready to accept requests.",
    }),
  ),
)
```

逐段人话：

1. 建一个 API 组，名字叫 `server.health`
2. 往组里加一条：**GET** `/api/health`，内部代号 `health.get`
3. 成功时响应形状必须是 `{ healthy: true }`
4. `annotateMerge(OpenApi...)` = 给文档/OpenAPI 加说明文字（不影响运行逻辑）

**这一文件没有任何「查数据库」——它只是合同。**

---

### 4.2 Health 实现 — `packages/server/src/handlers/health.ts`

```ts
export const HealthHandler = HttpApiBuilder.group(Api, "server.health", (handlers) =>
  handlers.handle("health.get", () => Effect.succeed({ healthy: true as const })),
)
```

人话：

1. 针对 API 里的 `server.health` 这一组，注册处理器
2. 当请求命中 `health.get` 时，执行右边的函数
3. 函数返回：成功值 `{ healthy: true }`
4. `as const` = 告诉 TypeScript「healthy 的类型就是字面量 true，不是普通 boolean」——你可先忽略

**整条 B01 里最简单的一条：永远健康，不查任何东西。**  
用途：客户端启动时 ping 一下，确认 server 进程在听端口。

---

### 4.3 Provider 合同 — `packages/protocol/src/groups/provider.ts`

要点（不必逐字背）：

- `GET /api/provider` → 列出供应商
- `GET /api/provider/:providerID` → 按 ID 取一个  
  （`:providerID` = URL 路径参数，比如 `/api/provider/opencode-go`）
- 可带 Location 查询参数（哪个工作目录/工作区视角）
- 成功时用 `Location.response(...)` 包一层（见后文）
- 可能的错误：服务不可用、provider 找不到

---

### 4.4 Provider 实现 — `packages/server/src/handlers/provider.ts`

```ts
export const ProviderHandler = HttpApiBuilder.group(Api, "server.provider", (handlers) =>
  Effect.gen(function* () {
    return handlers
      .handle(
        "provider.list",
        Effect.fn(function* () {
          const catalog = yield* Catalog.Service
          return yield* response(catalog.provider.available())
        }),
      )
      .handle(
        "provider.get",
        Effect.fn(function* (ctx) {
          const catalog = yield* Catalog.Service
          const provider = yield* catalog.provider.get(ctx.params.providerID)
          if (!provider)
            return yield* new ProviderNotFoundError({ ... })
          return yield* response(Effect.succeed(provider))
        }),
      )
  }),
)
```

人话逐步：

**list：**

1. `yield* Catalog.Service` → 拿到「模型/供应商目录」服务
2. `catalog.provider.available()` → 只要「当前真正可用」的供应商（有密钥/已接入且未禁用）
3. `response(...)` → 把结果包成 `{ location, data }` 再返回

**get：**

1. 从 `ctx.params.providerID` 取出 URL 里的 ID（`ctx` = 这次请求的上下文）
2. 去 Catalog 里查
3. 查不到 → 返回「找不到」错误
4. 查到 → 同样用 `response` 包一层返回

---

### 4.5 Model 实现 — `packages/server/src/handlers/model.ts`

```ts
const catalog = yield* Catalog.Service
return yield* response(catalog.model.available())
```

人话：要 Catalog → 要「可用模型列表」→ 包 location 返回。

和 provider 几乎同一套路，只是调用 `model.available()`。

---

### 4.6 Agent 实现 — `packages/server/src/handlers/agent.ts`

```ts
return yield* response(AgentV2.Service.use((agent) => agent.all()))
```

人话：

1. 使用 AgentV2 服务
2. 调用 `all()` = 把当前已注册的 agent 全部列出来
3. 再包成 `{ location, data }`

Agent 例子：`build`（默认干活）、`plan`（只规划）、`explore`（只探索）等。

---

### 4.7 `response` 为什么多包一层 — `packages/server/src/location.ts`

```ts
export function response(data) {
  return Effect.gen(function* () {
    const location = yield* Location.Service
    return {
      location: { directory, workspaceID, project },
      data: yield* data,
    }
  })
}
```

人话：很多接口返回的不是「裸数组」，而是：

```json
{
  "location": { "directory": "C:/你的项目", "workspaceID": null, "project": "..." },
  "data": [ /* 真正的 provider/model/agent 列表 */ ]
}
```

因为 OpenCode 可以面向不同工作目录；告诉客户端「这份列表是站在哪个位置上算出来的」。

---

### 4.8 Catalog 里「available」到底过滤了什么 — `packages/core/src/catalog.ts`

关键片段（人话版）：

**`provider.available()`：**

1. 拿出全部供应商 `provider.all()`
2. 再拿当前已连接的 integrations（登录/接入状态）
3. `filter`（过滤）：只留下「算可用」的  
   - 被 disabled 的不要  
   - 需要 key 却没有、又对不上 integration 的不要  

**`model.available()`：**

1. 先算可用 provider 的 id 集合
2. 拿出全部模型
3. 过滤：所属 provider 必须可用，且 `model.enabled === true`

所以：**列表 ≠ 配置文件里写过的全部；是「此刻真能拿来用的」。**

---

### 4.9 AgentV2.all — `packages/core/src/agent.ts`

```ts
all: Effect.fn("AgentV2.all")(function* () {
  return Array.fromIterable(state.get().agents.values())
}),
```

人话：

1. `state.get()` = 读当前内存里的 agent 表
2. `.agents.values()` = 所有 agent 记录
3. 转成数组返回

这里 **不做**「隐藏 subagent」过滤（那是选默认 agent 时的逻辑）。B01 的 list 就是「注册表里有啥列啥」。

---

## 5. 一次完整请求，按时间顺序

以「网页打开模型下拉」为例：

1. 前端调用：`GET /api/model?location[directory]=...`
2. 框架根据 protocol 匹配到 `model.list`
3. `ModelHandler` 运行
4. 注入/取得当前 `Location`（哪个目录）
5. 取得该 Location 下的 `Catalog.Service`
6. `catalog.model.available()` 过滤
7. `response(...)` 包上 location
8. JSON 返回给前端
9. 前端渲染下拉选项

**全程没有：** 创建会话、调用 LLM、写消息、跑工具。

---

## 6. 和相邻行为的边界（别学飞）

| 这是 B01 | 不是 B01，以后再学 |
|---|---|
| 列有哪些模型 | 选中模型并保存到 Session → **B04** |
| 列有哪些 agent | 真正发一句话让 AI 回 → **B06** |
| health 探针 | 登录 API Key / OAuth → **S08** |
| 读 Catalog 当前快照 | Catalog 如何从网络同步模型目录（可后挖） |

---

## 7. 你怎么自学才算过关

按顺序打开这些文件（只看注释里说的那几行）：

1. `packages/protocol/src/groups/health.ts`
2. `packages/server/src/handlers/health.ts`
3. `packages/protocol/src/groups/provider.ts`（扫 endpoint 名字即可）
4. `packages/server/src/handlers/provider.ts`
5. `packages/server/src/handlers/model.ts`
6. `packages/server/src/handlers/agent.ts`
7. `packages/server/src/location.ts` 里的 `response`
8. `packages/core/src/catalog.ts` 里 `available` 两段
9. `packages/core/src/agent.ts` 里 `all`

合上电脑，用中文说一遍：

> B01 是只读查询。protocol 规定 URL 和返回形状；server handler 接到请求后，health 直接返回 true，provider/model 问 Catalog 的 available，agent 问 AgentV2.all；多数响应用 response 包成 location + data。不进对话循环。

能说顺，B01 就过了。

---

## 8. 遇到看不懂的 TS 时怎么办

| 看到 | 怎么处理 |
|---|---|
| `Effect.gen` / `yield*` | 当成「分步骤执行，每步可能异步」 |
| `Effect.fn("名字")` | 给这段逻辑起追踪名，逻辑上仍是函数 |
| `Schema.Struct` / `Schema.Array` | 数据形状说明书，先跳过细节 |
| `annotateMerge` / `OpenApi` | 文档装饰，可忽略 |
| `Types.DeepMutable` 等高级类型 | B01 完全不用懂 |
| 很长的泛型 `<A, E, R>` | 先当「这里有类型约束」，不影响理解行为 |

**学行为时，优先问「数据从哪来、去哪、改没改状态」，不要先问「这个类型参数是什么」。**

---

## 9. 一句话总结

**B01 = 给客户端提供「服务是否可用 + 当前 Location 下能用的供应商/模型/代理」的只读目录查询；是 OpenCode HTTP 面最简单的一层，用来练 protocol → server → core 的读法。**
