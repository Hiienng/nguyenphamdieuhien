"""
EtseeMate Listing Extension Crawl — headless Playwright (GitHub Actions compatible)
====================================================================
Replicated from crawl_weekly.py with adjustments for single listing pages.
Flow:
  1. Load EtseeMate URLs từ listings table
  2. Crawl mỗi URL bằng headless Chromium + stealth
  3. Upsert kết quả vào listing_extense
  4. Tính original_price từ price/discount
"""

import asyncio
import csv
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, unquote_plus

from playwright.async_api import async_playwright, Browser, Page

# ── config ────────────────────────────────────────────────────────────────────

NAV_TIMEOUT_MS  = 35_000
RENDER_WAIT_MIN = 3.0
RENDER_WAIT_MAX = 5.5
DELAY_MIN       = 8
DELAY_MAX       = 20

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT  = 9222
PROFILE_DIR = Path.home() / ".etsy_cdp_profile"

# ── DB helpers ────────────────────────────────────────────────────────────────

def pg_dsn() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        env_path = os.path.join(os.path.dirname(__file__), "../../.env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("DATABASE_URL="):
                    raw = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not raw:
        raise SystemExit("[!] DATABASE_URL chưa cấu hình")
    url = raw.replace("postgresql+asyncpg://", "postgresql://", 1).replace("postgres://", "postgresql://", 1)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query); qs.pop("channel_binding", None)
    if "sslmode" not in qs:
        qs["sslmode"] = ["require"]
    return urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in qs.items()})))


def get_conn(dsn: str):
    import psycopg2
    return psycopg2.connect(dsn)


