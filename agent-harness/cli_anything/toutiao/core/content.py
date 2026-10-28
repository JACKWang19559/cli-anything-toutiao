"""Validation and text export for content read from the real Toutiao page."""
import re
from urllib.parse import urlparse

from .errors import ToutiaoError


def article_url(reference: str) -> str:
    value = reference.strip()
    if re.fullmatch(r"[0-9]{5,30}", value):
        return f"https://www.toutiao.com/article/{value}/"
    try:
        url = urlparse(value)
        valid_host = url.hostname in {"www.toutiao.com", "toutiao.com", "m.toutiao.com"}
        if url.scheme not in {"http", "https"} or not valid_host or url.username is not None or url.password is not None or url.port is not None or ':' in url.netloc:
            raise ValueError
    except ValueError:
        raise ToutiaoError("invalid_article", "请传入今日头条文章链接或纯数字文章 ID。") from None
    match = re.fullmatch(r"/(?:article/|a|i)([0-9]{5,30})/?", url.path)
    if not match:
        raise ToutiaoError("invalid_article", "仅支持 /article/ID/、/aID/、/iID/ 文章链接；热榜专题、视频和短链接请先打开并取得文章链接。")
    return f"https://www.toutiao.com/article/{match.group(1)}/"


def article_text(data: dict) -> str:
    title = str(data.get("title", ""))
    meta = " · ".join(str(data[k]) for k in ("author", "published_at") if data.get(k))
    body = str(data.get("text", "")).strip()
    return "\n\n".join(x for x in (title, meta, body, str(data.get("url", ""))) if x) + "\n"


def article_markdown(data: dict) -> str:
    title = re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", str(data.get("title", "")))
    meta = " · ".join(str(data[k]) for k in ("author", "published_at") if data.get(k))
    # Use paragraph text extracted from the article only. Images remain source links.
    body = str(data.get("markdown") or data.get("text", "")).strip()
    parts = [f"# {title}", meta, f"来源：{data.get('url', '')}", body]
    return "\n\n".join(x for x in parts if x) + "\n"
