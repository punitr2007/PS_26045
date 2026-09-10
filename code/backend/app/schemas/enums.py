from enum import Enum

class Jurisdiction(Enum):
    INDIA = "india"
    INTERNATIONAL = "international"


class ProductCategory(Enum):
    PROPRIETARY = "proprietary"
    CLASSICAL = "classical"
    COSMETIC = "cosmetic"
    NON_CLASSICAL = "non-classical"
    PHYTOPHARMACEUTICAL = "phytopharmaceutical"
    AYURVEDA_AAHAR = "ayurveda-aahar"
    UNCLASSIFIED = "unclassified"


class LegalArea(Enum):
    PATENT = "patent"
    ABS = "abs"
    TK_PRIOR_ART = "tk_prior_art"
    DRUG_REGULATION = "drug_regulation"
    TRADEMARK = "trademark"
    GI = "gi"