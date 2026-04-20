"""内容审核服务：对接阿里云百炼 LightApp 网络内容安全 API"""
import json
import logging
import re

from app.config import Config

logger = logging.getLogger(__name__)

# 审核标签类别（《网络信息内容生态治理规定》）
AUDIT_CATEGORIES = ['色情低俗', '暴力恐怖', '政治敏感', '违法犯罪', '仇恨言论', '垃圾广告']


class ContentAuditService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from alibabacloud_quanmiaolightapp20240801.client import Client as LightAppClient
            from alibabacloud_tea_openapi.models import Config as AliConfig

            self._client = LightAppClient(AliConfig(
                access_key_id=Config.ALIYUN_ACCESS_KEY_ID,
                access_key_secret=Config.ALIYUN_ACCESS_KEY_SECRET,
                endpoint=Config.ALIYUN_AUDIT_ENDPOINT,
            ))
        except ImportError:
            logger.warning("阿里云 SDK 未安装，内容审核不可用")
            self._client = None
        except Exception as e:
            logger.error("初始化阿里云内容审核客户端失败: %s", e)
            self._client = None

        return self._client

    def audit_text(self, text):
        """审核文本内容。

        返回:
            dict: {
                'passed': bool,          # 是否通过
                'labels': list[str],     # 命中的违规标签
                'details': str,          # 审核详情
            }

        未配置 / SDK 未安装 / 异常时默认放行。
        """
        if not Config.ALIYUN_ACCESS_KEY_ID or not Config.ALIYUN_ACCESS_KEY_SECRET:
            return {'passed': True, 'labels': [], 'details': '审核服务未配置'}
        if not Config.ALIYUN_AUDIT_API_KEY:
            return {'passed': True, 'labels': [], 'details': '审核API Key未配置'}

        client = self._get_client()
        if client is None:
            return {'passed': True, 'labels': [], 'details': '审核客户端不可用'}

        try:
            return self._run_audit(client, text)
        except Exception as e:
            # SDK 将 SSE 流当 JSON 解析会抛异常，但异常信息里包含完整 SSE 内容
            sse_text = str(e)
            if 'task-finished' in sse_text:
                return self._parse_sse_stream(sse_text)
            logger.error("内容审核异常: %s", sse_text[:300])
            return {'passed': True, 'labels': [], 'details': f'审核异常: {sse_text[:200]}'}

    def _run_audit(self, client, text):
        from alibabacloud_quanmiaolightapp20240801.models import (
            RunNetworkContentAuditRequest,
            RunNetworkContentAuditRequestTags,
        )

        tag_objects = [
            RunNetworkContentAuditRequestTags(tag_name=name)
            for name in AUDIT_CATEGORIES
        ]

        request = RunNetworkContentAuditRequest(
            content=text[:5000],
            tags=tag_objects,
            api_key=Config.ALIYUN_AUDIT_API_KEY,
        )

        response = client.run_network_content_audit(
            Config.ALIYUN_AUDIT_WORKSPACE_ID, request,
        )
        body = response.body
        if body is None:
            return {'passed': True, 'labels': [], 'details': '审核返回为空'}

        # 如果 SDK 能正常解析（非 SSE 场景）
        if hasattr(body, 'payload') and body.payload and body.payload.output:
            return self._parse_audit_json(body.payload.output.text)

        return {'passed': True, 'labels': [], 'details': '审核响应格式不明'}

    def _parse_sse_stream(self, sse_text):
        """从 SSE 流异常文本中提取最后一个 task-finished 事件的 output.text。

        API 返回格式：{"色情低俗":"","暴力恐怖":"1",...}
        value 为 "" 表示不命中，"1" 表示命中。

        SSE 流在异常 str(e) 中的格式：
            data:{"payload":{"output":{"text":"{\\"色情低俗\\":\\"\\",\\"暴力恐怖\\":\\"1\\"}"},...}}
        """
        # 1. 找最后一个 task-finished 对应的 data: 块
        idx = sse_text.rfind('task-finished')
        if idx < 0:
            return {'passed': True, 'labels': [], 'details': 'SSE 无 task-finished'}

        start = sse_text.rfind('data:', 0, idx)
        if start < 0:
            return {'passed': True, 'labels': [], 'details': 'SSE 找不到 data 块'}

        chunk = sse_text[start:idx + 50]

        # 2. 从 chunk 中提取 "text":"..." 的内容（双重转义的 JSON）
        m = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', chunk)
        if not m:
            return {'passed': True, 'labels': [], 'details': 'SSE text 字段缺失'}

        raw = m.group(1)
        # 解双重转义：\\" → " , \\\\ → \\
        # 先用 codecs 处理转义序列，再修复 UTF-8
        unescaped = raw.encode('utf-8').decode('unicode_escape').encode('latin-1').decode('utf-8')

        return self._parse_audit_json(unescaped)

    def _parse_audit_json(self, text):
        """解析审核 JSON 结果。

        格式：{"色情低俗":"","暴力恐怖":"1",...}
        空字符串 = 通过，"1" = 命中
        """
        try:
            parsed = json.loads(text) if isinstance(text, str) else text
        except (json.JSONDecodeError, TypeError):
            return {'passed': True, 'labels': [], 'details': f'JSON 解析失败: {str(text)[:200]}'}

        if not isinstance(parsed, dict):
            return {'passed': True, 'labels': [], 'details': str(text)[:200]}

        labels = [
            category for category, value in parsed.items()
            if value and str(value).strip() not in ('', '0', 'false', 'no')
        ]

        passed = len(labels) == 0
        return {
            'passed': passed,
            'labels': labels,
            'details': text if isinstance(text, str) else json.dumps(parsed, ensure_ascii=False),
        }


content_audit_service = ContentAuditService()