def init_db(dsn: str):
    """Ensure listing_extense table exists."""
    conn = get_conn(dsn); cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS listing_extense (
        id               VARCHAR(32) PRIMARY KEY,
        search_tag       TEXT,
        product_type     TEXT,
        title            TEXT,
        price            BIGINT,
        original_price   BIGINT,
        shop_name        TEXT,
        rating           REAL,
        review_count     INTEGER,
        badge            TEXT,
        discount         INTEGER,
        free_shipping    BOOLEAN,
        is_ad            BOOLEAN DEFAULT FALSE,
        tag_ranking      INTEGER,
        url              TEXT,
        import_date      DATE,
        importer         VARCHAR(32),
        updated_at       TIMESTAMPTZ DEFAULT now()
    );
    """)
    conn.commit(); conn.close()


def load_EtseeMate_listings(dsn: str) -> list[dict]:
    """Load EtseeMate listings từ bảng listings."""
    conn = get_conn(dsn); cur = conn.cursor()
    cur.execute("SELECT listing_id, url, category FROM listings WHERE url IS NOT NULL")
    rows = cur.fetchall()
    conn.close()
    return [{"listing_id": r[0], "url": r[1], "category": r[2]} for r in rows if r[0]]


def upsert_extense(dsn: str, items: list[dict]):
    """Upsert vào listing_extense (INSERT nếu chưa có, UPDATE nếu đã có)."""
    if not items:
        return 0
    import psycopg2
    conn = get_conn(dsn); cur = conn.cursor()
    updated = inserted = 0
    today = date.today()

    for item in items:
        lid = item.get("listing_id")
        if not lid:
            continue
        cur.execute("SELECT id FROM listing_extense WHERE id = %s", (lid,))
        exists = cur.fetchone()

        if exists:
            cur.execute("""
                UPDATE listing_extense SET
                    price          = COALESCE(%s, price),
                    title          = COALESCE(%s, title),
                    rating         = COALESCE(%s, rating),
                    badge          = COALESCE(%s, badge),
                    discount       = COALESCE(%s, discount),
                    review_count   = COALESCE(%s, review_count),
                    free_shipping  = %s,
                    import_date    = %s,
                    updated_at     = now()
                WHERE id = %s
            """, (
                item.get("price"), item.get("title"),
                item.get("rating_score"), item.get("badge"),
                item.get("discount"), item.get("review_count"),
                bool(item.get("free_shipping")), today, lid,
            ))
            updated += cur.rowcount
        else:
            cur.execute("""
                INSERT INTO listing_extense
                    (id, search_tag, product_type, title, price, shop_name,
                     rating, review_count, badge, discount, free_shipping, is_ad,
                     tag_ranking, url, import_date, importer)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'crawl_EtseeMate')
            """, (
                lid, item.get("category"), item.get("category"),
                item.get("title"), item.get("price"),
                item.get("shop"), item.get("rating_score"),
                item.get("review_count"), item.get("badge"),
                item.get("discount"), bool(item.get("free_shipping")),
                bool(item.get("is_ad")), item.get("tag_ranking") or 0,
                item.get("url"), today,
            ))
            inserted += cur.rowcount

    conn.commit(); conn.close()
    return inserted + updated


def fill_original_price(dsn: str) -> int:
    """Tính original_price = price / (1 - discount/100), overwrite mỗi lần crawl."""
    conn = get_conn(dsn); cur = conn.cursor()
    cur.execute("""
        UPDATE listing_extense
        SET original_price = ROUND(price::numeric / (1 - discount::numeric / 100))
        WHERE price IS NOT NULL AND discount IS NOT NULL
          AND discount > 0 AND discount < 100
    """)
    n = cur.rowcount
    conn.commit(); conn.close()
    return n


# ── JS extractor (search-result cards, ported from market_batch_scraper.py) ──

SEARCH_EXTRACT_JS = """
(maxItems) => {
    const clean = s => s ? s.replace(/\\s+/g, ' ').trim() : '';
    const getText = (el, sels) => {
        for (const s of sels) {
            const node = el.querySelector(s);
            if (node && node.textContent.trim()) return clean(node.textContent);
        }
        return '';
    };
    const parseRating = (aria) => {
        if (!aria) return { rating: null, review_count: null };
        const score   = (aria.match(/([\\d.]+)\\s+star/)   || [])[1];
        const reviews = (aria.match(/(\\d[\\d,]*)\\s+review/) || [])[1];
        return {
            rating:       score   ? parseFloat(score)                 : null,
            review_count: reviews ? parseInt(reviews.replace(',','')) : null,
        };
    };
    const parseDiscount = (text) => {
        if (!text) return null;
        const pats = [/\\b(\\d{1,3})\\s*%\\s*off\\b/i, /\\bsave\\s*(\\d{1,3})\\s*%\\b/i];
        for (const p of pats) {
            const m = text.match(p);
            if (m) { const v = parseInt(m[1]); if (v > 0 && v < 100) return v; }
        }
        return null;
    };
    const parsePrice = (text) => {
        if (!text) return null;
        const t = text.trim();
        const dots   = (t.match(/\\./g) || []).length;
        const commas = (t.match(/,/g)  || []).length;
        let normalized;
        if (dots > 1) {
            normalized = t.replace(/\\./g, '').replace(/,/g, '.');
        } else if (commas > 1) {
            normalized = t.replace(/,/g, '');
        } else if (dots === 1 && commas === 1) {
            normalized = t.lastIndexOf('.') > t.lastIndexOf(',')
                ? t.replace(/,/g, '')
                : t.replace(/\\./g, '').replace(',', '.');
        } else {
            normalized = t.replace(/[^\\d.,]/g, '');
            if (/\\.\\d{3}$/.test(normalized) && dots === 1 && commas === 0)
                normalized = normalized.replace('.', '');
        }
        const v = parseFloat(normalized.replace(/[^\\d.]/g, ''));
        return isFinite(v) && v > 0 ? v : null;
    };
    const allCards = [...document.querySelectorAll('[data-listing-id]')].filter(
        el => !el.parentElement?.closest('[data-listing-id]')
    );
    if (!allCards.length) return [];
    const seen = new Set(), results = [];
    for (const card of allCards) {
        const listingId = card.getAttribute('data-listing-id') || '';
        if (!listingId || seen.has(listingId)) continue;
        seen.add(listingId);
        const linkEl   = card.querySelector('a[href*="/listing/"]');
        const url      = linkEl ? linkEl.href.split('?')[0] : '';
        const imgEl    = card.querySelector('img[src], img[data-src], picture img');
        const imageUrl = imgEl ? (imgEl.src || imgEl.dataset.src || '') : '';
        let shop_name = '';
        const shopLinkEl = card.querySelector('a[href*="/shop/"]');
        if (shopLinkEl) {
            const parts = shopLinkEl.pathname.split('/shop/');
            if (parts.length > 1) shop_name = parts[1].split('/')[0] || '';
        }
        if (!shop_name) {
            const shopNameEl = card.querySelector('[class*="shop-name"],[class*="seller-name"],[data-shop-name]');
            if (shopNameEl) shop_name = clean(shopNameEl.textContent);
        }
        if (!shop_name) {
            const m = (card.textContent || '').match(/From shop\\s+(\\S+)/);
            if (m) shop_name = m[1];
        }
        let rating = null, review_count = null;
        const ratingEl = card.querySelector('[aria-label*="star"], [aria-label*="review"]');
        if (ratingEl) ({ rating, review_count } = parseRating(ratingEl.getAttribute('aria-label') || ''));
        const priceEl = card.querySelector('[class*="currency-value"],[class*="price-value"],span[class*="price"]');
        const price   = priceEl ? parsePrice(priceEl.textContent) : null;
        const txt     = card.textContent || '';
        const discEl  = card.querySelector('[class*="percent-off"],[class*="sale-percent"],[class*="discount"]');
        let discount  = discEl ? parseDiscount(clean(discEl.textContent || '')) : null;
        if (discount === null) discount = parseDiscount(txt);
        const badgeEl = card.querySelector('[class*="wt-badge"],[class*="listing-badge"]');
        let badge = badgeEl ? clean(badgeEl.textContent) : null;
        if (!badge) { const bm = txt.match(/\\b(Bestseller|Popular now|Etsy's Pick)\\b/); if (bm) badge = bm[1]; }
        results.push({
            listing_id:   listingId,
            title:        getText(card, ['h3','h2','[class*="title"]']),
            price,
            shop_name,
            rating,
            review_count,
            badge,
            discount,
            is_ad:        /\\bAd by\\b/i.test(txt) || !!card.querySelector('[class*="sponsored"]'),
            free_shipping:/FREE shipping/i.test(txt),
            tag_ranking:  results.length + 1,
            url,
            image_url:    imageUrl,
        });
        if (results.length >= maxItems) break;
    }
    return results;
}
"""

MAX_ITEMS = 48

# ── page helpers ──────────────────────────────────────────────────────────────

def launch_chrome():
    """Spawn real Chrome with remote-debugging port + persistent profile."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [CHROME_PATH, f"--remote-debugging-port={DEBUG_PORT}",
         f"--user-data-dir={PROFILE_DIR}", "--no-first-run",
         "--no-default-browser-check", "--disable-logging", "--log-level=3",
         "--start-maximized", "https://www.etsy.com"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(4)


async def simulate_scroll(page: Page):
    scroll_height = await page.evaluate("document.body.scrollHeight")
    viewport      = await page.evaluate("window.innerHeight")
    if scroll_height <= viewport:
        return
    target = int(scroll_height * random.uniform(0.6, 0.85))
    pos = 0
    while pos < target:
        step = random.randint(80, 180) if random.random() < 0.3 else random.randint(200, 420)
        pos  = min(pos + step, target)
        await page.evaluate(f"window.scrollTo({{top:{pos},behavior:'smooth'}})")
        if random.random() < 0.12:
            await asyncio.sleep(random.uniform(1.0, 2.5))
        else:
            await asyncio.sleep(random.uniform(0.15, 0.5))
    await asyncio.sleep(random.uniform(0.8, 1.8))
    await page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def wait_for_listings(page: Page, timeout_ms: int = 15_000) -> bool:
    try:
        await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 8_000))
    except Exception:
        pass
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        count = await page.evaluate(
            "() => document.querySelectorAll('[data-listing-id]').length"
        )
        if count >= 4:
            return True
        await asyncio.sleep(0.5)
    return False


async def is_blocked(page: Page) -> bool:
    """
    Detect real anti-bot pages only. The legacy check used
    `[class*="slider-button"]` which false-positives on every Etsy
    search-results page (Etsy uses that class for normal filter UI).
    """
    try:
        url   = page.url or ""
        title = (await page.title()).lower().strip()
        if "dd_referrer" in url or title in ("etsy.com", "") or "verification" in title:
            return True
        return await page.evaluate("""
            () => !!(document.querySelector('[class*="captcha"]') ||
                     document.querySelector('[class*="challenge"]'))
        """)
    except Exception:
        return False


async def handle_captcha(page: Page) -> bool:
    if not sys.stdin.isatty() or os.getenv("CRAWLER_UNATTENDED") == "1":
        print("  [!] CAPTCHA detected — unattended mode, skipping.")
        return False
    print("\n  [!] CAPTCHA detected — solve in Chrome then press ENTER...")
    try:
        await asyncio.get_event_loop().run_in_executor(None, input)
    except EOFError:
        return False
    await asyncio.sleep(2)
    return not await is_blocked(page)


# ── core crawl ────────────────────────────────────────────────────────────────

async def crawl_all(targets: list[dict], dsn: str):
    """
    Sequential crawl: for each internal listing, search Etsy by its listing_id
    (anti-bot friendly — same path as market_batch_scraper.scrape_search),
    find its card in the result set, upsert into listing_extense.
    """
    total_upserted = 0
    total_missed   = 0

    launch_chrome()
    print("[>] Waiting 5s for Chrome to settle...")
    await asyncio.sleep(5)

    async with async_playwright() as p:
        try:
            browser: Browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
        except Exception as e:
            print(f"[!] Cannot connect to Chrome CDP: {e}")
            return 0

        context = browser.contexts[0] if browser.contexts else None
        if not context:
            print("[!] No browser context found.")
            await browser.close()
            return 0

        page: Page = await context.new_page()

        try:
            for idx, row in enumerate(targets, 1):
                lid = row["listing_id"]
                search_url = f"https://www.etsy.com/search?q={lid}&currency=USD"
                print(f"  [{idx}/{len(targets)}] ID:{lid} -> search")

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                    await asyncio.sleep(random.uniform(RENDER_WAIT_MIN, RENDER_WAIT_MAX))
                except Exception as e:
                    print(f"  [{idx}] Navigation failed: {e}")
                    continue

                # Wait for results cards; if not present, then check for real block.
                has_cards = await wait_for_listings(page)
                if not has_cards:
                    try:
                        _t = (await page.title())[:80]; _u = page.url
                    except Exception:
                        _t = _u = "?"
                    print(f"  [{idx}] No cards loaded — url={_u!r} title={_t!r}")
                    if await is_blocked(page):
                        ok = await handle_captcha(page)
                        if not ok:
                            print(f"  [{idx}] Blocked — skipping.")
                            continue
                    else:
                        print(f"  [{idx}] Empty result page — skipping.")
                        continue

                await simulate_scroll(page)

                try:
                    cards = await page.evaluate(SEARCH_EXTRACT_JS, MAX_ITEMS) or []
                except Exception as e:
                    print(f"  [{idx}] JS extract failed: {e}")
                    continue

                # find own card in results
                own = next((c for c in cards if str(c.get("listing_id")) == str(lid)), None)
                if not own:
                    total_missed += 1
                    print(f"  [{idx}] Not found in {len(cards)} cards — skipping.")
                else:
                    item = dict(own)
                    item["listing_id"] = lid
                    item["url"] = item.get("url") or row.get("url")
                    item["category"] = row.get("category")
                    # adapt key names to upsert_extense() schema
                    item["shop"]         = item.get("shop_name")
                    item["rating_score"] = item.get("rating")
                    n = upsert_extense(dsn, [item])
                    total_upserted += n
                    print(f"  [{idx}] Upserted {n} for {lid}  rank_in_results={item.get('tag_ranking')}  (total {total_upserted})")

                if idx < len(targets):
                    delay = random.uniform(DELAY_MIN, DELAY_MAX)
                    print(f"  Sleeping {delay:.0f}s...")
                    await asyncio.sleep(delay)
        finally:
            await browser.close()

    print(f"\n[summary] upserted={total_upserted}  not_found_in_search={total_missed}")
    return total_upserted


# ── entry ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 62)
    print("  EtseeMate Listing Extension Crawl")
    print("=" * 62)

    dsn = pg_dsn()
    
    # 0. Init Table
    init_db(dsn)

    # 1. Load URLs
    targets = load_EtseeMate_listings(dsn)
    print(f"\n[1/3] Loaded {len(targets)} EtseeMate listings from DB")

    if not targets:
        print("      → Nothing to crawl. Exit.")
        return

    # 2. Crawl
    print(f"\n[2/3] Crawling sequentially via CDP + real Chrome...")
    total = await crawl_all(targets, dsn)
    print(f"      → {total} rows upserted into listing_extense")

    # 3. original_price
    print("\n[3/3] Computing original_price from price/discount...")
    n = fill_original_price(dsn)
    print(f"      → {n} rows filled")

    print("\n" + "=" * 62)
    print("  Done.")
    print("=" * 62)


if __name__ == "__main__":
    asyncio.run(main())
