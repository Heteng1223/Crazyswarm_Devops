#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "从轨迹JSON读取初始位置并更新 allCrazyflies.yaml。"
            "使用 --set 指定一个或多个ID的 ch/type（默认 ch=80, ty=defaultSingleMarker）。"
        )
    )
    parser.add_argument(
        "trajectory_json",
        help="轨迹json文件绝对路径。示例键: robot_1, robot_2 ...",
    )
    parser.add_argument(
        "--set",
        dest="sets",
        action="append",
        default=None,
        help=(
            "多组设置（可重复），格式示例: \n"
            "  --set id=3,ch=80,ty=large \n"
            "  --set id=3,ch=80,ty=large/id=5,ch=100/id=1,ty=default"
        ),
    )
    parser.add_argument(
        "--yaml",
        dest="yaml_path",
        default=None,
        help=(
            "allCrazyflies.yaml 路径；若不提供，默认相对本脚本定位到 ../launch/allCrazyflies.yaml"
        ),
    )
    parser.add_argument(
        "--keep-missing",
        action="store_true",
        help="不删除/注释 JSON 中不存在的ID（默认会删除）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印即将写入的变更，不落盘。",
    )
    parser.add_argument(
        "--run-chooser",
        action="store_true",
        help="执行 /desktop/sh/chooser.sh",
    )
    return parser.parse_args()


