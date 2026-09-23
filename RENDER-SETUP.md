# NEXIVO HUB Render 배포 가이드

## 1. GitHub
`NEXIVO HUB-CONTROL-CENTER-shared-bot-production.zip`을 풀어 새 GitHub 저장소에 올립니다. `.env`와 실제 Discord 토큰은 올리지 않습니다.

## 2. Render
Blueprint로 `render.yaml`을 사용하거나 Web Service + Background Worker를 각각 생성합니다.

### Web Service 환경변수
- `NEXIVO_OPERATOR_USER` = `0nTop`
- `NEXIVO_OPERATOR_PASSWORD` = 원하는 오너 비밀번호를 Secret으로 입력
- `NEXIVO_BOT_WORKER_SECRET` = 긴 랜덤 문자열
- `NEXIVO_LICENSE_ISSUE_SECRET` = 긴 랜덤 문자열
- `NEXIVO_DB_FILE` = `/var/data/db.json`
- `COOKIE_SECURE` = `true`

### Discord Bot Worker 환경변수
- `DISCORD_TOKEN` = 선택 사항. 웹 설정에 Token을 저장해 사용할 경우 비워둬도 됩니다.
- `WEBSITE_URL` = 실제 NEXIVO HUB Web Service URL
- `NEXIVO_BOT_WORKER_SECRET` = Web Service와 **완전히 같은 값**

## 3. 동작 구조
한 개의 Discord 봇이 여러 고객 서버에 들어갈 수 있습니다. 웹에서 고객 라이선스와 Guild ID가 연결되면 worker가 해당 서버를 tenant로 인식하고, 그 서버에 해당하는 상품/재고/주문만 동기화합니다.

웹 상품/재고 변경 → SSE 이벤트 → shared bot worker → 해당 Guild 재고 메시지 갱신

Discord 주문/상태 변경 → worker-state API → 웹 대시보드/매출 리포트 갱신

## 4. 공용 Bot Token 설정 및 보안
오너 로그인 → `설정` → `공용 Discord 봇 설정`에서 Bot Token을 입력하고 저장할 수 있습니다. 입력창은 password 타입이며 눈 아이콘으로 입력 중 표시/숨김이 가능합니다. 저장된 원문 Token은 브라우저로 다시 보내지 않으며 서버에서 AES-256-GCM으로 암호화합니다. 봇 Worker는 `NEXIVO_BOT_WORKER_SECRET`로 인증한 뒤 서버에서 Token을 받아 시작합니다. Token 자체는 구매자에게 노출하지 않습니다.

## 5. 데이터 영속성
`render.yaml`은 Web Service에 Persistent Disk(`/var/data`)를 연결합니다. 더 큰 규모에서는 Postgres로 옮기는 것을 권장합니다.
