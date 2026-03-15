"""评估结果 API — 读取 reports/evaluation/ 下的 CSV 文件并返回 JSON"""
import csv
import os

from flask import Blueprint, jsonify

evaluation_bp = Blueprint('evaluation', __name__)

REPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "reports", "evaluation",
)

CSV_FILES = {
    "ablation": "ablation_metrics.csv",
    "interest": "interest_alignment_metrics.csv",
    "behavior": "behavior_impact_metrics.csv",
    "stages": "stage_weight_summary.csv",
}


def _read_csv(filename):
    path = os.path.join(REPORT_DIR, filename)
    if not os.path.isfile(path):
        return None
    with open(path, newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        rows = []
        for row in reader:
            parsed = {}
            for key, value in row.items():
                try:
                    parsed[key] = float(value)
                except (ValueError, TypeError):
                    parsed[key] = value
            rows.append(parsed)
        return rows


@evaluation_bp.route('/reports', methods=['GET'])
def get_reports():
    data = {}
    for key, filename in CSV_FILES.items():
        rows = _read_csv(filename)
        if rows is not None:
            data[key] = rows
    return jsonify(data)
