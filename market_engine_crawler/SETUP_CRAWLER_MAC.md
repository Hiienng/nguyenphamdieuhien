# Crawler Mac Setup — One-time bootstrap

Mục tiêu: máy Mac thứ 2 chạy 24/7, kéo code từ git mỗi 5 phút, chạy 3 crawler theo lịch, ghi `crawl_run` vào Neon, gửi email khi gặp CAPTCHA.

---

## Phần 1 — Cài đặt môi trường (~30 phút)

### 1.1. System

```bash
# Tắt auto-sleep (System Settings → Battery → Power Adapter → Prevent display sleep)
sudo pmset -a sleep 0
sudo pmset -a disablesleep 1

# Đảm bảo Mac auto-login (System Settings → Users → Login Options)
# Để launchd chạy GUI Chrome cần user đang login

# Cài Xcode CLI
xcode-select --install
```

### 1.2. Git + clone

```bash
# Tạo SSH key (nếu repo private)
ssh-keygen -t ed25519 -C "crawler-mac"
cat ~/.ssh/id_ed25519.pub  # add vào GitHub deploy keys

# Clone repo
mkdir -p ~/Downloads/etsy_pilot
cd ~/Downloads/etsy_pilot
git clone <repo-url> nguyenphamdieuhien.online
```

### 1.3. Python via pyenv

```bash
# Cài pyenv
curl https://pyenv.run | bash

# Add vào ~/.zshrc
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# Cài Python (giống Mac dev)
pyenv install 3.11.9
pyenv global 3.11.9
```

### 1.4. Dependencies

```bash
cd ~/Downloads/etsy_pilot/nguyenphamdieuhien.online/market_engine_crawler

# Crawler deps (Playwright + psycopg)
pip install playwright psycopg2-binary 'psycopg[binary]'
playwright install chromium  # mặc dù dùng real Chrome — phòng hờ
```

### 1.5. Chrome

```bash
# Cài Google Chrome bản thường (DMG từ google.com/chrome)
# Đường dẫn phải là /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Mở 1 lần để Etsy lưu cookies (login nếu cần)
open -a "Google Chrome"
# Truy cập etsy.com, login, solve CAPTCHA lần đầu
```

---

## Phần 2 — Secrets

### 2.1. File `~/.EtseeMate-crawler.env`

```bash
cat > ~/.EtseeMate-crawler.env <<'EOF'
# Neon — cùng URL với backend production (xem .env của Mac dev hoặc Render dashboard)
export DATABASE_URL="postgresql://USER:PASS@HOST.neon.tech/etsy_pilot?sslmode=require"

# Email CAPTCHA — dùng Gmail App Password (Account → Security → App passwords)
export CRAWLER_NOTIFY_EMAIL_TO="us-da-ai-group@trustingsocial.com"
export CRAWLER_NOTIFY_EMAIL_FROM="your-bot@gmail.com"
export CRAWLER_NOTIFY_SMTP_HOST="smtp.gmail.com"
export CRAWLER_NOTIFY_SMTP_PORT="587"
export CRAWLER_NOTIFY_SMTP_USER="your-bot@gmail.com"
export CRAWLER_NOTIFY_SMTP_PASS="xxxx xxxx xxxx xxxx"
export CRAWLER_CAPTCHA_WAIT="180"   # giây — chờ user solve trước khi skip

# EtseeMate backend URL — trigger references/refresh sau market_discovery
export BACKEND_URL="https://nguyenphamdieuhien.online"

# Forces no-TTY path inside crawlers
export CRAWLER_UNATTENDED=1
EOF
chmod 600 ~/.EtseeMate-crawler.env

# Source mỗi shell mới
echo '[[ -f ~/.EtseeMate-crawler.env ]] && source ~/.EtseeMate-crawler.env' >> ~/.zshrc
source ~/.zshrc
```

### 2.2. Smoke test

```bash
cd ~/Downloads/etsy_pilot/nguyenphamdieuhien.online/market_engine_crawler

# Test DB connection
python3 -c "from crawl_ledger import start_run, finish_run; rid = start_run('smoke_test'); finish_run(rid, 'success', success_count=0, fail_count=0); print('OK', rid)"

# Test email (sẽ gửi 1 email tới TO)
python3 -c "from captcha_notify import send_captcha_email; send_captcha_email(job='smoke_test', url='https://example.com', screenshot_path=None)"
```

---

## Phần 3 — Cài launchd jobs

```bash
USERNAME=$(whoami)
PLIST_DIR=~/Library/LaunchAgents
mkdir -p $PLIST_DIR
SRC=~/Downloads/etsy_pilot/nguyenphamdieuhien.online/market_engine_crawler/launchd

# Copy + thay USERNAME placeholder
for f in $SRC/*.plist; do
  sed "s|USERNAME|$USERNAME|g" $f > $PLIST_DIR/$(basename $f)
done

# Load tất cả
for f in $PLIST_DIR/com.EtseeMate.crawler.*.plist; do
  launchctl unload "$f" 2>/dev/null
  launchctl load -w "$f"
done

# Verify
launchctl list | grep EtseeMate
```

Kết quả: 3 scheduled jobs hiện ra (EtseeMate crawler không còn chạy theo schedule):
- `com.EtseeMate.crawler.gitsync` — git pull mỗi 5p
- `com.EtseeMate.crawler.market` — Mon 02:00 hằng tuần
- `com.EtseeMate.crawler.rank` — daily 04:00

