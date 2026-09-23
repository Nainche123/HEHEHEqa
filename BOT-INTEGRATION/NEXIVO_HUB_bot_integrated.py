import asyncio
import json
import os
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# NEXIVO HUB • Discord Vending Bot
# Digital products / templates / bots / automation
# ============================================================

BRAND = "NEXIVO HUB"
WEBSITE_URL = os.getenv("WEBSITE_URL", "").rstrip("/")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
ORDER_CATEGORY_ID = int(os.getenv("ORDER_CATEGORY_ID", "0") or 0)
REVIEW_CHANNEL_ID = int(os.getenv("REVIEW_CHANNEL_ID", "0") or 0)
PURCHASE_LOG_CHANNEL_ID = int(os.getenv("PURCHASE_LOG_CHANNEL_ID", "0") or 0)
VERIFICATION_CHANNEL_ID = int(os.getenv("VERIFICATION_CHANNEL_ID", "0") or 0)
VERIFIED_ROLE_ID = int(os.getenv("VERIFIED_ROLE_ID", "0") or 0)
BUYER_ROLE_ID = int(os.getenv("BUYER_ROLE_ID", "0") or 0)
BANK_INFO = os.getenv("BANK_INFO", "입금 계좌는 관리자에게 안내받아 주세요.").strip()
ADMIN_NAME = os.getenv("ADMIN_NAME", "NEXIVO HUB 운영팀").strip()

# Shared Discord bot worker credentials. The one real Discord token lives only
# in this worker's environment. Customers never submit or receive it.
NEXIVO_BOT_WORKER_SECRET = os.getenv("NEXIVO_BOT_WORKER_SECRET", "").strip()
NEXIVO_WEB_SYNC_ENABLED = bool(WEBSITE_URL and NEXIVO_BOT_WORKER_SECRET)
NEXIVO_EVENT_STREAM_RETRY = 5
NEXIVO_ORDER_PUSH_INTERVAL = 3
NEXIVO_TASKS_STARTED = False
TENANTS: dict[str, dict[str, Any]] = {}
TENANT_LOCK = asyncio.Lock()
TENANT_LAST_REFRESH: datetime | None = None
LAST_NEXIVO_ORDER_SIGNATURE = ""
TENANT_REFRESH_INTERVAL = 30

SETUP_CATEGORY_NAMES = {
    "info": "╭・📢 NEXIVO INFORMATION",
    "store": "╭・🛒 NEXIVO STORE",
    "order": "╭・🎫 NEXIVO ORDER CENTER",
    "support": "╭・💬 NEXIVO SUPPORT",
    "community": "╭・⭐ NEXIVO COMMUNITY",
    "staff": "╭・🔒 NEXIVO STAFF",
}

SETUP_CHANNELS = {
    "info": {
        "welcome": ("「👋」환영", "새로운 멤버가 입장하면 환영 메시지가 표시됩니다."),
        "leave": ("「🚪」퇴장", "멤버가 퇴장하면 안내 메시지가 표시됩니다."),
        "notice": ("「📢」공지", "NEXIVO HUB의 주요 공지사항을 확인하는 공간입니다."),
        "verification": ("「✅」서버인증", "버튼을 눌러 NEXIVO HUB 인증 역할을 받을 수 있습니다."),
        "guide": ("「📖」이용방법", "구매와 주문 처리 방법을 안내합니다."),
    },
    "store": {
        "vending": ("「🛍️」자판기", "NEXIVO HUB 디지털 상품 자판기입니다."),
        "products": ("「📦」상품목록", "판매 중인 디지털 상품 안내 공간입니다."),
        "popular": ("「🔥」인기상품", "많이 찾는 상품을 빠르게 확인할 수 있습니다."),
        "reviews": ("「⭐」구매후기", "실제 구매후기를 확인하는 공간입니다."),
    },
    "order": {
        "order_guide": ("「🎫」주문안내", "주문 진행 순서를 안내합니다."),
        "payment_help": ("「🪟」이중창", "입금 시 이중창(분할 화면)으로 실제 이체를 확인하는 방법을 안내합니다."),
        "payment": ("「💳」결제안내", "입금 및 결제 확인 절차를 한눈에 확인합니다."),
    },
    "support": {
        "help": ("「💬」일반문의", "상품/주문 관련 일반 문의 티켓을 여는 공간입니다."),
        "partnership": ("「🤝」파트너문의", "제휴/협업 문의 티켓을 여는 공간입니다."),
        "custom": ("「🛠️」커스텀문의", "커스텀 봇/제작 상담 티켓을 여는 공간입니다."),
    },
    "community": {
        "chat": ("「💭」자유채팅", "자유롭게 이야기를 나누는 공간입니다."),
        "showcase": ("「🏆」구매인증", "NEXIVO HUB 상품 구매 인증 공간입니다."),
        "event": ("「🎉」이벤트", "이벤트, 혜택 및 시즌 소식을 확인하는 공간입니다."),
        "voice": ("「🔊」커뮤니티-보이스", "커뮤니티 음성 대화방입니다."),
    },
    "staff": {
        "purchase_log": ("「🧾」구매로그", "주문 관련 내부 로그입니다."),
        "bot_log": ("「🤖」봇로그", "봇 운영 로그입니다."),
        "staff_chat": ("「🔐」스태프채팅", "스태프 내부 대화 공간입니다."),
    },
}
DATA_FILE = Path(os.getenv("DATA_FILE", "data.json"))
BASE_DIR = Path(__file__).resolve().parent
DOUBLE_WINDOW_IMAGE = BASE_DIR / "assets" / "double_window.png"

KST = timezone(timedelta(hours=9))

# ----------------------------
# NEXIVO HUB • Operations automation
# ----------------------------
# No points/reward economy is used. These are purely operational safeguards.
PAYMENT_REMINDER_1_MINUTES = 10
PAYMENT_REMINDER_2_MINUTES = 30
UNPAID_ORDER_TIMEOUT_MINUTES = 60
PAYMENT_PENDING_TIMEOUT_MINUTES = 120
MAINTENANCE_INTERVAL_SECONDS = 60
BACKUP_INTERVAL_SECONDS = 30 * 60
BACKUP_KEEP_COUNT = 30
BACKUP_DIR = BASE_DIR / "backups"



# ----------------------------
# Data
# ----------------------------
DEFAULT_DATA = {
    "orders": {},
    "support_tickets": {},
    "reviews": [],
    "counters": {"order": 0, "support": 0},
    "server_config": {},
}


def load_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps(DEFAULT_DATA, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_DATA))
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = json.loads(json.dumps(DEFAULT_DATA))
    for key, value in DEFAULT_DATA.items():
        data.setdefault(key, json.loads(json.dumps(value)))
    return data


DATA = load_data()
DATA_LOCK = asyncio.Lock()
REVIEW_LOCKS: dict[str, asyncio.Lock] = {}
REVIEW_REMINDER_MINUTES = int(os.getenv("REVIEW_REMINDER_MINUTES", str(24 * 60)) or (24 * 60))  # one reminder, 24h by default
REVIEW_THANK_YOU_DM_ENABLED = True
TICKET_BACKUP_DIR = BASE_DIR / "ticket_backups"
TICKET_BACKUP_MAX_MESSAGES = 1000
TICKET_BACKUP_MAX_CHARS = 250_000
TICKET_BACKUP_KEEP_COUNT = 100


