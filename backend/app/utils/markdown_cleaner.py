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
    "mall.csdn.net", "立即使用",
    # 51CTO 特有
    "51CTO博客", "文章已被收录", "博主文章分类", "©著作权",
    "提问和评论都可以", "发布评论", "用心的回复会被更多人看到",
    # 开源中国特有
    "开源中国", "OSChina", "ai辅阅", "总结由社区平台通过AI大模型",
    # 掘金特有
    "阅读全文",
    # 博客园特有
    "posted @", "编辑 收藏 举报",
    # 通用作者/互动信息
    "原文链接：",
    # 评论/点赞/收藏/打赏残留
    "评论区", "发表评论", "写评论", "最新评论", "全部评论",
    "点赞收藏", "点赞并收藏", "一键收藏", "添加收藏",
    "点赞支持", "觉得还不错", "觉得不错", "觉得有用",
    "打赏", "扫一扫", "知道了",
    # CSDN 镜像/福利/专栏目录残留
    "您可能感兴趣", "确定要放弃", "福利倒计时", "专栏目录",
    "关注关注",
    # 公众号/微信号残留
    "公众号ID", "微信号", "扫码关注",
    # 掘金/通用站点 UI 残留
    "收藏成功", "已添加到", "点击更改",
    "AI代码助手", "立即体验", "APP内打开",
    "选择你感兴趣", "至少选择1个分类",
    "温馨提示", "沉浸阅读", "确定屏蔽该用户",
    "当前操作失败", "点击申诉",
    "微信扫码分享", "新浪微博",
    "精彩更新不错过", "加个关注",
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
    # CSDN 内部锚点链接行（独立成行的目录跳转）
    re.compile(r"^\s*\[.{1,60}\]\(https?://blog\.csdn\.net/[^)]+#[^)]+\)\s*$"),
    # CSDN 目录列表项（缩进 + 序号/列表标记 + 链接到 #anchor）
    re.compile(r"^\s*[-*]?\s*\[.+\]\(https?://.*?blog\.csdn\.net/[^)]*#"),
    # CSDN 作者主页链接（短行）
    re.compile(r"^.{0,20}\]\(https?://(?:\w+\.)?blog\.csdn\.net/[^/]*\)\s*$"),
    # CSDN 评论区链接 (#commentBox)
    re.compile(r"\]\(https?://blog\.csdn\.net/[^)]*#commentBox"),
    # CSDN 推广/广告链接
    re.compile(r"\]\(https?://kunyu\.csdn\.net/"),
    # CSDN 相关文章推荐链接（独立短行含 blog.csdn.net 链接）
    re.compile(r"^\s*\[.{1,80}\]\(https?://(?:\w+\.)?blog\.csdn\.net/"),
    # CSDN 残留片段：不完整的 markdown 链接 text](url)
    re.compile(r"^[^[]{0,30}\]\(https?://(?:\w+\.)?blog\.csdn\.net/"),
    # 「最新发布」等 CSDN 标记
    re.compile(r"^最新发布\]"),
    # 「发布于」时间戳行
    re.compile(r"^.*发布于\s*\d{4}[\-/]\d{2}[\-/]\d{2}"),
    re.compile(r'^\[.{1,30}\]\(https?://.*?/user/'),
    # 博客园系列链接行（标题 + 日期组合的短行）
    re.compile(r"^\[?\d+\..{2,40}\d{4}-\d{2}-\d{2}\]?\(?https?://www\.cnblogs\.com"),
    # 掘金/博客园作者主页链接（独立短行）
    re.compile(r"^\[.{1,20}\]\(https?://(?:juejin\.cn|www\.cnblogs\.com)/user/"),
    # 「原文链接：」独立行
    re.compile(r"^原文链接[：:]"),
    # 图片文件名标注行（如 image.jpg、xxx.png、xxx.webp）
    re.compile(r"^[\w\-. ]*\.(?:jpg|jpeg|png|gif|webp|bmp|svg|ico)\s*$", re.IGNORECASE),
    # 独立的短互动词（点赞/踩/评论/分享/收藏 单独成行）
    re.compile(r"^(?:点赞|踩|评论|分享|收藏|打赏|关注)\s*$"),
    # 「- 点赞」「- 2年前」「- 微信」等列表项
    re.compile(r"^-\s*(?:点赞|踩|评论|分享|收藏|微信|新浪微博|QQ|跳过|上一步)\s*$"),
    # 「N年前」「N个月前」等时间戳短行
    re.compile(r"^-?\s*\d+[年个月天小时分钟秒]+前\s*$"),
    # 纯标签行：「后端 人工智能」「前端 Android iOS」等（3个字以内的词 + 空格组合）
    re.compile(r"^(?:后端|前端|Android|iOS|人工智能|架构|开发工具|代码人生)(?:\s+(?:后端|前端|Android|iOS|人工智能|架构|开发工具|代码人生))*\s*$"),
    # 「!avatar」「!image」等 markdown 图片占位残留
    re.compile(r"^!(?:avatar|image)\s*$"),
    # 「0/ 1000」字数限制提示
    re.compile(r"^\d+/\s*\d+\s*$"),
    # 「暂无评论数据」
    re.compile(r"^暂无评论"),
    # 独立的「标签：」行（掘金评论区上方）
    re.compile(r"^标签[：:]\s*$"),
    # 「标点符号、链接等不计算在有效字数内」
    re.compile(r"^标点符号.*不计算"),
    # 「Ctrl + Enter」 发送按钮提示
    re.compile(r"^Ctrl\s*\+\s*Enter"),
    # 「-知道了」「-分享」「-打赏」 等带前缀的短行
    re.compile(r"^[-\s]*(?:知道了|分享|打赏|评论|举报|踩|收藏)\s*$"),
    # CSDN 残留的反斜杠行
    re.compile(r"^\\+\s*$"),
    # 「阿\_旭」等 CSDN 作者名残留（短行，含反斜杠转义）
    re.compile(r"^.{0,15}\\_"),
    # CSDN 推荐摘要片段（方括号开头，含 _斜体_ 标记的长推荐条目）
    re.compile(r"^\[.{0,15}(?:_[^_]+_).{0,200}\s*$"),
    # 残留的倒计时/占位行 「_:_ _:_」
    re.compile(r"^[_:\s]+$"),
    # 「AI应用」「AI课程」等短标签行
    re.compile(r"^(?:AI应用|AI课程|人工智能|机器学习|深度学习)\s*$"),
    # 「Machine Learning\\」等残留推荐标题行（含反斜杠换行）
    re.compile(r"^.{0,60}\\{2}\s*$"),
    # 纯域名短行（如 jiqizhixin.com）
    re.compile(r"^[a-z0-9.-]+\.[a-z]{2,6}\s*$"),
]