> **Note (2026-05-15):** `com.EtseeMate.crawler.EtseeMate` — **KHÔNG còn chạy định kỳ**.
> `StartInterval` đã bị disable trong plist. EtseeMate crawler chỉ chạy khi
> `crawl_queue` có item (queue-driven). Xem mục "EtseeMate Crawler — Queue-Driven Mode" bên dưới.

### Chạy thử ngay (không chờ lịch)

```bash
# EtseeMate crawler — chỉ chạy khi crawl_queue có item
python3 EtseeMate_listing_crawler.py --queue
tail -f /tmp/crawler-EtseeMate.log
```

---

## EtseeMate Crawler — Queue-Driven Mode (thay thế schedule từ 2026-05-15)

EtseeMate crawler **không còn chạy định kỳ**. Thay vào đó:

1. Mỗi khi user `confirm_import` một batch trong EtseeMate, backend tự động enqueue
   các `listing_id` mới vào bảng `crawl_queue` (status = `pending`).
2. EtseeMate crawler chạy theo lệnh thủ công hoặc được trigger bởi `run_scheduled.py`
   khi queue có item.

### Chạy thủ công

```bash
cd ~/Downloads/etsy_pilot/nguyenphamdieuhien.online/market_engine_crawler

# Pop tất cả pending items từ crawl_queue (batch mặc định: 50)
python3 EtseeMate_listing_crawler.py --queue

# Giới hạn batch size
python3 EtseeMate_listing_crawler.py --queue 20
```

### Kiểm tra queue status

```sql
SELECT status, COUNT(*) FROM crawl_queue GROUP BY status;
SELECT listing_id, queued_at, attempts, status FROM crawl_queue ORDER BY queued_at DESC LIMIT 20;
```

### Tại sao bỏ schedule?

- Trước đây crawler chạy mỗi 30 phút bất kể có listing mới hay không → tốn tài nguyên, tăng risk bị Etsy block.
- Nay crawler chỉ chạy khi có việc thực sự cần làm (confirmed batch → crawl_queue có item).
- `launchd/com.EtseeMate.crawler.EtseeMate.plist` vẫn giữ file để tham khảo, nhưng
  `StartInterval` đã bị comment out — **không load plist này lên launchd**.

---

## Phần 4 — Vận hành

### Xem log

```bash
tail -f /tmp/crawler-market.log
tail -f /tmp/crawler-EtseeMate.log
tail -f /tmp/crawler-rank.log
tail -f /tmp/gitsync.log
```

### Xem crawl_run từ DB

```sql
SELECT id, job_name, started_at, finished_at, status, success_count, fail_count
FROM crawl_run
ORDER BY started_at DESC LIMIT 20;
```

### Restart 1 job (sau khi update code)

`gitsync` đã tự pull mỗi 5p → không cần reload manual; lần chạy crawler kế tiếp dùng code mới.

Nếu cần restart hard:
```bash
launchctl unload ~/Library/LaunchAgents/com.EtseeMate.crawler.EtseeMate.plist
launchctl load -w  ~/Library/LaunchAgents/com.EtseeMate.crawler.EtseeMate.plist
```

### Tạm dừng tất cả

```bash
for f in ~/Library/LaunchAgents/com.EtseeMate.crawler.*.plist; do
  launchctl unload "$f"
done
```

---

## Phần 5 — CAPTCHA workflow

1. Crawler gặp CAPTCHA → screenshot + email gửi tới `CRAWLER_NOTIFY_EMAIL_TO`.
2. Email có:
   - Job name + host
   - URL Etsy đang dở
   - Screenshot CAPTCHA đính kèm
3. Bạn có **3 phút** (config `CRAWLER_CAPTCHA_WAIT`) để:
   - SSH vào Mac crawler: `ssh USERNAME@<lan-ip>`
   - Hoặc Screen Sharing (Cmd+K → vnc://lan-ip) → solve trong Chrome đang mở
4. Sau khi solve, crawler tự detect (no captcha element) → resume.
5. Quá 3 phút → skip target, ghi vào log, tiếp tục item tiếp theo.

### Tăng/giảm thời gian chờ

Sửa `CRAWLER_CAPTCHA_WAIT` trong `~/.EtseeMate-crawler.env`, lần run kế tiếp dùng giá trị mới.

---

## Phần 6 — Troubleshooting

| Triệu chứng | Nguyên nhân | Cách xử |
|---|---|---|
| `crawl_run` không có row | DATABASE_URL sai hoặc psycopg chưa cài | `pip install 'psycopg[binary]'` + check env |
| launchd job không chạy | plist sai cú pháp hoặc path wrong | `plutil -lint ~/Library/LaunchAgents/com.EtseeMate.*.plist` |
| Chrome không launch | Đường dẫn CHROME_PATH sai trên Mac mới | sửa `CHROME_PATH` constant trong 3 crawler scripts (tạm thời, sẽ refactor ra env sau) |
| Email không tới | App Password chưa enable hoặc less-secure-apps off | Google Account → Security → 2FA → App passwords |
| Git pull conflict | Có local change trên crawler Mac | Crawler Mac KHÔNG được modify code; nếu có conflict, `git reset --hard origin/main` |
