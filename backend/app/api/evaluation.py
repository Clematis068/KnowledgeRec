"""评估结果 API — 按数据集读取 reports/ 下的 CSV 文件并返回 JSON"""
import csv
import os

from flask import Blueprint, jsonify, request

evaluation_bp = Blueprint('evaluation', __name__)

REPORT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "reports", "evaluation",
)

CSV_FILES = {
    "ablation": "ablation_metrics.csv",
    "stratified": "stratified_metrics.csv",
    "coldstart_pure": "coldstart_pure_metrics.csv",
    "interest": "interest_alignment_metrics.csv",
    "behavior": "behavior_impact_metrics.csv",
    "stages": "stage_weight_summary.csv",
}

DATASET_DIRS = {
    "epinions": os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "reports", "evaluation_epinions",
    ),
    "knowledge_community_old": os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "reports", "evaluation_old_dataset",
    ),
}


def _read_csv(report_dir, filename):
    path = os.path.join(report_dir, filename)
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
    dataset = request.args.get('dataset', 'epinions')
    report_dir = DATASET_DIRS.get(dataset, REPORT_ROOT)
    data = {
        "dataset": dataset,
        "report_dir": os.path.relpath(report_dir, os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    }
    for key, filename in CSV_FILES.items():
        rows = _read_csv(report_dir, filename)
        if rows is not None:
            data[key] = rows
    return jsonify(data)
