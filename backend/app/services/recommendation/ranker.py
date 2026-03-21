"""GBDT 精排模型：sklearn GradientBoostingClassifier 封装。"""
import logging
import os
import pickle

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models"))
MODEL_PATH = os.path.join(MODEL_DIR, "gbdt_ranker.pkl")

FEATURE_NAMES = [
    "cf_score", "swing_score", "graph_score", "semantic_score",
    "knowledge_score", "hot_score",
    "recall_source_count", "tag_overlap_ratio", "tag_strength_sum",
    "domain_match", "user_stage", "post_freshness", "post_popularity",
    "region_match", "time_slot_match", "author_post_count",
    "behavior_count", "max_recall_score",
]


class GBDTRanker:
    """GBDT 二分类精排器。"""

    def __init__(self):
        self._model = None

    def is_available(self):
        return self._model is not None

    def load(self):
        if not os.path.isfile(MODEL_PATH):
            logger.info("GBDT 模型文件不存在 (%s)，将使用加权融合回退", MODEL_PATH)
            return False
        try:
            with open(MODEL_PATH, "rb") as f:
                self._model = pickle.load(f)
            logger.info("GBDT 模型加载成功: %s", MODEL_PATH)
            return True
        except Exception as e:
            logger.warning("GBDT 模型加载失败: %s", e)
            self._model = None
            return False

    def predict(self, features):
        """输出正类概率列表。"""
        if self._model is None:
            raise RuntimeError("GBDT 模型未加载")
        X = np.array(features, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return self._model.predict_proba(X)[:, 1].tolist()

    def train(self, X, y):
        """训练 GBDT，80/20 分层切分，返回评估指标。"""
        X = np.array(X, dtype=np.float64)
        y = np.array(y, dtype=np.int32)

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )

        clf = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=10,
            random_state=42,
        )
        clf.fit(X_train, y_train)
        self._model = clf

        y_pred_proba = clf.predict_proba(X_val)[:, 1]
        y_pred = clf.predict(X_val)

        auc = roc_auc_score(y_val, y_pred_proba)
        acc = accuracy_score(y_val, y_pred)

        importance = dict(zip(FEATURE_NAMES, clf.feature_importances_.tolist()))

        return {
            "auc": auc,
            "accuracy": acc,
            "feature_importance": importance,
            "train_size": len(X_train),
            "val_size": len(X_val),
            "positive_ratio_train": float(y_train.sum()) / len(y_train),
            "positive_ratio_val": float(y_val.sum()) / len(y_val),
        }

    def save(self):
        if self._model is None:
            raise RuntimeError("没有可保存的模型")
        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self._model, f)
        logger.info("GBDT 模型已保存: %s", MODEL_PATH)
