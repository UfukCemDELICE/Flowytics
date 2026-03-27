# Flowytics — MVP Sprint Planı

**Başlangıç:** 9 Mart 2026  
**Bitiş hedefi:** 3 Mayıs 2026 (8 hafta)  
**Çalışma modeli:** Solo founder + Claude Code (Opus 4.6 mimar) + Antigravity (Gemini implementasyon)  
**Genel prensip:** Lean Startup — en küçük değer üreten şeyi ship et, gerçek kullanıcılarla validate et.

---

## Genel Done Tanımı

Her hafta sonunda çalışan bir şey olmalı. "Çalışan" = test edilmiş, hatasız, demo gösterilebilir.

---

## Hafta 1 — Temel Altyapı & QBO Bağlantısı

**Tarih:** 9–15 Mart 2026  
**Done tanımı:** QBO sandbox'tan finansal veri çekilebiliyor ve veritabanına kaydediliyor.

### Tamamlanan Tasklar ✅
- [x] Proje scaffolding: FastAPI backend + Next.js frontend (monorepo)
- [x] SQLModel modelleri (7 tablo, 11/11 test passing)
- [x] Supabase projesi oluşturuldu (`flowytics-mvp`)
- [x] Supabase tabloları oluşturuldu (7 tablo + RLS + indexes)
- [x] DATABASE_URL .env'e eklendi
- [x] Health endpoint: GET /api/v1/health → {"status": "ok"}
- [x] GitHub Actions CI/CD (ci.yml + deploy.yml)
- [x] Frontend UI %90 tamamlandı (Stitch + Antigravity)
- [x] Proje dokümantasyonu sıfırdan yazıldı (8 md dosyası)
- [x] Intuit Developer sandbox oluşturuldu

