# 시장 변동성 모니터 — 자동 업데이트 대시보드

나스닥 · S&P 500 · 다우존스 급락 선행지표를 매일 자동으로 수집해 GitHub Pages에 게시합니다.

## 구성

```
.
├── index.html                        # 대시보드 (정적 HTML)
├── data/
│   └── indicators.json               # 매일 자동 업데이트되는 데이터
├── fetch_data.py                     # 데이터 수집 스크립트
├── requirements.txt
└── .github/workflows/update.yml     # GitHub Actions 스케줄러
```

## 데이터 소스

| 지표 | 소스 | 비용 |
|------|------|------|
| NASDAQ, S&P 500, DJIA, VIX | Yahoo Finance (yfinance) | 무료 |
| 10년물 국채, 2년물, 기준금리, HY스프레드 | FRED API | 무료 |
| Fear & Greed Index | Alternative.me API | 무료 |
| Put/Call Ratio | CBOE 공개 CSV | 무료 |

업데이트 주기: **매일 09:00 KST** (GitHub Actions cron `0 0 * * *`)

---

## 배포 방법 (5단계)

### 1. 레포 생성 및 파일 업로드

GitHub에서 새 레포 생성 후 이 폴더 전체를 push합니다.

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<YOUR_ID>/<REPO_NAME>.git
git push -u origin main
```

### 2. FRED API 키 발급 (무료, 5분)

1. https://fred.stlouisfed.org/docs/api/api_key.html 접속
2. 회원가입 → "Request API Key" 클릭
3. 발급된 키 복사

### 3. GitHub Secrets 등록

레포 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|------|-------|
| `FRED_API_KEY` | 위에서 발급한 키 |

### 4. GitHub Pages 활성화

레포 → **Settings** → **Pages**

- Source: **Deploy from a branch**
- Branch: `main` / `/ (root)`
- Save

약 1~2분 후 `https://<YOUR_ID>.github.io/<REPO_NAME>/` 로 접속 가능.

### 5. 첫 번째 수동 실행

Actions → **Daily Market Data Update** → **Run workflow**

정상 실행되면 `data/indicators.json`이 실제 데이터로 업데이트됩니다.

---

## 수동 실행

GitHub Actions 탭 → **Daily Market Data Update** → **Run workflow**

또는 로컬에서:

```bash
pip install -r requirements.txt
export FRED_API_KEY="your_key_here"
python fetch_data.py
```

## 업데이트 시간 변경

`.github/workflows/update.yml`의 cron 값 수정:

```yaml
- cron: "0 0 * * *"   # 09:00 KST
- cron: "0 1 * * *"   # 10:00 KST
- cron: "30 22 * * *" # 07:30 KST
```

## 주의사항

- Fear & Greed는 **암호화폐** 기반 Alternative.me 지수입니다. 주식 시장과 방향성은 유사하나 완전히 동일하지 않습니다.
- FRED 데이터는 1~2 영업일 지연이 있을 수 있습니다.
- Put/Call 비율은 CBOE CSV 구조 변경 시 fetch 실패할 수 있습니다. 실패 시 `null`로 저장됩니다.
- 이 대시보드는 정보 제공 목적이며 투자 조언이 아닙니다.
