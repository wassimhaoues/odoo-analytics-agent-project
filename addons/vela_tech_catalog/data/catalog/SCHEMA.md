# Catalog data format

One JSON file per top-level category (`electronics.json`, `audio.json`, ...). The loader
(`vela_tech_catalog`) reads every `*.json` here except `_meta.json` and `crosssell.json`.
Shared definitions (variant attributes, spec attributes, colors, ribbons, tags, SKU prefixes)
live in `_meta.json`.

```jsonc
{
  "category": "Electronics",                 // top-level eCommerce category
  "description": "One sentence shown on the category page.",
  "vendors": {                               // suppliers used in this file (merged across files)
    "Apple": {"lead_days": 10}
  },
  "colors": {"Sky Blue": "#9cc4e4"},         // OPTIONAL: colors not already in _meta.json
  "extra_specs": {"Keyboard Layout": "General"},   // OPTIONAL: spec attributes not in _meta.json -> spec group
  "subcategories": [
    {
      "name": "Laptops",                     // must match _meta.json sku_prefix keys
      "description": "One sentence for the subcategory page.",
      "products": [
        {
          "sku": "VT-LAP-001",               // VT-<prefix>-NNN, unique; variants get -1, -2... suffixes automatically
          "name": "Apple MacBook Air 13\" (M2)",   // real product name, brand first
          "brand": "Apple",                  // also becomes the "Brand" spec (shop filter)
          "vendor": "Apple",                 // key of "vendors"
          "list_price": 3999.0,              // TND, price of the base (cheapest) variant
          "compare_list_price": 4399.0,      // OPTIONAL: strike-through price -> product is "on sale"
          "cost": 3150.0,                    // TND purchase cost (also vendor price)
          "weight": 1.24,                    // kg
          "short": "One-line sales description (description_sale).",
          "description": "<p>Short paragraph.</p><ul><li>Point</li><li>Point</li><li>Point</li></ul>",
          "specs": {"Brand": "Apple", "Processor": "Apple M2 8-core CPU", "Screen Size": "13.6\""},
          "variants": [                      // OPTIONAL; attribute names from _meta.json variant_attributes
            {"attribute": "Color",   "values": [["Midnight", 0], ["Starlight", 0], ["Space Gray", 0]]},
            {"attribute": "Storage", "values": [["256 GB", 0], ["512 GB", 640]]}   // [value, price_extra TND]
          ],
          "stock": 8,                        // on-hand qty for EACH variant, or a dict per variant:
                                             // {"Midnight / 256 GB": 5, "Starlight / 512 GB": 0, "*": 7}
                                             // keys = values joined with " / " in variants order; "*" = default
          "reorder": {"min": 5, "max": 20},  // OPTIONAL replenishment rule (applied per variant)
          "tags": ["Apple Ecosystem", "Student Pick"],   // from _meta.json tags
          "ribbon": "Best Seller",           // OPTIONAL manual ribbon: New | Best Seller | Limited
          "alternatives": ["VT-LAP-002"],    // OPTIONAL: SKUs in the SAME file shown as alternatives
          "featured": true                   // OPTIONAL: pushed to top of the shop (website_sequence)
        }
      ]
    }
  ]
}
```

Images are NOT listed in JSON: the loader takes `static/img/products/<sku>.jpg` as the main
image and `<sku>_1.jpg`, `<sku>_2.jpg` as extra gallery images. Attribution lives in
`data/image_credits/<sku>.json` (written by `scripts/catalog/images.py pick`).

Cross-category links (accessories / optional products, e.g. laptop -> bag, mouse) live in
`crosssell.json`.

## Rules for realistic data
- Real products, real specs, plausible Tunisian retail prices in TND (≈ USD × 3.2–3.4, rounded).
- `cost` ≈ 72–85 % of price for devices, 45–65 % for accessories.
- Each subcategory: 5–8 products, a price spread (budget → premium), ≥1 product on sale,
  ≥1 out of stock (all variants 0), ≥1 low stock (1–4), ≥1 overstock (cheap item, 60+),
  `reorder` rules on roughly half the products.
- ≤ 12 variants per product; specs: 4–7 per product, always include "Brand".
- The product name MUST match what the main image shows (same model / generation).