### Kalan Tasklar
- [x] QBO sandbox env vars (.env'e QB_CLIENT_ID, QB_CLIENT_SECRET, QB_REDIRECT_URI ekle)
- [x] Config.py'ye QB_* env vars ekle
- [x] Clerk auth middleware (user_id + org_id extraction, 401 on invalid)
- [x] QBO OAuth flow (auth URL generation + callback + token save encrypted)
- [x] QBO data pull functions (P&L, Balance Sheet, Cash Flow → raw dict)
- [x] Sync service (QBO → financial_snapshots tablosuna JSONB olarak kaydet)
- [x] Manual sync endpoint (POST /api/v1/quickbooks/sync)
- [x] Router registration (main.py'de tüm route'ları include et)
- [x] Import path fix (backend.app.* prefix)

### Doğrulama
```bash
# OAuth test
GET /api/v1/quickbooks/auth → {"auth_url": "https://appcenter.intuit.com/..."}

# Sync test
POST /api/v1/quickbooks/sync → {"status": "synced", "snapshots_created": 3}

# DB test
SELECT count(*) FROM financial_snapshots; → 3 (profit_loss, balance_sheet, cash_flow)
```

### Risk
- QuickBooks API entegrasyonuna geçildi → **Çözüldü:** Direkt QBO API (`python-quickbooks`)
- QBO sandbox adres sorunu → **Çözüldü:** Intuit Developer hesabı açıldı

---

## Hafta 2 — Finansal Hesaplama Motoru (Deterministic Tools)

**Tarih:** 16–22 Mart 2026  
**Done tanımı:** QBO verisinden burn rate, runway, gross/net burn ve 13 haftalık cash forecast hesaplanabiliyor. Her tool'un testi var.

### Tasklar
- [x] Tool: `burn_rate.py` — net burn, gross burn, burn multiple, trend (linear regression slope)
- [x] Tool: `runway.py` — runway months, cash zero date, status (critical/warning/monitor/healthy)
- [x] Tool: `cash_forecast.py` — 13 haftalık nakit projeksiyonu (trend bazlı)
- [x] Tool: `get_financial_summary` — P&L ve bilanço özet çıkarma (Polars DataFrame ops)
- [x] Her tool için Pydantic input/output modelleri
- [x] Her tool `Decimal` kullanıyor (float yok) — test ile doğrula
- [x] Unit testler: her tool'un her code path'i test edilmiş (edge cases dahil)
- [x] Test fixtures: 5 startup profili (healthy, pre-revenue, dying, profitable, new)

### Doğrulama
```bash
uv run pytest tests/test_tools/ -v --cov=backend/app/tools --cov-report=term-missing
# Sonuç: tüm satırlar covered, 0 uncovered line
```

### Risk
- QBO verisi karmaşık olabilir (çoklu para birimi, düzensiz gelir)
- **Azaltma:** İlk fazda tek para birimi (USD), aylık bazda basitleştirilmiş hesaplama

---

## Hafta 3 — Anomali Tespiti & Senaryo Simülatörü

**Tarih:** 23–29 Mart 2026  
**Done tanımı:** Sistem anomali tespit edebiliyor ve "X kişi daha alırsak runway ne olur?" sorusuna cevap verebiliyor.

### Tasklar
- [x] Tool: `anomaly.py` — Z-score analizi per category per month (threshold: 2.0σ)
- [x] Tool: `scenario.py` — parametre değişikliğinin runway/burn'e etkisi (hire, fire, revenue, expense)
- [x] Tool: `fundraising.py` — readiness score (0-100), investor metrics, gaps
- [x] Claude Opus entegrasyonu: doğal dil soru → tool çağrısı → doğal dil cevap
- [x] LangGraph agent graph skeleton (state schema, tool registration)
- [x] Model routing logic (select_model function — Haiku/Sonnet/Opus)
- [x] Cross-validation logic (tool numbers vs LLM numbers)
- [x] Prompt dosyaları oluştur: `system_base.txt`, `scenario_analysis.txt`, `anomaly_interpretation.txt`
- [x] Senaryo testleri: 5 farklı what-if sorusuyla doğruluk kontrolü
- [x] Anomaly testleri: bilinen anomalili veri seti ile tespit doğrulaması

### Doğrulama
```python
# Senaryo test
scenario_simulate(current_state, [{"type": "hire", "count": 2, "salary": 12000}])
# → new_runway < current_runway, delta_burn = 24000

# Anomaly test
detect_anomalies(data_with_known_spike)
# → anomaly detected, z_score > 2.0, category matches
```

### Risk
- Claude'un doğal dil sorusunu doğru tool parametrelerine çevirmesi
- **Azaltma:** Few-shot examples prompt dosyalarında, açık tool descriptions

---

## Hafta 4 — Slack Bot & Proaktif Uyarı Sistemi

**Tarih:** 30 Mart – 5 Nisan 2026  
**Done tanımı:** Slack bot çalışıyor, soru cevaplayabiliyor ve kritik eşik uyarısı atabiliyor.

### Tasklar
- [x] Slack App oluştur (api.slack.com), bot token + signing secret al
- [x] Slack Bolt FastAPI'ye mount et (ASGI adapter)
- [x] Slack → LangGraph: kullanıcı sorusu alınıp agent'a iletiliyor
- [x] LangGraph → Slack: cevap formatlanıp Slack Block Kit ile dönüyor
- [x] Haiku entegrasyonu: Slack konuşmaları için hızlı yanıt
- [x] Sonnet/Opus upgrade: trigger words tespit edilince model switch
- [x] Proaktif uyarı: APScheduler ile günlük eşik kontrolü
- [x] Uyarı kuralları: runway < 4 ay, burn rate MoM > %25 artış, büyük tek seferlik harcama
- [x] Slack mesaj formatlaması: Block Kit ile okunabilir finansal uyarılar
- [x] 3-saniye kuralı: Slack event acknowledge → BackgroundTasks ile async agent run
- [x] slack_messages tablosuna loglama (direction, content, agent_run_id)
- [x] slack_user_map tablosuna kullanıcı mapping

### Doğrulama
```
Slack'te yaz: "What's my runway?"
→ Bot 3 saniye içinde acknowledge eder
→ 10-30 saniye içinde cevap gelir: "Your runway is X months at $Y/mo burn rate"

Slack'te yaz: "What if I hire 2 engineers?"
→ Opus model seçilir
→ Senaryo simülasyonu çalışır
→ Cevap: "Hiring 2 engineers at $12K/mo each reduces runway from X to Y months"
```

### Risk
- Slack API rate limits ve bot onay süreci
- **Azaltma:** Development workspace'te Socket Mode ile test, production Events API sonra

---

## Hafta 5 — Aylık CFO Raporu & Fundraising Readiness

**Tarih:** 6–12 Nisan 2026  
**Done tanımı:** Sistem aylık kapsamlı CFO raporunu otomatik oluşturup Slack'e atabiliyor.

### Tasklar
- [x] Tool: `monthly_report.py` — tüm tool çıktılarını aggregate et
- [x] Claude Sonnet entegrasyonu: rapor formatlaması ve doğal dil özet
- [x] Board-style executive summary formatı
- [x] Investor metrik hesaplamaları: MRR, ARR, growth rate, burn multiple
- [x] Rapor scheduler: ayın ilk iş günü otomatik Slack'e gönderim (APScheduler)
- [x] Rapor formatı: Slack Block Kit ile görsel olarak zengin mesaj (sections, dividers, metrics)
- [x] Prompt dosyası: `report_generation.txt`
- [x] computed_metrics tablosuna rapor cache'leme
- [x] agent_runs tablosuna rapor generation logu

### Doğrulama
```
Scheduler tetiklenir (veya manuel trigger)
→ Tüm tool'lar çalışır
→ Sonnet executive summary üretir
→ Slack'te Block Kit formatında rapor görünür:
  - Executive Summary (3-4 cümle)
  - Runway & Burn Rate
  - Cash Forecast (13 hafta)
  - Anomalies (varsa)
  - Fundraising Readiness Score
  - 1-2 Actionable Recommendation
```

### Risk
- SaaS metrikleri (ARR, CAC, LTV) için Stripe/payment entegrasyonu gerekebilir
- **Azaltma:** MVP'de bu metrikleri QBO revenue verisinden yaklaşık hesapla, Stripe entegrasyonu sonra

---

## Hafta 6 — Onboarding, Stripe & End-to-End Test

**Tarih:** 13–19 Nisan 2026  
**Done tanımı:** Yeni kullanıcı kayıt olup QBO'sunu bağlayabiliyor, 24 saat içinde ilk Slack mesajını alıyor.

### Tasklar
- [x] Onboarding UI: 5-step wizard (Clerk → Stripe → QBO → Bank → Slack → Done)
- [x] Stripe Checkout Session: $150/ay, 14 gün trial
- [x] Stripe webhook handler: `checkout.session.completed`, `customer.subscription.updated`, `invoice.payment_failed`
- [x] Tenant lifecycle: trial → active → past_due → cancelled → churned
- [x] Grace period: 14 gün past_due sonra cancelled
- [x] QBO connect: direkt QBO OAuth redirect
- [ ] Plaid connect: Plaid Link embed (optional, skip allowed)
- [x] Slack connect: "Add to Slack" OAuth button
- [x] İlk bağlantı sonrası otomatik veri çekme ve ilk rapor oluşturma
- [ ] Hoşgeldin mesajı: "✅ Connected. First report in 24h."
- [ ] End-to-end test: Signup → Connect → Sync → Slack report
- [x] Hata yönetimi: QBO bağlantı kopması, eksik veri, API hataları
- [ ] Loglama: temel structured logging kurulumu
- [x] Graceful degradation: QBO/Plaid (planned) kopması → stale data warning
- [ ] Graceful degradation: Stripe payment fail → past_due + Slack warning
- [ ] Next.js middleware → proxy migration (deprecation fix)

### Doğrulama
```
Yeni kullanıcı olarak:
1. Sign up (Clerk) ✓
2. Payment info (Stripe, trial starts) ✓
3. Connect QBO (OAuth flow) ✓
4. Skip bank (optional) ✓
5. Connect Slack (OAuth) ✓
6. "Check Slack" page ✓
7. 24 saat içinde Slack'te ilk rapor ✓
```

### Risk
- Onboarding UX'i düşük olursa ilk kullanıcılar kaybolur
- **Azaltma:** İlk 5 müşteriye manuel onboarding desteği, UX'i feedback'le geliştir

---

## Hafta 7 — Polish, Bug Fix & Demo Hazırlığı

**Tarih:** 20–26 Nisan 2026  
**Done tanımı:** Ürün demo gösterilebilir ve ilk beta kullanıcıya açılabilir durumda.

### Tasklar
- [ ] End-to-end test senaryolarını genişlet
- [ ] Edge case'ler: boş QBO hesabı, çok az işlem, negatif nakit, sıfır gelir
- [ ] Slack mesaj formatlarını geliştir (okunabilirlik, görsellik)
- [ ] Landing page güncelleme: demo video/GIF ekleme
- [ ] 2 dakikalık Loom demo videosu çek
- [ ] Temel dokümantasyon: "Nasıl çalışır" sayfası
- [ ] Performance optimizasyonu: rapor oluşturma süresi < 30 saniye
- [ ] Frontend smoke tests: middleware redirect, API error handling, stepper logic
- [ ] Security review: Claude Code ile tam codebase security audit
- [ ] API endpoint'lerinde rate limiting
- [ ] Error monitoring: structured logging review
- [ ] `.env.example` dosyası oluştur (credential'sız template)

### Doğrulama
```
- Loom demo videosu çekildi ✓
- Landing page güncel ✓
- Bilinen bug sayısı: 0 critical, max 3 minor ✓
- Rapor oluşturma < 30 saniye ✓
- Security audit geçti ✓
```

---

## Hafta 8 — İlk Müşteriler & Launch

**Tarih:** 27 Nisan – 3 Mayıs 2026  
**Done tanımı:** En az 3 startup kurucusuna demo gösterilmiş, en az 1 QBO bağlantısı yapılmış.

### Tasklar
- [ ] Clay ile hedefli outreach: seed-stage, ABD, 1-10 kişi, QBO kullanan
- [ ] Outreach mesajı: "$1,500/ay fractional CFO'nun analiz işini $150/ay'a al"
- [ ] Demo göster: Loom video + canlı demo teklifi
- [ ] İlk kullanıcıları onboard et (manuel destek)
- [ ] Feedback topla: neyi sevdiler, neyi sevmediler, neyi eksik buldular
- [ ] Retention sinyali: ilk haftada Slack bot'u kaç kez kullandılar?
- [ ] Build in public: "İlk müşterimiz QBO'sunu bağladı" tweet'i
- [ ] Sprint retrospective: 8 haftalık sürecin tam analizi
- [ ] Sonraki adımlar planı: Week 9+ roadmap

### Doğrulama
```
- En az 3 demo gösterildi ✓
- En az 1 gerçek QBO bağlantısı ✓
- Feedback dokümente edildi ✓
- Retention metrikleri toplanmaya başladı ✓
```

### Outreach Mesaj Şablonu
```
Hey {name} — fellow founder here. Quick question: your QBO has all your 
financial data, but does anyone actually tell you "your runway is 5 months 
and dropping"?

I built Flowytics — it connects to your QBO, calculates burn rate, runway, 
anomalies, and sends you a monthly CFO report on Slack. $150/mo instead 
of $1,500/mo fractional CFO.

2-min demo: {loom_link}
Want to try it? Takes 5 minutes to connect.
```

---

## Haftalık Ritüeller

### Her Gün
- Build in public tweet (Twitter/X, #BuildInPublic)
- `uv run pytest` — testler geçiyor mu?
- Git commit + push to develop

### Her Hafta Sonu
- Claude Code ile sprint raporu üret (`docs/sprints/SPRINT_W{N}.md`)
- Retrospective: ne iyi gitti, ne kötü gitti, ne değişmeli
- Sonraki hafta planını gözden geçir
- `develop` → `main` merge + deploy (GitHub Actions workflow_dispatch)

### Her Sprint Raporu İçerir
- Tamamlanan/kalan/blocker tasklar
- Test coverage (uncovered lines listesi)
- CI status (pass/fail)
- Metrikler: lines of code, tests added, endpoints, tools implemented
- Alınan kararlar
- Sonraki hafta planı

---

## Haftalık Success Metrikleri

| Hafta | Birincil Metrik | Kabul Kriteri |
|-------|----------------|---------------|
| 1 | QBO verisi çekildi mi? | Sandbox'tan P&L ve işlem verisi DB'de |
| 2 | Hesaplamalar doğru mu? | Bilinen verilerle burn rate/runway doğru, tüm tool paths covered |
| 3 | Senaryo ve anomali çalışıyor mu? | 5 farklı what-if sorusuna doğru cevap, anomali tespit doğru |
| 4 | Slack bot çalışıyor mu? | Soru-cevap + 1 proaktif uyarı çalışıyor |
| 5 | Aylık rapor oluşuyor mu? | Tam kapsamlı CFO raporu Slack'te |
| 6 | Onboarding çalışıyor mu? | Yeni kullanıcı uçtan uca akışı tamamlıyor |
| 7 | Demo gösterilebilir mi? | 2 dk Loom video çekildi, landing page güncel |
| 8 | Müşteri bulundu mu? | En az 3 demo, en az 1 QBO bağlantısı |

---

## Post-MVP Roadmap (Hafta 9+)

Bu öğeler MVP'de YOK. Müşteri feedback'ine göre önceliklendirilecek:

| Öğe | Ne Zaman |
|-----|----------|
| Xero desteği | İlk Xero kullanan müşteri istediğinde |
| Web dashboard | Müşteri feedback tekrar tekrar isterse |
| DSPy prompt optimization | 1000+ agent_run biriktikten sonra |
| Alembic migrations | Schema değişiklikleri sıklaştığında |
| Multi-currency | Uluslararası müşteri geldiğinde |
| Stripe revenue metrikleri | SaaS müşteri Stripe verisi istediğinde |
| Delaware C-Corp | MVP tamamlandığında (~2 hafta öncesinden başla) |
| Plaid production access | C-Corp kurulduktan sonra |
| YC başvurusu | MVP + ilk müşteri traction sonrası |
| HR modülü | CFO modülü product-market fit bulduktan sonra |

---

## Kritik Kurallar (Her Hafta Geçerli)

1. **Scope discipline:** "Bu hafta QBO'dan veri çekip burn rate hesaplayabilecek miyim?" sorusunu cevaplamayan her iş ertelenebilir.
2. **Tool tests non-negotiable:** Her tool'un her code path'i test edilmeden merge yok.
3. **Decimal everywhere:** `float` kullanıldığı tespit edilen her yere bug report.
4. **Ship weekly:** Her hafta sonunda çalışan, deploy edilmiş bir şey olmalı.
5. **Feedback over perfection:** %80 doğru çalışan shipped ürün > %100 doğru çalışan unshipped ürün.

---

*Son güncelleme: 11 Mart 2026. Bu plan, docs/09-mimari-ve-gelistirme-seans-raporu.md ile birlikte okunmalıdır.*
