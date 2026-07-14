"""
A small, hand-curated product catalog standing in for a real retailer API
(Leslie's, Amazon, etc.). This is honestly a stub — a real integration would
call an actual product search/inventory API. What matters for this project's
thesis is the PROTOCOL BOUNDARY: PoolAIQ's reasoning engine should never
construct product recommendations by hand-coding "if category == 'acid'
then say Muriatic Acid" logic inline — it should ask an external tool,
through one consistent interface, regardless of which real retailer sits
behind it later.

Products are tagged by which product_category (from reasoning_engine.py's
_category_for()) and chemistry_coupling issue they address, so the MCP tool
can do a real (if small-scale) lookup rather than a hardcoded switch
statement.
"""

from dataclasses import dataclass, field


@dataclass
class Product:
    sku: str
    name: str
    brand: str
    category: str            # matches reasoning_engine.py product_category values
    addresses: list = field(default_factory=list)  # e.g. ['ph_high','alkalinity_high']
    price_usd: float = 0.0
    size: str = ""
    retailer: str = "leslies"
    url: str = ""


CATALOG = [
    Product(
        sku="LES-MURIATIC-1GAL",
        name="Muriatic Acid",
        brand="Leslie's",
        category="acid",
        addresses=["ph_high", "alkalinity_high"],
        price_usd=8.99,
        size="1 gallon",
        url="https://www.lesliespool.com/muriatic-acid.html",
    ),
    Product(
        sku="LES-SODAASH-4LB",
        name="Soda Ash pH Increaser",
        brand="Leslie's",
        category="base",
        addresses=["ph_low"],
        price_usd=11.99,
        size="4 lb",
        url="https://www.lesliespool.com/soda-ash.html",
    ),
    Product(
        sku="LES-POWDERPLUS-25LB",
        name="Power Powder Plus Shock",
        brand="Leslie's",
        category="shock",
        addresses=["free_chlorine_low", "combined_chlorine_high"],
        price_usd=94.99,
        size="25 lb bucket",
        url="https://www.lesliespool.com/power-powder-plus.html",
    ),
    Product(
        sku="LES-CONDITIONER-4LB",
        name="Conditioner (Cyanuric Acid)",
        brand="Leslie's",
        category="stabilizer",
        addresses=["cyanuric_acid_low"],
        price_usd=13.99,
        size="4 lb",
        url="https://www.lesliespool.com/conditioner.html",
    ),
    Product(
        sku="NC-CLEARAID-67OZ",
        name="Clear Aid Enhancer",
        brand="Natural Chemistry",
        category="clarifier",
        addresses=["cloudy_water", "phosphates_high"],
        price_usd=24.99,
        size="67.6 fl oz",
        url="https://www.lesliespool.com/clear-aid.html",
    ),
    Product(
        sku="LES-NOMETAL-1QT",
        name="No Metal",
        brand="Leslie's",
        category="metal_sequestrant",
        addresses=["copper_high", "iron_high"],
        price_usd=15.99,
        size="1 quart",
        url="https://www.lesliespool.com/no-metal.html",
    ),
    Product(
        sku="LES-NOPHOS-1GAL",
        name="NoPHOS Phosphate Remover",
        brand="Leslie's",
        category="phosphate_remover",
        addresses=["phosphates_high"],
        price_usd=39.99,
        size="1 gallon",
        url="https://www.lesliespool.com/nophos.html",
    ),
    Product(
        sku="LES-POOLSALT-40LB",
        name="Pool Salt",
        brand="Leslie's",
        category="salt",
        addresses=["salt_low"],
        price_usd=9.99,
        size="40 lb bag",
        url="https://www.lesliespool.com/pool-salt.html",
    ),
    Product(
        sku="PLEATCO-PA131PAK4",
        name="Pleatco Advanced Pool Filter Cartridge (4-pack)",
        brand="Pleatco",
        category="equipment",
        addresses=["filtration_upgrade"],
        price_usd=189.99,
        size="PA131-PAK4",
        retailer="pleatco",
        url="https://www.pleatco.com",
    ),
]


def find_products_for(product_category: str = None, issue: str = None) -> list:
    """
    Core lookup used by the MCP tool. Filters by EITHER the reasoning
    engine's product_category value OR a specific issue tag — supports
    both "give me anything in the acid category" and "give me anything
    that addresses ph_high specifically" query shapes.
    """
    results = []
    for p in CATALOG:
        if product_category and p.category == product_category:
            results.append(p)
        elif issue and issue in p.addresses:
            results.append(p)
    return results


if __name__ == "__main__":
    print(f"Catalog: {len(CATALOG)} products\n")
    for p in find_products_for(product_category="acid"):
        print(f"  {p.name} ({p.brand}) — ${p.price_usd} — addresses: {p.addresses}")