def load_trajectory_initial_positions(json_path: str) -> Dict[int, Tuple[float, float, float]]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    id_to_pos: Dict[int, Tuple[float, float, float]] = {}
    for key, traj in data.items():
        # 支持 key 可能为 "robot_1" 或 "1"
        m = re.match(r"^(?:robot_)?(\d+)$", str(key))
        if not m:
            continue
        rid = int(m.group(1))
        if not isinstance(traj, list) or len(traj) == 0:
            continue
        first = traj[0]
        if (
            isinstance(first, list)
            and len(first) >= 3
            and all(isinstance(x, (int, float)) for x in first[:3])
        ):
            id_to_pos[rid] = (float(first[0]), float(first[1]), float(first[2]))
    return id_to_pos


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def update_yaml_content(
    yaml_text: str,
    id_to_pos: Dict[int, Tuple[float, float, float]],
    keep_missing: bool,
    multi_sets: List[Dict[str, object]] | None = None,
) -> str:
    # 简单行级解析保持格式：基于 "- id: N" 块定位并修改 channel/initialPosition/type
    lines = yaml_text.splitlines()
    result: List[str] = []

    # 记录已有的ID顺序与起止
    blocks: List[Tuple[int, int, int]] = []  # (id, start_idx, end_idx_exclusive)
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s*-\s+id:\s*(\d+)\s*$", line)
        if m:
            rid = int(m.group(1))
            start = i
            i += 1
            # 收集到下一个以 "- id:" 开头或文件结束
            while i < len(lines):
                if re.match(r"\s*-\s+id:\s*\d+\s*$", lines[i]):
                    break
                i += 1
            end = i
            blocks.append((rid, start, end))
        else:
            i += 1

    # 建立快速访问
    existing_ids = {rid for rid, _, _ in blocks}

    # 生成需要的块顺序：以 YAML 现有顺序 + 新增的（若有）
    needed_ids_in_order: List[int] = []
    for rid, _, _ in blocks:
        if rid in id_to_pos:
            needed_ids_in_order.append(rid)
    # 若 keep_missing 为真，保留所有；否则只保留在 JSON 中的ID
    if keep_missing:
        needed_ids_in_order = [rid for rid, _, _ in blocks]

    # 构造 ID -> 块文本的映射（稍后更新字段）
    id_to_block_lines: Dict[int, List[str]] = {}
    for rid, start, end in blocks:
        id_to_block_lines[rid] = lines[start:end]

    # 准备函数：在一个块内更新/插入 channel/initialPosition/type
    def render_block(block_lines: List[str], rid: int) -> List[str]:
        # 推断缩进: 第一行 "- id: N" 的前缀缩进，以及子项缩进
        first = block_lines[0]
        prefix_match = re.match(r"(\s*)-\s+id:\s*\d+\s*$", first)
        base_indent = prefix_match.group(1) if prefix_match else ""
        child_indent = base_indent + "  "

        # 现有字段行索引
        idx_channel = idx_init = idx_type = None
        for idx in range(1, len(block_lines)):
            l = block_lines[idx]
            if re.match(rf"{re.escape(child_indent)}channel:\s*\S+\s*$", l):
                idx_channel = idx
            elif re.match(rf"{re.escape(child_indent)}initialPosition:\s*\[.*\]\s*$", l):
                idx_init = idx
            elif re.match(rf"{re.escape(child_indent)}type:\s*\S+\s*$", l):
                idx_type = idx

        # 更新 initialPosition（若 JSON 中存在该ID）
        if rid in id_to_pos:
            x, y, z = id_to_pos[rid]
            init_line = f"{child_indent}initialPosition: [{x:.6f}, {y:.6f}, {z:.6f}]"
            if idx_init is not None:
                block_lines[idx_init] = init_line
            else:
                # 插到 type 之前或末尾
                insert_at = idx_type if idx_type is not None else len(block_lines)
                block_lines.insert(insert_at, init_line)

        # 处理 --set 多组
        if multi_sets:
            for s in multi_sets:
                sid = s.get("id")
                if sid == rid:
                    # 若未给出则使用默认值 ch=80, ty=defaultSingleMarker
                    ch_val = s.get("ch")
                    if ch_val is None and "channel" in s:
                        ch_val = s.get("channel")  # 兼容别名
                    if ch_val is None:
                        ch_val = 80
                    tp_val = s.get("ty")
                    if tp_val is None and "type" in s:
                        tp_val = s.get("type")  # 兼容别名
                    if tp_val is None:
                        tp_val = "defaultSingleMarker"

                    ch_line_m = f"{child_indent}channel: {int(ch_val)}"
                    if idx_channel is not None:
                        block_lines[idx_channel] = ch_line_m
                    else:
                        block_lines.insert(1, ch_line_m)

                    tp_line_m = f"{child_indent}type: {str(tp_val)}"
                    if idx_type is not None:
                        # 重新定位
                        for j, l in enumerate(block_lines):
                            if re.match(rf"{re.escape(child_indent)}type:\s*\S+\s*$", l):
                                idx_type = j
                                break
                        block_lines[idx_type] = tp_line_m
                    else:
                        block_lines.append(tp_line_m)

        # 不再全局统一设 channel=80，只有在 --set 指定的 ID 上应用默认值

        return block_lines

    # 组装输出：只保留需要的ID（或全部保留，取决于 keep_missing）
    out_lines: List[str] = []
    # 找到 header（到第一个块之前）
    header_end = blocks[0][1] if blocks else len(lines)
    out_lines.extend(lines[:header_end])

    if keep_missing:
        for rid, start, end in blocks:
            new_block = render_block(id_to_block_lines[rid][:], rid)
            out_lines.extend(new_block)
    else:
        for rid in needed_ids_in_order:
            new_block = render_block(id_to_block_lines[rid][:], rid)
            out_lines.extend(new_block)

    # 追加 JSON 中存在但 YAML 中缺失的 ID：按升序追加
    missing_ids = sorted(set(id_to_pos.keys()) - existing_ids)
    if missing_ids:
        # 推断新增块的缩进（若已有块，则沿用其缩进；否则假定列表项缩进为两个空格）
        if blocks:
            first_block_line = lines[blocks[0][1]]
            m_pref = re.match(r"(\s*)-\s+id:\s*\d+\s*$", first_block_line)
            base_indent_new = m_pref.group(1) if m_pref else "  "
        else:
            base_indent_new = "  "
        child_indent_new = base_indent_new + "  "

        # 将 multi_sets 组织为映射，便于快速覆盖
        set_overrides: Dict[int, Dict[str, object]] = {}
        if multi_sets:
            for s in multi_sets:
                sid = int(s.get("id"))
                set_overrides[sid] = s

        for rid in missing_ids:
            x, y, z = id_to_pos[rid]
            # 默认值，若 --set 覆盖则使用覆盖值
            ch_val = 80
            ty_val = "defaultSingleMarker"
            if rid in set_overrides:
                o = set_overrides[rid]
                if o.get("ch") is not None:
                    ch_val = int(o["ch"])  # 已通过参数校验
                if o.get("ty") is not None:
                    ty_val = str(o["ty"])  # 已通过参数校验

            new_block_lines = [
                f"{base_indent_new}- id: {rid}",
                f"{child_indent_new}channel: {ch_val}",
                f"{child_indent_new}initialPosition: [{x:.6f}, {y:.6f}, {z:.6f}]",
                f"{child_indent_new}type: {ty_val}",
            ]
            out_lines.extend(new_block_lines)

    # 末尾保留原有尾注释/空行（在最后一个块之后）
    if blocks:
        tail_start = blocks[-1][2]
        out_lines.extend(lines[tail_start:])

    return "\n".join(out_lines) + ("\n" if yaml_text.endswith("\n") else "")


