#!/usr/bin/env python3
"""Pull fresh GA4 data and build the shared growth-dashboard snapshot."""

from __future__ import annotations

import atexit
import datetime as dt
import json
import os
import pathlib
import re
import select
import subprocess
import time
from collections import defaultdict
from typing import Any
from zoneinfo import ZoneInfo


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
TZ = ZoneInfo("Asia/Kolkata")
TODAY = dt.datetime.now(TZ).date()
END = TODAY
START = END - dt.timedelta(days=89)
BUILT_AT = dt.datetime.now(TZ).isoformat(timespec="seconds")

PROPERTIES = {
    "pixelbin": {"id": "309592666", "label": "Pixelbin (Console)", "color": "#6933FA"},
    "wm": {"id": "303254358", "label": "WatermarkRemover.io", "color": "#FF7340"},
    "um": {"id": "298351464", "label": "Upscale.media", "color": "#0F9F85"},
}

PRODUCT_FLOWS = {
    "pixelbin": [
        {
            "name": "AI Image Editor",
            "slug": "ai-image-editor",
            "events": ["page_view", "GENERATION_STARTED", "GENERATION_COMPLETED", "GENERATION_FAILED"],
            "filter": ("customEvent:app_name", "ai-image-editor"),
        },
        {
            "name": "Video Generator",
            "slug": "video-generator",
            "events": ["page_view", "VIDEO_GENERATION_CLICKED", "VIDEO_GENERATED", "VIDEO_GENERATION_FAILED"],
            "filter": ("customEvent:app_name", "video-generator"),
        },
        {
            "name": "AI Image Generator",
            "slug": "ai-image-generator",
            "events": ["page_view", "GENERATE_CLICKED_IMAGE", "GENERATION_COMPLETED", "GENERATION_FAILED"],
            "filter": ("customEvent:app_name", "ai-image-generator"),
        },
        {
            "name": "Marketing Studio",
            "slug": "marketing-studio",
            "events": ["page_view", "MARKETING_STUDIO_GENERATE_CLICKED", "MARKETING_STUDIO_VIDEO_GENERATED", "MARKETING_STUDIO_VIDEO_FAILED"],
            "filter": ("customEvent:app_name", "marketing-studio"),
        },
        {
            "name": "Dynamic Image Apps",
            "slug": "dynamic-image-apps",
            "events": ["DYNAMIC_APP_FILE_UPLOAD_SUCCESS", "DYNAMIC_APP_TRANSFORMATION_TRIGGERED", "DYNAMIC_APP_TRANSFORMATION_POLLING_SUCCESS", "DYNAMIC_APP_TRANSFORMATION_FAILED"],
        },
        {
            "name": "Dynamic Video Apps",
            "slug": "dynamic-video-apps",
            "events": ["DYNAMIC_APP_FILE_UPLOAD_SUCCESS", "DYNAMIC_APP_VIDEO_GENERATION_CLICKED", "DYNAMIC_APP_VIDEO_GENERATED", "DYNAMIC_APP_VIDEO_FAILED"],
        },
        {
            "name": "Img-to-Img Playground",
            "slug": "img-to-img",
            "events": ["IMG_TO_IMG_PAGE_VIEW", "IMG_TO_IMG_GENERATE_CLICKED", "IMG_TO_IMG_TRANSFORMATION_SUCCESS", "IMG_TO_IMG_TRANSFORMATION_FAILED"],
        },
        {
            "name": "Mini Studio",
            "slug": "mini-studio",
            "events": ["page_view", "APPLY_TRANSFORMATION_CLICK", "DOWNLOAD_SINGLE", "VALIDATION_ERROR"],
            "filter": ("customEvent:app_name", "mini-studio"),
            "cacheVersion": "app-name-v2",
        },
        {
            "name": "AI Editor (Magic Studio)",
            "slug": "ai-editor",
            "events": ["page_view", "AI_EDITOR_TOOL_APPLY", "DOWNLOAD_SINGLE", "EXPORT_SHARE_FAILED"],
            "filter": ("customEvent:app_name", "ai-editor"),
            "cacheVersion": "app-name-v2",
        },
        {
            "name": "Magic Canvas",
            "slug": "magic-canvas",
            "events": ["page_view", "GENERATION_STARTED", "GENERATION_COMPLETED", "GENERATION_FAILED"],
            "filter": ("customEvent:app_name", "magic-canvas"),
        },
        {
            "name": "Batch Editor",
            "slug": "batch-editor",
            "events": ["page_view", "IMAGE_UPLOADED", "PAYMENT_POP_UP"],
            "filter": ("customEvent:app_name", "batch-editor"),
        },
        {
            "name": "AI Influencer",
            "slug": "ai-influencer",
            "events": ["page_view", "GENERATION_STARTED", "GENERATION_COMPLETED", "GENERATION_FAILED"],
            "filter": ("customEvent:app_name", "ai-influencer"),
        },
        {
            "name": "Free Watermark Remover",
            "slug": "free-watermark-remover",
            "events": ["IMG_FREE_PROPERTY_WM_PAGE_VIEW", "IMG_FREE_PROPERTY_WM_IMAGE_UPLOADED", "IMG_FREE_PROPERTY_WM_TRANSFORMATION_SUCC", "IMG_FREE_PROPERTY_WM_TRANSFORMATION_FAIL"],
        },
        {
            "name": "Free Image Upscaler",
            "slug": "free-image-upscaler",
            "events": ["IMG_FREE_PROPERTY_US_PAGE_VIEW", "IMG_FREE_PROPERTY_US_IMAGE_UPLOADED", "IMG_FREE_PROPERTY_US_TRANSFORMATION_SUCC", "IMG_FREE_PROPERTY_US_TRANSFORMATION_FAIL"],
        },
    ],
    "wm": [
        {
            "name": "Main Image Flow",
            "slug": "image-flow",
            "events": ["IMAGE_UPLOAD_ATTEMPT", "IMAGE_UPLOADED", "IMAGE_TRANSFORMED", "IMAGE_DOWNLOAD_CLICK"],
        },
        {
            "name": "Upload Health",
            "slug": "upload-health",
            "events": ["IMAGE_UPLOAD_ATTEMPT", "IMAGE_UPLOADED", "IMAGE_UPLOAD_FAILED", "IMAGE_TRANSFORMATION_FAILED"],
        },
    ],
    "um": [
        {
            "name": "Main Image Flow",
            "slug": "image-flow",
            "events": ["IMAGE_UPLOAD_ATTEMPT", "IMAGE_UPLOADED", "IMAGE_TRANSFORMED", "IMAGE_DOWNLOAD_CLICK"],
        },
        {
            "name": "Upload Health",
            "slug": "upload-health",
            "events": ["IMAGE_UPLOAD_ATTEMPT", "IMAGE_UPLOADED", "IMAGE_UPLOAD_FAILED", "IMAGE_TRANSFORMATION_FAILED"],
        },
    ],
}


