# NEXIVO HUB Control Center

NEXIVO HUB is a license-gated store/control panel for Discord vending bots.

## Architecture

- **Web Service (Node.js):** dashboard, products, stock, orders, reports, licensing.
- **Shared Discord Bot Worker (Python):** one Discord bot token for all customer servers.
- **Per-tenant isolation:** each active license is bound to a customer and Discord Guild ID. The shared bot receives only that tenant's products/orders/settings when operating inside the guild.
- **Plan gating:** BASIC / BASIC PREMIUM / PRO / PRO PREMIUM are enforced server-side. The browser cannot unlock a feature by changing its UI.
- **Realtime:** web changes emit events over SSE; the shared worker consumes them and updates the matching Discord server. Worker order/state updates flow back to the web service.

## Security

The Discord bot token is **worker-only**. It is never accepted by the customer browser, never returned by the web API, and must be stored as a Render Secret Environment Variable (or a local `.env` for development).

Do not commit a real `.env` or a real Discord token to GitHub.

## Local

1. Copy `.env.example` to `.env` and set the owner password + shared secrets.
2. `npm install` (the web app has no external runtime dependency, but this keeps the workflow consistent).
3. `npm start`.
4. Configure the bot worker from `BOT-INTEGRATION/NEXIVO_HUB_bot.env.example`.

## Render

Use `render.yaml` to create one Web Service and one Background Worker. The web service uses a Persistent Disk at `/var/data` so the JSON database survives normal restarts/redeploys. For larger production traffic, move to a managed database such as Postgres.


고객별 공용 봇 연결
--------------------
오너가 고객의 Discord User ID를 포함한 라이선스를 발급하고, 고객은 공용 봇을 자신의 서버에 초대한 뒤 Guild ID를 패널에 등록합니다. 하나의 Discord 봇 토큰으로 여러 서버를 운영하지만, 웹/봇 데이터는 라이선스와 Guild ID 기준으로 분리됩니다.

Bot Token은 설정 화면에 입력하지 않습니다. 실제 토큰은 Discord Worker의 DISCORD_TOKEN Secret Environment Variable 하나만 사용합니다. 오너 설정에서는 Client ID, 초대 링크, 봇 이름만 관리할 수 있습니다.

플랜별 권한
------------
BASIC / BASIC PREMIUM / PRO / PRO PREMIUM은 같은 봇을 사용하되, 각 라이선스의 features를 서버에서 확인하여 관리 기능 실행을 제한합니다. 현재 `tenant_is_admin()`은 고객 라이선스의 Discord User ID를 우선하며, 서버 소유권만으로 우회할 수 없습니다.


## 공용 Discord Bot Token 저장
오너는 설정 화면에서 Bot Token을 입력하고 저장할 수 있습니다. 입력란은 password 타입이며 눈 아이콘으로 입력 중 표시/숨김이 가능합니다. 저장 후 원문 토큰은 API/브라우저에 다시 반환하지 않고 서버에서 AES-256-GCM으로 암호화합니다. Worker는 `NEXIVO_BOT_WORKER_SECRET`로 인증한 뒤 `/api/bot/secret-token`에서 토큰을 받아 시작할 수 있습니다. 웹 서비스의 DB 저장 경로가 영속 저장소에 있어야 재시작 이후에도 유지됩니다.
