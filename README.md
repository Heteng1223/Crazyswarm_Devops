### 脚本使用文档 — update_crazyflies_from_trajectory.py

- 脚本位置: `src/crazyswarm/scripts/update_crazyflies_from_trajectory.py`
- 目标文件: 默认更新 `src/crazyswarm/launch/allCrazyflies.yaml`
- 轨迹文件: JSON，键支持 `robot_N` 或 `N`，每个值为 `[ [x,y,z], ... ]`，取第一帧作为初始位置

### 功能概述
- 从轨迹 JSON 读取每个无人机的初始位置，写入 `allCrazyflies.yaml` 的 `initialPosition`
- 仅保留 JSON 中出现的 ID（默认）；可用 `--keep-missing` 保留 YAML 中其他 ID
- JSON 有、YAML 没有的 ID 会自动追加，默认 `ch=80`、`ty=defaultSingleMarker`
- 支持用 `--set` 对指定 ID 设置 `ch` 与 `ty`；未提供的字段按默认值补齐
- 参数校验严格，非法则报错并且不写入

### 命令行参数
- 必选
  - `trajectory_json`: 轨迹 JSON 的绝对路径
- 可选
  - `--set`: 配置一个或多个 ID 的 `ch/ty`，支持两种写法：
    - 重复多次传入：
      - `--set "id=3,ch=80,ty=large" --set "id=5,ch=100"`
    - 单个参数内用 “/” 分多组：
      - `--set "id=3,ch=80,ty=large/id=5,ch=100/id=1,ty=default"`
    - 键名与取值
      - `id`: 数字（必须）
      - `ch`: 80 或 100（默认 80）
      - `ty`: 仅可为 `[default, defaultSingleMarker, CF21SingleMarker, medium, large]`（默认 `defaultSingleMarker`）
    - 注意
      - `--set` 中的每个 `id` 必须存在于轨迹 JSON，否则报错并终止。
      - 同一 `id` 多次设置时，后出现的覆盖先前设置。
      - 兼容别名：`channel≈ch`、`type≈ty`
  - `--yaml`: 自定义 `allCrazyflies.yaml` 路径（默认相对脚本 `../launch/allCrazyflies.yaml`）
  - `--keep-missing`: 保留 YAML 中 JSON 未包含的 ID（默认会删除）
  - `--dry-run`: 仅打印结果，不写回文件
  - `--run-chooser`: 执行 `/desktop/sh/chooser.sh`

### 行为细节
- 更新策略
  - 从 JSON 第一帧写入 `initialPosition`，保留 YAML 原有缩进与风格
  - 未加 `--keep-missing`：仅保留 JSON 中的 ID；其余 ID 删除
  - 缺失 ID（JSON 有、YAML 无）将自动追加；默认 `ch=80`、`ty=defaultSingleMarker`，若 `--set` 指定则覆盖
  - `--set` 中未提供的字段会用默认值补齐（`ch=80`、`ty=defaultSingleMarker`）
- 校验与安全
  - `ch` 仅可为 80 或 100；`ty` 仅可为允许集合；否则报错并不写文件
  - `--set` 中 `id` 不存在于 JSON 时，报错并不写文件

### 示例
- 基本用法（仅根据 JSON 更新 `initialPosition`，并只保留 JSON 中的 ID）
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json"
```
- 多组一次传入（推荐）
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --set "id=3,ch=80,ty=large/id=5,ch=100/id=1,ty=default"
```
- 多个 `--set`（等价）
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --set "id=3,ch=80,ty=large" --set "id=5,ch=100" --set "id=1,ty=default"
```
- 保留 YAML 中额外 ID
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --keep-missing
```
- 自定义 YAML 路径
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --yaml "ros_ws\src\crazyswarm\launch\allCrazyflies.yaml"
```
- 仅查看变更
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --dry-run
```

### 错误示例（不会写文件）
- `id` 不在 JSON 中：
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --set "id=5,ch=100"
# [错误] --set 指定的 id 不存在于轨迹 JSON: [5]
```
- `ch` 非法：
```bash
python src/crazyswarm/scripts/update_crazyflies_from_trajectory.py "ros_ws\test.json" --set "id=3,ch=90"
# [错误] --set 中 ch/channel 仅支持 [80, 100]: id=3,ch=90
```

### 退出码（简要）
- 2: 轨迹 JSON 不存在
- 3: YAML 不存在
- 6: `--set` 参数格式或取值非法
- 7: `--set` 指定了不在 JSON 的 id
