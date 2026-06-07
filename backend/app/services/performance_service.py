import json
from decimal import Decimal
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ── Scenario matrix from senarious_rules.xlsx (sheet "Kịch bản Ads") ───────
# Thresholds: CTR ≥ 1.5% = Cao, CR ≥ 3% = Cao, ROAS breakeven default = 2.0
# Columns: (roas_band, cr_level, ctr_level, case_name, action, cause, fix_listing, fix_ads)
_SCENARIO_SEED = [
    # --- ROAS trên huề vốn (profitable) ---
    ("profitable", "high", "high",
     "Có sales và đang lời", "keep", None, None, None),
    ("profitable", "low", "high",
     "Có sales và đang lời", "improve",
     "Listing: Khách clicks vào đúng intent nhưng listing chưa tốt.\nAds: Keywords trong ads chưa tối ưu.",
     "Kiểm tra giá bán, giá ship, review, hình thông tin sp đã rõ chưa, option sản phẩm có thể thêm gì không.",
     "Tắt bớt các keywords không hiệu quả đang chạy trong listing."),
    ("profitable", "high", "low",
     "Có sales và đang lời", "improve",
     "Listing: hình main chưa đúng intent, keywords dùng trong listing chưa chuẩn, giá mòi đang cao.\nAds: Keywords dùng trong ads đang chưa đúng intent.",
     "Tăng CTR: xem lại keywords, hình main, alt trong hình main, giá mòi.",
     "Tắt bớt các keywords không hiệu quả đang chạy trong listing."),
    ("profitable", "low", "low",
     "Có sales và đang lời", "improve",
     "Ads: Keyword đang không hiệu quả, giá mòi đang cao.\nListing: vừa chưa đúng intent vừa chưa đủ hấp dẫn để khách mua.\nViews cao, CTR thấp: Keywords trong ads và listing quá rộng, cạnh tranh cao.",
     "Tăng CTR: xem lại keywords, hình main, alt trong hình main, giá mòi.\nTăng CR: tối ưu giá bán, offers, giá ship, reviews.\nGiảm CPC: đổi keywords rộng thành long-tailed.",
     "Tắt bớt các keywords không đúng intent hoặc target rộng, cpc cao."),

    # --- Lỗ nhẹ (1 ≤ ROAS < breakeven) ---
    ("slight_loss", "high", "high",
     "Có sales, đang lỗ nhẹ", "improve",
     "Khi views và clicks quá thấp.\nAOV chưa đủ cover tiền ads, cpc quá cao (>$0.8).",
     "Views và clicks thấp: xem lại keywords, giá mòi, hình main, alt trong hình main.\nTăng AOV: thêm Offer hoặc dùng related products.",
     "Tắt bớt các keywords không đúng intent hoặc target rộng, cpc cao."),
    ("slight_loss", "high", "low",
     "Có sales, đang lỗ nhẹ", "improve",
     "Do keywords trong listing chưa đúng intent hoặc target quá rộng, do hình main, giá mòi.\nDo phần keywords trong ads chưa đúng intent hoặc quá rộng, cạnh tranh cao.",
     "Tối ưu keywords, hình main, alt trong hình main, giá mòi.",
     "Tắt bớt các keywords không đúng intent hoặc target rộng, cpc cao."),
    ("slight_loss", "low", "high",
     "Có sales, đang lỗ nhẹ", "improve",
     "Do listing chưa đủ hấp dẫn.",
     "Xem lại keywords dùng trong listing, đổi long-tailed keywords, bỏ bớt keywords target rộng.\nHình main, alt trong hình main.\nGiá mòi: giảm.",
     "Tắt bớt các keywords không đúng intent hoặc target rộng, cpc cao."),
    ("slight_loss", "low", "low",
     "Có sales, đang lỗ nhẹ", "improve",
     "Nếu có views: do listing, do keywords trong ads.\nViews thấp: do listing (xem lại keywords, hình main đúng intent), do keywords đang chạy trong ads.",
     "Tăng CTR: sửa keywords khi cần, kiểm tra alt trong hình main, cân nhắc đổi hình main, video, giảm giá mòi.\nTăng CR: xem giá bán, giá ship, offer, reviews.",
     "Tắt bớt các keywords không hiệu quả đang chạy trong listing."),

    # --- Lỗ nặng (0 < ROAS < 1) ---
    ("heavy_loss", "high", "high",
     "Có sales, lỗ nặng", "improve",
     "AOV chưa đủ cover ads spend.\nDo CPC quá cao (>$0.8).\nViews thấp.",
     "Views thấp: kiểm tra lại keywords trong listing và ads (loại bỏ từ không đúng intent, target quá rộng), hình main hoặc alt trong hình main.\nAOV thấp: thay đổi offer, thêm related products.",
     "Tắt keywords không đúng intent, target rộng, cạnh tranh cao trong ads."),
    ("heavy_loss", "low", "high",
     "Có sales, lỗ nặng", "improve",
     "CR thấp do listing chưa tốt, keywords trong ads chưa đúng intent hoặc quá rộng.",
     "Xem lại keywords dùng trong listing, đổi long-tailed keywords, bỏ bớt keywords target rộng.\nHình main, alt trong hình main.\nGiá mòi: giảm.",
     "Tắt keywords không đúng intent, target rộng, cạnh tranh cao trong ads."),
    ("heavy_loss", "high", "low",
     "Có sales, lỗ nặng", "improve",
     "Keywords (trong listing và trong ads), hình main, giá mòi.",
     "Xem lại keywords dùng trong listing, đổi long-tailed keywords, bỏ bớt keywords target rộng.\nHình main, alt trong hình main.\nGiá mòi: giảm.",
     "Tắt keywords không đúng intent, target rộng, cạnh tranh cao trong ads."),
    ("heavy_loss", "low", "low",
     "Có sales, lỗ nặng", "improve_or_off",
     "Listing chưa tối ưu: do keywords, hình main, giá mòi.\nĐã tối ưu nhưng không có xu hướng cải thiện: tắt.",
     "Xem lại keywords dùng trong listing, đổi long-tailed keywords, bỏ bớt keywords target rộng.\nHình main, alt trong hình main.\nGiá mòi: giảm.\nKiểm tra giá bán, giá ship, reviews xem có review xấu không.",
     "Tắt keywords không đúng intent, target rộng, cạnh tranh cao trong ads."),

    # --- Không có sale (ROAS = 0) ---
    ("no_sales", "zero", "high",
     "Không có sale, có clicks", "improve_or_off",
     "Listing mới: để theo dõi thêm, kiểm tra keywords trong ads.\nListing cũ, đã tối ưu nhưng không cải thiện: tắt.\nListing cũ, chưa tối ưu: keywords có thể không liên quan, giá bán, giá mòi, hình chi tiết hoặc reviews.",
     "Đổi keywords thành long-tailed, up thêm ảnh chi tiết, xin reviews, gỡ review xấu.",
     "Tắt keywords không đúng intent, target rộng, cạnh tranh cao trong ads."),
    ("no_sales", "zero", "low",
     "Không có sale, có clicks", "improve_or_off",
     "Listing mới: để theo dõi thêm, kiểm tra keywords trong ads.\nListing cũ, đã tối ưu nhưng không cải thiện: tắt.\nListing cũ, chưa tối ưu: keywords có thể không liên quan, giá bán, giá mòi, hình chi tiết hoặc reviews.\nDo listing mất index.",
     "Đổi keywords thành long-tailed, up thêm ảnh chi tiết, xin reviews, gỡ review xấu.\nThêm offers, giảm giá.\nNếu do listing mất index: deactive → reactive lại listing.",
     "Tắt keywords không đúng intent, target rộng, cạnh tranh cao trong ads."),
]