# UI 图标图片 URL 模式（这些图片是站点 UI 元素，不是正文内容）
_UI_IMAGE_PATTERNS = [
    r"csdnimg\.cn/release/",
    r"i-operation\.csdnimg\.cn/",
    r"img-home\.csdnimg\.cn/",
    r"csdnimg\.cn/images/",
    r"Base64-Image-Removed",
    r"avatar\.csdnimg\.cn/",
    # 掘金 UI 图标
    r"lf-web-assets\.juejin\.cn/",
    r"lf3-cdn-tos\.bytescm\.com/",
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
        "您可能感兴趣的与本文相关",
        "确定要放弃本次机会",
        "福利倒计时",
        "专栏目录",
        # 掘金特有尾部噪声
        "收藏成功",
        "AI代码助手",
        "选择你感兴趣的技术方向",
        "微信扫码分享",
        "微信公众号",
        "APP内打开",
        "温馨提示",
        "沉浸阅读",
        "确定屏蔽该用户",
        "屏蔽后，对方将不能",
        "至少选择1个分类",
        "当前操作失败",
        # 掘金相关推荐列表（标题重复出现）
        "加个关注",
        "精彩更新不错过",
        # 掘金评论/标签栏
        "评论 0",
        # 51CTO 特有尾部噪声
        "上一篇：",
        "下一篇：",
        "提问和评论都可以",
        "发布评论",
    ]

    # 从正文 1/3 位置开始找 footer（避免误截正文，又不会留太多尾部噪声）
    search_start = len(lines) // 3
    for i in range(search_start, len(lines)):
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

    # 4) 后处理：清理标题中的链接包装和残留外链
    text = _post_process(text)

    # 5) 如果清洗后太短，返回原始内容的简单清理版本
    if len(text) < 50:
        return _fallback_clean(raw)

    return text


def _post_process(text: str) -> str:
    """清洗后的后处理：清理标题链接包装、外站作者链接等。"""
    # 将外站博客链接转为纯文字（保留链接文字，去掉 URL）
    # 匹配 [text](https://blog.csdn.net/...) 等站点链接
    _SITE_LINK_RE = re.compile(
        r"\[([^\]]{1,100})\]\(https?://(?:[\w.-]*\.)?(?:csdn\.net|cnblogs\.com|juejin\.cn|51cto\.com|oschina\.net)/[^)]*\)"
    )
    text = _SITE_LINK_RE.sub(r"\1", text)

    # 清理残留的不完整 markdown 链接片段 text](url)
    text = re.sub(r"([^\[]{0,20})\]\(https?://(?:[\w.-]*\.)?(?:csdn\.net|cnblogs\.com)/[^)]*\)", r"\1", text)

    lines = text.split("\n")
    processed = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 标题行如果被链接包装了，去掉链接只留文字
        heading_match = re.match(r"^(#{1,6}\s+)\[([^\]]+)\]\(https?://[^)]+\)\s*$", stripped)
        if heading_match:
            line = heading_match.group(1) + heading_match.group(2)
        # 清理独立的外站链接行（开头25行内，非正文的短链接行）
        if i < 25 and stripped and len(stripped) < 120:
            if re.match(r"^\[.{1,60}\]\(https?://[^)]+\)\s*$", stripped):
                continue
        processed.append(line)
    return "\n".join(processed)


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
