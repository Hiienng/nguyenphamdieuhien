"""
Etsy Product Category Catalog
─────────────────────────────
Canonical list of popular Etsy product categories shown in the onboarding wizard.
Source: Etsy taxonomy + top-selling categories (Marmalade/eRank insights).

Each entry: (id, label, group)
- id: snake_case identifier — stored in users.product_categories JSON
- label: human-readable label shown to user
- group: visual grouping in the UI

Categories are merged with DISTINCT product_type from market_listing so users see
both crawled categories (data available immediately) and uncrawled ones
(data will be crawled after they sign up).
"""

ETSY_CATEGORY_CATALOG: list[dict] = [
    # ── Clothing & Apparel ─────────────────────────────────────
    {"id": "onesie", "label": "Custom Onesie", "group": "Clothing"},
    {"id": "sweater", "label": "Custom Sweater", "group": "Clothing"},
    {"id": "shirt", "label": "Custom T-Shirt", "group": "Clothing"},
    {"id": "hoodie", "label": "Custom Hoodie", "group": "Clothing"},
    {"id": "hat", "label": "Hat / Cap", "group": "Clothing"},
    {"id": "socks", "label": "Custom Socks", "group": "Clothing"},

    # ── Accessories ────────────────────────────────────────────
    {"id": "jewelry", "label": "Jewelry", "group": "Accessories"},
    {"id": "necklace", "label": "Necklace", "group": "Accessories"},
    {"id": "earrings", "label": "Earrings", "group": "Accessories"},
    {"id": "bracelet", "label": "Bracelet", "group": "Accessories"},
    {"id": "ring", "label": "Ring", "group": "Accessories"},
    {"id": "bag", "label": "Bag / Tote", "group": "Accessories"},
    {"id": "wallet", "label": "Wallet / Purse", "group": "Accessories"},
    {"id": "keychain", "label": "Keychain", "group": "Accessories"},

    # ── Home & Living ──────────────────────────────────────────
    {"id": "blanket", "label": "Personalized Blanket", "group": "Home & Living"},
    {"id": "pillow", "label": "Throw Pillow", "group": "Home & Living"},
    {"id": "mug", "label": "Custom Mug", "group": "Home & Living"},
    {"id": "tumbler", "label": "Tumbler / Water Bottle", "group": "Home & Living"},
    {"id": "candle", "label": "Candle", "group": "Home & Living"},
    {"id": "sign", "label": "Wall Sign", "group": "Home & Living"},
    {"id": "doormat", "label": "Doormat", "group": "Home & Living"},
    {"id": "cutting_board", "label": "Cutting Board", "group": "Home & Living"},
    {"id": "ornament", "label": "Ornament", "group": "Home & Living"},

    # ── Wall Art & Prints ──────────────────────────────────────
    {"id": "wall_art", "label": "Wall Art", "group": "Art & Prints"},
    {"id": "print", "label": "Art Print / Poster", "group": "Art & Prints"},
    {"id": "digital_print", "label": "Digital Print / Download", "group": "Art & Prints"},
    {"id": "photo_print", "label": "Photo Print", "group": "Art & Prints"},
    {"id": "canvas", "label": "Canvas Art", "group": "Art & Prints"},

    # ── Stickers & Paper ───────────────────────────────────────
    {"id": "sticker", "label": "Sticker", "group": "Stickers & Paper"},
    {"id": "decal", "label": "Decal", "group": "Stickers & Paper"},
    {"id": "card", "label": "Greeting Card", "group": "Stickers & Paper"},
    {"id": "invitation", "label": "Invitation", "group": "Stickers & Paper"},
    {"id": "planner", "label": "Planner / Journal", "group": "Stickers & Paper"},

    # ── Kids & Baby ────────────────────────────────────────────
    {"id": "crown", "label": "Birthday Crown", "group": "Kids & Baby"},
    {"id": "baby_gift", "label": "Baby Gift Set", "group": "Kids & Baby"},
    {"id": "toy", "label": "Toy / Plush", "group": "Kids & Baby"},
    {"id": "kids_apparel", "label": "Kids Apparel", "group": "Kids & Baby"},

    # ── Weddings ───────────────────────────────────────────────
    {"id": "wedding_gift", "label": "Wedding Gift", "group": "Weddings"},
    {"id": "wedding_decor", "label": "Wedding Decor", "group": "Weddings"},
    {"id": "bridesmaid", "label": "Bridesmaid Gift", "group": "Weddings"},

    # ── Craft Supplies ─────────────────────────────────────────
    {"id": "svg_file", "label": "SVG / Cut File", "group": "Digital Goods"},
    {"id": "pattern", "label": "Sewing / Knit Pattern", "group": "Digital Goods"},
    {"id": "clipart", "label": "Clipart / Graphic", "group": "Digital Goods"},
    {"id": "font", "label": "Font", "group": "Digital Goods"},

    # ── Beauty & Bath ──────────────────────────────────────────
    {"id": "soap", "label": "Soap / Bath Bomb", "group": "Beauty & Bath"},
    {"id": "skincare", "label": "Skincare", "group": "Beauty & Bath"},
    {"id": "hair_accessory", "label": "Hair Accessory", "group": "Beauty & Bath"},

    # ── Pet ─────────────────────────────────────────────────────
    {"id": "pet_accessory", "label": "Pet Accessory", "group": "Pets"},
    {"id": "pet_portrait", "label": "Pet Portrait", "group": "Pets"},

    # ── Fallback ───────────────────────────────────────────────
    {"id": "other", "label": "Other Products", "group": "Other"},
]


def get_catalog() -> list[dict]:
    """Return the full canonical Etsy category catalog."""
    return ETSY_CATEGORY_CATALOG


def get_catalog_ids() -> set[str]:
    """Return set of all valid category ids in the catalog (for validation)."""
    return {entry["id"] for entry in ETSY_CATEGORY_CATALOG}


def merge_with_crawled(crawled_types: list[str]) -> list[dict]:
    """
    Merge the canonical catalog with categories actually present in market_listing.

    Each returned entry adds `has_data: bool` flag so the frontend can show a
    "Data available" badge for crawled categories vs "Coming soon" for the rest.

    Crawled categories not in the catalog are appended at the end (lowercase id,
    title-cased label, group="Other").
    """
    crawled_set = {t.lower() for t in crawled_types if t}
    catalog_ids = get_catalog_ids()

    result: list[dict] = []
    for entry in ETSY_CATEGORY_CATALOG:
        result.append({
            "id": entry["id"],
            "name": entry["id"],
            "label": entry["label"],
            "group": entry["group"],
            "has_data": entry["id"] in crawled_set,
        })

    # Append crawled types that aren't in the canonical catalog (excluding "other")
    for t in sorted(crawled_set - catalog_ids):
        if t == "other":
            continue
        result.append({
            "id": t,
            "name": t,
            "label": t.replace("_", " ").title(),
            "group": "Other",
            "has_data": True,
        })

    return result
