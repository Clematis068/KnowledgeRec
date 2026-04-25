"""Post content embedding 向量索引（Faiss IndexFlatIP + IDMap，内存常驻）。

启动时懒加载：首次 search 会从 MySQL 全量拉取 content_embedding 构建索引；
后续发帖/改帖/删帖通过 add_post / remove_post 做增量维护。

设计选择：
- Faiss CPU + IndexFlatIP：帖子级规模（万级）完全够用，精确检索不需 ANN；
- normalize_L2 后的内积 == cosine，统一量纲；
- IndexIDMap 让 post_id 直接作为向量 ID，无需额外映射表；
- 进程内单例，线程安全（faiss 本身的 search 是线程安全的，这里只在写入时加锁）。
"""
import logging
import threading

import numpy as np

from app import db
from app.models.post import Post

logger = logging.getLogger(__name__)


class PostVectorIndex:

    def __init__(self):
        self._lock = threading.RLock()
        self._index = None
        self._dim = None
        self._post_ids = set()
        self._built = False

    @staticmethod
    def _faiss():
        import faiss  # 懒加载，避免冷启动强依赖
        return faiss

    # ──────────────── 构建 ────────────────

    def build(self):
        """从 MySQL 全量加载 content_embedding，构建 Faiss 索引（幂等，可重建）。"""
        with self._lock:
            faiss = self._faiss()
            rows = db.session.execute(
                db.select(Post.id, Post.content_embedding)
                .filter(Post.content_embedding.isnot(None))
            ).all()

            ids, vecs = [], []
            for pid, emb in rows:
                if not emb:
                    continue
                try:
                    v = np.asarray(emb, dtype=np.float32)
                except Exception:
                    continue
                if v.ndim != 1 or v.size < 16:
                    continue
                ids.append(int(pid))
                vecs.append(v)

            if not vecs:
                logger.warning("PostVectorIndex: 无可用 embedding，索引为空")
                self._index = None
                self._dim = None
                self._post_ids = set()
                self._built = True
                return

            dim = vecs[0].size
            # 过滤维度不一致的异常向量（极少但要防御）
            good = [(i, v) for i, v in zip(ids, vecs) if v.size == dim]
            ids = [i for i, _ in good]
            X = np.vstack([v for _, v in good]).astype(np.float32)
            faiss.normalize_L2(X)

            inner = faiss.IndexFlatIP(dim)
            index = faiss.IndexIDMap(inner)
            index.add_with_ids(X, np.asarray(ids, dtype=np.int64))

            self._index = index
            self._dim = dim
            self._post_ids = set(ids)
            self._built = True
            logger.info("PostVectorIndex 构建完成: %d 向量 × %d 维", len(ids), dim)

    def ensure_built(self):
        if not self._built:
            try:
                self.build()
            except Exception as e:
                logger.warning("PostVectorIndex 构建失败: %s", e)
                self._built = True  # 防止反复重试刷日志；后续 search 返回空

    # ──────────────── 增量维护 ────────────────

    def add_post(self, post_id, embedding):
        if embedding is None:
            return
        with self._lock:
            faiss = self._faiss()
            v = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
            if self._index is None:
                dim = v.shape[1]
                inner = faiss.IndexFlatIP(dim)
                self._index = faiss.IndexIDMap(inner)
                self._dim = dim
                self._built = True
            if v.shape[1] != self._dim:
                logger.warning("PostVectorIndex: 维度不符 (%d vs %d)，跳过 post=%s",
                               v.shape[1], self._dim, post_id)
                return
            pid = int(post_id)
            if pid in self._post_ids:
                self._index.remove_ids(np.asarray([pid], dtype=np.int64))
            faiss.normalize_L2(v)
            self._index.add_with_ids(v, np.asarray([pid], dtype=np.int64))
            self._post_ids.add(pid)

    def remove_post(self, post_id):
        with self._lock:
            pid = int(post_id)
            if self._index is None or pid not in self._post_ids:
                return
            self._index.remove_ids(np.asarray([pid], dtype=np.int64))
            self._post_ids.discard(pid)

    # ──────────────── 查询 ────────────────

    def search(self, query_vec, k=200, exclude_ids=None, candidate_ids=None):
        """返回 [(post_id, cosine_sim)]，相似度 ∈ [-1, 1]。

        若传入 candidate_ids：只在该子集中返回结果（后过滤，简单但有效）。
        若传入 exclude_ids：过滤掉这些 post_id。
        """
        self.ensure_built()
        if self._index is None or self._index.ntotal == 0 or query_vec is None:
            return []

        faiss = self._faiss()
        q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
        if q.shape[1] != self._dim:
            return []
        faiss.normalize_L2(q)

        exclude_set = {int(x) for x in (exclude_ids or ())}
        cand_set = {int(x) for x in candidate_ids} if candidate_ids else None

        # 过滤时需要超额取，避免过滤后候选不足
        over = k if (not exclude_set and cand_set is None) else min(max(k * 3, 200),
                                                                    self._index.ntotal)
        scores, ids = self._index.search(q, over)
        scores, ids = scores[0], ids[0]

        result = []
        for pid, s in zip(ids, scores):
            if pid == -1:
                continue
            pid = int(pid)
            if pid in exclude_set:
                continue
            if cand_set is not None and pid not in cand_set:
                continue
            result.append((pid, float(s)))
            if len(result) >= k:
                break
        return result

    @property
    def size(self):
        return len(self._post_ids)


post_vector_index = PostVectorIndex()
