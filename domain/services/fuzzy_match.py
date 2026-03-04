"""模糊比對演算法 — VS Code Ctrl+P 風格輕量實作."""


def fuzzy_score(pattern: str, text: str) -> int:
    """
    計算 pattern 與 text 的模糊比對分數，分數越高越相關。
    若 pattern 的所有字元無法在 text 中依序找到，回傳 -1。

    加分規則：
    - 連續字元匹配：遞增加分（5, 10, 15...），連續越長分數越高
    - 匹配首字母（text 開頭或 _ . - / 之後）：+3
    - 完全相等：+100
    """
    return fuzzy_score_positions(pattern, text)[0]


def fuzzy_score_positions(pattern: str, text: str) -> tuple[int, list[int]]:
    """
    與 fuzzy_score 相同的演算法，但額外回傳匹配字元的索引位置。
    回傳 (score, positions)；若不匹配回傳 (-1, [])。
    """
    if not pattern:
        return (0, [])

    p = pattern.lower()
    t = text.lower()

    if t == p:
        return (100 + len(p), list(range(len(p))))

    pi = 0
    score = 0
    consecutive = 0
    prev_ti = -1
    positions: list[int] = []

    for ti, ch in enumerate(t):
        if pi >= len(p):
            break
        if ch == p[pi]:
            if ti == prev_ti + 1:
                consecutive += 1
            else:
                consecutive = 1
            score += 5 * consecutive

            if ti == 0 or t[ti - 1] in "._-/ \\":
                score += 3

            score += 1
            prev_ti = ti
            positions.append(ti)
            pi += 1

    if pi < len(p):
        return (-1, [])

    return (score, positions)


def fuzzy_filter(pattern: str,
                 items: list[dict],
                 key: str = "name",
                 limit: int = 50) -> list[dict]:
    """
    對 items 列表做模糊過濾，依分數排序後回傳前 limit 筆。
    每筆 dict 會附加 '_score' 欄位。
    """
    if not pattern:
        return items[:limit]

    scored = []
    for item in items:
        s = fuzzy_score(pattern, item.get(key, ""))
        if s >= 0:
            scored.append({**item, "_score": s})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:limit]