AI_FUNNEL_MAP = {
    "video-generator": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Generate clicked", "events": ["DYNAMIC_APP_VIDEO_GENERATION_CLICKED"], "kind": "action"},
        {"label": "Video generated", "events": ["DYNAMIC_APP_VIDEO_GENERATED"], "kind": "success"},
        {"label": "Limit gate", "events": ["DYNAMIC_APP_DAILY_LIMIT_EXCEEDED", "DYNAMIC_APP_VIDEO_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "watermark-remover": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_FREE_PROPERTY_WM_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Transform success", "events": ["IMG_FREE_PROPERTY_WM_TRANSFORMATION_SUCC"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_FREE_PROPERTY_WM_FREE_TRIAL_LIMIT_RE"], "kind": "gate"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "image-upscaler": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_FREE_PROPERTY_US_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Transform success", "events": ["IMG_FREE_PROPERTY_US_TRANSFORMATION_SUCC"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_FREE_PROPERTY_US_FREE_TRIAL_LIMIT_RE"], "kind": "gate"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "video-watermark-remover": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "File upload", "events": ["DYNAMIC_APP_FILE_UPLOAD_SUCCESS"], "kind": "input"},
        {"label": "Transform started", "events": ["DYNAMIC_APP_TRANSFORMATION_TRIGGERED"], "kind": "action"},
        {"label": "Transform success", "events": ["DYNAMIC_APP_TRANSFORMATION_POLLING_SUCCE"], "kind": "success"},
        {"label": "Payment popup", "events": ["DYNAMIC_APP_PAYMENT_TRIGGERED"], "kind": "gate"},
        {"label": "Sign-up popup", "events": ["DYNAMIC_APP_SIGNUP_TRIGGERED"], "kind": "gate"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "emoji-remover": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_TO_IMG_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Generate clicked", "events": ["IMG_TO_IMG_GENERATE_CLICKED"], "kind": "action"},
        {"label": "Transform success", "events": ["IMG_TO_IMG_TRANSFORMATION_SUCCESS"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_TO_IMG_FREE_TRIAL_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Signup CTA", "events": ["IMG_TO_IMG_FREE_TRIAL_SIGNUP_CLICKED", "IMG_TO_IMG_PREMIUM_SIGNUP_CLICKED"], "kind": "cta"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "add-suit-to-photo": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_TO_IMG_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Generate clicked", "events": ["IMG_TO_IMG_GENERATE_CLICKED"], "kind": "action"},
        {"label": "Transform success", "events": ["IMG_TO_IMG_TRANSFORMATION_SUCCESS"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_TO_IMG_FREE_TRIAL_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Signup CTA", "events": ["IMG_TO_IMG_FREE_TRIAL_SIGNUP_CLICKED", "IMG_TO_IMG_PREMIUM_SIGNUP_CLICKED"], "kind": "cta"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "unblur-image": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_TO_IMG_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Generate clicked", "events": ["IMG_TO_IMG_GENERATE_CLICKED"], "kind": "action"},
        {"label": "Transform success", "events": ["IMG_TO_IMG_TRANSFORMATION_SUCCESS"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_TO_IMG_FREE_TRIAL_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Signup CTA", "events": ["IMG_TO_IMG_FREE_TRIAL_SIGNUP_CLICKED", "IMG_TO_IMG_PREMIUM_SIGNUP_CLICKED"], "kind": "cta"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "ai-image-generator": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Generate clicked", "events": ["IMG_TO_IMG_GENERATE_CLICKED"], "kind": "action"},
        {"label": "Transform success", "events": ["IMG_TO_IMG_TRANSFORMATION_SUCCESS"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_TO_IMG_FREE_TRIAL_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Signup CTA", "events": ["IMG_TO_IMG_FREE_TRIAL_SIGNUP_CLICKED", "IMG_TO_IMG_PREMIUM_SIGNUP_CLICKED"], "kind": "cta"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "old-photo-restoration": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_TO_IMG_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Generate clicked", "events": ["IMG_TO_IMG_GENERATE_CLICKED"], "kind": "action"},
        {"label": "Transform success", "events": ["IMG_TO_IMG_TRANSFORMATION_SUCCESS"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_TO_IMG_FREE_TRIAL_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Signup CTA", "events": ["IMG_TO_IMG_FREE_TRIAL_SIGNUP_CLICKED", "IMG_TO_IMG_PREMIUM_SIGNUP_CLICKED"], "kind": "cta"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "image-editor": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_TO_IMG_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Generate clicked", "events": ["IMG_TO_IMG_GENERATE_CLICKED"], "kind": "action"},
        {"label": "Transform success", "events": ["IMG_TO_IMG_TRANSFORMATION_SUCCESS"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_TO_IMG_FREE_TRIAL_LIMIT_REACHED"], "kind": "gate"},
        {"label": "Signup CTA", "events": ["IMG_TO_IMG_FREE_TRIAL_SIGNUP_CLICKED", "IMG_TO_IMG_PREMIUM_SIGNUP_CLICKED"], "kind": "cta"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
    "hd-photo-converter": [
        {"label": "Page view", "events": ["page_view"], "kind": "traffic"},
        {"label": "Image uploaded", "events": ["IMG_FREE_PROPERTY_US_IMAGE_UPLOADED"], "kind": "input"},
        {"label": "Transform success", "events": ["IMG_FREE_PROPERTY_US_TRANSFORMATION_SUCC"], "kind": "success"},
        {"label": "Free-trial limit", "events": ["IMG_FREE_PROPERTY_US_FREE_TRIAL_LIMIT_RE"], "kind": "gate"},
        {"label": "Payment popup", "events": ["DYNAMIC_APP_PAYMENT_TRIGGERED"], "kind": "gate"},
        {"label": "Sign-up popup", "events": ["DYNAMIC_APP_SIGNUP_TRIGGERED"], "kind": "gate"},
        {"label": "Sign-up attempt", "events": ["USER_SIGN_UP_ATTEMPT"], "kind": "key"},
    ],
}


class MCPClient:
    def __init__(self) -> None:
        node_dir = "/Users/anandpareek/.nvm/versions/node/v22.22.0/bin"
        cmd = [
            f"{node_dir}/npx",
            "-y",
            "mcp-remote@0.1.37",
            "https://mcp-google-analytics.stape.io/mcp",
        ]
        env = os.environ.copy()
        env["PATH"] = f"{node_dir}:{env.get('PATH', '')}"
        ca_bundle = "/Users/anandpareek/Documents/SEO content Skill/scripts/system-ca-bundle.pem"
        if pathlib.Path(ca_bundle).exists():
            env["NODE_EXTRA_CA_CERTS"] = ca_bundle
            env["SSL_CERT_FILE"] = ca_bundle
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self.next_id = 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": self.next_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "codex-render-growth-dashboard", "version": "2.0"},
                },
            }
        )
        self._wait(self.next_id, 180)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def _send(self, obj: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def _wait(self, request_id: int, timeout: int = 90) -> dict[str, Any]:
        assert self.proc.stdout is not None
        started = time.time()
        while time.time() - started < timeout:
            ready, _, _ = select.select([self.proc.stdout], [], [], 0.25)
            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("id") == request_id:
                    return message
        stderr = ""
        if self.proc.stderr:
            ready, _, _ = select.select([self.proc.stderr], [], [], 0)
            if ready:
                stderr = self.proc.stderr.read(2000)
        raise TimeoutError(f"MCP response timeout for id={request_id}. {stderr}")

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.next_id += 1
        request_id = self.next_id
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        message = self._wait(request_id)
        if "error" in message:
            raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
        result = message.get("result", {})
        if result.get("isError"):
            detail = " | ".join(
                item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"
            )
            raise RuntimeError(f"{name} failed: {detail}")
        if result.get("structuredContent"):
            return result["structuredContent"]
        for item in result.get("content", []):
            if item.get("type") == "text":
                return json.loads(item.get("text", "{}"))
        return result

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def exact(field: str, value: str, case_sensitive: bool = False) -> dict[str, Any]:
    return {
        "filter": {
            "field_name": field,
            "string_filter": {
                "match_type": "EXACT",
                "value": value,
                "case_sensitive": case_sensitive,
            },
        }
    }


def contains(field: str, value: str, case_sensitive: bool = False) -> dict[str, Any]:
    return {
        "filter": {
            "field_name": field,
            "string_filter": {
                "match_type": "CONTAINS",
                "value": value,
                "case_sensitive": case_sensitive,
            },
        }
    }


def in_list(field: str, values: list[str]) -> dict[str, Any]:
    return {
        "filter": {
            "field_name": field,
            "in_list_filter": {"values": values, "case_sensitive": False},
        }
    }


def and_filter(*expressions: dict[str, Any]) -> dict[str, Any]:
    return {"and_group": {"expressions": list(expressions)}}


client = MCPClient()
atexit.register(client.close)


def report(
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
    dimension_filter: dict[str, Any] | None = None,
    limit: int = 250000,
    start_date: dt.date = START,
    end_date: dt.date = END,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "property_id": property_id,
        "date_ranges": [{"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}],
        "dimensions": dimensions,
        "metrics": metrics,
        "limit": limit,
        "return_property_quota": False,
    }
    if dimension_filter:
        arguments["dimension_filter"] = dimension_filter
    return client.call("run_report", arguments)


def rows(data: dict[str, Any]) -> list[dict[str, str]]:
    dimension_headers = data.get("dimension_headers", data.get("dimensionHeaders", []))
    metric_headers = data.get("metric_headers", data.get("metricHeaders", []))
    dimension_names = [item.get("name", "") for item in dimension_headers]
    metric_names = [item.get("name", "") for item in metric_headers]
    output: list[dict[str, str]] = []
    for row in data.get("rows", []):
        dimension_values = row.get("dimension_values", row.get("dimensionValues", []))
        metric_values = row.get("metric_values", row.get("metricValues", []))
        record = {
            name: dimension_values[index].get("value", "")
            for index, name in enumerate(dimension_names)
        }
        record.update(
            {
                name: metric_values[index].get("value", "0")
                for index, name in enumerate(metric_names)
            }
        )
        output.append(record)
    return output


def write_raw(name: str, payload: dict[str, Any]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n")


def cached_report(
    name: str,
    property_id: str,
    dimensions: list[str],
    metrics: list[str],
    dimension_filter: dict[str, Any] | None = None,
    start_date: dt.date = START,
    end_date: dt.date = END,
) -> dict[str, Any]:
    path = RAW_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    payload = report(
        property_id,
        dimensions,
        metrics,
        dimension_filter,
        start_date=start_date,
        end_date=end_date,
    )
    write_raw(name, payload)
    return payload


def normalize_date(value: str) -> str:
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def number(value: str | int | float | None) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def daily_property(property_key: str, property_id: str) -> list[dict[str, Any]]:
    base = cached_report(
        f"{property_key}_daily",
        property_id,
        ["date"],
        ["sessions", "activeUsers", "screenPageViews", "bounceRate", "engagementRate"],
    )
    organic = cached_report(
        f"{property_key}_organic_daily",
        property_id,
        ["date"],
        ["sessions"],
        exact("sessionDefaultChannelGroup", "Organic Search"),
    )
    organic_by_day = {normalize_date(item["date"]): int(number(item["sessions"])) for item in rows(organic)}
    output = []
    for item in rows(base):
        day = normalize_date(item["date"])
        output.append(
            {
                "date": day,
                "sessions": int(number(item["sessions"])),
                "activeUsers": int(number(item["activeUsers"])),
                "pageViews": int(number(item["screenPageViews"])),
                "bounceRate": number(item["bounceRate"]),
                "engagementRate": number(item["engagementRate"]),
                "organicSessions": organic_by_day.get(day, 0),
            }
        )
    return sorted(output, key=lambda item: item["date"])


def canonical_tool(path: str) -> str | None:
    match = re.search(r"/ai-tools/([^/?#]+)", path, flags=re.I)
    return match.group(1).lower() if match else None


def title_from_slug(slug: str) -> str:
    replacements = {"ai": "AI", "bg": "BG", "url": "URL", "3d": "3D", "hd": "HD"}
    return " ".join(replacements.get(part, part.capitalize()) for part in slug.split("-"))


NOISE_EVENTS = {
    "PAGE_VIEW",
    "SESSION_START",
    "FIRST_VISIT",
    "USER_ENGAGEMENT",
    "SCROLL",
    "CLICK",
    "FORM_START",
    "FORM_SUBMIT",
    "LOGIN",
    "SIGN_UP",
}


def event_stage(event_name: str) -> str | None:
    value = event_name.upper()
    if value in NOISE_EVENTS or re.search(r"FAILED|FAILURE|ERROR|PAYMENT|PRICING|PLAN|CREDIT|LIMIT|AUTH|SIGNUP", value):
        return None
    if re.search(r"DOWNLOAD|GENERATED|TRANSFORMED|COMPLETED|POLLING_SUCC|TRANSFORMATION_SUCC|GENERATION_SUCC", value):
        return "output"
    if re.search(r"GENERAT(?:E|ION).*CLICK|GENERATION_STARTED|TRANSFORMATION_TRIGGERED|APPLY|PROCESS|ENHANCE|UPSCALE", value):
        return "action"
    if re.search(r"UPLOAD|PROMPT_ENTER|URL_PASTE|FILE_SELECT|IMAGE_SELECT|VIDEO_SELECT", value):
        return "input"
    return None


def discover_top_tools() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    property_id = PROPERTIES["pixelbin"]["id"]
    page_report = cached_report(
        f"pixelbin_ai_tools_content_group_pageviews_{END.isoformat()}",
        property_id,
        ["date", "customEvent:content_group"],
        ["eventCount"],
        and_filter(
            exact("eventName", "page_view"),
            contains("customEvent:content_group", "ai-tool:"),
        ),
    )
    daily_by_slug: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in rows(page_report):
        content_group = item.get("customEvent:content_group", "")
        if not content_group.startswith("ai-tool:"):
            continue
        slug = content_group.split(":", 1)[1]
        count = int(number(item.get("eventCount")))
        day = normalize_date(item.get("date", ""))
        daily_by_slug[slug][day] += count

    ranked = sorted(daily_by_slug, key=lambda slug: sum(daily_by_slug[slug].values()), reverse=True)[:10]
    tools: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}
    for rank, slug in enumerate(ranked, start=1):
        content_group = f"ai-tool:{slug}"
        tools.append(
            {
                "rank": rank,
                "slug": slug,
                "name": title_from_slug(slug),
                "contentGroup": content_group,
                "pageViews": dict(daily_by_slug[slug]),
                "pageViewTotal90d": sum(daily_by_slug[slug].values()),
                "topPaths": [],
                "events": [],
                "trackingNote": f"Exact customEvent:content_group={content_group} for every stage.",
            }
        )
        evidence[slug] = {
            "contentGroup": content_group,
            "pageViewTotal90d": sum(daily_by_slug[slug].values()),
        }
    return tools, evidence


def discover_ai_funnels(tools: list[dict[str, Any]]) -> dict[str, Any]:
    content_groups = [tool["contentGroup"] for tool in tools]
    raw_name = f"ai_tools_content_group_funnel_90d_{END.isoformat()}"
    payload = cached_report(
        raw_name,
        PROPERTIES["pixelbin"]["id"],
        ["date", "eventName", "customEvent:content_group"],
        ["eventCount", "keyEvents", "totalUsers"],
        in_list("customEvent:content_group", content_groups),
        start_date=START,
        end_date=END,
    )

    observed: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "daily": defaultdict(int),
                "keyEvents": 0.0,
            }
        )
    )
    for item in rows(payload):
        content_group = item.get("customEvent:content_group", "")
        tool_slug = content_group.split(":", 1)[1] if content_group.startswith("ai-tool:") else ""
        if not tool_slug or tool_slug not in AI_FUNNEL_MAP:
            continue
        event_name = item.get("eventName", "")
        event = observed[tool_slug][event_name]
        count = int(number(item.get("eventCount")))
        event["daily"][normalize_date(item.get("date", ""))] += count
        event["keyEvents"] += number(item.get("keyEvents"))

    output: dict[str, Any] = {}
    for tool in tools:
        tool_slug = tool["slug"]
        stage_rows = []
        for config in AI_FUNNEL_MAP.get(tool_slug, []):
            daily: dict[str, int] = defaultdict(int)
            key_event_count = 0.0
            for event_name in config["events"]:
                event = observed[tool_slug].get(event_name)
                if not event:
                    continue
                for day, count in event["daily"].items():
                    daily[day] += count
                key_event_count += event["keyEvents"]

            stage_rows.append(
                {
                    "label": config["label"],
                    "kind": config["kind"],
                    "eventNames": config["events"],
                    "daily": dict(daily),
                    "total": sum(daily.values()),
                    "mapping": f"content_group=ai-tool:{tool_slug}",
                    "keyEventCount": int(round(key_event_count)),
                    "isRegisteredKeyEvent": key_event_count > 0,
                }
            )
        output[tool_slug] = {
            "start": START.isoformat(),
            "end": END.isoformat(),
            "scope": f"content_group=ai-tool:{tool_slug}",
            "appName": None,
            "stages": stage_rows,
        }
    return output


def fetch_flow(property_key: str, index: int, config: dict[str, Any]) -> dict[str, Any]:
    property_id = PROPERTIES[property_key]["id"]
    version = f"_{config['cacheVersion']}" if config.get("cacheVersion") else ""
    raw_name = f"{property_key}_flow_{index:02d}_{config['slug']}{version}"
    payloads: list[dict[str, Any]] = []
    query_error = None
    if config.get("pagePath"):
        try:
            page_payload = cached_report(
                f"{raw_name}_page",
                property_id,
                ["date", "eventName"],
                ["eventCount"],
                and_filter(exact("eventName", "page_view"), contains("pagePath", config["pagePath"])),
            )
            action_payload = cached_report(
                f"{raw_name}_actions",
                property_id,
                ["date", "eventName"],
                ["eventCount"],
                in_list("eventName", [event for event in config["events"] if event != "page_view"]),
            )
            payloads = [page_payload, action_payload]
        except Exception as error:
            query_error = str(error)
    else:
        event_filter = in_list("eventName", config["events"])
        if config.get("filter"):
            field, value = config["filter"]
            event_filter = and_filter(event_filter, exact(field, value))
        try:
            payloads = [cached_report(raw_name, property_id, ["date", "eventName"], ["eventCount"], event_filter)]
        except Exception as error:
            query_error = str(error)

    if query_error and not payloads:
        payloads = [{"error": query_error, "rows": []}]
    daily: dict[str, dict[str, int]] = {event: {} for event in config["events"]}
    for payload in payloads:
        for item in rows(payload):
            event = item.get("eventName", "")
            if event in daily:
                day = normalize_date(item.get("date", ""))
                daily[event][day] = daily[event].get(day, 0) + int(number(item.get("eventCount")))
    return {
        "name": config["name"],
        "slug": config["slug"],
        "events": [{"name": event, "daily": daily[event], "total90d": sum(daily[event].values())} for event in config["events"]],
        "scope": (
            f"pagePath contains {config['pagePath']}; action event totals"
            if config.get("pagePath")
            else f"{config['filter'][0]}={config['filter'][1]}"
            if config.get("filter")
            else "eventName totals"
        ),
        "queryError": query_error,
    }


def main() -> None:
    print(f"Pulling GA4 growth data for {START} through {END} (today may be partial)...", flush=True)
    properties = {
        key: {**config, "daily": daily_property(key, config["id"])}
        for key, config in PROPERTIES.items()
    }
    top_tools, evidence = discover_top_tools()
    funnels = discover_ai_funnels(top_tools)
    for tool in top_tools:
        tool["funnel"] = funnels.get(tool["slug"], {})
    flows = {
        key: [fetch_flow(key, index, config) for index, config in enumerate(configs, start=1)]
        for key, configs in PRODUCT_FLOWS.items()
    }
    snapshot = {
        "generatedAt": BUILT_AT,
        "timezone": "Asia/Kolkata",
        "range": {"start": START.isoformat(), "end": END.isoformat(), "todayPartial": True},
        "windows": {"7": 7, "30": 30, "90": 90},
        "properties": properties,
        "aiTools": {
            "selectionWindow": {"start": START.isoformat(), "end": END.isoformat()},
            "selectionRule": "Top 10 exact customEvent:content_group=ai-tool:<slug> values by GA4 page_view over 90 days; the same set is used in all windows.",
            "tools": top_tools,
            "eventEvidence": evidence,
        },
        "flows": flows,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "dashboard.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(DATA_DIR / "dashboard.json"),
                "generatedAt": BUILT_AT,
                "topTools": [
                    {
                        "rank": tool["rank"],
                        "slug": tool["slug"],
                        "pageViews90d": tool["pageViewTotal90d"],
                        "events": [event for stage in tool["funnel"]["stages"] for event in stage["eventNames"]],
                    }
                    for tool in top_tools
                ],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
