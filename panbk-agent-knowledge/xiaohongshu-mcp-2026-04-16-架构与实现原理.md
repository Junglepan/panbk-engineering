# xiaohongshu-mcp 架构与实现原理

> 日期：2026-04-16  
> 来源：GitHub xpzouying/xiaohongshu-mcp（主实现，Go 语言，12.9k+ stars）

---

## 一、项目概述

**xiaohongshu-mcp** 是一个 MCP（Model Context Protocol）服务器，让 Claude、Cursor、Gemini CLI 等 AI 助手可以通过自然语言直接操作小红书平台。

**核心价值**：小红书没有公开 API，该项目通过 Headless Chrome 自动化模拟真实用户操作，绕过这一限制。

**典型使用场景**：
- 内容创作者自动发布图文/视频笔记
- 批量搜索、点赞、收藏、评论
- 监控特定话题下的帖子动态

---

## 二、整体架构

```
AI 客户端 (Claude / Cursor)
        │
        │ MCP 协议（HTTP POST /mcp）
        ▼
┌────────────────────────────┐
│      MCP Server Layer      │
│  /mcp  ←→  /api/v1/*       │  端口 18060
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│    XiaohongshuService      │  核心业务逻辑
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Headless Chrome (go-rod)  │  浏览器自动化
│  + Stealth 反指纹模块       │
└────────────┬───────────────┘
             │
             ▼
       小红书网页端
```

**两层并行接口**：
- `/mcp` —— 供 AI 客户端调用，遵循 MCP 协议
- `/api/v1/*` —— REST 接口，用于测试或非 MCP 集成

两个接口底层共用同一套 `XiaohongshuService` 方法。

---

## 三、技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 主语言 | Go (71%) | 核心服务 |
| 浏览器驱动 | go-rod/rod | Chrome DevTools Protocol |
| 反指纹 | go-rod/stealth | 绕过小红书检测 |
| 替代实现 | Python + Playwright + fastmcp | 另一活跃分支 |

---

## 四、关键代码结构

```
xiaohongshu-mcp/
├── main.go           # 入口，服务器初始化
├── mcp_server.go     # 注册 13 个 MCP Tool（InitMCPServer）
├── mcp_handlers.go   # MCP 工具调用的 Handler
├── handlers_api.go   # REST API Handler
├── service.go        # 核心服务层
├── browser/
│   └── browser.go    # Headless Chrome 会话管理
└── cookies/
    └── cookies.go    # Cookie 序列化/反序列化
```

**两个二进制产物**：
- `xiaohongshu-login` —— 首次登录，扫码工具
- `xiaohongshu-mcp` —— 主服务（MCP + REST）

---

## 五、认证机制

```
首次登录：
用户执行 xiaohongshu-login
  → 打开浏览器窗口
  → 用户用手机 App 扫描二维码
  → Cookie 保存至 ~/.mcp/xiaohongshu/cookies.json

后续使用：
服务器启动时读取 cookies.json
  → 注入到每次 Headless Chrome 会话
  → 无需重新登录（Cookie 有效期约 7 天）
```

**注意事项**：
- 同一账号不能在多处 Web 端同时登录，否则 Cookie 会失效
- Cookie 过期时需重新扫码，但不等于账号封禁

---

## 六、数据流全链路

```
1. 用户输入       → "帮我搜索关于护肤的笔记"
2. LLM 翻译       → mcp0_search_feeds(keywords="护肤")
3. MCP 请求       → HTTP POST /mcp {tool: search_feeds, params: {...}}
4. Handler 路由   → mcp_handlers.go 分发到对应 Handler
5. Service 调用   → XiaohongshuService.SearchFeeds()
6. 浏览器自动化   → go-rod 开启 Headless Chrome，注入 Cookie，执行搜索
7. 数据提取       → 解析 DOM，提取标题/封面/点赞数等结构化数据
8. MCP 响应       → 返回 JSON 给 AI 客户端
9. LLM 处理       → Claude 汇总结果呈现给用户
```

**关键数据依赖**（重要）：
- `feed_id` 和 `xsec_token` 必须通过 `list_feeds` 或 `search_feeds` 先获取
- 点赞、评论、获取详情等操作都依赖这两个字段
- 不能跳过发现步骤直接操作

---

## 七、暴露的 13 个 MCP Tools

### 认证管理
| Tool | 功能 |
|------|------|
| `check_login_status` | 检查当前登录状态 |
| `get_login_qrcode` | 获取登录二维码 |
| `delete_cookies` | 清除 Cookie，重置会话 |

### 内容发布
| Tool | 关键参数 |
|------|---------|
| `publish_content` | title(≤20字), content(≤1000字), images, tags?, schedule_at?, visibility? |
| `publish_with_video` | title, content, video_path(MP4/MOV/AVI), images? |

### 内容发现
| Tool | 功能 |
|------|------|
| `list_feeds` | 获取首页推荐流 |
| `search_feeds` | 关键词搜索，支持排序和类型过滤 |

### 互动操作（均需 feed_id + xsec_token）
| Tool | 功能 |
|------|------|
| `get_feed_detail` | 获取笔记详情（含评论） |
| `post_comment_to_feed` | 发表评论 |
| `reply_comment_in_feed` | 回复指定评论 |
| `like_feed` | 点赞/取消点赞 |
| `favorite_feed` | 收藏/取消收藏 |

### 用户信息
| Tool | 功能 |
|------|------|
| `user_profile` | 获取用户主页数据 |

---

## 八、多种实现对比

| 实现 | 语言 | 特点 |
|------|------|------|
| xpzouying/xiaohongshu-mcp | Go | 最成熟，稳定运行 1 年以上 |
| luyike221/xiaohongshu-mcp-python | Python | 异步支持，Playwright + fastmcp |
| rednote-mcp | Node.js | npm 包，轻量 |
| xiaohongshu-mcp-server | Python | PyPI 发布，适合快速集成 |

---

## 九、运营约束与最佳实践

**内容限制**：
- 标题最多 20 字（严格限制）
- 正文最多 1000 字
- 建议每日发布上限 50 条

**稳定性建议**：
- 避免并发操作同一账号
- Cookie 失效后及时重新登录
- 图文内容比视频更受平台算法青睐

**安全提醒**：
- 项目声明仅供学习研究使用
- 存在账号风险，请勿用于非法用途

---

## 十、与 MCP 协议的关系

MCP（Model Context Protocol）是 Anthropic 提出的开放协议，定义了 AI 助手如何调用外部工具：
- AI 客户端发现服务器暴露的 Tool 列表
- LLM 根据用户意图选择合适 Tool 并填充参数
- 服务器执行后返回结构化结果
- LLM 将结果翻译为自然语言呈现给用户

xiaohongshu-mcp 本质上是一个 **MCP 适配层**，将小红书的网页操作封装成标准化 Tool 接口，让 AI 可以像调用函数一样操作社交平台。

---

## 参考资源

- [GitHub - xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)
- [DeepWiki - 项目结构深度解析](https://deepwiki.com/xpzouying/xiaohongshu-mcp)
- [Skywork AI - 技术深度解析](https://skywork.ai/skypage/en/xiaohongshu-mcp-server-guide/1980054737602781184)
