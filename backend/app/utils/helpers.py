import numpy as np


def cosine_similarity(vec_a, vec_b):
    """计算两个向量的余弦相似度"""
    a, b = np.array(vec_a), np.array(vec_b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(np.dot(a, b) / norm)


def min_max_normalize(scores: dict) -> dict:
    """对分数字典做 min-max 归一化到 [0, 1]"""
    if not scores:
        return {}
    values = list(scores.values())
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return {k: 0.5 for k in scores}
    return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}
