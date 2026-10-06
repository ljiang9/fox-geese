#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""狐狸与鹅 (Fox and Geese)：1 只狐狸 vs 13 只鹅的不对称围堵棋。

规则（简化经典版）：
- 十字形 33 点棋盘，邻接为上下左右。
- 鹅：每回合沿邻接走一步（可前后左右）；不能吃子。
- 狐狸：每回合可沿邻接走一步，或跳过相邻的鹅落到空点，吃掉该鹅。
- 狐狸胜：鹅数 < 6（已无法围堵）；鹅胜：狐狸无合法走法。
"""
import argparse
import copy
import random
import sys

DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))

GEESE_START = (
    [(r, c) for r in range(3) for c in range(2, 5)]   # 顶部 9 点
    + [(3, 0), (3, 1), (3, 2), (3, 3)]                  # 中行左 4 点
)
FOX_START = (4, 2)


def build_points():
    pts = set()
    for r in range(7):
        for c in range(7):
            if 2 <= r <= 4 or 2 <= c <= 4:
                pts.add((r, c))
    return pts


POINTS = build_points()
assert len(POINTS) == 33

NEIGH = {p: [(p[0] + dr, p[1] + dc) for dr, dc in DIRS
             if (p[0] + dr, p[1] + dc) in POINTS] for p in POINTS}


class Game:
    def __init__(self):
        self.geese = set(GEESE_START)
        self.fox = FOX_START
        self.turn = "geese"  # 鹅先手
        self.captured = 0
        self.moves = 0

    def clone(self):
        return copy.deepcopy(self)

    # ---- 走法 ----
    def geese_moves(self):
        out = []
        for g in sorted(self.geese):
            for nb in NEIGH[g]:
                if nb != self.fox and nb not in self.geese:
                    out.append((g, nb))
        return out

    def fox_moves(self):
        """返回 (kind, src, dst[, captured])，kind: 'step' / 'jump'。"""
        out = []
        f = self.fox
        for nb in NEIGH[f]:
            if nb in self.geese:
                land = (2 * nb[0] - f[0], 2 * nb[1] - f[1])
                if land in POINTS and land != self.fox and land not in self.geese:
                    out.append(("jump", f, land, nb))
            elif nb not in self.geese:
                out.append(("step", f, nb, None))
        return out

    def apply(self, move):
        if self.turn == "geese":
            src, dst = move
            if src not in self.geese:
                raise ValueError(f"起点没有鹅: {src}")
            if (src, dst) not in self.geese_moves():
                raise ValueError(f"鹅走法非法: {src} -> {dst}")
            self.geese.discard(src)
            self.geese.add(dst)
        else:
            kind, src, dst, cap = move
            if src != self.fox:
                raise ValueError(f"狐狸不在起点: {src}")
            if move not in self.fox_moves():
                raise ValueError(f"狐狸走法非法: {move}")
            self.fox = dst
            if kind == "jump":
                self.geese.discard(cap)
                self.captured += 1
        self.moves += 1
        self.turn = "fox" if self.turn == "geese" else "geese"

    # ---- 终局 ----
    def winner(self):
        """返回 'fox' / 'geese' / None。"""
        if len(self.geese) < 6:
            return "fox"
        if not self.fox_moves():
            return "geese"
        return None

    def is_over(self):
        return self.winner() is not None


# ---- AI ----
def fox_ai(game, rng):
    moves = game.fox_moves()
    jumps = [m for m in moves if m[0] == "jump"]
    if jumps:
        return rng.choice(jumps)
    # 无吃子：优先走到鹅多的位置施压（相邻鹅数多），其次靠近最近的鹅
    def score(m):
        dst = m[2]
        adj = sum(1 for g in game.geese if g in NEIGH[dst])
        dist = min(abs(dst[0] - g[0]) + abs(dst[1] - g[1]) for g in game.geese)
        return (-adj * 10 + dist, rng.random())
    return min(moves, key=score)


def geese_ai(game, rng, recent=()):
    moves = game.geese_moves()
    # 评估三要素（按优先级）：① 走完后狐狸有无立即跳吃（重罚）；
    # ② 狐狸合法走法数（越少越好，围堵）；③ 鹅群到狐狸的平均距离
    # （越近越好，收紧包围圈，避免互绕耗到上限）。
    # recent：近期局面键，走回近期局面重罚（防原地打转）。
    def score(m):
        g2 = game.clone()
        g2.apply(m)
        fm = g2.fox_moves()
        captures = sum(1 for x in fm if x[0] == "jump")
        avg_d = sum(abs(g[0] - g2.fox[0]) + abs(g[1] - g2.fox[1])
                    for g in g2.geese) / max(1, len(g2.geese))
        rep = 50 if _pos_key(g2) in recent else 0
        return (captures * 100 + len(fm) * 10 + avg_d + rep, rng.random())
    return min(moves, key=score)


# ---- 渲染 ----
def render(game):
    grid = [["·"] * 7 for _ in range(7)]
    for r, c in POINTS:
        grid[r][c] = "．"
    for r, c in game.geese:
        grid[r][c] = "鹅"
    r, c = game.fox
    grid[r][c] = "狐"
    lines = []
    for r in range(7):
        row = []
        for c in range(7):
            row.append(grid[r][c] if (r, c) in POINTS else "  ")
        lines.append(" ".join(row))
    return "\n".join(lines)


def _pos_key(game):
    return (game.fox, frozenset(game.geese), game.turn)


def play_auto(seed=42, games=10, max_moves=600, verbose=False):
    rng = random.Random(seed)
    res = {"fox": 0, "geese": 0, "draw": 0}
    for i in range(games):
        g = Game()
        seen = {}
        recent = []
        rep_draw = False
        while not g.is_over() and g.moves < max_moves:
            if g.turn == "fox":
                g.apply(fox_ai(g, rng))
            else:
                g.apply(geese_ai(g, rng, recent))
            key = _pos_key(g)
            seen[key] = seen.get(key, 0) + 1
            recent.append(key)
            recent = recent[-8:]
            if seen[key] >= 3:  # 三次重复局面判和（标准规则）
                rep_draw = True
                break
        w = "draw" if rep_draw or not g.winner() else g.winner()
        res[w] += 1
        if verbose:
            tag = "（三次重复判和）" if rep_draw else ""
            print(f"第 {i+1}/{games} 局：{w} 胜，吃鹅 {g.captured} 只，"
                  f"用时 {g.moves} 手{tag}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="狐狸与鹅：1 狐 vs 13 鹅的围堵棋")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true", help="自动演示打印每局")
    args = ap.parse_args(argv)

    if args.auto:
        res = play_auto(args.seed, args.games, verbose=args.verbose)
        print(f"自动演示结束：共 {args.games} 局，狐狸胜 {res['fox']}，"
              f"鹅胜 {res['geese']}，平局 {res['draw']}")
        return 0

    if not sys.stdin.isatty():
        print("交互模式需要终端；无头演示请用 --auto", file=sys.stderr)
        return 2
    g = Game()
    print("狐狸与鹅：你执鹅（输入如 3,0-3,1），狐狸由 AI 走。")
    while not g.is_over():
        print(render(g))
        print(f"鹅 {len(g.geese)} 只 | 已被吃 {g.captured} 只")
        if g.turn == "geese":
            try:
                raw = input("鹅走法 (起点行,列-终点行,列)：").strip()
                a, b = raw.split("-")
                src = tuple(int(x) for x in a.split(","))
                dst = tuple(int(x) for x in b.split(","))
                g.apply((src, dst))
            except (ValueError, IndexError) as e:
                print(f"非法走法：{e}")
        else:
            mv = fox_ai(g, random.Random())
            g.apply(mv)
            kind = "跳吃" if mv[0] == "jump" else "走"
            print(f"狐狸{kind}：{mv[1]} -> {mv[2]}")
    print(render(g))
    w = g.winner()
    print("狐狸获胜！" if w == "fox" else "鹅获胜！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