# Thresholds
CTR_THRESHOLD = 1.5
CR_THRESHOLD = 3.0
ROAS_BREAKEVEN = 2.0


async def seed_scenarios(db: AsyncSession) -> None:
    """Create scenarios_rules if not exists, and seed only if empty."""
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS scenarios_rules (
            id SERIAL PRIMARY KEY,
            roas_band VARCHAR(32) NOT NULL,
            cr_level  VARCHAR(8)  NOT NULL,
            ctr_level VARCHAR(8)  NOT NULL,
            case_name TEXT        NOT NULL,
            action    VARCHAR(32) NOT NULL,
            cause     TEXT,
            fix_listing TEXT,
            fix_ads   TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    
    # Check if empty
    res = await db.execute(text("SELECT count(*) FROM scenarios_rules"))
    count = res.scalar()
    if count == 0:
        for row in _SCENARIO_SEED:
            await db.execute(
                text("""
                    INSERT INTO scenarios_rules
                        (roas_band, cr_level, ctr_level, case_name, action, cause, fix_listing, fix_ads)
                    VALUES (:rb, :cr, :ctr, :cn, :act, :cause, :fl, :fa)
                """),
                dict(rb=row[0], cr=row[1], ctr=row[2], cn=row[3],
                     act=row[4], cause=row[5], fl=row[6], fa=row[7]),
            )
        await db.commit()


async def get_dashboard_listings(db: AsyncSession, tenant_id: str) -> list[dict]:
    """
    Build listing dashboard by reading the materialized reporting layer
    (`listings_int_ext`, `listings_int_hist`, `keywords`).

    The reporting tables are populated by `reporting_etl.rebuild_reporting`.
    """
    # Global set: keywords từng có revenue > 0 trong lịch sử raw của tenant này.
    sql = text("""
        WITH kw_history_earners AS (
            SELECT DISTINCT keyword
            FROM (
                SELECT keyword, revenue FROM keyword_report       WHERE tenant_id = :tid
                UNION ALL
                SELECT keyword, revenue FROM manual_keyword_report WHERE tenant_id = :tid
            ) s
            WHERE COALESCE(revenue, 0) > 0
        )
        SELECT
            e.listing_id,
            e.title,
            e.product,
            e.period,
            e.reference_date,
            e.ctr,
            e.cr,
            e.roas,
            e.url,
            e.no_vm,
            e.views,
            e.clicks,
            e.orders,
            e.revenue,
            e.spend,
            e.cpc,
            e.cpp,
            e.scenario_action,
            e.scenario_label,
            e.scenario_cause,
            e.scenario_fix_listing,
            e.scenario_fix_ads,
            kw.keywords     AS keywords,
            hist.history    AS history
        FROM listings_int_ext e
        LEFT JOIN LATERAL (
            SELECT json_agg(
                json_build_object(
                    'keyword',              k.keyword,
                    'currently_status',     k.currently_status,
                    'period',               k.period,
                    'views',                k.views,
                    'clicks',               k.clicks,
                    'orders',               k.orders,
                    'revenue',              k.revenue,
                    'spend',                k.spend,
                    'roas',                 k.roas,
                    'click_rate',           k.click_rate,
                    'cpc',                  k.cpc,
                    'cpp',                  k.cpp,
                    'history_has_revenue',  (he.keyword IS NOT NULL)
                ) ORDER BY COALESCE(k.orders, 0) DESC, COALESCE(k.clicks, 0) DESC, k.keyword ASC
            ) AS keywords
            FROM keywords k
            LEFT JOIN kw_history_earners he ON he.keyword = k.keyword
            WHERE k.listing_id = e.listing_id AND k.tenant_id = e.tenant_id
        ) kw ON true
        LEFT JOIN LATERAL (
            SELECT json_agg(
                json_build_object(
                    'history_id',     h.listing_id || ':' || h.period,
                    'period',         h.period,
                    'views',          h.views,
                    'clicks',         h.clicks,
                    'orders',         h.orders,
                    'revenue',        h.revenue,
                    'spend',          h.spend,
                    'roas',           h.roas,
                    'cpc',            h.cpc,
                    'cpp',            h.cpp,
                    'source',         h.source,
                    'reference_date', h.reference_date
                ) ORDER BY h.period DESC
            ) AS history
            FROM listings_int_hist h
            WHERE h.listing_id = e.listing_id AND h.tenant_id = e.tenant_id
        ) hist ON true
        WHERE e.tenant_id = :tid
        ORDER BY e.listing_id ASC, e.period ASC
    """)
    result = await db.execute(sql, {"tid": tenant_id})
    rows = [dict(r) for r in result.mappings().all()]
    return rows


def write_dashboard_json(listings: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(listings, default=lambda o: float(o) if isinstance(o, Decimal) else str(o), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
