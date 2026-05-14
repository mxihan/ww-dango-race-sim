# Phoebe and Luuk Herssen Skills Design

## 目标

新增两个内置团子技能：

- 菲比（Phoebe）：50% 概率额外前进 1 格。
- 陆·赫斯（Luuk Herssen）：当自己触发推进装置时，额外前进 3 格；当自己触发阻遏装置时，额外后退 1 格。

实现应延续当前 hook-based 技能架构，保持改动小、规则清晰、容易测试。

## 推荐方案

使用现有技能钩子处理菲比，并为地块解析增加一个小的行动者地块钩子处理陆·赫斯。

菲比的规则属于行动前移动值修正，可以直接实现 `modify_roll()`。陆·赫斯的规则依赖“触发了哪种地块”和“是否由自己行动触发”，现有 `before_move` / `after_move` 无法可靠表达这个时序，因此需要在 `resolve_single_tile()` / `resolve_chained_tiles()` 中，在地块返回基础 `next_position` 后、实际应用地块移动前，给当前行动者技能一次改写地块目标位置的机会。

## 范围

包含：

- 在 `src/dango_sim/skills.py` 中新增 `PhoebeSkill` 和 `LuukHerssenSkill`。
- 在地块解析路径中新增一个只面向当前行动者的 tile modifier hook。
- 在样例配置中加入两个团子，遵循当前 `sample_config.py` 的参赛列表组织方式。
- 增加技能单测和必要的引擎集成测试。
- 如公共导出或文档列出了技能集合，则同步更新。

不包含：

- 重写技能系统为完整事件总线。
- 改变 `Booster` / `Inhibitor` 自身的通用语义。
- 改变 Bu King、排名、起点冲线、二阶段起始状态或 trace viewer 行为。
- 让陆·赫斯在被其他团子携带触发地块时生效。

## 技能规则

### Phoebe

菲比行动时，在移动值确定阶段进行一次概率判定：

- 以 50% 概率让本回合移动值 `+1`。
- 未命中概率时，移动值保持原值。
- 该效果发生在正式移动前，因此会自然影响移动路径、是否经过起点、落点地块和后续堆叠。
- 如果菲比被其他团子携带移动，不触发该技能。

建议实现为：

- `PhoebeSkill(chance=0.5, bonus=1)`
- `modify_roll(dango, roll, state, context, rng) -> int`

### Luuk Herssen

陆·赫斯只有在自己作为当前行动者触发地块时，才检查技能：

- 触发 `Booster`：在推进装置基础目标位置上额外 `+3`。
- 触发 `Inhibitor`：在阻遏装置基础目标位置上额外 `-1`。
- 触发其他地块：不改变目标位置。
- 陆·赫斯被其他团子携带落到推进装置或阻遏装置时，不触发。

例如：

- 陆·赫斯从 2 移动到 3，3 是默认 `Booster(steps=1)`：基础目标是 4，技能后目标是 7。
- 陆·赫斯从 9 移动到 10，10 是默认 `Inhibitor(steps=1)`：基础目标是 9，技能后目标是 8。

建议实现为：

- `LuukHerssenSkill(booster_bonus=3, inhibitor_penalty=1)`
- 一个新的 tile modifier hook，例如 `modify_tile_destination(dango, tile, current, next_position, state, context, rng) -> int`

## 引擎设计

`TurnContext` 需要继续承载本次行动者上下文。普通行动路径已有 `actor_id=dango_id` 传入 `move_group_to()`；地块解析需要保留这个行动者信息。

推荐的最小扩展：

- `move_group_to(group, destination, actor_id, path, bottom=False)` 调用 `resolve_tiles(group, destination, actor_id=actor_id)`。
- `resolve_tiles()`、`resolve_single_tile()`、`resolve_chained_tiles()` 接受 `actor_id`。
- 地块返回基础 `next_position` 后，调用一个内部 helper，例如 `modify_tile_destination(actor_id, group, tile, current, next_position)`。
- helper 只查看 `actor_id` 对应的技能；如果没有行动者、行动者不是普通团子、或技能没有该 hook，则返回原始 `next_position`。
- 被携带的陆·赫斯不会触发，因为当前 `actor_id` 是实际行动团子，不是陆·赫斯。

Bu King 的地块解析可以继续传入 `actor_id=BU_KING_ID` 或 `None`；由于 Bu King 没有 `LuukHerssenSkill`，不会产生额外效果。

### Single 与 Chain 模式

默认 `tile_resolution="single"`：

- 只解析陆·赫斯实际落到的第一块地块。
- 陆·赫斯技能改写后的目标位置会作为这次地块移动的最终位置。
- 技能额外移动不会再触发第二块地块。

`tile_resolution="chain"`：

- 陆·赫斯技能改写后的目标位置会成为链式解析的下一当前位置。
- 如果该位置仍有地块，继续按现有 chain 规则解析，直到无地块、未移动、冲线或达到深度上限。

## 测试设计

新增或更新测试应覆盖：

- `PhoebeSkill` 概率命中时移动值 `+1`。
- `PhoebeSkill` 概率未命中时移动值不变。
- 陆·赫斯自己触发 `Booster` 时，在基础推进后额外 `+3`。
- 陆·赫斯自己触发 `Inhibitor` 时，在基础后退后额外 `-1`。
- 其他团子携带陆·赫斯触发 `Booster` / `Inhibitor` 时，陆·赫斯技能不生效。
- 陆·赫斯触发非推进/阻遏地块时不改变该地块结果。
- 至少一个集成测试确认 single 模式不因陆·赫斯额外位移而继续解析第二块地块。
- 如果改动触及 chain 分支，增加一个 chain 模式测试确认技能改写后的落点会继续链式解析。

验证命令：

```powershell
uv run pytest
uv run python main.py --runs 20 --seed 42
```

## 兼容性与风险

主要风险是地块解析时序。陆·赫斯技能必须发生在地块基础效果之后、`apply_tile_movement()` 之前，否则会难以解释“额外前进/后退”到底叠加在哪个结果上。

另一个风险是误把被携带触发当作陆·赫斯自己触发。测试应显式覆盖该场景，并让引擎只把当前行动者技能用于 tile modifier hook。

该设计不要求变更现有地块类的行为，因此已有 `Booster`、`Inhibitor`、`SpaceTimeRift` 测试应继续成立。
