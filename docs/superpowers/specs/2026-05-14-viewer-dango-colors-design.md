# Viewer Dango Colors Design

## 目标

让 trace viewer 对所有已有团子都使用固定颜色，避免未配置团子在棋盘上显示为默认灰色。

## 推荐方案

采用固定颜色表方案，只更新 `viewer/src/colors.ts` 的 `DANGO_COLORS`。

不增加运行时 hash 颜色生成，也不改变 trace 数据结构或棋盘渲染逻辑。这样改动范围最小，颜色结果稳定，且不会影响模拟器规则、trace 生成或事件回放。

## 范围

包含：

- 为所有当前已有团子 ID 补齐固定颜色。
- 保留 `bu_king` 的特殊颜色。
- 保留未知 ID fallback 为 `#888`。
- 运行 viewer 构建验证 TypeScript/Vite 能通过。

不包含：

- 修改模拟器规则或样例参赛名单。
- 修改 trace JSON schema。
- 添加颜色配置 UI。
- 添加运行时 hash fallback。
- 重做 viewer 布局或棋子形状。

## 团子列表

颜色表需要覆盖这些 ID：

- `carlotta`
- `chisa`
- `lynae`
- `mornye`
- `aemeath`
- `shorekeeper`
- `augusta`
- `iuno`
- `phrolova`
- `changli`
- `jinhsi`
- `calcharo`
- `phoebe`
- `luuk_herssen`
- `bu_king`

这些 ID 来自当前已有技能类、样例配置和 Bu King 特殊参与者。

## 颜色原则

- 在深色 viewer 背景上保持清晰可见。
- 尽量避免相邻常用团子颜色过于接近。
- 不让整体 palette 只集中在单一色系。
- 颜色值使用稳定 hex 字符串，方便未来 trace 截图和人工辨认。

建议保留现有颜色，并补充缺失 ID：

| ID | Hex |
| --- | --- |
| `carlotta` | `#ff6b6b` |
| `chisa` | `#ffd166` |
| `lynae` | `#06d6a0` |
| `mornye` | `#8ecae6` |
| `aemeath` | `#c77dff` |
| `shorekeeper` | `#4cc9f0` |
| `augusta` | `#e74c3c` |
| `iuno` | `#3498db` |
| `phrolova` | `#1abc9c` |
| `changli` | `#2ecc71` |
| `jinhsi` | `#e67e22` |
| `calcharo` | `#9b59b6` |
| `phoebe` | `#f78fb3` |
| `luuk_herssen` | `#95a5a6` |
| `bu_king` | `#f1c40f` |

## 实现设计

`viewer/src/components/BoardView.vue` 已经通过 `dangoColor(id)` 读取 `DANGO_COLORS`，未命中时回退到 `#888`。因此实现只需要更新 `viewer/src/colors.ts`：

```ts
export const DANGO_COLORS: Record<string, string> = {
  carlotta: '#ff6b6b',
  chisa: '#ffd166',
  lynae: '#06d6a0',
  mornye: '#8ecae6',
  aemeath: '#c77dff',
  shorekeeper: '#4cc9f0',
  augusta: '#e74c3c',
  iuno: '#3498db',
  phrolova: '#1abc9c',
  changli: '#2ecc71',
  jinhsi: '#e67e22',
  calcharo: '#9b59b6',
  phoebe: '#f78fb3',
  luuk_herssen: '#95a5a6',
  bu_king: '#f1c40f',
}
```

## 验证

在 `viewer/` 目录运行：

```powershell
npm run build
```

预期结果：

- TypeScript 和 Vite 构建成功。
- `DANGO_COLORS` 包含所有已知团子 ID。
- 未知 ID fallback 行为保持不变。