async def save_data() -> None:
    async with DATA_LOCK:
        tmp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
        tmp.write_text(json.dumps(DATA, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA_FILE)


# ----------------------------
# Utilities
# ----------------------------

def now() -> datetime:
    return datetime.now(KST)


def money(value: int) -> str:
    return f"{int(value):,}원"


def is_admin(member: discord.Member | discord.User) -> bool:
    # Legacy helper retained for compatibility; tenant-aware handlers use tenant_is_admin().
    return bool(OWNER_ID and member.id == OWNER_ID)


# Channel/role security: explicitly deny dangerous management permissions for all
# NEXIVO-created member-role overwrites. The bot itself receives only the permissions
# required to operate the setup/ticket system. The server owner remains unrestricted.
SECURITY_DENIES = {
    "create_instant_invite": False,
    "manage_channels": False,
    "manage_permissions": False,
    "manage_webhooks": False,
    "manage_messages": False,
    "mention_everyone": False,
    "manage_threads": False,
    "create_public_threads": False,
    "create_private_threads": False,
    "send_messages_in_threads": False,
}


def secure_overwrite(**kwargs) -> discord.PermissionOverwrite:
    values = dict(SECURITY_DENIES)
    values.update(kwargs)
    return discord.PermissionOverwrite(**values)


def truncate(text: str, limit: int = 100) -> str:
    text = str(text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def next_number(kind: str) -> int:
    DATA["counters"][kind] = int(DATA["counters"].get(kind, 0)) + 1
    return DATA["counters"][kind]


# ----------------------------
# Shared NEXIVO HUB worker sync
# ----------------------------

async def _worker_request(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> tuple[int, Any]:
    if not NEXIVO_WEB_SYNC_ENABLED:
        return 503, {"error": "NEXIVO HUB shared worker is not configured."}
    url = nexivo_hub_api_url(path)
    headers = {"User-Agent": "NEXIVO HUB-Shared-Bot/2.0", "Accept": "application/json", "X-NEXIVO-Worker-Secret": NEXIVO_BOT_WORKER_SECRET}
    timeout = aiohttp.ClientTimeout(total=35, connect=10, sock_connect=10, sock_read=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, url, json=json_body, headers=headers) as response:
            text = await response.text()
            try:
                payload = json.loads(text) if text else {}
            except json.JSONDecodeError:
                payload = {"error": text[:500]}
            return response.status, payload


def nexivo_hub_api_url(path: str) -> str:
    return f"{WEBSITE_URL}{path}"


def tenant_for_guild(guild_id: int | str | None) -> dict[str, Any] | None:
    if guild_id is None:
        return None
    return TENANTS.get(str(guild_id))


def tenant_products(guild_id: int | str | None) -> list[dict[str, Any]]:
    tenant = tenant_for_guild(guild_id)
    return list(tenant.get("products", [])) if tenant else []


def tenant_orders(guild_id: int | str | None) -> list[dict[str, Any]]:
    tenant = tenant_for_guild(guild_id)
    return list(tenant.get("orders", [])) if tenant else []


def tenant_features(guild_id: int | str | None) -> set[str]:
    tenant = tenant_for_guild(guild_id)
    return set(tenant.get("features", [])) if tenant else set()


def tenant_has_feature(guild_id: int | str | None, feature: str) -> bool:
    return feature in tenant_features(guild_id)


def tenant_is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not interaction.user:
        return False
    tenant = tenant_for_guild(interaction.guild.id)
    if not tenant:
        return False
    discord_user_id = str(tenant.get("discordUserId") or "").strip()
    # Customer licenses are bound to the Discord User ID entered by the NEXIVO HUB owner.
    # Server ownership alone does not bypass that binding.
    if discord_user_id:
        return discord_user_id == str(interaction.user.id)
    # Owner's own tenant can use the shared bot without a customer Discord ID.
    if str(tenant.get("role") or "").upper() == "OWNER":
        return True
    return False


def require_tenant_feature(interaction: discord.Interaction, feature: str) -> bool:
    if not interaction.guild:
        return False
    return tenant_has_feature(interaction.guild.id, feature)


def _tenant_cache_path() -> Path:
    return BASE_DIR / "tenant_cache.json"


def _load_tenant_cache() -> None:
    global TENANTS, TENANT_LAST_REFRESH
    path = _tenant_cache_path()
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("tenants", []) if isinstance(payload, dict) else []
        if isinstance(items, list):
            TENANTS = {str(t.get("guildId")): t for t in items if isinstance(t, dict) and t.get("guildId")}
            cached_at = payload.get("cached_at")
            if cached_at:
                TENANT_LAST_REFRESH = datetime.fromisoformat(str(cached_at))
    except Exception as exc:
        print(f"[{BRAND}] tenant cache load failed: {exc!r}")


def _save_tenant_cache() -> None:
    try:
        path = _tenant_cache_path()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({"cached_at": now().isoformat(), "tenants": list(TENANTS.values())}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        print(f"[{BRAND}] tenant cache save failed: {exc!r}")


_load_tenant_cache()


async def refresh_tenants(*, force: bool = False) -> dict[str, dict[str, Any]]:
    global TENANTS, TENANT_LAST_REFRESH
    if not NEXIVO_WEB_SYNC_ENABLED:
        return TENANTS
    if not force and TENANT_LAST_REFRESH is not None:
        age = (now() - TENANT_LAST_REFRESH).total_seconds()
        if 0 <= age < TENANT_REFRESH_INTERVAL:
            return TENANTS
    async with TENANT_LOCK:
        if not force and TENANT_LAST_REFRESH is not None:
            age = (now() - TENANT_LAST_REFRESH).total_seconds()
            if 0 <= age < TENANT_REFRESH_INTERVAL:
                return TENANTS
        try:
            status, payload = await _worker_request("GET", "/api/bot/tenants")
            if status >= 400:
                print(f"[{BRAND}] tenant refresh failed: HTTP {status} {payload}")
                return TENANTS
            items = payload.get("tenants", []) if isinstance(payload, dict) else []
            if isinstance(items, list):
                TENANTS = {str(t.get("guildId")): t for t in items if isinstance(t, dict) and t.get("guildId")}
                # Rehydrate order history from the web service after a worker restart.
                for gid, tenant in TENANTS.items():
                    for order in tenant.get("orders", []) if isinstance(tenant.get("orders"), list) else []:
                        oid = str(order.get("id") or "").strip().upper()
                        if oid:
                            DATA.setdefault("orders", {})[oid] = dict(order)
                TENANT_LAST_REFRESH = now()
                _save_tenant_cache()
                try:
                    await save_data()
                except Exception:
                    pass
                print(f"[{BRAND}] 활성 테넌트 {len(TENANTS)}개 동기화")
        except Exception as exc:
            print(f"[{BRAND}] tenant refresh error: {exc!r}")
        return TENANTS


async def sync_products(*, guild_id: int | str | None = None, force: bool = False) -> list[dict[str, Any]]:
    await refresh_tenants(force=force)
    return tenant_products(guild_id)


async def sync_stock_message_for_guild(guild_id: int | str) -> bool:
    await refresh_tenants()
    gid = str(guild_id)
    tenant = tenant_for_guild(gid)
    if not tenant or tenant.get("stockSyncEnabled") is False:
        return False
    guild = bot.get_guild(int(gid)) if bot else None
    if not guild:
        return False
    channel_id = str(tenant.get("stockChannelId") or "").strip()
    if not channel_id:
        return False
    try:
        channel = guild.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
        return False
    if not isinstance(channel, discord.TextChannel):
        return False
    products = sorted(tenant_products(gid), key=lambda p: (str(p.get("category", "")), str(p.get("name", ""))))
    embed = discord.Embed(title="📦 NEXIVO HUB • 실시간 재고", description="웹 관리 패널과 연결된 현재 재고입니다.", color=discord.Colour.from_rgb(59, 130, 246), timestamp=now())
    if not products:
        embed.add_field(name="상품 없음", value="현재 등록된 상품이 없습니다.", inline=False)
    else:
        lines = []
        for p in products[:24]:
            try:
                stock = int(p.get("stock", -1))
            except (TypeError, ValueError):
                stock = -1
            stock_text = "무제한" if stock < 0 else f"{stock:,}개"
            lines.append(f"• **{truncate(p.get('name', '상품'), 70)}**  ·  `{money(int(p.get('price', 0)))}`  ·  **{stock_text}**")
        embed.add_field(name=f"총 {len(products):,}개 상품", value="\n".join(lines), inline=False)
    embed.set_footer(text=f"{BRAND} • 서버별 라이선스 플랜 동기화")
    message_id = str(tenant.get("stockMessageId") or "").strip()
    message = None
    if message_id:
        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            message = None
    try:
        if message:
            await message.edit(embed=embed)
        else:
            message = await channel.send(embed=embed)
        await _worker_request("POST", "/api/bot/heartbeat", json_body={"guildId": gid, "botUserId": str(bot.user.id) if bot.user else None, "botUsername": str(bot.user) if bot.user else None, "tokenConfigured": bool(DISCORD_TOKEN), "stockMessageId": str(message.id), "stockSyncedAt": now().isoformat(), "stockSyncError": None})
        tenant["stockMessageId"] = str(message.id)
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        await _worker_request("POST", "/api/bot/heartbeat", json_body={"guildId": gid, "botUserId": str(bot.user.id) if bot.user else None, "botUsername": str(bot.user) if bot.user else None, "stockSyncError": str(exc)[:300]})
        return False


async def sync_all_stock() -> None:
    await refresh_tenants(force=True)
    for guild_id in list(TENANTS):
        try:
            await sync_stock_message_for_guild(guild_id)
        except Exception as exc:
            print(f"[{BRAND}] stock sync error for {guild_id}: {exc!r}")


async def nexivo_hub_event_stream_loop() -> None:
    if not NEXIVO_WEB_SYNC_ENABLED:
        print(f"[{BRAND}] shared worker disabled: set NEXIVO_BOT_WORKER_SECRET on the bot worker")
        return
    url = nexivo_hub_api_url("/api/bot/stream")
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=None, connect=15, sock_connect=15, sock_read=None)
            headers = {"User-Agent": "NEXIVO HUB-Shared-Bot/2.0", "Accept": "text/event-stream", "X-NEXIVO-Worker-Secret": NEXIVO_BOT_WORKER_SECRET}
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, timeout=None) as response:
                    if response.status >= 400:
                        body = await response.text()
                        print(f"[{BRAND}] event stream failed: HTTP {response.status} {body[:300]}")
                        await asyncio.sleep(NEXIVO_EVENT_STREAM_RETRY)
                        continue
                    current_event = None
                    async for raw in response.content:
                        line = raw.decode("utf-8", "ignore").rstrip("\r\n")
                        if not line:
                            current_event = None
                            continue
                        if line.startswith("event:"):
                            current_event = line.split(":", 1)[1].strip()
                            continue
                        if line.startswith("data:") and current_event in {"ready", "sync"}:
                            try:
                                payload = json.loads(line.split(":", 1)[1].strip())
                            except json.JSONDecodeError:
                                continue
                            if current_event == "ready":
                                items = payload.get("tenants", []) if isinstance(payload, dict) else []
                                TENANTS.update({str(t.get("guildId")): t for t in items if isinstance(t, dict) and t.get("guildId")})
                            else:
                                event = payload if isinstance(payload, dict) else {}
                                owner_id = str((event.get("payload") or {}).get("ownerId") or "")
                                await refresh_tenants(force=True)
                                if owner_id:
                                    tenant = next((t for t in TENANTS.values() if str(t.get("userId")) == owner_id), None)
                                    if tenant and tenant.get("guildId"):
                                        await sync_stock_message_for_guild(tenant["guildId"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[{BRAND}] event stream error: {exc!r}")
        await asyncio.sleep(NEXIVO_EVENT_STREAM_RETRY)


async def nexivo_hub_order_push_loop() -> None:
    global LAST_NEXIVO_ORDER_SIGNATURE
    if not NEXIVO_WEB_SYNC_ENABLED:
        return
    while True:
        try:
            await refresh_tenants()
            for gid, tenant in list(TENANTS.items()):
                guild_orders = [o for o in DATA.get("orders", {}).values() if str(o.get("guild_id", "")) == str(gid)]
                signature = json.dumps(guild_orders, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                key = f"{gid}:{signature}"
                if tenant.get("_order_sig") == signature:
                    continue
                tenant["_order_sig"] = signature
                status, payload = await _worker_request("POST", "/api/bot/worker-state", json_body={"guildId": gid, "orders": guild_orders, "botUserId": str(bot.user.id) if bot.user else None, "botUsername": str(bot.user) if bot.user else None, "tokenConfigured": bool(DISCORD_TOKEN)})
                if status >= 400:
                    print(f"[{BRAND}] order sync failed for {gid}: HTTP {status} {payload}")
            LAST_NEXIVO_ORDER_SIGNATURE = now().isoformat()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[{BRAND}] order sync error: {exc!r}")
        await asyncio.sleep(NEXIVO_ORDER_PUSH_INTERVAL)


async def shared_worker_heartbeat_loop() -> None:
    while True:
        try:
            await refresh_tenants()
            for gid in list(TENANTS):
                # Only report CONNECTED when this shared bot is actually present in the
                # customer guild. A stored Guild ID alone must never make the UI look
                # connected.
                try:
                    guild = bot.get_guild(int(gid)) if bot else None
                except (TypeError, ValueError):
                    guild = None
                if guild is None:
                    continue
                await _worker_request("POST", "/api/bot/heartbeat", json_body={"guildId": gid, "botUserId": str(bot.user.id) if bot.user else None, "botUsername": str(bot.user) if bot.user else None, "tokenConfigured": bool(DISCORD_TOKEN)})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[{BRAND}] heartbeat loop error: {exc!r}")
        await asyncio.sleep(60)


async def product_sync_loop() -> None:
    while True:
        try:
            await refresh_tenants(force=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[{BRAND}] tenant sync error: {exc!r}")
        await asyncio.sleep(300)


# ----------------------------
# Embeds
# ----------------------------

def base_embed(title: str, description: str = "", color: discord.Colour = discord.Colour.from_rgb(59, 130, 246)) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=now())
    embed.set_author(name=f"{BRAND} • Commerce Studio", icon_url=bot.user.display_avatar.url if bot.user else discord.Embed.Empty)
    embed.set_footer(text=f"{BRAND}  •  Digital Goods  •  Secure Order Flow")
    return embed


def stock_label(product: dict[str, Any]) -> str:
    try:
        stock = int(product.get('stock', -1))
    except (TypeError, ValueError):
        stock = -1
    return '무제한' if stock < 0 else f'{stock:,}개'


def product_embed(product: dict[str, Any]) -> discord.Embed:
    badge = str(product.get("badge") or "DIGITAL")
    embed = base_embed(
        f"🛍️  {product['name']}",
        f"{product.get('description', '원하는 NEXIVO HUB 상품을 확인해보세요.')}\n\n"
        f"**{money(int(product.get('price', 0)))}**  ·  `{badge}`",
        discord.Colour.from_rgb(59, 130, 246),
    )
    embed.add_field(name="📂 카테고리", value=f"`{str(product.get('category', '기타'))}`", inline=True)
    embed.add_field(name="💳 가격", value=f"**{money(int(product.get('price', 0)))}**", inline=True)
    embed.add_field(name="📦 재고", value=f"**{stock_label(product)}**", inline=True)
    features = product.get("features") or []
    embed.add_field(name="✨ 포함 기능", value="\n".join(f"`✓` {truncate(f, 88)}" for f in features[:8]) if features else "`✓` 상품 상세 안내 후 주문을 진행합니다.", inline=False)
    embed.add_field(name="🔒 주문 방식", value="상품 선택 → 비공개 주문 티켓 → 입금 확인 → 처리 → 지급 → 후기", inline=False)
    return embed


def category_embed(category: str, guild_id: int | str | None = None) -> discord.Embed:
    items = [p for p in tenant_products(guild_id) if str(p.get("category", "기타")) == category]
    rows = []
    for p in items[:12]:
        badge = str(p.get("badge") or "DIGITAL")
        rows.append(f"**{truncate(str(p.get('name', '상품')), 46)}**\n`{badge}`  ·  **{money(int(p.get('price', 0)))}**  ·  📦 **{stock_label(p)}**")
    body = "\n\n".join(rows) if rows else "현재 등록된 상품이 없습니다."
    embed = base_embed(f"📦  {category}", "원하는 상품을 골라 상세 내용을 확인한 뒤 구매를 진행해주세요.\n\n" + body, discord.Colour.from_rgb(59, 130, 246))
    embed.set_footer(text=f"{BRAND}  •  {len(items)}개 상품  •  NEXIVO DIGITAL STORE")
    return embed


def main_panel_embed(ephemeral: bool = False, guild_id: int | str | None = None) -> discord.Embed:
    products = sorted(tenant_products(guild_id), key=lambda p: (str(p.get("category", "")), int(p.get("price", 0))))
    categories = []
    for p in products:
        cat = str(p.get("category", "기타"))
        if cat not in categories: categories.append(cat)
    desc = "**원하는 상품을 골라 NEXIVO 스타일로 안전하게 주문하세요.**\n공개 패널은 고정되고 상품 선택은 **구매자 본인에게만 보이는 창**에서 진행됩니다." if not ephemeral else "카테고리 → 상품을 선택하고 가격/구성을 확인한 뒤 `🎫 구매하기`를 눌러주세요."
    embed = base_embed("╭─ ✦ NEXIVO HUB DIGITAL STORE ✦ ─╮", desc, discord.Colour.from_rgb(59, 130, 246))
    embed.add_field(name="🛍️ 판매 상품", value=f"**{len(products):,}개**", inline=True)
    embed.add_field(name="📂 카테고리", value=f"**{len(categories):,}개**", inline=True)
    embed.add_field(name="⚡ 주문 방식", value="개인 선택창 → 비공개 티켓", inline=True)
    embed.add_field(name="━━━  BUY FLOW  ━━━", value="**① 상품 선택  →  ② 상세 확인  →  ③ 주문 티켓  →  ④ 입금  →  ⑤ 확인  →  ⑥ 지급  →  ⑦ 후기**", inline=False)
    embed.add_field(name="🔒 안전한 결제", value="결제 정보는 공개 채널에 노출하지 않고 **개인 주문 티켓에서만** 안내합니다.", inline=False)
    return embed


class VendingLaunchView(discord.ui.View):
    def __init__(self, guild_id: int | str | None = None):
        super().__init__(timeout=None); self.guild_id = guild_id
    @discord.ui.button(label="🛒  상품 둘러보기", style=discord.ButtonStyle.primary, custom_id="nexivo_vending_open")
    async def open(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        gid = interaction.guild.id if interaction.guild else self.guild_id
        await refresh_tenants(force=True)
        await interaction.followup.send(embed=main_panel_embed(ephemeral=True, guild_id=gid), view=ProductCategoryView(gid), ephemeral=True)
    @discord.ui.button(label="🌐  웹사이트", style=discord.ButtonStyle.secondary, custom_id="nexivo_vending_web")
    async def website(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message(f"🌐 **{BRAND} 공식 웹사이트**\n{WEBSITE_URL}", ephemeral=True)


class CategorySelect(discord.ui.Select):
    def __init__(self, guild_id: int | str | None):
        self.guild_id = guild_id
        products = tenant_products(guild_id)
        categories=[]
        for p in products:
            c=str(p.get("category","기타"))
            if c not in categories: categories.append(c)
        options=[discord.SelectOption(label=truncate(c,80), value=c, emoji="📂", description=truncate(f"{sum(1 for p in products if str(p.get('category','기타'))==c)}개 상품",100)) for c in categories[:25]]
        if not options: options=[discord.SelectOption(label="상품 없음",value="__none__",emoji="⚠️")]
        super().__init__(placeholder="📂  카테고리를 선택하세요", options=options, custom_id=f"nexivo_category_select::{str(guild_id)[:60]}")
    async def callback(self, interaction: discord.Interaction):
        v=self.values[0]; gid=interaction.guild.id if interaction.guild else self.guild_id
        if v=="__none__": await interaction.response.send_message("❌ 현재 불러온 상품이 없습니다.",ephemeral=True); return
        await interaction.response.edit_message(embed=category_embed(v,gid), view=ProductSelectView(v,gid))


class ProductSelect(discord.ui.Select):
    def __init__(self, category:str, guild_id: int | str | None):
        self.guild_id=guild_id
        products=[p for p in tenant_products(guild_id) if str(p.get("category"))==category][:25]
        options=[discord.SelectOption(label=truncate(str(p["name"]),100),description=truncate(f"{money(int(p.get('price',0)))} · 재고 {stock_label(p)} · {p.get('description','')}",100),value=str(p["id"]),emoji="📦") for p in products]
        if not options: options=[discord.SelectOption(label="상품 없음",value="__none__",emoji="⚠️")]
        super().__init__(placeholder="📦  구매할 상품을 선택하세요", options=options, custom_id=f"nexivo_product_select::{category[:50]}::{str(guild_id)[:20]}")
    async def callback(self, interaction: discord.Interaction):
        pid=self.values[0]; gid=interaction.guild.id if interaction.guild else self.guild_id
        if pid=="__none__": await interaction.response.send_message("❌ 상품을 찾을 수 없습니다.",ephemeral=True); return
        product=next((p for p in tenant_products(gid) if str(p.get("id"))==pid),None)
        if not product: await interaction.response.send_message("❌ 상품 정보를 찾지 못했습니다. 잠시 후 다시 시도해주세요.",ephemeral=True); return
        await interaction.response.edit_message(embed=product_embed(product), view=ProductActionView(product,gid))


class ProductCategoryView(discord.ui.View):
    def __init__(self, guild_id: int | str | None = None, timeout:float|None=600):
        super().__init__(timeout=timeout); self.add_item(CategorySelect(guild_id))


class ProductSelectView(discord.ui.View):
    def __init__(self, category:str, guild_id: int | str | None = None, timeout:float|None=600):
        super().__init__(timeout=timeout); self.category=category; self.guild_id=guild_id; self.add_item(ProductSelect(category,guild_id)); self.add_item(BackToCategoriesButton(guild_id))


class BackToCategoriesButton(discord.ui.Button):
    def __init__(self, guild_id: int | str | None = None): super().__init__(label="↩  카테고리", style=discord.ButtonStyle.secondary); self.guild_id=guild_id
    async def callback(self, interaction: discord.Interaction):
        gid=interaction.guild.id if interaction.guild else self.guild_id
        await refresh_tenants()
        await interaction.response.edit_message(embed=main_panel_embed(ephemeral=True,guild_id=gid), view=ProductCategoryView(gid))


class BackToProductsButton(discord.ui.Button):
    def __init__(self, category:str, guild_id: int | str | None = None): super().__init__(label="↩  상품목록", style=discord.ButtonStyle.secondary); self.category=category; self.guild_id=guild_id
    async def callback(self, interaction: discord.Interaction):
        gid=interaction.guild.id if interaction.guild else self.guild_id
        await refresh_tenants()
        await interaction.response.edit_message(embed=category_embed(self.category,gid), view=ProductSelectView(self.category,gid))


class ProductActionView(discord.ui.View):
    def __init__(self, product:dict[str,Any], guild_id: int | str | None = None):
        super().__init__(timeout=600); self.product=product; self.guild_id=guild_id; self.add_item(BackToProductsButton(str(product.get("category","기타")),guild_id))
    @discord.ui.button(label="🎫  지금 구매하기", style=discord.ButtonStyle.primary)
    async def buy(self, interaction:discord.Interaction, _:discord.ui.Button):
        gid=interaction.guild.id if interaction.guild else self.guild_id
        await refresh_tenants(force=True)
        current = next((p for p in tenant_products(gid) if str(p.get('id')) == str(self.product.get('id'))), self.product)
        try: current_stock = int(current.get('stock', -1))
        except (TypeError,ValueError): current_stock = -1
        if current_stock == 0:
            await interaction.response.send_message('❌ 현재 재고가 모두 소진되었습니다. 잠시 후 다시 확인해주세요.',ephemeral=True); return
        await create_order_ticket(interaction, current)


class TicketView(discord.ui.View):
    def __init__(self, order_id:str):
        super().__init__(timeout=None)
        self.add_item(PaymentRequestButton(order_id,f"nexivo_order::{order_id}:payment"))
        self.add_item(StartProcessButton(order_id,f"nexivo_order::{order_id}:process"))
        self.add_item(CompleteOrderButton(order_id,f"nexivo_order::{order_id}:complete"))
        self.add_item(CloseOrderButton(order_id,f"nexivo_order::{order_id}:close"))


class PaymentRequestButton(discord.ui.Button):
    def __init__(self, order_id:str, custom_id:str): super().__init__(label="💳 입금 확인 요청", style=discord.ButtonStyle.success, custom_id=custom_id); self.order_id=order_id
    async def callback(self, interaction:discord.Interaction):
        order=DATA["orders"].get(self.order_id)
        if not order or int(order.get("user_id",0))!=interaction.user.id: await interaction.response.send_message("❌ 본인 주문만 요청할 수 있습니다.",ephemeral=True); return
        if order.get("status") in {"완료","취소"}: await interaction.response.send_message("❌ 이미 종료된 주문입니다.",ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        order["status"]="입금확인요청"; order["payment_requested_at"]=now().isoformat(); order.pop("payment_reminder_10_sent", None); order.pop("payment_reminder_30_sent", None); await save_data()
        if interaction.guild:
            await send_staff_alert(
                interaction.guild,
                title="💳 새 입금 확인 요청",
                description=f"구매자가 주문 `{self.order_id}`의 **입금 확인 요청**을 보냈습니다. 관리자 확인 후 처리해주세요.",
                order=order,
                level="normal",
            )
            await send_audit_log(interaction.guild, action="입금 확인 요청", detail="구매자가 입금 확인을 요청했습니다.", order=order, target=interaction.user)
        if isinstance(interaction.channel,discord.TextChannel):
            embed = base_embed(
                "╭─── ✦ PAYMENT CHECK REQUESTED ✦ ───╮",
                f"**{interaction.user.mention}**님의 입금 확인 요청이 접수되었습니다.\n\n관리자가 실제 입금 내역을 확인한 뒤 다음 단계로 진행합니다.",
                discord.Colour.gold(),
            )
            embed.add_field(name="🧾 주문번호", value=f"`{self.order_id}`", inline=True)
            embed.add_field(name="📌 상태", value="`입금확인요청`", inline=True)
            embed.add_field(name="⏰ 자동 알림", value=f"{PAYMENT_REMINDER_1_MINUTES}분 / {PAYMENT_REMINDER_2_MINUTES}분 미처리 시 스태프 알림", inline=False)
            await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ 입금 확인 요청을 접수했습니다. 스태프에게 알림이 전송되었습니다.",ephemeral=True)


class StartProcessButton(discord.ui.Button):
    def __init__(self, order_id:str, custom_id:str): super().__init__(label="📦 처리 시작", style=discord.ButtonStyle.primary, custom_id=custom_id); self.order_id=order_id
    async def callback(self, interaction:discord.Interaction):
        if not tenant_is_admin(interaction): await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.",ephemeral=True); return
        order=DATA["orders"].get(self.order_id)
        if not order: await interaction.response.send_message("❌ 주문을 찾을 수 없습니다.",ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        order["status"]="처리중"; order["processed_by"]=str(interaction.user); order["processed_at"]=now().isoformat(); await save_data()
        if interaction.guild:
            await send_audit_log(interaction.guild, action="주문 처리 시작", detail="관리자가 입금 확인 후 상품 지급 작업을 시작했습니다.", order=order, actor=interaction.user, level="normal")
        if isinstance(interaction.channel,discord.TextChannel):
            embed = base_embed(
                "╭─── ✦ ORDER PROCESSING ✦ ───╮",
                f"주문 `{self.order_id}`의 상품 지급 작업이 **시작되었습니다.**\n입금 확인 및 상품 전달 절차를 진행합니다.",
                discord.Colour.blurple(),
            )
            embed.add_field(name="🛠️ 처리 담당", value=interaction.user.mention, inline=True)
            embed.add_field(name="📌 상태", value="`처리중`", inline=True)
            await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ 처리 상태로 변경했습니다.",ephemeral=True)


class CompleteOrderButton(discord.ui.Button):
    def __init__(self, order_id:str, custom_id:str):
        super().__init__(label="✅ 지급 완료", style=discord.ButtonStyle.success, custom_id=custom_id)
        self.order_id=order_id

    async def callback(self, interaction:discord.Interaction):
        if not tenant_is_admin(interaction):
            await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.",ephemeral=True)
            return
        order=DATA["orders"].get(self.order_id)
        if not order:
            await interaction.response.send_message("❌ 주문을 찾을 수 없습니다.",ephemeral=True)
            return
        if order.get("status") == "완료":
            await interaction.response.send_message("ℹ️ 이미 지급 완료 처리된 주문입니다.",ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        order["status"]="완료"
        order["completed_at"]=now().isoformat()
        order["completed_by"]=str(interaction.user)
        await save_data()
        role_msg=None
        member=None
        if interaction.guild:
            try:
                member=interaction.guild.get_member(int(order.get("user_id",0))) or await interaction.guild.fetch_member(int(order.get("user_id",0)))
            except (discord.NotFound,discord.HTTPException):
                member=None
            if member:
                _,role_msg=await add_buyer_role(member)
        total_completed_purchases = completed_purchase_count(int(order.get("user_id", 0) or 0))
        order["completed_purchase_count"] = total_completed_purchases
        if interaction.guild:
            await send_audit_log(interaction.guild, action="지급 완료", detail="상품 지급을 완료하고 구매자 후기를 요청했습니다.", order=order, actor=interaction.user, level="success")
        if isinstance(interaction.channel,discord.TextChannel):
            embed = base_embed(
                "╭─── ✦ NEXIVO HUB • DELIVERY COMPLETE ✦ ───╮",
                f"🎉 **{interaction.user.mention}**, 주문 `{self.order_id}`의 상품 지급이 완료되었습니다!\n\n💜 이용해주셔서 감사합니다. 아래 버튼에서 후기를 남겨주세요.",
                discord.Colour.green(),
            )
            embed.add_field(name="📌 주문 상태", value="`지급 완료`", inline=True)
            embed.add_field(name="🛍️ 구매 횟수", value=f"`{total_completed_purchases}건`", inline=True)
            embed.add_field(name="⭐ 후기", value="아래 `⭐ 후기 작성하기` 버튼을 눌러주세요.", inline=True)
            if role_msg:
                embed.add_field(name="🎖️ 구매자 역할", value=role_msg, inline=False)
            review_msg=await interaction.channel.send(embed=embed,view=ReviewTicketView(self.order_id))
            order["review_message_id"]=review_msg.id
            await save_data()

        # 지급 완료 직후 구매자에게 DM으로 후기 작성 안내를 보냅니다.
        # DM이 차단되어 있어도 구매 완료 처리는 실패하지 않도록 안전하게 무시합니다.
        review_dm_sent = False
        if member:
            review_dm_sent = await send_review_request_dm(member, order)
            if review_dm_sent:
                order["review_dm_sent_at"] = now().isoformat()
                await save_data()

        await send_log("completed",order)
        if review_dm_sent:
            await interaction.followup.send("✅ 지급 완료 처리했습니다. 티켓에 후기 버튼을 표시했고 구매자 DM으로도 후기 작성 안내를 보냈습니다.",ephemeral=True)
        else:
            await interaction.followup.send("✅ 지급 완료 처리했습니다. 티켓에 후기 작성 버튼을 표시했습니다. 구매자의 DM이 차단되어 있으면 DM 안내는 전송되지 않습니다.",ephemeral=True)


class CloseOrderButton(discord.ui.Button):
    def __init__(self, order_id:str, custom_id:str): super().__init__(label="🔒 주문 닫기", style=discord.ButtonStyle.secondary, custom_id=custom_id); self.order_id=order_id
    async def callback(self, interaction:discord.Interaction):
        order=DATA["orders"].get(self.order_id,{})
        if not (tenant_is_admin(interaction) or int(order.get("user_id",0))==interaction.user.id): await interaction.response.send_message("❌ 주문 당사자 또는 관리자만 닫을 수 있습니다.",ephemeral=True); return
        channel=interaction.channel
        if interaction.guild:
            await send_audit_log(interaction.guild, action="주문 티켓 닫기", detail="주문 티켓을 닫았습니다.", order=order, actor=interaction.user)
        await interaction.response.send_message("🔒 주문 티켓을 2초 후 닫습니다.",ephemeral=True); await asyncio.sleep(2)
        if isinstance(channel,discord.TextChannel):
            await backup_ticket_transcript(channel, metadata=order, reason="manual_order_close")
            await channel.delete(reason=f"{BRAND} order closed {self.order_id}")


async def backup_ticket_transcript(
    channel: discord.TextChannel,
    *,
    metadata: dict[str, Any] | None = None,
    reason: str = "closed",
) -> Path | None:
    """Back up a ticket transcript locally and, when possible, upload it to the private staff room.

    The backup is created before a ticket channel is deleted. This intentionally stores message text,
    embeds, and attachment URLs rather than copying attachment bytes, keeping the backup small and usable.
    """
    TICKET_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y%m%d_%H%M%S")
    safe_channel = re.sub(r"[^a-zA-Z0-9._-]+", "_", channel.name)[:70] or "ticket"
    order_id = str((metadata or {}).get("id") or (metadata or {}).get("ticket_id") or "ticket")
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "_", order_id)[:40]
    path = TICKET_BACKUP_DIR / f"{stamp}_{safe_id}_{safe_channel}.txt"

    lines: list[str] = []
    lines.append(f"{BRAND} TICKET TRANSCRIPT")
    lines.append(f"Reason: {reason}")
    lines.append(f"Channel: #{channel.name} ({channel.id})")
    lines.append(f"Guild: {channel.guild.name} ({channel.guild.id})")
    if metadata:
        for key in ("id", "ticket_id", "user_id", "username", "product_name", "status", "total", "type", "subject"):
            if key in metadata:
                lines.append(f"{key}: {metadata.get(key)}")
    lines.append(f"Backup time: {now().isoformat()}")
    lines.append("=" * 80)

    try:
        count = 0
        async for message in channel.history(limit=TICKET_BACKUP_MAX_MESSAGES, oldest_first=True):
            count += 1
            stamp_msg = message.created_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
            author = f"{message.author} ({message.author.id})"
            lines.append(f"[{stamp_msg}] {author}")
            if message.content:
                lines.append(message.content)
            for embed in message.embeds:
                if embed.title:
                    lines.append(f"[EMBED TITLE] {embed.title}")
                if embed.description:
                    lines.append(f"[EMBED DESCRIPTION] {embed.description}")
                for field in embed.fields:
                    lines.append(f"[EMBED FIELD] {field.name}: {field.value}")
            for attachment in message.attachments:
                lines.append(f"[ATTACHMENT] {attachment.filename} | {attachment.url}")
            if not message.content and not message.embeds and not message.attachments:
                lines.append("[no text content]")
            lines.append("-" * 80)
            if sum(len(x) + 1 for x in lines) >= TICKET_BACKUP_MAX_CHARS:
                lines.append("[TRANSCRIPT TRUNCATED: character safety limit reached]")
                break
        lines.append(f"Messages captured: {count}")
    except (discord.Forbidden, discord.HTTPException) as exc:
        lines.append(f"[TRANSCRIPT ERROR] {exc!r}")

    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        backups = sorted(TICKET_BACKUP_DIR.glob("*.txt"), key=lambda item: item.stat().st_mtime, reverse=True)
        for old_path in backups[TICKET_BACKUP_KEEP_COUNT:]:
            try:
                old_path.unlink()
            except OSError:
                pass
    except OSError as exc:
        print(f"[{BRAND}] ticket backup write failed: {exc!r}")
        return None

    # Send a durable copy to the private staff room whenever possible.
    try:
        staff_channel = await _resolve_staff_channel(channel.guild)
        if staff_channel and path.exists():
            embed = base_embed(
                "╭─── ✦ NEXIVO HUB • TICKET BACKUP ✦ ───╮",
                f"티켓 `{channel.name}`이(가) 삭제되기 전에 대화 백업을 저장했습니다.",
                discord.Colour.blurple(),
            )
            embed.add_field(name="🎫 채널", value=f"`#{channel.name}`", inline=True)
            embed.add_field(name="🧾 구분", value=f"`{reason}`", inline=True)
            embed.add_field(name="💾 보관 위치", value="서버 로컬 백업 + 스태프 채널 첨부파일", inline=False)
            await staff_channel.send(embed=embed, file=discord.File(str(path), filename=path.name))
    except (discord.Forbidden, discord.HTTPException, OSError) as exc:
        print(f"[{BRAND}] ticket backup staff upload failed: {exc!r}")

    return path


def completed_purchase_count(user_id: int) -> int:
    return sum(
        1
        for order in DATA.get("orders", {}).values()
        if int(order.get("user_id", 0) or 0) == int(user_id)
        and order.get("status") == "완료"
    )


def completed_purchase_count_before(user_id: int, *, exclude_order_id: str | None = None) -> int:
    return sum(
        1
        for oid, order in DATA.get("orders", {}).items()
        if int(order.get("user_id", 0) or 0) == int(user_id)
        and oid != exclude_order_id
        and order.get("status") == "완료"
    )


def purchase_customer_label(prior_completed: int) -> str:
    return "🔁 재구매 고객" if prior_completed > 0 else "🆕 첫 구매 고객"


async def send_review_thank_you_dm(user: discord.abc.User, order: dict[str, Any], review: dict[str, Any]) -> bool:
    """Send a one-time thank-you DM after a review is successfully submitted."""
    if not REVIEW_THANK_YOU_DM_ENABLED or order.get("review_thank_you_dm_sent_at"):
        return False
    try:
        embed = base_embed(
            "╭─── ✦ NEXIVO HUB • THANK YOU ✦ ───╮",
            "⭐ **소중한 후기를 남겨주셔서 감사합니다!**\n\n"
            f"주문 `{order.get('id', '-')}`의 후기가 정상적으로 등록되었습니다. 💜",
            discord.Colour.green(),
        )
        embed.add_field(name="📦 상품", value=truncate(order.get("product_name"), 100), inline=False)
        embed.add_field(name="⭐ 별점", value="⭐" * int(review.get("rating", 0) or 0), inline=True)
        embed.add_field(name="📝 상태", value="`후기 등록 완료`", inline=True)
        embed.set_footer(text=f"{BRAND} • REVIEW THANK YOU")
        await user.create_dm()
        await user.send(embed=embed)
        order["review_thank_you_dm_sent_at"] = now().isoformat()
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


async def send_review_reminder_dm(user: discord.abc.User, order: dict[str, Any]) -> bool:
    """Send a single reminder DM 24h after payout when no review exists."""
    try:
        embed = base_embed(
            "╭─── ✦ NEXIVO HUB • REVIEW REMINDER ✦ ───╮",
            "⭐ **아직 후기를 작성하지 않으셨나요?**\n\n"
            f"주문 `{order.get('id', '-')}`의 후기를 남겨주시면 정말 큰 도움이 됩니다. 💜",
            discord.Colour.gold(),
        )
        embed.add_field(name="📦 구매 상품", value=truncate(order.get("product_name"), 100), inline=False)
        embed.add_field(name="⏱️ 안내", value="후기는 같은 주문에 한 번만 작성할 수 있습니다.", inline=False)
        embed.set_footer(text=f"{BRAND} • REVIEW REMINDER • 1회 안내")
        dm = await user.create_dm()
        message = await dm.send(embed=embed, view=ReviewDMView(str(order.get("id", ""))))
        order["review_reminder_sent"] = True
        order["review_reminder_sent_at"] = now().isoformat()
        order["review_reminder_message_id"] = message.id
        order["review_reminder_channel_id"] = dm.id
        return True
    except (discord.Forbidden, discord.HTTPException):
        order["review_reminder_attempted_at"] = now().isoformat()
        return False


class OrderQuickJumpButton(discord.ui.Button):
    def __init__(self, order: dict[str, Any], row: int | None = None):
        order_id = str(order.get("id", "-"))
        channel_id = int(order.get("channel_id", 0) or 0)
        guild_id = int(order.get("guild_id", 0) or 0)
        if guild_id and channel_id:
            url = f"https://discord.com/channels/{guild_id}/{channel_id}"
        else:
            url = "https://discord.com/app"
        super().__init__(label=f"🎫 {order_id}", style=discord.ButtonStyle.link, url=url, row=row)


class ReviewAlreadyDoneView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="✅ 이미 후기 작성 완료",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id="nexivo_review_already_done",
            )
        )


class ReviewTicketDoneView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="✅ 후기 작성 완료",
                style=discord.ButtonStyle.success,
                disabled=True,
                custom_id="nexivo_review_ticket_done",
            )
        )


def _review_exists(order_id: str) -> bool:
    return any(str(r.get("order_id")) == str(order_id) for r in DATA.get("reviews", []))


def _review_lock(order_id: str) -> asyncio.Lock:
    return REVIEW_LOCKS.setdefault(str(order_id), asyncio.Lock())


async def _mark_review_prompts_completed(order: dict[str, Any]) -> None:
    """Update both the ticket and DM review prompts so either side shows completed."""
    # Ticket prompt
    guild_id = int(order.get("guild_id", 0) or 0)
    channel_id = int(order.get("channel_id", 0) or 0)
    message_id = int(order.get("review_message_id", 0) or 0)
    if guild_id and channel_id and message_id:
        guild = bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id) if guild else None
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(message_id)
                embed = base_embed(
                    "╭─── ✦ NEXIVO HUB • REVIEW COMPLETE ✦ ───╮",
                    "⭐ **후기가 정상적으로 등록되었습니다.**\n\n"
                    "이 주문의 후기는 이미 작성되어 더 이상 중복 작성할 수 없습니다.\n"
                    "잠시 후 주문 티켓이 자동으로 닫힙니다.",
                    discord.Colour.green(),
                )
                embed.add_field(name="🧾 주문번호", value=f"`{order.get('id', '-')}`", inline=True)
                embed.add_field(name="📦 상품", value=truncate(order.get("product_name"), 100), inline=True)
                embed.add_field(name="✅ 상태", value="`후기 작성 완료`", inline=True)
                await message.edit(embed=embed, view=ReviewTicketDoneView())
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

    # DM prompt
    dm_channel_id = int(order.get("review_dm_channel_id", 0) or 0)
    dm_message_id = int(order.get("review_dm_message_id", 0) or 0)
    if dm_channel_id and dm_message_id:
        try:
            dm_channel = bot.get_channel(dm_channel_id)
            if not isinstance(dm_channel, (discord.DMChannel, discord.PartialMessageable)):
                user = bot.get_user(int(order.get("user_id", 0))) or await bot.fetch_user(int(order.get("user_id", 0)))
                dm_channel = await user.create_dm()
            message = await dm_channel.fetch_message(dm_message_id)
            embed = base_embed(
                "╭─── ✦ NEXIVO HUB • REVIEW COMPLETE ✦ ───╮",
                "⭐ **후기 작성이 완료되었습니다!**\n\n"
                f"주문 `{order.get('id', '-')}`의 후기가 정상적으로 접수되었습니다. 💜\n"
                "이 주문에는 더 이상 후기를 작성할 수 없습니다.",
                discord.Colour.green(),
            )
            embed.add_field(name="📦 구매 상품", value=truncate(order.get("product_name"), 100), inline=False)
            embed.add_field(name="✅ 상태", value="`후기 작성 완료`", inline=True)
            embed.add_field(name="🎫 티켓", value="후기 작성이 완료되어 주문 티켓도 자동으로 닫힙니다.", inline=True)
            await message.edit(embed=embed, view=ReviewAlreadyDoneView())
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def _close_review_ticket(order: dict[str, Any]) -> None:
    """Auto-close the order ticket after a review is submitted."""
    if order.get("review_ticket_closed_at"):
        return
    guild = bot.get_guild(int(order.get("guild_id", 0) or 0)) if order.get("guild_id") else None
    channel = guild.get_channel(int(order.get("channel_id", 0) or 0)) if guild else None
    if not isinstance(channel, discord.TextChannel):
        order["review_ticket_closed_at"] = now().isoformat()
        await save_data()
        return

    try:
        embed = base_embed(
            "╭─── ✦ NEXIVO HUB • TICKET CLOSED ✦ ───╮",
            "⭐ 후기 작성이 완료되었습니다.\n\n"
            "후기 확인이 완료되어 이 주문 티켓은 **자동으로 닫힙니다.**",
            discord.Colour.green(),
        )
        embed.add_field(name="🧾 주문번호", value=f"`{order.get('id', '-')}`", inline=True)
        embed.add_field(name="✅ 상태", value="`후기 완료`", inline=True)
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass

    await asyncio.sleep(2)
    await backup_ticket_transcript(channel, metadata=order, reason="review_completed_auto_close")
    try:
        await channel.delete(reason=f"{BRAND} review completed - ticket auto close {order.get('id', '-')}")
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass
    order["review_ticket_closed_at"] = now().isoformat()
    await save_data()


async def _complete_review_submission(
    interaction: discord.Interaction,
    order: dict[str, Any],
    stars: int,
    content: str,
) -> bool:
    """Save one review, synchronize all review prompts, and close its ticket."""
    order_id = str(order.get("id", ""))
    async with _review_lock(order_id):
        # Re-read from shared DATA so simultaneous DM/ticket clicks cannot double-submit.
        current_order = DATA.get("orders", {}).get(order_id)
        if not current_order or int(current_order.get("user_id", 0)) != interaction.user.id:
            msg = "❌ 본 주문의 구매자만 후기를 작성할 수 있습니다."
            await interaction.followup.send(msg, ephemeral=bool(interaction.guild))
            return False
        if current_order.get("status") != "완료":
            msg = "❌ 지급 완료된 주문만 후기를 작성할 수 있습니다."
            await interaction.followup.send(msg, ephemeral=bool(interaction.guild))
            return False
        if _review_exists(order_id):
            msg = "ℹ️ **이미 후기를 작성하셨습니다.**\n한 번 작성된 후기는 티켓과 DM 모두에서 다시 작성할 수 없습니다."
            await interaction.followup.send(msg, ephemeral=bool(interaction.guild))
            return False

        review = {
            "id": f"RV-{len(DATA['reviews']) + 1:04d}",
            "order_id": order_id,
            "user_id": interaction.user.id,
            "username": str(interaction.user),
            "rating": stars,
            "content": content,
            "created_at": now().isoformat(),
        }
        DATA["reviews"].append(review)
        current_order["review_completed_at"] = now().isoformat()
        await save_data()

        posted = await publish_review(review, current_order)
        await _mark_review_prompts_completed(current_order)
        thank_you_sent = await send_review_thank_you_dm(interaction.user, current_order, review)
        await save_data()

        if posted:
            await interaction.followup.send(
                "⭐ **후기가 등록되었습니다!**\n후기 채널에 게시되었고, 주문 티켓은 잠시 후 자동으로 닫힙니다."
                + ("\n💌 후기 감사 DM도 전송했습니다." if thank_you_sent else ""),
                ephemeral=bool(interaction.guild),
            )
        else:
            await interaction.followup.send(
                "⭐ **후기는 정상적으로 저장되었습니다.**\n후기 채널 게시에 실패했지만 중복 작성은 방지되며, 주문 티켓은 잠시 후 자동으로 닫힙니다."
                + ("\n💌 후기 감사 DM도 전송했습니다." if thank_you_sent else ""),
                ephemeral=bool(interaction.guild),
            )

        await _close_review_ticket(current_order)
        return True


class ReviewModal(discord.ui.Modal, title="⭐ NEXIVO HUB 후기 작성"):
    order_id = discord.ui.TextInput(label="주문번호", placeholder="예: VX-0001", required=True, max_length=40)
    rating = discord.ui.TextInput(label="별점 (1~5)", placeholder="5", required=True, max_length=1)
    content = discord.ui.TextInput(label="후기 내용", style=discord.TextStyle.paragraph, placeholder="상품과 서비스에 대한 후기를 작성해주세요.", required=True, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        oid = str(self.order_id.value).strip().upper()
        order = DATA["orders"].get(oid)
        if not order or int(order.get("user_id", 0)) != interaction.user.id:
            await interaction.response.send_message("❌ 본인의 주문번호가 아니거나 존재하지 않습니다.", ephemeral=bool(interaction.guild))
            return
        if order.get("status") != "완료":
            await interaction.response.send_message("❌ 완료된 주문만 후기를 작성할 수 있습니다.", ephemeral=bool(interaction.guild))
            return
        if _review_exists(oid):
            await interaction.response.send_message("ℹ️ **이미 후기를 작성하셨습니다.** 이 주문은 더 이상 중복 작성할 수 없습니다.", ephemeral=bool(interaction.guild))
            return
        try:
            stars = max(1, min(5, int(str(self.rating.value).strip())))
        except ValueError:
            await interaction.response.send_message("❌ 별점은 1~5 숫자로 입력해주세요.", ephemeral=bool(interaction.guild))
            return
        await interaction.response.defer(ephemeral=bool(interaction.guild))
        await _complete_review_submission(interaction, order, stars, str(self.content.value).strip())


class TicketReviewModal(discord.ui.Modal):
    def __init__(self, order_id: str):
        super().__init__(title="⭐ NEXIVO HUB 후기 작성")
        self.order_id = order_id
        self.rating = discord.ui.TextInput(label="별점 (1~5)", placeholder="5", required=True, max_length=1)
        self.content = discord.ui.TextInput(
            label="후기 내용",
            style=discord.TextStyle.paragraph,
            placeholder="상품과 서비스에 대한 후기를 작성해주세요.",
            required=True,
            max_length=1000,
        )
        self.add_item(self.rating)
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        order = DATA["orders"].get(self.order_id)
        if not order or int(order.get("user_id", 0)) != interaction.user.id:
            await interaction.response.send_message("❌ 본 주문의 구매자만 후기를 작성할 수 있습니다.", ephemeral=bool(interaction.guild))
            return
        if order.get("status") != "완료":
            await interaction.response.send_message("❌ 지급 완료된 주문만 후기를 작성할 수 있습니다.", ephemeral=bool(interaction.guild))
            return
        if _review_exists(self.order_id):
            await interaction.response.send_message("ℹ️ **이미 후기를 작성하셨습니다.** 티켓과 DM 모두 작성 완료 상태로 변경되었습니다.", ephemeral=bool(interaction.guild))
            return
        try:
            stars = max(1, min(5, int(str(self.rating.value).strip())))
        except ValueError:
            await interaction.response.send_message("❌ 별점은 1~5 숫자로 입력해주세요.", ephemeral=bool(interaction.guild))
            return
        await interaction.response.defer(ephemeral=bool(interaction.guild))
        await _complete_review_submission(interaction, order, stars, str(self.content.value).strip())


class ReviewTicketView(discord.ui.View):
    def __init__(self, order_id: str):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.add_item(ReviewTicketButton(order_id))


class ReviewTicketButton(discord.ui.Button):
    def __init__(self, order_id: str):
        super().__init__(label="⭐ 후기 작성하기", style=discord.ButtonStyle.primary, custom_id=f"nexivo_review::{order_id}")
        self.order_id = order_id

    async def callback(self, interaction: discord.Interaction):
        order = DATA["orders"].get(self.order_id)
        if not order or int(order.get("user_id", 0)) != interaction.user.id:
            await interaction.response.send_message("❌ 주문 구매자만 후기를 작성할 수 있습니다.", ephemeral=True)
            return
        if _review_exists(self.order_id):
            await interaction.response.send_message("ℹ️ **이미 후기를 작성하셨습니다.** 이 버튼과 DM 버튼 모두 작성 완료 상태입니다.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketReviewModal(self.order_id))


def _latest_completed_order_for_user(user_id: int) -> dict[str, Any] | None:
    """Return the user's most recently completed order for the DM review flow."""
    completed = [
        order
        for order in DATA.get("orders", {}).values()
        if int(order.get("user_id", 0)) == int(user_id)
        and order.get("status") == "완료"
        and not _review_exists(str(order.get("id", "")))
    ]
    if not completed:
        return None
    return max(
        completed,
        key=lambda order: str(order.get("completed_at") or order.get("created_at") or ""),
    )


class ReviewDMView(discord.ui.View):
    """Persistent DM review prompt for one specific order."""

    def __init__(self, order_id: str | None = None):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.add_item(ReviewDMButton(order_id))


class ReviewDMButton(discord.ui.Button):
    def __init__(self, order_id: str | None = None):
        custom_id = f"nexivo_review_dm::{order_id}" if order_id else "nexivo_review_dm_start"
        super().__init__(
            label="⭐ 후기 작성하기",
            style=discord.ButtonStyle.primary,
            custom_id=custom_id,
        )
        self.order_id = order_id

    async def callback(self, interaction: discord.Interaction):
        order = DATA.get("orders", {}).get(self.order_id) if self.order_id else _latest_completed_order_for_user(interaction.user.id)
        if not order or int(order.get("user_id", 0)) != interaction.user.id or order.get("status") != "완료":
            await interaction.response.send_message("ℹ️ 작성할 수 있는 완료 주문이 없습니다.")
            return
        if _review_exists(str(order.get("id", ""))):
            await interaction.response.send_message("ℹ️ **이미 후기를 작성하셨습니다.** 티켓과 이 DM 모두 작성 완료 상태입니다.")
            return
        await interaction.response.send_modal(TicketReviewModal(str(order["id"])))


async def send_review_request_dm(user: discord.abc.User, order: dict[str, Any]) -> bool:
    """Send a review request DM without allowing DM failure to block delivery completion."""
    try:
        embed = base_embed(
            "╭─── ✦ NEXIVO HUB • REVIEW REQUEST ✦ ───╮",
            "🎉 **상품 지급이 완료되었습니다!**\n\n"
            f"주문 `{order.get('id', '-')}`의 후기를 남겨주시면 큰 도움이 됩니다. 💜\n"
            "아래 버튼을 누르면 바로 후기 작성창이 열립니다.",
            discord.Colour.gold(),
        )
        embed.add_field(
            name="📦 구매 상품",
            value=truncate(order.get("product_name"), 100),
            inline=False,
        )
        embed.add_field(
            name="⭐ 후기 작성",
            value="별점과 후기를 간단하게 남겨주세요. 동일 주문은 한 번만 작성할 수 있습니다.",
            inline=False,
        )
        embed.set_footer(text=f"{BRAND} • REVIEW REQUEST • 주문번호 {order.get('id', '-')}")
        dm = await user.create_dm()
        message = await dm.send(embed=embed, view=ReviewDMView(str(order.get("id", ""))))
        order["review_dm_channel_id"] = dm.id
        order["review_dm_message_id"] = message.id
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


class ReviewStartView(discord.ui.View):
    @discord.ui.button(label="⭐ 후기 작성하기",style=discord.ButtonStyle.primary)
    async def start(self,interaction:discord.Interaction, _:discord.ui.Button): await interaction.response.send_modal(ReviewModal())


SUPPORT_TYPES={
    "general":{"title":"💬 일반 문의","prefix":"help","subject":"상품/주문/서버 이용 관련 문의"},
    "partnership":{"title":"🤝 파트너 문의","prefix":"partner","subject":"제휴/협업/홍보 관련 문의"},
    "custom":{"title":"🛠️ 커스텀 문의","prefix":"custom","subject":"커스텀 봇/서버/자동화 제작 상담"},
}


class SupportTicketView(discord.ui.View):
    def __init__(self,ticket_type:str): super().__init__(timeout=None); self.add_item(SupportOpenButton(ticket_type,f"nexivo_support_open::{ticket_type}"))


class SupportOpenButton(discord.ui.Button):
    def __init__(self,ticket_type:str,custom_id:str):
        labels={"general":"💬 문의 티켓 열기","partnership":"🤝 파트너 문의 열기","custom":"🛠️ 커스텀 상담 열기"}
        super().__init__(label=labels[ticket_type],style=discord.ButtonStyle.primary,custom_id=custom_id); self.ticket_type=ticket_type
    async def callback(self,interaction:discord.Interaction): await interaction.response.send_modal(SupportTicketModal(self.ticket_type))


class SupportTicketModal(discord.ui.Modal):
    def __init__(self,ticket_type:str):
        super().__init__(title=SUPPORT_TYPES[ticket_type]["title"][:45]); self.ticket_type=ticket_type
        self.request=discord.ui.TextInput(label="문의 내용을 적어주세요",placeholder=SUPPORT_TYPES[ticket_type]["subject"]+"에 대해 자세하게 작성해주세요.",style=discord.TextStyle.paragraph,required=True,max_length=1200); self.add_item(self.request)
    async def on_submit(self,interaction:discord.Interaction):
        if not interaction.guild: await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.",ephemeral=True); return
        for ticket in DATA.get("support_tickets",{}).values():
            if int(ticket.get("guild_id",0))==interaction.guild.id and int(ticket.get("user_id",0))==interaction.user.id and ticket.get("type")==self.ticket_type and ticket.get("status")=="open":
                existing=interaction.guild.get_channel(int(ticket.get("channel_id",0)))
                if existing: await interaction.response.send_message(f"❌ 이미 열린 문의 티켓이 있습니다: {existing.mention}",ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        ticket_no=f"VS-{next_number('support'):04d}"; cfg=config_for_guild(interaction.guild.id); cid=cfg.get("categories",{}).get("support",0)
        category=interaction.guild.get_channel(int(cid)) if cid else None
        if not isinstance(category,discord.CategoryChannel): category=discord.utils.get(interaction.guild.categories,name=SETUP_CATEGORY_NAMES["support"])
        if not isinstance(category,discord.CategoryChannel): category=await ensure_category(interaction.guild,"support")
        overwrites={interaction.guild.default_role:secure_overwrite(view_channel=False),interaction.user:secure_overwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True)}
        staff_role_id=cfg.get("roles",{}).get("staff",0); staff_role=interaction.guild.get_role(int(staff_role_id)) if staff_role_id else None
        if staff_role: overwrites[staff_role]=secure_overwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True)
        if interaction.guild.me: overwrites[interaction.guild.me]=secure_overwrite(view_channel=True,send_messages=True,manage_channels=True,manage_messages=True,read_message_history=True)
        info=SUPPORT_TYPES[self.ticket_type]
        channel=await interaction.guild.create_text_channel(f"{info['prefix']}-{ticket_no.lower()}",category=category,overwrites=overwrites,topic=f"{BRAND} {info['title']} {ticket_no}",reason=f"{BRAND} support ticket")
        ticket={"id":ticket_no,"guild_id":interaction.guild.id,"user_id":interaction.user.id,"username":str(interaction.user),"channel_id":channel.id,"type":self.ticket_type,"subject":str(self.request.value).strip(),"status":"open","created_at":now().isoformat()}
        DATA.setdefault("support_tickets",{})[ticket_no]=ticket; await save_data()
        embed=base_embed(f"╔══ {info['title']} • 티켓 ══╗",f"안녕하세요 {interaction.user.mention}님! 담당자가 확인 후 답변드립니다.")
        embed.add_field(name="🧾 문의번호",value=f"`{ticket_no}`",inline=True); embed.add_field(name="👤 문의자",value=interaction.user.mention,inline=True); embed.add_field(name="📌 유형",value=info["subject"],inline=True)
        embed.add_field(name="📝 문의내용",value=truncate(ticket["subject"],1000),inline=False); embed.add_field(name="🔒 보안",value="개인정보·계좌 비밀번호·인증번호는 절대 남기지 마세요.",inline=False)
        msg=await channel.send(content=interaction.user.mention,embed=embed,view=SupportCloseView(ticket_no)); ticket["message_id"]=msg.id; await save_data()
        await interaction.followup.send(f"✅ 문의 티켓을 생성했습니다. {channel.mention}",ephemeral=True)


class SupportCloseView(discord.ui.View):
    def __init__(self,ticket_id:str): super().__init__(timeout=None); self.add_item(SupportCloseButton(ticket_id,f"nexivo_support_close::{ticket_id}"))


class SupportCloseButton(discord.ui.Button):
    def __init__(self,ticket_id:str,custom_id:str): super().__init__(label="🔒 문의 닫기",style=discord.ButtonStyle.secondary,custom_id=custom_id); self.ticket_id=ticket_id
    async def callback(self,interaction:discord.Interaction):
        ticket=DATA.get("support_tickets",{}).get(self.ticket_id,{})
        if not ticket: await interaction.response.send_message("❌ 문의 티켓 정보를 찾을 수 없습니다.",ephemeral=True); return
        if not (tenant_is_admin(interaction) or int(ticket.get("user_id",0))==interaction.user.id): await interaction.response.send_message("❌ 문의 당사자 또는 관리자만 닫을 수 있습니다.",ephemeral=True); return
        ticket["status"]="closed"; ticket["closed_at"]=now().isoformat(); ticket["closed_by"]=str(interaction.user); await save_data()
        if interaction.guild:
            await send_audit_log(interaction.guild, action="문의 티켓 닫기", detail=f"문의번호 `{self.ticket_id}`를 닫았습니다.", actor=interaction.user)
        channel=interaction.channel; await interaction.response.send_message("🔒 문의 티켓을 2초 후 닫습니다.",ephemeral=True); await asyncio.sleep(2)
        if isinstance(channel,discord.TextChannel):
            await backup_ticket_transcript(channel, metadata=ticket, reason="manual_support_close")
            await channel.delete(reason=f"{BRAND} support closed {self.ticket_id}")


# ----------------------------
# Verification / member roles
# ----------------------------

ROLE_ALIASES = {
    "customer": ["NEXIVO CUSTOMER", "🛍️ NEXIVO CUSTOMER", "🛒 NEXIVO 구매자"],
    "verified": ["NEXIVO VERIFIED", "✅ NEXIVO VERIFIED", "✅ NEXIVO 인증완료"],
    "staff": ["NEXIVO STAFF", "🛡️ NEXIVO STAFF", "🛡️ NEXIVO 스태프"],
}


def _role_is_expected(role: discord.Role | None, key: str) -> bool:
    return bool(role and role.name in ROLE_ALIASES.get(key, []))


async def role_from_config(guild: discord.Guild, key: str, env_id: int = 0) -> discord.Role | None:
    # VERIFIED/CUSTOMER are resolved by BOTH ID and expected role name.
    # This prevents swapped IDs from ever granting the buyer role on verification.
    cfg = config_for_guild(guild.id)
    candidates: list[discord.Role] = []
    for role_id in (cfg.get("roles", {}).get(key, 0), env_id):
        if not role_id:
            continue
        role = guild.get_role(int(role_id))
        if role and role not in candidates:
            candidates.append(role)

    for role in candidates:
        if _role_is_expected(role, key):
            return role

    return next((role for role in guild.roles if _role_is_expected(role, key)), None)


async def add_verified_role(member: discord.Member) -> tuple[bool, str]:
    role = await role_from_config(member.guild, "verified", VERIFIED_ROLE_ID)
    if not role:
        return False, "NEXIVO VERIFIED 역할을 찾을 수 없습니다. `/설정`을 먼저 실행해주세요."
    if role in member.roles:
        return True, "이미 인증되어 있습니다."
    me = member.guild.me
    if me and role >= me.top_role:
        return False, "인증 역할이 봇의 역할보다 위에 있습니다. 서버 역할 목록에서 NEXIVO HUB 봇 역할을 인증 역할보다 위로 올려주세요."
    try:
        # Last-line guard: verification must never target the buyer role.
        customer = await role_from_config(member.guild, "customer", BUYER_ROLE_ID)
        if customer and role.id == customer.id:
            return False, "❌ 인증 역할 설정이 잘못되어 있습니다. `/기능업데이트`를 실행한 뒤 다시 시도해주세요."
        await member.add_roles(role, reason=f"{BRAND} server verification")
        return True, "✅ **인증이 완료되었습니다!**\n🔐 `NEXIVO 인증완료` 역할이 지급되었습니다.\n🛒 구매자 역할은 **상품 구매 완료 후** 별도로 지급됩니다."
    except discord.Forbidden:
        return False, "봇에게 역할 관리 권한이 없거나 인증 역할이 봇보다 높습니다."


async def add_buyer_role(member: discord.Member) -> tuple[bool, str]:
    role = await role_from_config(member.guild, "customer", BUYER_ROLE_ID)
    if not role:
        return False, "NEXIVO CUSTOMER 역할을 찾을 수 없습니다. `/설정`을 먼저 실행해주세요."
    if role in member.roles:
        return True, "이미 구매자 역할이 있습니다."
    me = member.guild.me
    if me and role >= me.top_role:
        return False, "구매자 역할이 봇의 역할보다 위에 있습니다. 봇 역할 순서를 확인해주세요."
    try:
        await member.add_roles(role, reason=f"{BRAND} completed purchase")
        return True, "NEXIVO CUSTOMER 역할을 지급했습니다."
    except discord.Forbidden:
        return False, "구매자 역할 지급에 필요한 역할 관리 권한이 없습니다."


class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VerificationButton())


class VerificationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✅ 인증하기", style=discord.ButtonStyle.success, emoji="🔐", custom_id="nexivo_verify")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
            return
        ok, message = await add_verified_role(interaction.user)
        if ok:
            await send_audit_log(interaction.guild, action="서버 인증", detail="인증 버튼으로 NEXIVO 인증완료 역할을 지급했습니다.", target=interaction.user, actor=interaction.user, level="success")
        await interaction.response.send_message(message, ephemeral=True)


async def send_verification_panel(channel: discord.TextChannel) -> None:
    try:
        async for message in channel.history(limit=30):
            if message.author.id == bot.user.id and message.embeds and message.components:
                for row in message.components:
                    for item in row.children:
                        if getattr(item, "custom_id", None) == "nexivo_verify":
                            return
    except discord.HTTPException:
        pass
    embed = base_embed("✅ NEXIVO HUB • 서버 인증", "아래 버튼을 눌러 간단하게 서버 인증을 완료해주세요.")
    embed.add_field(name="1️⃣ 버튼 클릭", value="`✅ 인증하기` 버튼을 누릅니다.", inline=False)
    embed.add_field(name="2️⃣ 역할 지급", value="인증 성공 시 `NEXIVO VERIFIED` 역할이 자동 지급됩니다.", inline=False)
    await channel.send(embed=embed, view=VerificationView())


# ----------------------------
# Ticket / logging
# ----------------------------

async def get_or_create_category(guild: discord.Guild) -> discord.CategoryChannel | None:
    if ORDER_CATEGORY_ID:
        ch = guild.get_channel(ORDER_CATEGORY_ID)
        if isinstance(ch, discord.CategoryChannel): return ch
    cid = config_for_guild(guild.id).get("categories", {}).get("order_category")
    if cid:
        ch = guild.get_channel(int(cid))
        if isinstance(ch, discord.CategoryChannel): return ch
    ch = discord.utils.get(guild.categories, name=SETUP_CATEGORY_NAMES["order"])
    if isinstance(ch, discord.CategoryChannel):
        config_for_guild(guild.id).setdefault("categories", {})["order_category"] = ch.id; return ch
    try:
        ch = await guild.create_category(SETUP_CATEGORY_NAMES["order"], reason=f"{BRAND} order category recovery")
        config_for_guild(guild.id).setdefault("categories", {})["order_category"] = ch.id; await save_data(); return ch
    except discord.HTTPException: return None


async def create_order_ticket(interaction: discord.Interaction, product: dict[str, Any]) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ 서버에서만 구매할 수 있습니다.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    for oid, order in DATA["orders"].items():
        if int(order.get("user_id",0))==interaction.user.id and int(order.get("guild_id",0))==interaction.guild.id and order.get("status") not in {"완료","취소"}:
            existing=interaction.guild.get_channel(int(order.get("channel_id",0)))
            if existing: await interaction.followup.send(f"❌ 이미 진행 중인 주문이 있습니다. {existing.mention}",ephemeral=True); return
    order_id=f"VX-{next_number('order'):04d}"; cfg=config_for_guild(interaction.guild.id)
    prior_completed = completed_purchase_count_before(interaction.user.id)
    overwrites={interaction.guild.default_role:secure_overwrite(view_channel=False),interaction.user:secure_overwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True)}
    staff_role_id=cfg.get("roles",{}).get("staff",0); staff_role=interaction.guild.get_role(int(staff_role_id)) if staff_role_id else None
    if staff_role: overwrites[staff_role]=secure_overwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True)
    if interaction.guild.me: overwrites[interaction.guild.me]=secure_overwrite(view_channel=True,send_messages=True,manage_channels=True,read_message_history=True,attach_files=True)
    category=await get_or_create_category(interaction.guild)
    channel=await interaction.guild.create_text_channel(f"order-{order_id.lower()}",category=category,overwrites=overwrites,topic=f"{BRAND} 주문 {order_id} · {product['name']}",reason=f"{BRAND} order ticket")
    total=int(product.get("price",0))
    order={"id":order_id,"guild_id":interaction.guild.id,"user_id":interaction.user.id,"username":str(interaction.user),"channel_id":channel.id,"product_id":product["id"],"product_name":product["name"],"category":product.get("category","기타"),"quantity":1,"unit_price":total,"total":total,"status":"주문접수","created_at":now().isoformat(),"prior_completed_purchase_count":prior_completed,"customer_type":"repeat" if prior_completed > 0 else "first"}
    DATA["orders"][order_id]=order; await save_data()
    intro = "안녕하세요 {0}님! **주문 내용을 먼저 확인한 뒤 결제를 진행해주세요.**".format(interaction.user.mention)
    if prior_completed > 0:
        intro += f"\n\n🔁 **재구매 고객** · 완료 구매 {prior_completed}건"
    else:
        intro += "\n\n🆕 **첫 구매 고객**"
    embed=base_embed("╔══ 🎫 NEXIVO HUB • PURCHASE CENTER ══╗",intro)
    embed.add_field(name="🧾 주문번호",value=f"`{order_id}`",inline=True); embed.add_field(name="👤 구매자",value=interaction.user.mention,inline=True); embed.add_field(name="📌 상태",value="`주문접수`",inline=True)
    embed.add_field(name="🛍️ 구매 상태", value=purchase_customer_label(prior_completed), inline=True)
    embed.add_field(name="📊 이전 완료 구매", value=f"`{prior_completed}건`", inline=True)
    embed.add_field(name="📦 주문 상품",value=truncate(product["name"],100),inline=False); embed.add_field(name="🔢 수량",value="`1개`",inline=True); embed.add_field(name="💰 단가",value=money(order["unit_price"]),inline=True); embed.add_field(name="💵 최종 결제금액",value=f"**{money(order['total'])}**",inline=True)
    embed.add_field(name="〔 PAYMENT ACCOUNT 〕",value=f"**{BANK_INFO}**",inline=False); embed.add_field(name="〔 DOUBLE WINDOW 〕",value="`「🪟」이중창` 안내를 확인한 뒤 **실제 결제 앱에서만** 이체해주세요.",inline=False)
    embed.add_field(name="📌 진행 순서",value="① 주문 확인 → ② 실제 입금 → ③ `💳 입금 확인 요청` → ④ 관리자 확인 → ⑤ 상품 지급 → ⑥ 후기",inline=False)
    if product.get("features"): embed.add_field(name="📦 상품 구성",value="\n".join(f"• {truncate(x,90)}" for x in product["features"][:8]),inline=False)
    embed.add_field(name="⚠️ 중요",value="계좌 정보는 **이 구매 티켓 내부에서만** 안내됩니다. 다른 공개 채널에 복사하지 마세요.",inline=False); embed.set_footer(text=f"{BRAND} • 주문번호 {order_id}")
    msg=await channel.send(content=interaction.user.mention,embed=embed,view=TicketView(order_id)); order["ticket_message_id"]=msg.id; await save_data()
    await channel.send("🔒 주문 티켓은 구매자와 스태프만 볼 수 있습니다. 개인정보·OTP·비밀번호를 남기지 마세요.")
    await send_audit_log(interaction.guild, action="주문 생성", detail="새 주문 티켓이 생성되었습니다.", order=order, target=interaction.user)
    await interaction.followup.send(f"✅ 구매 티켓을 생성했습니다. {channel.mention}",ephemeral=True)


def _parse_dt(value: Any) -> datetime | None:
    try:
        if not value:
            return None
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _status_label(status: str) -> str:
    return {
        "주문접수": "🟡 주문접수",
        "입금확인요청": "🟠 입금확인",
        "처리중": "🔵 처리중",
        "완료": "🟢 완료",
        "취소": "🔴 취소",
    }.get(status, f"⚪ {status or '-'}")


async def _resolve_staff_channel(guild: discord.Guild) -> discord.TextChannel | None:
    cfg = config_for_guild(guild.id)
    cid = cfg.get("channels", {}).get("staff_chat", 0)
    channel = guild.get_channel(int(cid)) if cid else None
    if isinstance(channel, discord.TextChannel):
        return channel
    fallback = discord.utils.get(guild.text_channels, name=SETUP_CHANNELS["staff"]["staff_chat"][0])
    if isinstance(fallback, discord.TextChannel):
        cfg.setdefault("channels", {})["staff_chat"] = fallback.id
        try:
            await save_data()
        except Exception:
            pass
        return fallback
    return None


async def send_staff_alert(
    guild: discord.Guild,
    *,
    title: str,
    description: str,
    order: dict[str, Any] | None = None,
    actor: discord.abc.User | None = None,
    level: str = "normal",
) -> bool:
    """Send an operational alert to the private staff room, never to DMs."""
    channel = await _resolve_staff_channel(guild)
    if not channel:
        # Fallback to the order ticket so an alert is still visible to staff.
        if order:
            ticket = guild.get_channel(int(order.get("channel_id", 0)))
            if isinstance(ticket, discord.TextChannel):
                channel = ticket
    if not channel:
        return False

    color = {
        "success": discord.Colour.green(),
        "warning": discord.Colour.gold(),
        "danger": discord.Colour.red(),
        "normal": discord.Colour.blurple(),
    }.get(level, discord.Colour.blurple())
    embed = base_embed(f"╭─── ✦ {title} ✦ ───╮", description, color)
    if order:
        embed.add_field(name="🧾 주문번호", value=f"`{order.get('id', '-')}`", inline=True)
        embed.add_field(name="👤 구매자", value=f"<@{int(order.get('user_id', 0))}>" if order.get("user_id") else "-", inline=True)
        embed.add_field(name="📦 상품", value=truncate(order.get("product_name"), 70), inline=True)
        embed.add_field(name="📌 상태", value=_status_label(str(order.get("status", "-"))), inline=True)
        embed.add_field(name="💵 금액", value=money(int(order.get("total", 0))), inline=True)
    if actor:
        embed.add_field(name="🛠️ 작업자", value=f"{actor.mention}\n`{actor.id}`", inline=True)
    embed.set_footer(text=f"{BRAND} • STAFF ALERT • {_discord_date(now())}")
    try:
        cfg = config_for_guild(guild.id)
        staff_id = int(cfg.get("roles", {}).get("staff", 0) or 0)
        staff_role = guild.get_role(staff_id) if staff_id else None
        content = staff_role.mention if staff_role else None
        allowed = discord.AllowedMentions(roles=True, users=False, everyone=False) if staff_role else discord.AllowedMentions.none()
        await channel.send(content=content, embed=embed, allowed_mentions=allowed)
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[{BRAND}] staff alert failed: {exc!r}")
        return False


async def send_audit_log(
    guild: discord.Guild,
    *,
    action: str,
    detail: str = "",
    order: dict[str, Any] | None = None,
    actor: discord.abc.User | None = None,
    target: discord.abc.User | None = None,
    level: str = "normal",
) -> None:
    """Internal audit log. This is separate from the public purchase-complete log."""
    cfg = config_for_guild(guild.id)
    channel_id = cfg.get("channels", {}).get("bot_log", 0)
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        return
    color = {
        "success": discord.Colour.green(),
        "warning": discord.Colour.gold(),
        "danger": discord.Colour.red(),
        "normal": discord.Colour.blurple(),
    }.get(level, discord.Colour.blurple())
    embed = base_embed(f"╭─── ✦ AUDIT • {action} ✦ ───╮", detail or "내부 작업 로그", color)
    if actor:
        embed.add_field(name="🛠️ 작업자", value=f"{actor.mention}\n`{actor.id}`", inline=True)
    if target:
        embed.add_field(name="👤 대상", value=f"{target.mention}\n`{target.id}`", inline=True)
    if order:
        embed.add_field(name="🧾 주문", value=f"`{order.get('id', '-')}`", inline=True)
        embed.add_field(name="📦 상품", value=truncate(order.get("product_name"), 70), inline=True)
        embed.add_field(name="📌 상태", value=_status_label(str(order.get("status", "-"))), inline=True)
    embed.set_footer(text=f"{BRAND} • INTERNAL AUDIT • {_discord_date(now())}")
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[{BRAND}] audit log failed: {exc!r}")


def build_order_dashboard_embed(guild: discord.Guild, status_filter: str = "전체") -> discord.Embed:
    orders = [o for o in DATA.get("orders", {}).values() if str(o.get("guild_id", "")) == str(guild.id)]
    total_count = len(orders)
    count_map = {status: sum(1 for o in orders if o.get("status") == status) for status in ("주문접수", "입금확인요청", "처리중", "완료", "취소")}
    active = [o for o in orders if o.get("status") not in {"완료", "취소"}]
    if status_filter != "전체":
        visible = [o for o in orders if o.get("status") == status_filter]
    else:
        visible = active or orders
    visible = sorted(visible, key=lambda o: o.get("created_at", ""), reverse=True)[:12]

    embed = base_embed(
        "╭─── ✦ NEXIVO HUB • ORDER CONTROL ✦ ───╮",
        "실시간 주문 상태를 한눈에 확인하는 **관리자 전용 운영 대시보드**입니다.\n버튼으로 상태별 주문을 필터링할 수 있습니다.",
    )
    embed.add_field(name="🛒 전체", value=f"`{total_count:,}`건", inline=True)
    embed.add_field(name="🟡 접수", value=f"`{count_map['주문접수']:,}`건", inline=True)
    embed.add_field(name="🟠 입금확인", value=f"`{count_map['입금확인요청']:,}`건", inline=True)
    embed.add_field(name="🔵 처리중", value=f"`{count_map['처리중']:,}`건", inline=True)
    embed.add_field(name="🟢 완료", value=f"`{count_map['완료']:,}`건", inline=True)
    embed.add_field(name="🔴 취소", value=f"`{count_map['취소']:,}`건", inline=True)

    if not visible:
        embed.add_field(name="📭 주문 없음", value="해당 조건의 주문이 없습니다.", inline=False)
    else:
        rows = []
        for o in visible:
            created = _parse_dt(o.get("created_at"))
            age = "-"
            if created:
                mins = max(0, int((now() - created).total_seconds() // 60))
                age = f"{mins}분 전" if mins < 60 else f"{mins // 60}시간 {mins % 60}분 전"
            rows.append(
                f"{_status_label(str(o.get('status', '-')))}  `#{o.get('id','-')}` · **{truncate(o.get('product_name'), 45)}**\n"
                f"└ <@{int(o.get('user_id', 0))}> · `{money(int(o.get('total', 0)))}` · {age}"
            )
        embed.add_field(name=f"📋 {status_filter} • 최근 {len(rows)}건", value="\n\n".join(rows), inline=False)
        quick_count = sum(
            1
            for o in visible
            if bot.get_guild(int(o.get("guild_id", 0) or 0))
            and isinstance(
                bot.get_guild(int(o.get("guild_id", 0) or 0)).get_channel(int(o.get("channel_id", 0) or 0)),
                discord.TextChannel,
            )
        )
        if quick_count:
            embed.add_field(name="⚡ 빠른 이동", value="아래 `🎫 주문번호` 버튼을 누르면 해당 주문 티켓으로 바로 이동합니다.", inline=False)
    embed.set_footer(text=f"{BRAND} • FILTER: {status_filter} • 관리자 전용")
    return embed


def _dashboard_visible_orders(status_filter: str = "전체", guild_id: int | str | None = None) -> list[dict[str, Any]]:
    orders = [o for o in DATA.get("orders", {}).values() if guild_id is None or str(o.get("guild_id", "")) == str(guild_id)]
    active = [o for o in orders if o.get("status") not in {"완료", "취소"}]
    if status_filter != "전체":
        visible = [o for o in orders if o.get("status") == status_filter]
    else:
        visible = active or orders
    return sorted(visible, key=lambda o: o.get("created_at", ""), reverse=True)[:12]


class OrderDashboardView(discord.ui.View):
    def __init__(self, quick_orders: list[dict[str, Any]] | None = None):
        super().__init__(timeout=300)
        # Five fixed filter buttons use row 0. Up to 20 quick-jump buttons fill rows 1-4.
        # This keeps the view inside Discord's 25-component / 5-row limits.
        for index, order in enumerate((quick_orders or [])[:20]):
            guild = bot.get_guild(int(order.get("guild_id", 0) or 0))
            channel = guild.get_channel(int(order.get("channel_id", 0) or 0)) if guild else None
            if isinstance(channel, discord.TextChannel):
                row = 1 + index // 5
                self.add_item(OrderQuickJumpButton(order, row=row))

    async def _show(self, interaction: discord.Interaction, status_filter: str):
        if not tenant_is_admin(interaction):
            await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
            return
        embed = build_order_dashboard_embed(interaction.guild, status_filter)
        visible = _dashboard_visible_orders(status_filter, interaction.guild.id if interaction.guild else None)
        view = OrderDashboardView(visible)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="전체", style=discord.ButtonStyle.secondary, row=0)
    async def all_orders(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "전체")

    @discord.ui.button(label="🟡 접수", style=discord.ButtonStyle.primary, row=0)
    async def new_orders(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "주문접수")

    @discord.ui.button(label="🟠 입금확인", style=discord.ButtonStyle.success, row=0)
    async def payment_orders(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "입금확인요청")

    @discord.ui.button(label="🔵 처리중", style=discord.ButtonStyle.primary, row=0)
    async def processing_orders(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "처리중")

    @discord.ui.button(label="🔴 취소", style=discord.ButtonStyle.danger, row=0)
    async def cancelled_orders(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "취소")


async def create_data_backup(reason: str = "scheduled") -> bool:
    """Create a timestamped backup of data.json and keep a bounded rolling history."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        try:
            await save_data()
        except Exception as exc:
            print(f"[{BRAND}] backup source save failed: {exc!r}")
            return False
    stamp = now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"data_{stamp}_{reason}.json"
    try:
        shutil.copy2(DATA_FILE, target)
        # Keep the newest N data backups.
        backups = sorted(BACKUP_DIR.glob("data_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[BACKUP_KEEP_COUNT:]:
            try:
                old.unlink()
            except OSError:
                pass
        return True
    except Exception as exc:
        print(f"[{BRAND}] automatic backup failed: {exc!r}")
        return False


async def maintenance_loop() -> None:
    """Payment reminders, safe order timeouts, and periodic data backups."""
    loop_started = now()
    last_backup = loop_started - timedelta(seconds=BACKUP_INTERVAL_SECONDS + 1)
    while True:
        try:
            current = now()
            changed = False
            for oid, order in list(DATA.get("orders", {}).items()):
                status = str(order.get("status", ""))
                guild = bot.get_guild(int(order.get("guild_id", 0))) if order.get("guild_id") else None
                if not guild:
                    continue

                if status == "완료":
                    # One review reminder after 24h, only when the purchase still has no review.
                    if not _review_exists(str(order.get("id", ""))) and not order.get("review_reminder_sent"):
                        completed_at = _parse_dt(order.get("completed_at"))
                        attempted_at = _parse_dt(order.get("review_reminder_attempted_at"))
                        elapsed = (current - completed_at).total_seconds() / 60 if completed_at else 0
                        retry_ok = attempted_at is None or (current - attempted_at).total_seconds() >= 6 * 3600
                        if elapsed >= REVIEW_REMINDER_MINUTES and retry_ok:
                            try:
                                user = guild.get_member(int(order.get("user_id", 0))) or await guild.fetch_member(int(order.get("user_id", 0)))
                            except (discord.NotFound, discord.HTTPException):
                                user = None
                            if user:
                                sent = await send_review_reminder_dm(user, order)
                                if sent:
                                    changed = True
                                    print(f"[{BRAND}] review reminder sent for {order.get('id')}")
                                else:
                                    changed = True
                    continue
                if status == "취소":
                    continue

                if status == "입금확인요청":
                    requested = _parse_dt(order.get("payment_requested_at"))
                    if requested:
                        elapsed_min = (current - requested).total_seconds() / 60
                        if elapsed_min >= PAYMENT_REMINDER_2_MINUTES and not order.get("payment_reminder_30_sent"):
                            await send_staff_alert(
                                guild,
                                title="⏰ 입금 확인 재알림",
                                description=f"주문 `{oid}`의 입금 확인 요청이 **{PAYMENT_REMINDER_2_MINUTES}분 이상** 미처리 상태입니다. 확인해주세요.",
                                order=order,
                                level="warning",
                            )
                            await send_audit_log(guild, action="입금 확인 재알림", detail="30분 미처리 자동 알림", order=order, level="warning")
                            order["payment_reminder_30_sent"] = current.isoformat()
                            changed = True
                        elif elapsed_min >= PAYMENT_REMINDER_1_MINUTES and not order.get("payment_reminder_10_sent"):
                            await send_staff_alert(
                                guild,
                                title="🔔 입금 확인 알림",
                                description=f"주문 `{oid}`의 입금 확인 요청이 **{PAYMENT_REMINDER_1_MINUTES}분 이상** 미처리 상태입니다.",
                                order=order,
                                level="warning",
                            )
                            await send_audit_log(guild, action="입금 확인 알림", detail="10분 미처리 자동 알림", order=order, level="warning")
                            order["payment_reminder_10_sent"] = current.isoformat()
                            changed = True

                        if elapsed_min >= PAYMENT_PENDING_TIMEOUT_MINUTES:
                            order["status"] = "취소"
                            order["cancelled_at"] = current.isoformat()
                            order["cancelled_reason"] = f"입금확인요청 {PAYMENT_PENDING_TIMEOUT_MINUTES}분 초과 자동 만료"
                            changed = True
                            await send_staff_alert(
                                guild,
                                title="🛑 주문 자동 만료",
                                description=f"주문 `{oid}`이 입금 확인 요청 후 **{PAYMENT_PENDING_TIMEOUT_MINUTES}분**이 지나 자동 취소되었습니다.",
                                order=order,
                                level="danger",
                            )
                            await send_audit_log(guild, action="주문 자동 취소", detail=order["cancelled_reason"], order=order, level="danger")
                            channel = guild.get_channel(int(order.get("channel_id", 0))) if order.get("channel_id") else None
                            if isinstance(channel, discord.TextChannel):
                                try:
                                    await channel.send(embed=base_embed(
                                        "╭─── ✦ NEXIVO HUB • ORDER EXPIRED ✦ ───╮",
                                        f"⏰ 주문 `{oid}`은(는) 입금 확인 요청 후 제한 시간을 초과하여 **자동 취소**되었습니다.\n새 주문이 필요하면 다시 자판기를 이용해주세요.",
                                        discord.Colour.red(),
                                    ))
                                    await asyncio.sleep(2)
                                    await backup_ticket_transcript(channel, metadata=order, reason="payment_pending_timeout")
                                    await channel.delete(reason=f"{BRAND} automatic order timeout {oid}")
                                except discord.HTTPException:
                                    pass
                            continue

                elif status == "주문접수":
                    created = _parse_dt(order.get("created_at"))
                    if created:
                        elapsed_min = (current - created).total_seconds() / 60
                        if elapsed_min >= UNPAID_ORDER_TIMEOUT_MINUTES:
                            order["status"] = "취소"
                            order["cancelled_at"] = current.isoformat()
                            order["cancelled_reason"] = f"주문 생성 후 {UNPAID_ORDER_TIMEOUT_MINUTES}분 내 입금 확인 요청 없음"
                            changed = True
                            await send_staff_alert(
                                guild,
                                title="🛑 미입금 주문 자동 만료",
                                description=f"주문 `{oid}`이 **{UNPAID_ORDER_TIMEOUT_MINUTES}분** 동안 입금 확인 요청 없이 남아 있어 자동 취소되었습니다.",
                                order=order,
                                level="danger",
                            )
                            await send_audit_log(guild, action="미입금 주문 자동 취소", detail=order["cancelled_reason"], order=order, level="danger")
                            channel = guild.get_channel(int(order.get("channel_id", 0))) if order.get("channel_id") else None
                            if isinstance(channel, discord.TextChannel):
                                try:
                                    await channel.send(embed=base_embed(
                                        "╭─── ✦ NEXIVO HUB • ORDER EXPIRED ✦ ───╮",
                                        f"⏰ 주문 `{oid}`은(는) **{UNPAID_ORDER_TIMEOUT_MINUTES}분** 동안 결제 확인 요청이 없어 자동 취소되었습니다.\n필요한 경우 자판기에서 새 주문을 생성해주세요.",
                                        discord.Colour.red(),
                                    ))
                                    await asyncio.sleep(2)
                                    await backup_ticket_transcript(channel, metadata=order, reason="unpaid_order_timeout")
                                    await channel.delete(reason=f"{BRAND} unpaid order timeout {oid}")
                                except discord.HTTPException:
                                    pass

            if changed:
                await save_data()

            if (current - last_backup).total_seconds() >= BACKUP_INTERVAL_SECONDS:
                if await create_data_backup("scheduled"):
                    last_backup = current
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[{BRAND}] maintenance loop error: {exc!r}")
        await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)


async def send_log(kind: str, order: dict[str, Any]) -> None:
    if kind != "completed":
        return
    channel_id = PURCHASE_LOG_CHANNEL_ID
    if not channel_id and order.get("guild_id"):
        channel_id = config_for_guild(int(order["guild_id"]))["channels"].get("purchase_log", 0)
    channel = bot.get_channel(int(channel_id)) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        return
    embed = base_embed(
        "╔══ ✅ NEXIVO HUB • 구매 완료 ══╗",
        "**구매해주셔서 감사합니다!**\n상품 지급이 정상적으로 완료되었습니다.",
        discord.Colour.green(),
    )
    embed.add_field(name="👤 구매자", value=f"<@{order['user_id']}>", inline=True)
    embed.add_field(name="📦 상품", value=truncate(order.get("product_name"), 80), inline=True)
    embed.add_field(name="💵 결제금액", value=money(order.get("total", 0)), inline=True)
    embed.add_field(name="🧾 주문번호", value=f"`{order['id']}`", inline=True)
    embed.add_field(name="🛍️ 구매 횟수", value=f"`{int(order.get('completed_purchase_count', completed_purchase_count(int(order.get('user_id', 0) or 0))))}건`", inline=True)
    embed.add_field(name="✅ 상태", value="`지급 완료`", inline=True)
    try:
        user = channel.guild.get_member(int(order["user_id"])) or await channel.guild.fetch_member(int(order["user_id"]))
        if user:
            embed.set_author(name=f"{user.display_name} • 구매 완료", icon_url=user.display_avatar.url)
            embed.set_thumbnail(url=user.display_avatar.url)
    except (discord.NotFound, discord.HTTPException):
        pass
    embed.set_footer(text=f"{BRAND} • 구매해주셔서 감사합니다")
    await channel.send(embed=embed)


async def publish_review(review: dict[str, Any], order: dict[str, Any]) -> bool:
    channel_id = REVIEW_CHANNEL_ID
    if not channel_id and order.get("guild_id"):
        channel_id = config_for_guild(int(order["guild_id"]))["channels"].get("review", 0)
    channel = bot.get_channel(int(channel_id)) if channel_id else None
    if not isinstance(channel, discord.TextChannel) and order.get("guild_id"):
        guild = bot.get_guild(int(order["guild_id"]))
        if guild:
            channel = discord.utils.get(guild.text_channels, name="「⭐」구매후기")
    if not isinstance(channel, discord.TextChannel):
        return False
    stars = "⭐" * int(review["rating"])
    embed = base_embed("╔══ ⭐ NEXIVO HUB • 구매후기 ══╗", color=discord.Colour.gold())
    embed.add_field(name="👤 구매자", value=f"<@{review['user_id']}>", inline=True)
    embed.add_field(name="📦 상품", value=truncate(order.get("product_name"), 80), inline=True)
    embed.add_field(name="⭐ 별점", value=stars, inline=True)
    embed.add_field(name="💬 후기", value=truncate(review["content"], 1000), inline=False)
    try:
        user = channel.guild.get_member(int(review["user_id"])) or await channel.guild.fetch_member(int(review["user_id"]))
        if user:
            embed.set_author(name=f"{user.display_name} • 구매후기", icon_url=user.display_avatar.url)
            embed.set_thumbnail(url=user.display_avatar.url)
    except (discord.NotFound, discord.HTTPException):
        pass
    embed.set_footer(text=f"주문번호 {order['id']} • {review['id']}")
    await channel.send(embed=embed)
    return True



# ----------------------------
# Server auto setup / aesthetic layout
# ----------------------------

def config_for_guild(guild_id: int) -> dict[str, Any]:
    cfg = DATA.setdefault("server_config", {})
    return cfg.setdefault(str(guild_id), {"categories": {}, "channels": {}, "roles": {}})


async def get_or_create_role(guild: discord.Guild, name: str, **kwargs) -> discord.Role:
    existing = discord.utils.get(guild.roles, name=name)
    if existing:
        return existing
    return await guild.create_role(name=name, reason=f"{BRAND} server setup", **kwargs)


async def _apply_staff_overwrites(guild: discord.Guild, channel_or_category: discord.CategoryChannel | discord.TextChannel) -> None:
    if not isinstance(channel_or_category, (discord.CategoryChannel, discord.TextChannel)):
        return
    staff_role_id = config_for_guild(guild.id).get("roles", {}).get("staff", 0) or 0
    overwrites = dict(channel_or_category.overwrites)
    staff_role = guild.get_role(int(staff_role_id)) if staff_role_id else None
    if staff_role:
        overwrites[staff_role] = secure_overwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
    if guild.me:
        overwrites[guild.me] = secure_overwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True)
    await channel_or_category.edit(overwrites=overwrites, reason=f"{BRAND} security layout update")


async def ensure_category(guild: discord.Guild, key: str) -> discord.CategoryChannel:
    cfg = config_for_guild(guild.id)
    cat_id = cfg["categories"].get(key)
    if cat_id:
        cat = guild.get_channel(int(cat_id))
        if isinstance(cat, discord.CategoryChannel):
            await cat.edit(name=SETUP_CATEGORY_NAMES[key], reason=f"{BRAND} category design")
            if key == "staff":
                await _apply_staff_overwrites(guild, cat)
            return cat
    name = SETUP_CATEGORY_NAMES[key]
    cat = discord.utils.get(guild.categories, name=name)
    if not cat:
        overwrites = {}
        if key == "staff":
            overwrites[guild.default_role] = secure_overwrite(view_channel=False)
            if guild.me:
                overwrites[guild.me] = secure_overwrite(view_channel=True, manage_channels=True, send_messages=True, read_message_history=True)
            staff_role = discord.utils.get(guild.roles, name="NEXIVO STAFF")
            if staff_role:
                overwrites[staff_role] = secure_overwrite(view_channel=True, send_messages=True, read_message_history=True)
        cat = await guild.create_category(name=name, overwrites=overwrites, reason=f"{BRAND} auto layout")
    cfg["categories"][key] = cat.id
    return cat


async def update_existing_category(guild: discord.Guild, key: str) -> tuple[discord.CategoryChannel | None, str]:
    cfg = config_for_guild(guild.id)
    cat_id = cfg.get("categories", {}).get(key)
    cat = guild.get_channel(int(cat_id)) if cat_id else None

    if not isinstance(cat, discord.CategoryChannel):
        # Recover the saved mapping by the exact NEXIVO category name.
        cat = discord.utils.get(guild.categories, name=SETUP_CATEGORY_NAMES[key])
        if isinstance(cat, discord.CategoryChannel):
            cfg.setdefault("categories", {})[key] = cat.id
            state = "linked"
        else:
            return None, "missing"
    else:
        state = "checked"

    changed = cat.name != SETUP_CATEGORY_NAMES[key]
    if changed:
        await cat.edit(name=SETUP_CATEGORY_NAMES[key], reason=f"{BRAND} category redesign")
        state = "updated"
    if key == "staff":
        await _apply_staff_overwrites(guild, cat)
    return cat, state


async def ensure_text_channel(guild: discord.Guild, category: discord.CategoryChannel, channel_key: str, name: str, topic: str) -> discord.TextChannel:
    cfg = config_for_guild(guild.id)
    cid = cfg["channels"].get(channel_key)
    if cid:
        ch = guild.get_channel(int(cid))
        if isinstance(ch, discord.TextChannel):
            await ch.edit(name=name, topic=topic, category=category, reason=f"{BRAND} channel design")
            return ch
    ch = discord.utils.get(category.text_channels, name=name)
    if not ch:
        ch = await guild.create_text_channel(name, category=category, topic=topic, reason=f"{BRAND} auto layout")
    cfg["channels"][channel_key] = ch.id
    return ch


async def update_existing_text_channel(guild: discord.Guild, category: discord.CategoryChannel, channel_key: str, name: str, topic: str) -> tuple[discord.TextChannel | None, str]:
    cfg = config_for_guild(guild.id)
    cid = cfg.get("channels", {}).get(channel_key)
    ch = guild.get_channel(int(cid)) if cid else None

    if not isinstance(ch, discord.TextChannel):
        # Recover stale/missing channel mappings by exact name.
        ch = discord.utils.get(category.text_channels, name=name)
        if not isinstance(ch, discord.TextChannel):
            return None, "missing"
        cfg.setdefault("channels", {})[channel_key] = ch.id
        state = "linked"
    else:
        state = "updated"

    await ch.edit(name=name, topic=topic, category=category, reason=f"{BRAND} channel redesign")
    return ch, state


async def ensure_voice_channel(guild: discord.Guild, category: discord.CategoryChannel, channel_key: str, name: str) -> discord.VoiceChannel:
    cfg = config_for_guild(guild.id)
    cid = cfg["channels"].get(channel_key)
    if cid:
        ch = guild.get_channel(int(cid))
        if isinstance(ch, discord.VoiceChannel):
            await ch.edit(name=name, category=category, reason=f"{BRAND} channel design")
            return ch
    ch = discord.utils.get(category.voice_channels, name=name)
    if not ch:
        ch = await guild.create_voice_channel(name, category=category, reason=f"{BRAND} auto layout")
    cfg["channels"][channel_key] = ch.id
    return ch


async def update_existing_voice_channel(guild: discord.Guild, category: discord.CategoryChannel, channel_key: str, name: str) -> tuple[discord.VoiceChannel | None, str]:
    cfg = config_for_guild(guild.id)
    cid = cfg.get("channels", {}).get(channel_key)
    ch = guild.get_channel(int(cid)) if cid else None
    if not isinstance(ch, discord.VoiceChannel):
        return None, "missing"
    await ch.edit(name=name, category=category, reason=f"{BRAND} channel redesign")
    return ch, "updated"


async def _verified_overwrites(guild: discord.Guild, *, readonly: bool = True) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    cfg = config_for_guild(guild.id)
    verified_id = cfg.get("roles", {}).get("verified", 0) or VERIFIED_ROLE_ID
    customer_id = cfg.get("roles", {}).get("customer", 0) or BUYER_ROLE_ID
    staff_id = cfg.get("roles", {}).get("staff", 0) or 0
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: secure_overwrite(view_channel=False, send_messages=False),
    }
    for rid in (verified_id, customer_id):
        if rid:
            role = guild.get_role(int(rid))
            if role:
                overwrites[role] = secure_overwrite(
                    view_channel=True,
                    send_messages=not readonly,
                    read_message_history=True,
                    attach_files=not readonly,
                    embed_links=True,
                    use_application_commands=True,
                )
    if staff_id:
        role = guild.get_role(int(staff_id))
        if role:
            overwrites[role] = secure_overwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True, use_application_commands=True,
            )
    if guild.me:
        overwrites[guild.me] = secure_overwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True, manage_channels=True, manage_messages=True,
            use_application_commands=True,
        )
    return overwrites


async def update_channel_permissions(guild: discord.Guild, key: str, channel: discord.abc.GuildChannel) -> None:
    if isinstance(channel, discord.VoiceChannel):
        # Voice is public only to verified members; no text chat restriction is needed here.
        overwrites = await _verified_overwrites(guild, readonly=True)
        for ow in overwrites.values():
            ow.send_messages = False
        await channel.edit(overwrites=overwrites, reason=f"{BRAND} verified-only voice layout")
        return
    if not isinstance(channel, discord.TextChannel):
        return

    # Welcome / leave / verification are the only onboarding channels visible before verification.
    if key in {"welcome", "leave", "verification"}:
        overwrites = dict(channel.overwrites)
        overwrites[guild.default_role] = secure_overwrite(
            view_channel=True, send_messages=False, read_message_history=True, add_reactions=False
        )
        # Prevent unverified members from bypassing read-only via broader role/channel defaults.
        cfg = config_for_guild(guild.id)
        for rid in (cfg.get("roles", {}).get("verified", 0) or VERIFIED_ROLE_ID, cfg.get("roles", {}).get("customer", 0) or BUYER_ROLE_ID):
            if rid:
                role = guild.get_role(int(rid))
                if role:
                    overwrites[role] = secure_overwrite(view_channel=True, send_messages=False, read_message_history=True)
        staff_id = cfg.get("roles", {}).get("staff", 0) or 0
        if staff_id and (role := guild.get_role(int(staff_id))):
            overwrites[role] = secure_overwrite(view_channel=True, send_messages=False, read_message_history=True)
        if guild.me:
            overwrites[guild.me] = secure_overwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True)
        await channel.edit(overwrites=overwrites, reason=f"{BRAND} onboarding channel permissions")
        return

    # Store/order/support/informational panels are read-only and visible only after verification.
    readonly_keys = {
        "notice", "guide", "vending", "products", "popular", "reviews", "order_guide", "payment_help", "payment",
        "help", "partnership", "custom", "showcase", "event",
    }
    if key in readonly_keys:
        await channel.edit(overwrites=await _verified_overwrites(guild, readonly=True), reason=f"{BRAND} verified-only readonly layout")
        return

    # Community chat is visible to verified members and writable for them.
    if key == "chat":
        await channel.edit(overwrites=await _verified_overwrites(guild, readonly=False), reason=f"{BRAND} verified-only chat layout")
        return

    # Staff area is private.
    if key in {"purchase_log", "bot_log", "staff_chat"}:
        overwrites = await _verified_overwrites(guild, readonly=True)
        for role in list(overwrites):
            if role != guild.me and role != guild.default_role:
                overwrites[role] = secure_overwrite(view_channel=False)
        cfg = config_for_guild(guild.id)
        staff_id = cfg.get("roles", {}).get("staff", 0) or 0
        if staff_id and (role := guild.get_role(int(staff_id))):
            overwrites[role] = secure_overwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
        await channel.edit(overwrites=overwrites, reason=f"{BRAND} staff-only layout")
        return


async def send_setup_panel(channel: discord.TextChannel, kind: str, force: bool = False) -> None:
    marker = f"nexivo_setup::{kind}"
    # During an update, edit the existing bot panel instead of posting another copy.
    target_message: discord.Message | None = None
    if kind == "vending":
        panel_id = config_for_guild(channel.guild.id).get("panels", {}).get("vending_message_id", 0)
        if panel_id:
            try:
                target_message = await channel.fetch_message(int(panel_id))
            except (discord.NotFound, discord.HTTPException, ValueError, TypeError):
                target_message = None
    try:
        if target_message is None:
            async for message in channel.history(limit=50):
                if message.author.id == bot.user.id and message.embeds:
                    footer = message.embeds[0].footer.text if message.embeds[0].footer else ""
                    if marker in footer:
                        target_message = message
                        break
    except discord.HTTPException:
        pass

    if kind == "welcome":
        embed = base_embed(
            "╭─── 👋 NEXIVO HUB • WELCOME ───╮",
            "**NEXIVO HUB에 오신 것을 환영합니다.**\n\n디지털 상품 · 자동화 · 주문 시스템을 한곳에서 편하게 이용하세요.",
        )
        embed.add_field(name="✅ 01 • 서버 인증", value="`「✅」서버인증`에서 **인증하기**를 눌러 `NEXIVO 인증완료` 역할을 받아주세요.", inline=False)
        embed.add_field(name="🛒 02 • 상품 선택", value="`「🛍️」자판기`에서 원하는 상품을 선택하고 상세 정보를 확인합니다.", inline=False)
        embed.add_field(name="🎫 03 • 주문 티켓", value="구매 버튼을 누르면 **구매자와 스태프만 볼 수 있는 비공개 티켓**이 생성됩니다.", inline=False)
        embed.add_field(name="⭐ 04 • 후기", value="상품 지급이 완료되면 후기를 남겨주시면 큰 도움이 됩니다.", inline=False)
    elif kind == "verification":
        embed = base_embed(
            "╭─── 🔐 NEXIVO HUB • SERVER VERIFY ───╮",
            "아래 **✅ 인증하기** 버튼을 눌러 서버 인증을 완료해주세요.",
        )
        embed.add_field(name="① 🔐 인증 버튼", value="버튼을 누르면 **본인 Discord 계정에만** 인증 처리가 진행됩니다.", inline=False)
        embed.add_field(name="② ✅ 지급 역할", value="성공 시 **`NEXIVO 인증완료`** 역할만 지급됩니다.\n`NEXIVO 구매자` 역할은 구매 완료 시에만 지급됩니다.", inline=False)
        embed.add_field(name="③ 🛡️ 안전한 운영", value="인증 역할에는 서버 관리 권한이 없으며, 필요한 채널 접근 권한만 적용됩니다.", inline=False)
        view = VerificationView()
        if target_message:
            await target_message.edit(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
        return
    elif kind == "guide":
        embed = base_embed("╔══ 📖 NEXIVO HUB • 이용 가이드 ══╗", "처음 오셨다면 아래 순서대로 진행해주세요.")
        steps = [
            "`🛒 상품 선택하기` → 카테고리 → 상품을 선택합니다.",
            "상품 상세에서 가격과 구성을 확인합니다.",
            "`🎫 티켓 열기`로 개인 주문 티켓을 생성합니다.",
            "구매 티켓이 생성된 뒤에만 결제 안내와 계좌 정보가 표시됩니다.",
            "티켓에 표시된 계좌와 정확한 금액을 확인한 뒤 실제 이체를 진행합니다.",
            "입금 후 `💳 입금 확인 요청`을 눌러주세요.",
            "관리자가 확인·처리한 뒤 상품이 전달됩니다.",
        ]
        for i, text in enumerate(steps, 1):
            embed.add_field(name=f"〔 {i:02d} 〕", value=text, inline=False)
    elif kind == "order_guide":
        embed = base_embed("╔══ 🎫 NEXIVO HUB • ORDER CENTER ══╗", "주문은 모두 개인 티켓에서 안전하게 진행됩니다. 계좌는 구매 티켓에서만 확인할 수 있습니다.")
        embed.add_field(name="① 상품 선택", value="공개 자판기는 그대로 유지되고, 상품 선택창은 본인에게만 보입니다.", inline=False)
        embed.add_field(name="② 티켓 생성", value="상품 상세 화면의 `🎫 티켓 열기` 버튼을 누릅니다.", inline=False)
        embed.add_field(name="③ 입금", value="티켓에 표시된 정확한 금액으로 입금합니다.", inline=False)
        embed.add_field(name="④ 확인", value="`💳 입금 확인 요청` → 관리자 확인 → 처리 시작", inline=False)
        embed.add_field(name="⑤ 완료", value="상품 전달 후 주문 완료 + 구매자 역할 + 후기 안내가 진행됩니다.", inline=False)
    elif kind == "notice":
        embed = base_embed("╔══ 📢 NEXIVO HUB • NOTICE ══╗", "중요한 서버·상품 공지는 이곳에서 안내합니다.")
    elif kind == "popular":
        await refresh_tenants()
        products = tenant_products(channel.guild.id)
        popular = sorted(products, key=lambda p: int(p.get("price", 0)))[:10]
        embed = base_embed("╔══ 🔥 NEXIVO HUB • POPULAR ══╗", "현재 판매 상품 중 빠르게 확인하기 좋은 상품입니다.")
        if popular:
            embed.add_field(name="✦ 추천 목록", value="\n".join(f"**{p['name']}** · `{money(int(p.get('price', 0)))}`" for p in popular), inline=False)
        else:
            embed.add_field(name="📭 상품 준비 중", value="현재 불러온 상품이 없습니다.", inline=False)
    elif kind == "payment":
        embed = base_embed("╔══ 💳 NEXIVO HUB • PAYMENT GUIDE ══╗", "결제 과정은 주문 티켓 안에서 안전하게 확인할 수 있습니다.")
        embed.add_field(name="① 금액 확인", value="티켓에 표시된 최종 결제금액을 확인합니다.", inline=False)
        embed.add_field(name="② 입금", value="안내된 계좌로 정확한 금액을 이체합니다.", inline=False)
        embed.add_field(name="③ 확인 요청", value="입금 후 티켓의 `입금 확인 요청` 버튼을 눌러주세요.", inline=False)
        embed.add_field(name="④ 지급", value="실제 입금 확인 후 관리자 처리 및 상품 지급이 진행됩니다.", inline=False)
    elif kind == "event":
        embed = base_embed("╔══ 🎉 NEXIVO HUB • EVENT ══╗", "이벤트와 시즌별 혜택을 안내하는 공간입니다.")
        embed.add_field(name="✨ 이벤트 안내", value="새 이벤트가 시작되면 이 채널에 안내합니다.", inline=False)
        embed.add_field(name="🎁 혜택", value="한정 패키지·할인·커뮤니티 이벤트 등 다양한 소식을 확인하세요.", inline=False)
    elif kind == "vending":
        await refresh_tenants()
        embed = main_panel_embed(guild_id=channel.guild.id)
        embed.set_footer(text=f"{BRAND} • nexivo_setup::vending")
        view = VendingLaunchView(channel.guild.id)
        if target_message:
            await target_message.edit(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
        return
    elif kind == "products":
        await refresh_tenants()
        embed = base_embed("╔══ 📦 NEXIVO HUB • PRODUCTS ══╗", "현재 판매 중인 상품입니다.")
        cats: dict[str, list[dict[str, Any]]] = {}
        for prod in tenant_products(channel.guild.id):
            cats.setdefault(str(prod.get("category", "기타")), []).append(prod)
        for cat, items in cats.items():
            embed.add_field(name=f"〔 📂 {cat} 〕", value="\n".join(f"• **{p['name']}** · `{money(int(p.get('price', 0)))}`" for p in items[:15]), inline=False)
    elif kind == "reviews":
        embed = base_embed("╔══ ⭐ NEXIVO HUB • REVIEWS ══╗", "완료된 구매후기가 이 채널에 올라옵니다.", discord.Colour.gold())
        embed.add_field(name="📝 후기 작성", value="완료된 주문은 `/후기작성`으로 간단하게 후기를 남길 수 있습니다.", inline=False)
    elif kind == "payment_help":
        embed = base_embed("╔══ 🪟 NEXIVO HUB • 이중창 입금 안내 ══╗", "실제 입금 여부를 확인하기 위한 **이중창(분할 화면) 방식**을 안내합니다.")
        embed.add_field(name="① 이중창으로 준비", value="한쪽에는 **NEXIVO 주문 티켓**, 다른 한쪽에는 **은행/토스 등 실제 결제 앱**을 띄워주세요.", inline=False)
        embed.add_field(name="② 정확한 금액 확인", value="주문 티켓에 표시된 최종 결제금액과 계좌를 다시 확인합니다.", inline=False)
        embed.add_field(name="③ 실제 이체", value="결제 앱에서 실제로 이체를 완료한 뒤 주문 티켓의 `💳 입금 확인 요청`을 눌러주세요.", inline=False)
        embed.add_field(name="④ 상품 지급", value="관리자가 **실제 입금 내역을 확인한 뒤** 상품 지급을 진행합니다.", inline=False)
        embed.add_field(name="🛡️ 주의", value="비밀번호·OTP·인증번호·카드 전체번호 같은 보안정보는 절대 공유하지 마세요.", inline=False)
        if DOUBLE_WINDOW_IMAGE.exists() and target_message is None:
            embed.set_image(url="attachment://double_window.png")
    elif kind in {"help", "partnership", "custom"}:
        support_type = {"help": "general", "partnership": "partnership", "custom": "custom"}[kind]
        info = SUPPORT_TYPES[support_type]
        embed = base_embed(f"╔══ {info['title']} • NEXIVO HUB ══╗", f"{info['subject']}\n\n버튼을 누르면 **본인과 스태프만 볼 수 있는 비공개 티켓**이 생성됩니다.")
        embed.add_field(name="🔒 비공개 티켓", value="문의마다 별도의 티켓 채널이 만들어지며 다른 회원에게 보이지 않습니다.", inline=False)
        embed.add_field(name="⚠️ 보안", value="비밀번호, OTP, 인증번호, 개인 계좌 비밀번호 등 민감정보는 입력하지 마세요.", inline=False)
        view = SupportTicketView(support_type)
        embed.set_footer(text=f"{BRAND} • {marker}")
        if target_message:
            await target_message.edit(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
        return
    else:
        return
    embed.set_footer(text=f"{BRAND} • {marker}")
    if target_message:
        await target_message.edit(embed=embed)
        if kind == "payment_help" and not target_message.attachments and DOUBLE_WINDOW_IMAGE.exists():
            await channel.send(file=discord.File(str(DOUBLE_WINDOW_IMAGE), filename="double_window.png"))
    else:
        if kind == "payment_help" and DOUBLE_WINDOW_IMAGE.exists():
            await channel.send(embed=embed, file=discord.File(str(DOUBLE_WINDOW_IMAGE), filename="double_window.png"))
        else:
            await channel.send(embed=embed)


async def get_or_create_role(guild: discord.Guild, name: str, **kwargs) -> discord.Role:
    existing = discord.utils.get(guild.roles, name=name)
    if existing:
        return existing
    return await guild.create_role(name=name, reason=f"{BRAND} server setup", **kwargs)


ROLE_DESIGN = {
    "customer": {"name": "🛒 NEXIVO 구매자", "colour": discord.Colour.from_rgb(96, 165, 250), "hoist": False, "mentionable": True},
    "verified": {"name": "✅ NEXIVO 인증완료", "colour": discord.Colour.from_rgb(45, 212, 191), "hoist": False, "mentionable": False},
    "staff": {"name": "🛡️ NEXIVO 스태프", "colour": discord.Colour.from_rgb(167, 139, 250), "hoist": True, "mentionable": True},
}


async def harden_nexivo_role(role: discord.Role) -> None:
    """Strip server-management permissions from NEXIVO-managed roles.

    Channel-specific overwrites below grant only the minimum access needed for
    tickets/community rooms, so the role itself never receives management powers.
    """
    safe = discord.Permissions.none()
    await role.edit(permissions=safe, reason=f"{BRAND} security: owner-only management")


async def update_existing_role(guild: discord.Guild, key: str, role_id: int | None) -> tuple[discord.Role | None, str]:
    role = guild.get_role(int(role_id)) if role_id else None
    if not role:
        return None, "missing"
    design = ROLE_DESIGN[key]
    await role.edit(
        name=design["name"],
        colour=design["colour"],
        hoist=design["hoist"],
        mentionable=design["mentionable"],
        permissions=discord.Permissions.none(),
        reason=f"{BRAND} role redesign + owner-only security",
    )
    return role, "updated"


async def setup_nexivo_server(guild: discord.Guild, update_only: bool = False) -> dict[str, Any]:
    cfg = config_for_guild(guild.id)

    # FAQ channel was intentionally removed from the NEXIVO layout. Clean up the
    # old bot-created channel when it exists so /설정업데이트 does not leave it behind.
    info_category_id = cfg.get("categories", {}).get("info", 0)
    info_category = guild.get_channel(int(info_category_id)) if info_category_id else None
    if isinstance(info_category, discord.CategoryChannel):
        old_faq = discord.utils.get(info_category.text_channels, name="「💡」자주묻는질문")
        if old_faq:
            try:
                await old_faq.delete(reason=f"{BRAND} FAQ channel removed from layout")
            except discord.HTTPException:
                pass

    created_categories = 0
    created_channels = 0
    updated_categories = 0
    updated_channels = 0
    missing = []

    if update_only:
        role_results = {}
        # Repair each managed role independently. A customer role can never be
        # selected as the verification role, even when the saved IDs were swapped.
        for key in ("customer", "verified", "staff"):
            role_id = int(cfg.get("roles", {}).get(key, 0) or 0)
            role = guild.get_role(role_id) if role_id else None

            if not _role_is_expected(role, key):
                role = next((r for r in guild.roles if r.name in ROLE_ALIASES[key]), None)

            if not role:
                design = ROLE_DESIGN[key]
                role = await get_or_create_role(
                    guild,
                    design["name"],
                    colour=design["colour"],
                    hoist=design["hoist"],
                    mentionable=design["mentionable"],
                    permissions=discord.Permissions.none(),
                )
                state = "created"
            else:
                state = "updated"

            cfg["roles"][key] = role.id
            await harden_nexivo_role(role)
            await update_existing_role(guild, key, role.id)
            role_results[key] = state
    else:
        customer_role = await get_or_create_role(guild, ROLE_DESIGN["customer"]["name"], colour=ROLE_DESIGN["customer"]["colour"], hoist=False, mentionable=True, permissions=discord.Permissions.none())
        verified_role = await get_or_create_role(guild, ROLE_DESIGN["verified"]["name"], colour=ROLE_DESIGN["verified"]["colour"], hoist=False, mentionable=False, permissions=discord.Permissions.none())
        staff_role = await get_or_create_role(guild, ROLE_DESIGN["staff"]["name"], colour=ROLE_DESIGN["staff"]["colour"], hoist=True, mentionable=True, permissions=discord.Permissions.none())
        await harden_nexivo_role(customer_role)
        await harden_nexivo_role(verified_role)
        await harden_nexivo_role(staff_role)
        cfg["roles"]["customer"] = customer_role.id
        cfg["roles"]["verified"] = verified_role.id
        cfg["roles"]["staff"] = staff_role.id

    cats: dict[str, discord.CategoryChannel] = {}
    if update_only:
        for key in SETUP_CATEGORY_NAMES:
            cat, state = await update_existing_category(guild, key)
            if cat:
                cats[key] = cat
                if state == "updated":
                    updated_categories += 1
            else:
                missing.append(f"카테고리:{key}")
    else:
        for key in SETUP_CATEGORY_NAMES:
            cats[key] = await ensure_category(guild, key)
            created_categories += 1

    channels: dict[str, discord.abc.GuildChannel] = {}
    for category_key, channel_defs in SETUP_CHANNELS.items():
        category = cats.get(category_key)
        if not category:
            continue
        for channel_key, (name, topic) in channel_defs.items():
            if update_only:
                if channel_key == "voice":
                    ch, state = await update_existing_voice_channel(guild, category, channel_key, name)
                else:
                    ch, state = await update_existing_text_channel(guild, category, channel_key, name, topic)
                    if not ch:
                        same = discord.utils.get(category.text_channels, name=name)
                        if same:
                            cfg["channels"][channel_key] = same.id; ch = same; state = "linked"
                        elif channel_key in SETUP_CHANNELS.get(category_key, {}):
                            ch = await guild.create_text_channel(name, category=category, topic=topic, reason=f"{BRAND} new feature channel")
                            cfg["channels"][channel_key] = ch.id; state = "created-new-feature"
                if ch:
                    channels[channel_key] = ch; updated_channels += 1; await update_channel_permissions(guild, channel_key, ch)
                else:
                    missing.append(f"채널:{channel_key}")
            else:
                if channel_key == "voice":
                    ch = await ensure_voice_channel(guild, category, channel_key, name)
                else:
                    ch = await ensure_text_channel(guild, category, channel_key, name, topic)
                channels[channel_key] = ch
                created_channels += 1
                await update_channel_permissions(guild, channel_key, ch)

    if "purchase_log" in channels:
        cfg["channels"]["purchase_log"] = channels["purchase_log"].id
    if "reviews" in channels:
        cfg["channels"]["review"] = channels["reviews"].id
    if "verification" in channels:
        cfg["channels"]["verification"] = channels["verification"].id
    if "order" in cats:
        cfg["categories"]["order_category"] = cats["order"].id
    await save_data()

    # Setup creates initial panels; update edits those bot-managed panels in place.
    for kind in ("welcome", "verification", "notice", "guide", "vending", "products", "popular", "reviews", "order_guide", "payment_help", "payment", "help", "partnership", "custom", "event"):
        channel_key = kind
        ch = channels.get(channel_key)
        if isinstance(ch, discord.TextChannel):
            await send_setup_panel(ch, kind, force=update_only)

    return {
        "categories": cats,
        "channels": channels,
        "roles": cfg["roles"],
        "role_results": role_results if update_only else {
            "customer": "created/ready",
            "verified": "created/ready",
            "staff": "created/ready",
        },
        "created_categories": created_categories,
        "created_channels": created_channels,
        "updated_categories": updated_categories,
        "updated_channels": updated_channels,
        "missing": missing,
        "update_only": update_only,
    }


# ----------------------------
# Bot
# ----------------------------

class NexivoHubBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.sync_task: asyncio.Task | None = None
        self.maintenance_task: asyncio.Task | None = None
        self._commands_synced = False

    async def setup_hook(self) -> None:
        # Do not block Discord startup while Render is waking from sleep.
        self.add_view(VerificationView())
        self.add_view(VendingLaunchView())
        self.add_view(ReviewDMView())
        # Restore specific review DM buttons so an old DM can open the correct order.
        for order_id, order in DATA.get("orders", {}).items():
            if order.get("status") == "완료" and order.get("review_dm_message_id"):
                try:
                    self.add_view(ReviewDMView(str(order_id)), message_id=int(order["review_dm_message_id"]))
                except (ValueError, TypeError):
                    pass
        self.add_view(SupportTicketView("general"))
        self.add_view(SupportTicketView("partnership"))
        self.add_view(SupportTicketView("custom"))
        # Restore persistent order controls for currently-open tickets.
        for order_id, order in DATA.get("orders", {}).items():
            if order.get("status") in {"완료", "취소"}:
                continue
            message_id = order.get("ticket_message_id")
            channel_id = order.get("channel_id")
            if message_id and channel_id:
                try:
                    self.add_view(TicketView(order_id), message_id=int(message_id))
                except (ValueError, TypeError):
                    pass
        for order_id, order in DATA.get("orders", {}).items():
            if order.get("status") == "완료" and order.get("review_message_id"):
                try:
                    self.add_view(ReviewTicketView(order_id), message_id=int(order["review_message_id"]))
                except (ValueError, TypeError):
                    pass
        for ticket_id, ticket in DATA.get("support_tickets", {}).items():
            if ticket.get("status") == "open" and ticket.get("message_id"):
                try:
                    self.add_view(SupportCloseView(ticket_id), message_id=int(ticket["message_id"]))
                except (ValueError, TypeError):
                    pass
        self.sync_task = asyncio.create_task(product_sync_loop())
        self.maintenance_task = asyncio.create_task(maintenance_loop())

    async def sync_commands(self) -> None:
        if self._commands_synced:
            return
        self._commands_synced = True
        try:
            if GUILD_ID:
                guild = self.get_guild(GUILD_ID)
                if guild is None:
                    print(f"[{BRAND}] WARNING: GUILD_ID={GUILD_ID} is not in the bot guild list. Skipping guild sync.")
                else:
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    print(f"[{BRAND}] slash commands synced to {guild.name} ({guild.id})")
            else:
                await self.tree.sync()
                print(f"[{BRAND}] global slash command sync completed")
        except discord.Forbidden as error:
            print(f"[{BRAND}] WARNING: guild command sync forbidden: {error}. Check bot membership and applications.commands scope.")
        except discord.HTTPException as error:
            print(f"[{BRAND}] WARNING: command sync failed: {error!r}")

    async def close(self) -> None:
        for task in (self.sync_task, self.maintenance_task):
            if task:
                task.cancel()
        await super().close()

bot = NexivoHubBot()


@bot.event
async def on_ready():
    global NEXIVO_TASKS_STARTED
    await bot.sync_commands()
    await refresh_tenants(force=True)
    print(f"[{BRAND}] logged in as {bot.user} | shared-tenants={len(TENANTS)}")
    if NEXIVO_WEB_SYNC_ENABLED and not NEXIVO_TASKS_STARTED:
        NEXIVO_TASKS_STARTED = True
        bot.loop.create_task(nexivo_hub_event_stream_loop())
        bot.loop.create_task(nexivo_hub_order_push_loop())
        bot.loop.create_task(shared_worker_heartbeat_loop())
        bot.loop.create_task(sync_all_stock())
        print(f"[{BRAND}] shared NEXIVO HUB worker sync started")


def _discord_date(dt: datetime) -> str:
    return dt.astimezone(KST).strftime("%Y년 %m월 %d일 %H:%M")


def _member_age(created_at: datetime) -> str:
    days = max(0, (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).days)
    return f"약 {days:,}일"


async def _resolve_member_event_channel(guild: discord.Guild, key: str) -> discord.TextChannel | None:
    """Resolve welcome/leave channels even when their saved IDs are stale/missing."""
    cfg = config_for_guild(guild.id)
    cid = cfg.get("channels", {}).get(key, 0)
    channel = guild.get_channel(int(cid)) if cid else None
    if isinstance(channel, discord.TextChannel):
        return channel

    definition = None
    for channel_defs in SETUP_CHANNELS.values():
        if key in channel_defs:
            definition = channel_defs[key]
            break
    if not definition:
        return None

    name, _ = definition
    channel = discord.utils.get(guild.text_channels, name=name)
    if not isinstance(channel, discord.TextChannel):
        return None

    cfg.setdefault("channels", {})[key] = channel.id
    try:
        await save_data()
    except Exception:
        pass
    return channel


async def _send_member_event(guild: discord.Guild, member: discord.Member, *, joined: bool) -> None:
    key = "welcome" if joined else "leave"
    channel = await _resolve_member_event_channel(guild, key)
    if not isinstance(channel, discord.TextChannel):
        print(f"[{BRAND}] {key} channel not found for guild={guild.id}. Run /기능업데이트.")
        return

    count = guild.member_count or len(guild.members)
    display_name = truncate(member.display_name, 80)
    if joined:
        embed = base_embed(
            "╭─── ✦ WELCOME TO NEXIVO HUB ✦ ───╮",
            f"**{member.mention}** 님이 NEXIVO HUB에 입장했습니다. 🎉\n\n"
            "새로운 하루의 시작을 환영합니다. 아래 안내부터 천천히 확인해주세요.",
            discord.Colour.from_rgb(45, 212, 191),
        )
        embed.set_author(name=f"{display_name} • WELCOME", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 MEMBER", value=f"**{display_name}**\n`{member}`", inline=True)
        embed.add_field(name="👥 SERVER", value=f"**{count:,}명**", inline=True)
        embed.add_field(name="🕐 JOINED", value=_discord_date(now()), inline=True)
        embed.add_field(
            name="🔐 START HERE",
            value="`「✅」서버인증`에서 **인증하기**를 눌러 인증 역할을 받아주세요.",
            inline=False,
        )
        embed.add_field(
            name="✨ NEXT",
            value="인증 후 자판기 · 문의 · 커뮤니티 기능을 편하게 이용할 수 있습니다.",
            inline=False,
        )
        embed.set_footer(text=f"{BRAND} • WELCOME • MEMBER #{count:,}")
        content = f"🎉 {member.mention} **님, NEXIVO HUB에 오신 것을 환영합니다!**"
        allowed = discord.AllowedMentions(users=True)
    else:
        embed = base_embed(
            "╭─── ✦ NEXIVO HUB • GOODBYE ✦ ───╮",
            f"**{display_name}** 님이 서버를 떠났습니다. 👋\n\n"
            "함께해주셔서 감사합니다. 언젠가 다시 만날 수 있기를 바랍니다.",
            discord.Colour.from_rgb(251, 146, 60),
        )
        embed.set_author(name=f"{display_name} • GOODBYE", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 MEMBER", value=f"**{display_name}**\n`{member}`", inline=True)
        embed.add_field(name="👥 SERVER", value=f"**{count:,}명**", inline=True)
        embed.add_field(name="🕐 LEFT", value=_discord_date(now()), inline=True)
        embed.add_field(name="💜 THANK YOU", value="NEXIVO HUB와 함께해주셔서 감사합니다.", inline=False)
        embed.set_footer(text=f"{BRAND} • GOODBYE • MEMBER #{count:,}")
        content = None
        allowed = discord.AllowedMentions.none()

    try:
        await channel.send(content=content, embed=embed, allowed_mentions=allowed)
    except discord.Forbidden as exc:
        print(f"[{BRAND}] {key} send forbidden in #{channel.name}: {exc!r}")
    except discord.HTTPException as exc:
        print(f"[{BRAND}] {key} send failed: {exc!r}")


@bot.event
async def on_member_join(member: discord.Member):
    await _send_member_event(member.guild, member, joined=True)


@bot.event
async def on_member_remove(member: discord.Member):
    await _send_member_event(member.guild, member, joined=False)


@bot.tree.command(name="설정", description="관리자용: NEXIVO HUB 전용 카테고리/채널/패널을 자동으로 구성합니다.")
async def setup_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if not require_tenant_feature(interaction, "settings"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        result = await setup_nexivo_server(interaction.guild)
        embed = base_embed("✅ NEXIVO HUB 서버 세팅 완료", "판매 서버에 필요한 기본 구조를 자동으로 구성했습니다.")
        embed.add_field(name="📂 카테고리", value=f"`{len(result['categories'])}`개", inline=True)
        embed.add_field(name="💬 채널", value=f"`{len(result['channels'])}`개", inline=True)
        embed.add_field(name="🎨 디자인", value="NEXIVO HUB 퍼플 테마 + 보안 권한 적용", inline=True)
        embed.add_field(name="🛒 자판기", value="상품 자판기 패널 자동 게시", inline=False)
        embed.add_field(name="🔐 보안", value="관리 기능은 오너 ID 단독 사용 · NEXIVO 역할의 서버 관리 권한 전부 제거", inline=False)
        embed.add_field(name="✅ 인증", value="버튼 인증 + NEXIVO VERIFIED 역할 자동 지급", inline=False)
        embed.add_field(name="⭐ 후기", value="후기 안내 패널 및 후기 채널 준비", inline=False)
        embed.add_field(name="🧾 로그", value="구매 로그 채널 자동 연결", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ 봇에게 **채널 관리 / 역할 관리** 권한이 부족합니다. 봇에게 필요한 권한을 추가해주세요.", ephemeral=True)
    except discord.HTTPException as exc:
        await interaction.followup.send(f"❌ 서버 세팅 중 Discord 오류가 발생했습니다: `{exc}`", ephemeral=True)
    except Exception as exc:
        print(f"[{BRAND}] setup error: {exc!r}")
        await interaction.followup.send(f"❌ 서버 세팅 중 오류가 발생했습니다: `{exc}`", ephemeral=True)


async def _run_feature_update(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if not require_tenant_feature(interaction, "settings"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        result = await setup_nexivo_server(interaction.guild, update_only=True)
        backup_ok = await create_data_backup("feature_update")
        role_results = result.get("role_results", {})
        verified_state = role_results.get("verified", "ready")
        customer_state = role_results.get("customer", "ready")
        staff_state = role_results.get("staff", "ready")

        embed = base_embed(
            "╭─── ✦ NEXIVO HUB • FEATURE UPDATE ✦ ───╮",
            "기존 NEXIVO 서버 구조를 최대한 유지하면서 **인증 · 입퇴장 · 패널 · 채널 연결 · 역할 매핑**을 한 번에 점검하고 갱신했습니다.",
        )
        embed.add_field(name="🔐 인증 역할", value=f"`NEXIVO 인증완료` · **{verified_state}**", inline=True)
        embed.add_field(name="🛒 구매자 역할", value=f"`NEXIVO 구매자` · **{customer_state}**", inline=True)
        embed.add_field(name="🛡️ 스태프 역할", value=f"`NEXIVO 스태프` · **{staff_state}**", inline=True)
        embed.add_field(name="👋 입장/퇴장", value="환영·퇴장 채널 자동 연결 + 프로필/인원/시간이 포함된 예쁜 멤버 이벤트 임베드", inline=False)
        embed.add_field(name="✅ 인증", value="인증 버튼은 **NEXIVO 인증완료 역할만** 지급하도록 안전장치를 적용했습니다. 구매자 역할은 구매 완료에서만 지급됩니다.", inline=False)
        embed.add_field(name="⏰ 주문 보호", value=f"입금확인 {PAYMENT_REMINDER_1_MINUTES}/{PAYMENT_REMINDER_2_MINUTES}분 재알림 + 미입금 {UNPAID_ORDER_TIMEOUT_MINUTES}분 / 입금확인 대기 {PAYMENT_PENDING_TIMEOUT_MINUTES}분 자동 만료", inline=False)
        embed.add_field(name="📊 운영", value="`/주문대시보드` 상태별 실시간 주문 현황 + `「🤖」봇로그` 내부 작업 감사 로그", inline=False)
        embed.add_field(name="💾 백업", value=f"자동 데이터 백업 활성화 · 최근 **{BACKUP_KEEP_COUNT}개** 보관 · 즉시 백업 {'성공' if backup_ok else '실패'}", inline=False)
        embed.add_field(name="🎨 UI", value="입금 알림·처리 시작·지급 완료·자동 만료·취소 메시지를 NEXIVO HUB 스타일로 통일", inline=False)
        if result["missing"]:
            embed.add_field(name="⚠️ 확인이 필요한 항목", value="\n".join(f"• {x}" for x in result["missing"][:20]), inline=False)
        else:
            embed.add_field(name="✨ 상태", value="모든 기능 연결이 정상적으로 점검되었습니다.", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ 봇에게 채널 관리/역할 관리 권한이 부족합니다. 봇 역할이 필요한 역할보다 위에 있는지도 확인해주세요.", ephemeral=True)
    except discord.HTTPException as exc:
        await interaction.followup.send(f"❌ Discord 오류로 업데이트하지 못했습니다: `{exc}`", ephemeral=True)
    except Exception as exc:
        print(f"[{BRAND}] feature update error: {exc!r}")
        await interaction.followup.send(f"❌ 서버 업데이트 중 오류가 발생했습니다: `{exc}`", ephemeral=True)


@bot.tree.command(name="설정업데이트", description="관리자용: NEXIVO HUB 기존 서버의 기능/디자인을 안전하게 갱신합니다.")
async def setup_update_command(interaction: discord.Interaction):
    await _run_feature_update(interaction)


@bot.tree.command(name="기능업데이트", description="관리자용: 인증·입퇴장·역할·패널 기능을 한 번에 업데이트합니다.")
async def feature_update_command(interaction: discord.Interaction):
    await _run_feature_update(interaction)


@bot.tree.command(name="인증패널", description="관리자용: NEXIVO HUB 서버 인증 패널을 게시합니다.")
async def verification_panel_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if not require_tenant_feature(interaction, "settings"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    target = interaction.guild.get_channel(VERIFICATION_CHANNEL_ID) if VERIFICATION_CHANNEL_ID else None
    if not isinstance(target, discord.TextChannel):
        cid = config_for_guild(interaction.guild.id).get("channels", {}).get("verification", 0)
        target = interaction.guild.get_channel(int(cid)) if cid else None
    if not isinstance(target, discord.TextChannel):
        await interaction.response.send_message("❌ 인증 채널을 찾을 수 없습니다. `/설정`을 먼저 실행해주세요.", ephemeral=True)
        return
    await send_verification_panel(target)
    await interaction.response.send_message(f"✅ 인증 패널을 {target.mention}에 게시했습니다.", ephemeral=True)


@bot.tree.command(name="자판기", description="상품을 본인에게만 보이는 선택창에서 고르고 주문합니다.")
async def vending_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await refresh_tenants(force=True)
    await interaction.followup.send(embed=main_panel_embed(ephemeral=True, guild_id=interaction.guild.id if interaction.guild else None), view=ProductCategoryView(interaction.guild.id if interaction.guild else None), ephemeral=True)


async def _install_vending_panel(interaction: discord.Interaction) -> tuple[bool, str]:
    if not interaction.guild:
        return False, "❌ 서버에서만 사용할 수 있습니다."
    if not require_tenant_feature(interaction, "products"):
        return False, "🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다."
    if not tenant_is_admin(interaction):
        return False, "❌ 관리자만 사용할 수 있습니다."
    if not isinstance(interaction.channel, discord.TextChannel):
        return False, "❌ 텍스트 채널에서 실행해주세요."
    await refresh_tenants(force=True)
    embed = main_panel_embed(guild_id=interaction.guild.id)
    embed.set_footer(text=f"{BRAND} • 공개 자판기 • 상품 선택창은 개인 표시")
    message = await interaction.channel.send(embed=embed, view=VendingLaunchView(interaction.guild.id))
    cfg = config_for_guild(interaction.guild.id)
    cfg.setdefault("panels", {})["vending_message_id"] = message.id
    cfg.setdefault("panels", {})["vending_channel_id"] = interaction.channel.id
    await save_data()
    return True, "✅ 예쁜 공개 자판기를 설치했습니다. 이후 상품 선택은 구매자 본인에게만 표시됩니다."


@bot.tree.command(name="자판기설치", description="관리자용: 현재 채널에 공개 자판기를 설치합니다. 상품 선택은 개인창으로 진행됩니다.")
async def vending_install_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ok, message = await _install_vending_panel(interaction)
    await interaction.followup.send(message, ephemeral=True)


@bot.tree.command(name="패널", description="관리자용: 현재 채널에 자판기 패널을 게시합니다. /자판기설치와 동일한 방식입니다.")
async def panel_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ok, message = await _install_vending_panel(interaction)
    await interaction.followup.send(message, ephemeral=True)


@bot.tree.command(name="상품목록", description="NEXIVO HUB 전체 상품을 확인합니다.")
async def products_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await refresh_tenants(force=True)
    embed = base_embed("🛍️ NEXIVO HUB • 전체 상품")
    categories: dict[str, list[dict[str, Any]]] = {}
    for p in tenant_products(interaction.guild.id if interaction.guild else None):
        categories.setdefault(str(p.get("category", "기타")), []).append(p)
    for category, items in categories.items():
        value = "\n".join(f"• **{p['name']}** · `{money(int(p.get('price', 0)))}`" for p in items[:12])
        embed.add_field(name=f"〔 {category} 〕", value=value or "-", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="후기작성", description="완료된 주문에 대한 구매후기를 작성합니다.")
async def review_command(interaction: discord.Interaction):
    embed = base_embed(
        "⭐ NEXIVO HUB • 후기작성",
        "완료된 주문의 주문번호를 입력하고 별점과 후기를 남겨주세요.\n동일 주문은 한 번만 작성할 수 있습니다.",
        discord.Colour.gold(),
    )
    await interaction.response.send_message(embed=embed, view=ReviewStartView(), ephemeral=True)


@bot.tree.command(name="내구매", description="내 구매내역을 확인합니다.")
async def my_orders_command(interaction: discord.Interaction):
    mine = [o for o in DATA["orders"].values() if int(o.get("user_id", 0)) == interaction.user.id and (not interaction.guild or str(o.get("guild_id", "")) == str(interaction.guild.id))]
    mine = sorted(mine, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
    embed = base_embed("📋 NEXIVO HUB • 내 구매내역")
    if not mine:
        embed.description = "아직 구매내역이 없습니다. `/자판기`에서 상품을 선택해보세요."
    else:
        for o in mine:
            embed.add_field(
                name=f"{o['id']} · {truncate(o['product_name'], 70)}",
                value=f"{money(o['total'])} · **{o['status']}**",
                inline=False,
            )
    await interaction.response.send_message(embed=embed, ephemeral=True)




@bot.tree.command(name="내후기", description="내가 작성한 후기 목록을 확인합니다.")
async def my_reviews_command(interaction: discord.Interaction):
    mine = [r for r in DATA["reviews"] if int(r.get("user_id", 0)) == interaction.user.id and (not interaction.guild or str(DATA["orders"].get(r.get("order_id"), {}).get("guild_id", "")) == str(interaction.guild.id))]
    embed = base_embed("⭐ NEXIVO HUB • 내 후기", color=discord.Colour.gold())
    if not mine:
        embed.description = "아직 작성한 후기가 없습니다."
    else:
        for r in mine[-10:]:
            embed.add_field(name=f"{r['id']} · 주문 {r['order_id']}", value=f"{'⭐'*r['rating']}\n{truncate(r['content'], 250)}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="상품동기화", description="관리자용: 웹사이트 상품을 다시 불러옵니다.")
async def sync_command(interaction: discord.Interaction):
    if not require_tenant_feature(interaction, "products"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    products = await sync_products(guild_id=interaction.guild.id if interaction.guild else None, force=True)
    await interaction.followup.send(f"✅ 웹사이트에서 상품 **{len(products)}개**를 불러왔습니다.", ephemeral=True)


@bot.tree.command(name="주문대시보드", description="관리자용: 주문 상태를 한눈에 확인하는 운영 대시보드를 표시합니다.")
async def order_dashboard_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if not require_tenant_feature(interaction, "orders"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    await interaction.response.send_message(
        embed=build_order_dashboard_embed(interaction.guild, "전체"),
        view=OrderDashboardView(_dashboard_visible_orders("전체", interaction.guild.id)),
        ephemeral=True,
    )


@bot.tree.command(name="주문조회", description="관리자용: 주문번호로 주문을 조회합니다.")
@app_commands.describe(order_id="예: VX-0001")
async def order_lookup_command(interaction: discord.Interaction, order_id: str):
    if not require_tenant_feature(interaction, "orders"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    oid = order_id.strip().upper()
    order = DATA["orders"].get(oid)
    if order and interaction.guild and str(order.get("guild_id", "")) != str(interaction.guild.id): order = None
    if not order:
        await interaction.response.send_message("❌ 해당 주문을 찾을 수 없습니다.", ephemeral=True)
        return
    embed = base_embed("🔎 주문 조회")
    embed.add_field(name="주문번호", value=f"`{oid}`", inline=True)
    embed.add_field(name="구매자", value=f"<@{order['user_id']}>", inline=True)
    embed.add_field(name="상품", value=truncate(order['product_name'], 80), inline=False)
    embed.add_field(name="금액", value=money(order['total']), inline=True)
    embed.add_field(name="상태", value=order['status'], inline=True)
    ch = interaction.guild.get_channel(int(order.get("channel_id", 0))) if interaction.guild else None
    embed.add_field(name="티켓", value=ch.mention if isinstance(ch, discord.TextChannel) else "없음", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="주문취소", description="관리자용: 주문을 취소하고 해당 주문 티켓을 닫습니다.")
@app_commands.describe(order_id="예: VX-0001")
async def cancel_order_command(interaction: discord.Interaction, order_id: str):
    if not require_tenant_feature(interaction, "orders"):
        await interaction.response.send_message("🔒 현재 라이선스 플랜에서는 이 기능을 사용할 수 없습니다.", ephemeral=True)
        return
    if not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    oid = order_id.strip().upper()
    order = DATA["orders"].get(oid)
    if order and interaction.guild and str(order.get("guild_id", "")) != str(interaction.guild.id): order = None
    if not order:
        await interaction.response.send_message("❌ 해당 주문을 찾을 수 없습니다.", ephemeral=True)
        return
    if order.get("status") == "완료":
        await interaction.response.send_message("❌ 이미 완료된 주문은 취소할 수 없습니다.", ephemeral=True)
        return
    order["status"] = "취소"
    order["cancelled_at"] = now().isoformat()
    order["cancelled_by"] = str(interaction.user)
    await save_data()
    if interaction.guild:
        await send_audit_log(interaction.guild, action="주문 취소", detail="관리자가 주문을 취소했습니다.", order=order, actor=interaction.user, level="danger")
        await send_staff_alert(interaction.guild, title="⛔ 주문 취소", description=f"관리자가 `{oid}` 주문을 취소했습니다.", order=order, actor=interaction.user, level="danger")
    channel = interaction.guild.get_channel(int(order.get("channel_id", 0))) if interaction.guild else None
    await interaction.response.send_message(f"✅ `{oid}` 주문을 취소 처리했습니다.", ephemeral=True)
    if isinstance(channel, discord.TextChannel):
        try:
            embed = base_embed(
                "╭─── ✦ NEXIVO HUB • ORDER CANCELLED ✦ ───╮",
                f"주문번호 `{oid}`이(가) 관리자에 의해 취소되었습니다.\n잠시 후 티켓이 닫힙니다.",
                discord.Colour.red(),
            )
            embed.add_field(name="🛠️ 처리 관리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="📌 상태", value="`취소`", inline=True)
            await channel.send(embed=embed)
            await asyncio.sleep(3)
            await backup_ticket_transcript(channel, metadata=order, reason="admin_order_cancel")
            await channel.delete(reason=f"{BRAND} order cancelled {oid}")
        except discord.HTTPException:
            pass


@bot.tree.command(name="통계", description="관리자용: NEXIVO HUB 운영 통계를 확인합니다.")
async def stats_command(interaction: discord.Interaction):
    if not interaction.guild or not tenant_is_admin(interaction):
        await interaction.response.send_message("❌ 해당 Discord 서버의 관리자만 사용할 수 있습니다.", ephemeral=True)
        return
    if not tenant_has_feature(interaction.guild.id, "reports"):
        await interaction.response.send_message("🔒 `/통계`는 Pro 이상 플랜에서 사용할 수 있습니다.", ephemeral=True)
        return
    orders = tenant_orders(interaction.guild.id if interaction.guild else None)
    completed = [o for o in orders if o.get("status") == "완료"]
    revenue = sum(int(o.get("total", 0)) for o in completed)
    avg = round(revenue / len(completed)) if completed else 0
    embed = base_embed("📊 NEXIVO HUB • 운영 통계")
    embed.add_field(name="🛒 주문", value=f"`{len(orders):,}`건", inline=True)
    embed.add_field(name="✅ 완료", value=f"`{len(completed):,}`건", inline=True)
    scoped_review_ids = {str(r.get("id")) for r in DATA.get("reviews", []) if str(DATA.get("orders", {}).get(r.get("order_id"), {}).get("guild_id", "")) == str(interaction.guild.id)}
    embed.add_field(name="⭐ 후기", value=f"`{len(scoped_review_ids):,}`개", inline=True)
    embed.add_field(name="💰 완료 매출", value=money(revenue), inline=True)
    embed.add_field(name="📈 평균 주문액", value=money(avg), inline=True)
    embed.add_field(name="🛍️ 상품", value=f"`{len(tenant_products(interaction.guild.id if interaction.guild else None)):,}`개", inline=True)
    pending = sum(1 for o in orders if o.get("status") in {"주문접수", "입금확인요청", "처리중"})
    embed.add_field(name="⏳ 진행중", value=f"`{pending:,}`건", inline=True)
    embed.set_footer(text=f"{BRAND} • 운영 통계 • {_discord_date(now())}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="도움말", description="NEXIVO HUB 봇 사용법을 안내합니다.")
async def help_command(interaction: discord.Interaction):
    embed = base_embed(
        "❔ NEXIVO HUB • 도움말",
        "디지털 상품을 판매하는 자판기형 Discord 봇입니다.",
    )
    embed.add_field(name="🛒 구매", value="공개 자판기 `🛒 상품 선택하기` → 개인 선택창 → 상품 → `🎫 티켓 열기`", inline=False)
    embed.add_field(name="✅ 인증", value="`✅ 인증하기` 버튼 → NEXIVO VERIFIED 역할 자동 지급", inline=False)
    embed.add_field(name="⭐ 후기", value="주문 완료 후 `/후기작성`", inline=False)
    embed.add_field(name="📋 내역", value="`/내구매` · `/내후기`", inline=False)
    embed.add_field(name="🏦 계좌", value="구매 티켓에서 계좌 확인 → 입금 후 입금확인 요청", inline=False)
    embed.add_field(name="⏰ 운영 자동화", value=f"입금 확인 {PAYMENT_REMINDER_1_MINUTES}/{PAYMENT_REMINDER_2_MINUTES}분 알림 · 주문 자동 만료 · 주기적 데이터 백업", inline=False)
    plan = tenant_for_guild(interaction.guild.id).get("planLabel", "연결 안됨") if interaction.guild else "연결 안됨"
    feature_names = {"products":"상품/자판기", "orders":"주문 관리", "settings":"서버 설정", "notice":"공지", "grades":"등급", "reports":"매출 통계", "customers":"고객 관리", "audit":"감사 로그"}
    available = [feature_names[k] for k in feature_names if tenant_has_feature(interaction.guild.id if interaction.guild else None, k)]
    embed.add_field(name="🔐 현재 플랜", value=f"`{plan}` · 사용 가능: **{', '.join(available) if available else '기본 구매 기능'}**", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def fetch_shared_discord_token() -> str:
    """Use env token when provided; otherwise wait for the owner-saved token from NEXIVO HUB."""
    if DISCORD_TOKEN:
        print(f"[{BRAND}] using Discord token from Worker environment")
        return DISCORD_TOKEN
    if not WEBSITE_URL or not NEXIVO_BOT_WORKER_SECRET:
        raise RuntimeError("DISCORD_TOKEN 또는 WEBSITE_URL + NEXIVO_BOT_WORKER_SECRET가 필요합니다.")
    timeout = aiohttp.ClientTimeout(total=20, connect=8, sock_connect=8, sock_read=15)
    attempt = 0
    while True:
        attempt += 1
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{WEBSITE_URL}/api/bot/secret-token",
                    headers={"X-NEXIVO-WORKER-SECRET": NEXIVO_BOT_WORKER_SECRET, "Accept": "application/json"},
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status == 404:
                        print(f"[{BRAND}] 저장된 Bot Token이 없습니다. 웹 설정에서 Token을 저장하면 자동으로 시작합니다. ({attempt}회)")
                    elif response.status >= 400:
                        print(f"[{BRAND}] Bot Token 조회 실패: HTTP {response.status} {payload}")
                    else:
                        token = str(payload.get("token") or "").strip() if isinstance(payload, dict) else ""
                        if token:
                            print(f"[{BRAND}] owner-saved Discord token loaded securely from NEXIVO HUB")
                            return token
                        print(f"[{BRAND}] 저장된 Bot Token이 비어 있습니다. ({attempt}회)")
        except Exception as exc:
            print(f"[{BRAND}] Bot Token 조회 중 오류: {exc!r}")
        await asyncio.sleep(15)


if __name__ == "__main__":
    try:
        runtime_token = asyncio.run(fetch_shared_discord_token())
    except Exception as exc:
        raise SystemExit(str(exc))
    bot.run(runtime_token)