def try_run_chooser() -> None:
    if sys.platform.startswith("linux"):
        chooser = "/desktop/sh/chooser.sh"
        if os.path.isfile(chooser) and os.access(chooser, os.X_OK):
            try:
                subprocess.run([chooser], check=False)
            except Exception:
                pass


def main() -> int:
    args = parse_args()

    # 参数校验
    valid_channels = {80, 100}
    valid_types = {"default", "defaultSingleMarker", "CF21SingleMarker", "medium", "large"}

    # 解析 --set 多组并校验
    multi_sets: List[Dict[str, object]] | None = None
    if args.sets:
        multi_sets = []
        # 支持单个 --set 内用 '/' 分隔多组
        raw_items: List[str] = []
        for raw in args.sets:
            raw_items.extend([seg for seg in raw.split("/") if seg.strip()])
        for raw in raw_items:
            item: Dict[str, object] = {}
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            for p in parts:
                if "=" not in p:
                    print(f"[错误] --set 参数格式错误: {raw}", file=sys.stderr)
                    return 6
                k, v = p.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "id":
                    if not v.isdigit():
                        print(f"[错误] --set 中 id 必须为数字: {raw}", file=sys.stderr)
                        return 6
                    item["id"] = int(v)
                elif k in ("ch", "channel"):
                    if not v.isdigit() or int(v) not in valid_channels:
                        print(f"[错误] --set 中 ch/channel 仅支持 {sorted(valid_channels)}: {raw}", file=sys.stderr)
                        return 6
                    item["ch"] = int(v)
                elif k in ("ty", "type"):
                    if v not in valid_types:
                        print(f"[错误] --set 中 ty/type 仅支持 {sorted(valid_types)}: {raw}", file=sys.stderr)
                        return 6
                    item["ty"] = v
                else:
                    print(f"[错误] --set 不支持的键: {k}", file=sys.stderr)
                    return 6
            if "id" not in item:
                print(f"[错误] --set 必须包含 id 字段: {raw}", file=sys.stderr)
                return 6
            multi_sets.append(item)

    # 解析 YAML 路径
    if args.yaml_path:
        yaml_path = args.yaml_path
    else:
        # 相对本脚本定位到 ../launch/allCrazyflies.yaml
        script_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.normpath(os.path.join(script_dir, "..", "launch", "allCrazyflies.yaml"))

    if not os.path.isfile(args.trajectory_json):
        print(f"[错误] 轨迹JSON不存在: {args.trajectory_json}", file=sys.stderr)
        return 2
    if not os.path.isfile(yaml_path):
        print(f"[错误] YAML不存在: {yaml_path}", file=sys.stderr)
        return 3

    id_to_pos = load_trajectory_initial_positions(args.trajectory_json)
    if not id_to_pos:
        print("[警告] 未从JSON解析出任何初始位置，仍将按保持/参数要求处理。", file=sys.stderr)

    # 校验：--set 指定的 id 必须存在于 JSON（否则报错并停止写入）
    if multi_sets:
        json_ids = set(id_to_pos.keys())
        set_ids = {int(s.get("id")) for s in multi_sets if s.get("id") is not None}
        missing_from_json = sorted(set_ids - json_ids)
        if missing_from_json:
            print(
                f"[错误] --set 指定的 id 不存在于轨迹 JSON: {missing_from_json}",
                file=sys.stderr,
            )
            return 7

    yaml_text = read_text(yaml_path)
    new_yaml = update_yaml_content(
        yaml_text=yaml_text,
        id_to_pos=id_to_pos,
        keep_missing=args.keep_missing,
        multi_sets=multi_sets,
    )

    if args.dry_run:
        print(new_yaml)
    else:
        write_text(yaml_path, new_yaml)
        print(f"[信息] 已更新: {yaml_path}")

    if args.run_chooser:
        try_run_chooser()

    return 0


if __name__ == "__main__":
    sys.exit(main())


