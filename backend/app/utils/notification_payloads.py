import json


def mask_middle_text(text):
    """只保留首尾字符，中间用 * 打码。"""
    value = (text or '').strip()
    if len(value) <= 1:
        return value
    if len(value) == 2:
        return f'{value[0]}*'
    return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"


def _normalize_labels(audit_labels=None, audit_details=None):
    labels = []
    for label in (audit_labels or []):
        value = str(label).strip()
        if value and value not in labels:
            labels.append(value)

    if labels:
        return labels

    if isinstance(audit_details, dict):
        for key, value in audit_details.items():
            if value and str(value).strip() not in ('', '0', 'false', 'no'):
                text = str(key).strip()
                if text and text not in labels:
                    labels.append(text)
    elif isinstance(audit_details, str) and audit_details.strip():
        try:
            parsed = json.loads(audit_details)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if value and str(value).strip() not in ('', '0', 'false', 'no'):
                    text = str(key).strip()
                    if text and text not in labels:
                        labels.append(text)

    return labels


def build_audit_rejection_reason(*, reason=None, audit_labels=None, audit_details=None):
    """把审核结果整理成可直接展示给用户的原因文本。"""
    labels = _normalize_labels(audit_labels=audit_labels, audit_details=audit_details)
    if reason and str(reason).strip():
        return str(reason).strip()
    if labels:
        return '、'.join(labels)
    return '内容不符合社区规范'


def build_rejection_notification_content(*, post_title, source, reason=None, audit_labels=None, audit_details=None):
    """构造审核失败通知的展示文本。"""
    display_reason = build_audit_rejection_reason(
        reason=reason,
        audit_labels=audit_labels,
        audit_details=audit_details,
    )
    prefix = '机器审核' if source == 'machine' else '管理员审核'
    return f"您的帖子《{mask_middle_text(post_title)}》{prefix}未通过：{display_reason}"
