## YAML 示例

> 注意：`proxies` 至少需要 1 个节点；程序会把 `proxies` 里**第一个有 name 的节点**视为“落地家宽（US-Home）”。
>
> 示例中的 `203.0.113.0/24` 为文档保留网段（非真实地址）。

```yaml
proxies:
  - name: US-Home
    type: socks5
    server: 203.0.113.10
    port: 3128
    username: your_user
    password: your_pass
    udp: true

proxy-providers:
  订阅1: https://example.com/sub1.yaml
  订阅2:
    url: https://example.com/sub2.yaml

# 可选：覆盖“西部牛仔”的测速目标/期望状态码
west-cowboy:
  url: http://203.0.113.10:3128/
  expected-status: 407
```

## 程序行为

- 输出文件 `proxies` 只保留你上传 YAML 里的手动节点；不会把订阅链接里的节点展开写入 `proxies`。
- 输出文件会保留 `proxy-providers`；订阅 URL 来自你上传 YAML 的 `proxy-providers`（也兼容旧字段 `subs`）。
- 模板里所有带 `use` 的 proxy-group，会把它的 `use` 同步为所有订阅名（如 `[订阅1, 订阅2]`）。
- 自动确保存在 `proxy-groups.西部牛仔`（`url-test`），并将所有订阅节点纳入其中用于 dialer 选择。
- `西部牛仔.url` 默认使用 `http://<US-Home.server>:<US-Home.port>/`，并设置 `expected-status: 407`；可用 `west-cowboy` 覆盖。
- 上传后生成一次性下载短链 `/{token}.yaml`：有效期 60 分钟；下载一次后即失效并删除临时文件。
