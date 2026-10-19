"""User-requested price-list templates; never inserted automatically."""

from datetime import date

from alloq_commons.models.price_list import PriceList, PricePosition

TEMPLATE_OPTIONS = [
    {"value": "germany", "label": "Germany"},
    {"value": "2025", "label": "Tagessätze 2025"},
    {"value": "2026", "label": "Tagessätze 2026"},
]
GERMANY = [
    ("Requirements", "88.52"),
    ("Senior Data Scientist", "104.80"),
    ("Data Scientist", "88.52"),
    ("PL", "88.52"),
    ("Senior Architekt", "104.80"),
    ("DEV / Data Engineer", "77.57"),
    ("Student", "56.45"),
    ("Mischsatz", "91.90"),
    ("Extern", "125"),
]
RATES_2025 = [
    ("8030", "ML-/Data Engineer", "710", "1280"),
    ("8030", "Data Scientist", "710", "1280"),
    ("8040", "Senior ML-/Data Engineer", "840", "1450"),
    ("8040", "(Senior) Data Scientist", "840", "1450"),
    ("8040", "Project Manager", "840", "1350"),
    ("8050", "Senior Project Manager", "920", "1450"),
    ("", "Extern?", "1000", "1600"),
]
RATES_2026 = [
    ("Junior", "59.44", "1280"),
    ("Advanced", "72.99", "1280"),
    ("Senior", "83.91", "1450"),
    ("Expert", "98.76", "1450"),
]


def price_list_template(key: str) -> PriceList:
    if key == "germany":
        return PriceList(
            name="Germany",
            cost_basis="hour",
            positions=[
                PricePosition(label=label, cost=cost) for label, cost in GERMANY
            ],
        )
    if key == "2025":
        return PriceList(
            name="Tagessätze 2025",
            as_of=date(2025, 9, 1),
            positions=[
                PricePosition(la=la, label=label, cost=cost, sales_price=sales)
                for la, label, cost, sales in RATES_2025
            ],
        )
    if key == "2026":
        return PriceList(
            name="Tagessätze 2026",
            as_of=date(2026, 1, 1),
            cost_basis="hour",
            positions=[
                PricePosition(la=la, cost=cost, sales_price=sales)
                for la, cost, sales in RATES_2026
            ],
        )
    raise ValueError("Unknown template")
