"""
Markdown 正文清洗工具。

将 Firecrawl 抓取的原始 markdown 去除导航栏、广告、搜索栏、登录弹窗、
侧边栏推荐等噪声，只保留正文内容和正文中的图片。
"""
from __future__ import annotations

import re

# ── 各社区噪声关键词（出现在行内则删除整行） ──

_NOISE_KEYWORDS = [
    # 导航 / 站点 UI
    "搜索", "AI 搜索", "登录", "注册", "立即登录", "登录后您可以",
    "免费复制代码", "和博主大V互动", "下载海量资源", "发动态/写文章",
    "创作中心", "消息", "会员", "新客开通", "VIP",
    "立减", "新人礼包", "购物车",
    # 互动栏
    "关注博主", "举报", "一键三连", "分享到微博", "分享到微信",
    "分享到QQ", "分享到", "阅读更多", "查看更多", "展开全文",
    "点击阅读全文", "复制链接",
    # 广告 / 推广
    "官方活动", "精选推荐", "热门推荐", "推荐阅读", "为你推荐",
    "相关推荐", "更多精彩", "下载APP", "打开App",
    # CSDN 特有
    "CSDN认证", "码龄", "关注他的用户也关注", "最新文章",
    "分类专栏", "归档", "热门文章", "博主简介", "个人成就",
    "CC 4.0 BY-SA", "版权声明", "版权协议", "转载请附上",
    "文章标签", "so.csdn.net",
    "专栏收录", "订阅专栏", "篇文章",
    "一键部署", "ccmusic-database",
    # 51CTO 特有
    "51CTO博客", "文章已被收录", "博主文章分类", "©著作权",
    # 开源中国特有
    "开源中国", "OSChina", "ai辅阅", "总结由社区平台通过AI大模型",
    # 掘金特有
    "阅读全文",
]

# 整行匹配的正则噪声模式（匹配则删除整行）
_NOISE_LINE_PATTERNS = [
    # CSDN 文章元信息行：「原创 于 2024-03-16 发布·1k 阅读」
    re.compile(r"^(?:原创|最新推荐文章于|已于).*(?:发布|修改)"),
    # 纯数字行（点赞/收藏计数）：「0」「11」「25」
    re.compile(r"^\d{1,5}$"),
    # 只有「·」和数字的行：「·2.1k 阅读」
    re.compile(r"^[·\s\d.km阅读赞收藏]+$", re.IGNORECASE),
    # 「阅读N分钟」「关注」等短元信息
    re.compile(r"^阅读\d+分钟$"),
    re.compile(r"^关注$"),
    re.compile(r"^复制$"),
    re.compile(r"^原创$"),
    # 合集行 [合集 - xxx(N)]
    re.compile(r"^\[合集\s"),
    # 标签链接行 [#机器学习](https://so.csdn.net/...)
    re.compile(r"^\[#.+\]\(https?://so\.csdn\.net"),
    # CSDN 专栏/分类链接行
    re.compile(r"^\[?!\[.*专栏收录"),
    re.compile(r"\]\(https?://blog\.csdn\.net/.+/category_"),
    # CSDN 文章内目录锚点链接 - [xxx](url#_56)
    re.compile(r"^\s+-\s+\[.+\]\(https?://blog\.csdn\.net/.+#"),
]

# UI 图标图片 URL 模式（这些图片是站点 UI 元素，不是正文内容）
_UI_IMAGE_PATTERNS = [
    r"csdnimg\.cn/release/",
    r"i-operation\.csdnimg\.cn/",
    r"img-home\.csdnimg\.cn/",
    r"csdnimg\.cn/images/",
    r"Base64-Image-Removed",
    r"avatar\.csdnimg\.cn/",
]

# 预编译：匹配含 UI 图片 URL 的 markdown 图片标记（含可选外层链接）
_UI_IMG_INLINE_RE = re.compile(
    r"\[?\s*!\[[^\]]*\]\([^)]*(?:" + "|".join(_UI_IMAGE_PATTERNS) + r")[^)]*\)\s*(?:\]\([^)]*\))?"
)


def _strip_ui_images(line: str) -> str:
    """从一行中移除 UI 图标图片，保留其余文字。"""
    return _UI_IMG_INLINE_RE.sub("", line)


def _is_junk_after_strip(line: str) -> bool:
    """判断一行在剥离 UI 图片后是否只剩无意义内容。"""
    stripped = line.strip()
    if not stripped:
        return True
    # 只剩标点、空白、数字、·
    if re.match(r"^[\s·\-|,，.。、；;：:！!？?\d]+$", stripped):
        return True
    return False


