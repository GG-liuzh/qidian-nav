import hashlib
import json
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from .dependencies import DB, Current
from .schemas import Input, checked_url
from .transfer import import_personal, preview_data, unpack
from .transfer_schemas import ImportInput

router = APIRouter(prefix="/api/v1/me/bookmarks")


class BookmarkInput(Input):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    html: str = Field(min_length=1, max_length=5 * 1024 * 1024)
    folders: Literal["preserve", "flat"] = "preserve"
    duplicates: Literal["skip", "copy"] = "skip"


class BookmarkParser(HTMLParser):
    """Read Netscape bookmark exports as data; never render HTML or fetch URLs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames = []
        self.pending_folder = None
        self.capture = None
        self.entries = []
        self.folder_paths = []

    def current_path(self):
        return [frame for frame in self.frames if frame]

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("h3", "a"):
            self.capture = {"tag": tag, "attrs": attrs, "text": []}
        elif tag == "dl":
            if len(self.frames) >= 64:
                raise ValueError("书签文件层级过深。")
            self.frames.append(self.pending_folder)
            self.pending_folder = None
            if self.frames[-1]:
                self.folder_paths.append(self.current_path())

    def handle_data(self, data):
        if self.capture:
            self.capture["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "dl":
            if self.frames:
                self.frames.pop()
        elif self.capture and tag == self.capture["tag"]:
            item = self.capture
            self.capture = None
            title = " ".join("".join(item["text"]).split())
            if tag == "h3":
                toolbar = item["attrs"].get("personal_toolbar_folder", "").lower() == "true"
                self.pending_folder = None if toolbar else title or "未命名文件夹"
            else:
                self.entries.append({"name": title, "url": item["attrs"].get("href", "").strip(), "path": self.current_path()})


def short_name(value, length=80):
    if len(value) <= length:
        return value
    return value[:length-9] + "…" + hashlib.sha256(value.encode()).hexdigest()[:8]


def build_bundle(data):
    if "netscape-bookmark-file" not in data.html[:2000].lower():
        raise HTTPException(422, "请选择 Chrome 浏览器导出的 HTML 书签文件。")
    parser = BookmarkParser()
    try:
        parser.feed(data.html)
        parser.close()
    except Exception:
        raise HTTPException(422, "书签文件结构无法解析，请重新从浏览器导出。") from None
    if not parser.entries:
        raise HTTPException(422, "这个文件没有可识别的书签。")
    if len(parser.entries) > 2000:
        raise HTTPException(422, "单次最多导入 2,000 个书签，请分批导出。")
    categories, resources, examples = {}, [], []
    skipped, duplicate_file, deep_folders = 0, 0, 0
    seen_urls = set()

    def category_for(path):
        if data.folders == "flat":
            return None
        parent = None
        if len(path) > 8:
            path = path[:7] + [" / ".join(path[7:])]
        for depth, name in enumerate(path):
            identifier = hashlib.sha256(("folder:"+json.dumps(path[:depth+1], ensure_ascii=False)).encode()).hexdigest()[:32]
            if identifier not in categories:
                categories[identifier] = {"id": identifier, "name": short_name(name), "parent_id": parent, "sort_order": len(categories)}
            parent = identifier
        return parent

    for path in parser.folder_paths:
        category_for(path)
    for index, entry in enumerate(parser.entries):
        try:
            checked_url(entry["url"])
            if len(entry["url"]) > 4096:
                raise ValueError
        except ValueError:
            skipped += 1
            continue
        if entry["url"] in seen_urls:
            duplicate_file += 1
            if data.duplicates == "skip":
                continue
        seen_urls.add(entry["url"])
        if len(entry["path"]) > 8:
            deep_folders += 1
        name = entry["name"] or urlsplit(entry["url"]).hostname or "未命名书签"
        identifier = hashlib.sha256(f"bookmark:{index}:{entry['url']}".encode()).hexdigest()[:32]
        category = category_for(entry["path"])
        description = "原书签路径：" + " / ".join(entry["path"]) if entry["path"] else ""
        if len(name) > 120:
            description = "原书签标题：" + name + "\n" + description
        resources.append({"id": identifier, "type": "bookmark", "name": short_name(name, 120), "category_id": category, "description": description[:2000], "tags": ["Chrome导入"], "is_public": False, "endpoints": [{"id": identifier, "url": entry["url"], "environment_id": None, "enabled": True}]})
        if len(examples) < 12:
            examples.append({"name": name, "url": entry["url"], "path": " / ".join(entry["path"])})
    if len(categories) > 2000:
        raise HTTPException(422, "文件夹数量超过 2,000 个，请分批整理。")
    if not resources:
        raise HTTPException(422, "没有可导入的 HTTP/HTTPS 书签；浏览器内部页、脚本地址和本地文件地址会被跳过。")
    package_id = hashlib.sha256(("chrome-bookmarks-v1:"+data.folders+":"+data.duplicates+":"+data.html).encode()).hexdigest()
    package = {"format": "qidian-personal-v1", "package_id": package_id, "created_at": "", "categories": list(categories.values()), "environments": [], "resources": resources}
    return package, {"read": len(parser.entries), "skipped_invalid": skipped, "duplicates_in_file": duplicate_file, "flattened_deep_folders": deep_folders, "examples": examples}


@router.post("/preview")
def preview_bookmarks(data: BookmarkInput, db: DB, actor: Current):
    package, stats = build_bundle(data)
    bundle = unpack(ImportInput(package=package, duplicates=data.duplicates))
    return {**preview_data(db, actor, bundle), **stats}


@router.post("/import")
def import_bookmarks(data: BookmarkInput, request: Request, db: DB, actor: Current):
    package, stats = build_bundle(data)
    # Importing bookmarks must not reset an existing user's theme or personal preferences.
    result = import_personal(ImportInput(package=package, duplicates=data.duplicates), request, db, actor, restore_preferences=False)
    return {**result, **{key: value for key, value in stats.items() if key != "examples"}}
