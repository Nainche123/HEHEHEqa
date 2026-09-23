NEXIVO HUB • Shared Discord Bot Worker
===================================

구조
----
- Discord 봇은 딱 1개만 실행합니다.
- 실제 DISCORD_TOKEN은 이 봇 워커의 환경변수에만 존재합니다.
- 구매자/고객은 봇 토큰을 입력하거나 볼 수 없습니다.
- 고객별로 NEXIVO HUB 라이선스 + Discord Guild ID를 연결하면 같은 봇이 해당 서버의 상품/재고/주문을 분리해서 처리합니다.

실시간 흐름
------------
웹 상품/재고 변경
  → NEXIVO HUB 이벤트 스트림
  → 공용 Discord 봇 워커
  → 해당 Guild의 재고 메시지 갱신

Discord 주문 상태 변경
  → 공용 Discord 봇 워커
  → NEXIVO HUB worker-state API
  → 웹 대시보드 / 매출 데이터 갱신

플랜 권한
---------
웹 패널은 라이선스 플랜을 기준으로 메뉴/API를 서버 측에서도 제한합니다.
현재 4개 플랜은 다음과 같이 유지됩니다.
- BASIC
- BASIC PREMIUM
- PRO
- PRO PREMIUM

Discord 봇에서도 동일한 테넌트의 plan/features를 가져와 서버 측에서 명령 실행을 제한합니다.
예: /통계는 reports 권한이 필요하므로 PRO 이상에서만 실행됩니다.

설치 (로컬)
-----------
1. Python 3.11+ 권장
2. pip install -r requirements.txt
3. NEXIVO_HUB_bot.env.example을 기준으로 환경변수를 설정
4. python NEXIVO HUB_bot_integrated.py

배포 (Render)
-------------
- NEXIVO HUB 웹: Web Service
- NEXIVO HUB Discord 봇: Background Worker
- 웹은 Render Persistent Disk 또는 외부 DB가 필요합니다.
- 봇 워커의 DISCORD_TOKEN과 NEXIVO_BOT_WORKER_SECRET은 Render Secret Environment Variables로 설정합니다.
- 봇 토큰을 웹 프론트엔드나 GitHub 저장소에 넣지 마세요.

고객 연결 흐름
--------------
1. 오너가 공용 봇 초대 링크를 제공합니다.
2. 구매자가 자신의 Discord 서버에 공용 봇을 초대합니다.
3. 오너가 구매자의 Discord User ID를 넣어 BASIC / BASIC PREMIUM / PRO / PRO PREMIUM 라이선스를 발급합니다.
4. 구매자가 라이선스를 활성화합니다.
5. 구매자는 설정에서 자신의 Discord Guild ID와 필요한 채널 ID만 입력합니다. Bot Token은 입력하지 않습니다.
6. Worker가 실제로 해당 Guild에 봇이 들어와 있는지 확인한 뒤 연결 상태를 CONNECTED로 바꿉니다.
7. 상품/재고 변경은 해당 Guild의 테넌트 데이터에만 반영됩니다.
8. 관리자 명령은 라이선스에 등록된 Discord User ID와 플랜 권한을 모두 통과해야 합니다. 서버 소유자라는 이유만으로 고객 라이선스를 우회할 수 없습니다.

계정/데이터 유지
----------------
- 계정, 라이선스, 상품, 주문, 설정은 웹 서비스 DB에 계속 저장됩니다.
- 페이지 새로고침은 서버 세션 쿠키가 살아 있으면 로그인 상태를 복구합니다.
- 명시적으로 로그아웃하면 세션만 폐기되고 계정/상품/주문 데이터는 삭제되지 않습니다.
- 로그인 화면에는 마지막 사용 아이디만 기억시키며 비밀번호는 브라우저에 저장하지 않습니다.

토큰 보안
----------
- 공용 Discord Bot Token은 Worker의 DISCORD_TOKEN Secret Environment Variable에만 넣습니다.
- 웹 설정에는 토큰 자체를 저장하거나 반환하지 않습니다.
- 고객에게 보이는 화면에는 Token 값이 전달되지 않습니다.
