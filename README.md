## proxysub

> ref: https://linux.do/t/topic/1282245, 原始规则模板等来自于
> 一个用于 **Clash/Mihomo** 的“订阅拼装器”：

- 最终配置里只保留你手动写的 `proxies`（比如落地家宽 `US-Home`）
- 订阅节点通过 `proxy-providers` 引入（不把订阅节点展开写进 `proxies`）
- 自动维护 `proxy-groups.西部牛仔`（`url-test`），用于挑选 **dialer-proxy → 落地家宽** 链路最优的订阅节点
- 提供一个简单页面：上传 YAML 后生成一次性短链下载 `/xxxxxx.yaml`

> 本项目默认按 **Mihomo v1.19.17** 的行为来设计（如 `expected-status` 等字段）。

---

## 快速开始

需要 Python 3.10（见 `.python-version`）以及 [`uv`](https://github.com/astral-sh/uv)。

```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

打开：

- `http://127.0.0.1:8000/` 上传页面

---

## 接口

- `GET /`：上传页面（说明文档来自 `docs/index.md`，Markdown 渲染）
- `POST /upload`：上传 YAML，生成一次性短链
- `GET /{token}.yaml`：一次性下载链接（下载 1 次即失效；默认 60 分钟过期清理）

---

## 上传 YAML 格式（输入）

上传/`subs.yaml` 支持两种订阅写法：

### 1) 推荐：`proxy-providers` 为字典（可写全配置或只写 URL）

```yaml
proxies:
  - name: US-Home
    type: socks5
    server: 203.0.113.10
    port: 3128
    username: your_user
    password: your_pass

proxy-providers:
  订阅1: https://example.com/sub1.yaml
  订阅2:
    url: https://example.com/sub2.yaml
    interval: 3600
    health-check:
      enable: true
      url: https://www.gstatic.com/generate_204
      interval: 300
      lazy: true
```

程序会补齐缺省字段（如 `type/http`、`interval`、`health-check`、`path`）。

### 2) 兼容：`proxy-providers`/`subs` 为 URL 列表

```yaml
proxies:
  - name: US-Home
    type: socks5
    server: 203.0.113.10
    port: 3128

# 旧字段 subs 也兼容
proxy-providers:
  - https://example.com/sub1.yaml
  - https://example.com/sub2.yaml
```

这种形式下，程序会用模板里的 provider 名称（如 `订阅1/订阅2/...`）来“对号入座”；不够则自动补 `订阅N`。

---

## dialer 优化（西部牛仔）

你的目标通常是：

`本地客户端 -> (西部牛仔选出来的订阅节点) -> US-Home(落地家宽) -> 目标站点`

本项目会自动：

1. 把 `proxies` 里第一个有 `name` 的节点当作 `US-Home`（用于 dialer 配置）
2. 强制 `US-Home.dialer-proxy = 西部牛仔`
3. 确保存在 `proxy-groups.西部牛仔`（`type: url-test`，并使用所有订阅 providers）
4. 默认把 `西部牛仔` 的测速目标设置为：
   - `url: http://<US-Home.server>:<US-Home.port>/`
   - `expected-status: 407`（把 HTTP 代理的 407 视作可达）

### 上传时覆盖西部牛仔测速参数

```yaml
west-cowboy:
  url: http://203.0.113.10:3128/
  expected-status: 407
```

也支持 `west_cowboy` / `expected_status` 等写法（见源码解析逻辑）。

---

## 输出配置（生成结果）

输出 YAML 具有这些特点：

- `proxies`：只包含输入文件里的手动节点（不会把订阅节点展开写入）
- `proxy-providers`：保留并归一化（URL 来自输入）
- `proxy-groups[*].use`：凡是模板里出现了 `use` 的组，都会被同步为“所有订阅名”
- `proxy-groups` 内的 `proxies/use` 列表使用 `[]` 形式输出（flow style）
- 对于 `include-all-proxies: true` 的 proxy-group，不会额外把 `US-Home` 写进该组的 `proxies`（Mihomo 会自动包含手动节点）

---

## 项目结构

- `main.py`：FastAPI 服务、上传页面、一次性短链下载
- `templates/ryan.yaml`：基础模板（规则/分组/DNS 等）
- `proxysub/builder.py`：把输入配置应用到模板、写出最终 YAML
- `proxysub/converter.py`：核心“脚本化”逻辑（西部牛仔、dialer-proxy 等）
- `docs/index.md`：页面说明文档（Markdown）

---

## 注意事项

- 一次性短链存储在内存里：服务重启会丢失；不适合多进程/多副本部署（除非你自己改成外部存储）。
- 生成文件会写入 `temp/` 目录并在“一次性下载”后删除；未下载的文件会在过期清理时删除。