def _has_noise_keyword(line: str) -> bool:
    """判断一行是否包含噪声关键词。"""
    stripped = line.strip()
    # 跳过太长的行（正文段落可能偶然含有"搜索"等词）
    if len(stripped) > 300:
        return False
    for kw in _NOISE_KEYWORDS:
        if kw in stripped:
            return True
    return False


def _matches_noise_pattern(line: str) -> bool:
    """判断一行是否匹配正则噪声模式。"""
    stripped = line.strip()
    if not stripped:
        return False
    for pat in _NOISE_LINE_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def _is_nav_link_line(line: str) -> bool:
    """判断一行是否为导航链接列表项（如 '- [博客](url)'）。"""
    stripped = line.strip()
    if not stripped.startswith("- ") and not stripped.startswith("* "):
        return False
    # 短导航项（< 60 字符，含链接）
    if len(stripped) < 80 and re.search(r"\[.{1,20}\]\(https?://", stripped):
        return True
    return False


def _find_content_start(lines: list[str], community: str) -> int:
    """找到正文开始的行索引。"""
    # 通用：找第一个 markdown 标题行（# 开头）
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and len(stripped) > 4:
            return i

    # 如果没有标题，找第一个较长的正文段落
    for i, line in enumerate(lines):
        stripped = line.strip()
        if len(stripped) > 80 and not stripped.startswith("[") and not stripped.startswith("!"):
            return i

    return 0


def _find_content_end(lines: list[str], community: str) -> int:
    """找到正文结束的行索引（不含该行）。"""
    footer_markers = [
        "登录后您可以享受",
        "登录后您可以：",
        "×立即登录",
        "关注博主即可阅读全文",
        "文章被以下专栏收录",
        "分类专栏",
        "最新评论",
        "你可能感兴趣的",
        "热门推荐",
        "为你推荐",
        "相关推荐",
        "推荐阅读",
        "相关文章",
        "猜你喜欢",
        "点赞后赠送",
        "100%+1:1还原",
    ]

    # 从后往前找 footer
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        for marker in footer_markers:
            if marker in stripped:
                return i

    return len(lines)


def clean_markdown(raw: str, community: str = "") -> str:
    """
    清洗 Firecrawl 抓取的原始 markdown，只保留正文。

    Parameters
    ----------
    raw : str
        原始 markdown 文本
    community : str
        社区标识 (csdn / cnblogs / juejin / oschina / 51cto)

    Returns
    -------
    str
        清洗后的 markdown 正文
    """
    if not raw or not raw.strip():
        return ""

    lines = raw.split("\n")

    # 1) 定位正文范围
    start = _find_content_start(lines, community)
    end = _find_content_end(lines, community)
    if end <= start:
        end = len(lines)
    lines = lines[start:end]

    # 2) 逐行过滤噪声
    cleaned = []
    for line in lines:
        # 先剥离行内 UI 图标图片
        line = _strip_ui_images(line)
        # 剥离后只剩标点/空白/数字则视为空行
        if _is_junk_after_strip(line):
            cleaned.append("")
            continue
        # 跳过导航链接行
        if _is_nav_link_line(line):
            continue
        # 跳过含噪声关键词的短行
        if _has_noise_keyword(line):
            continue
        # 跳过匹配正则噪声模式的行
        if _matches_noise_pattern(line):
            continue
        cleaned.append(line)

    # 3) 合并连续空行（最多保留 2 个）
    result = []
    blank_count = 0
    for line in cleaned:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                result.append("")
        else:
            blank_count = 0
            result.append(line)

    text = "\n".join(result).strip()

    # 4) 如果清洗后太短，返回原始内容的简单清理版本
    if len(text) < 50:
        return _fallback_clean(raw)

    return text


def _fallback_clean(raw: str) -> str:
    """最简清洗：只去掉明显的 UI 图片和导航行。"""
    lines = raw.split("\n")
    cleaned = []
    for line in lines:
        line = _strip_ui_images(line)
        if _is_junk_after_strip(line):
            cleaned.append("")
            continue
        if _is_nav_link_line(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def markdown_to_plaintext(md: str, max_length: int = 300) -> str:
    """将 markdown 转为纯文本摘要（用于 summary 字段）。"""
    text = md
    # 去掉图片
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # 去掉链接，保留文字
    text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # 去掉标题标记
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 去掉加粗/斜体
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # 去掉代码块标记
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 去掉引用标记
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    # 去掉水平线
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    # 压缩空白
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]
