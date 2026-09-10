from app.schemas.pipeline import QueryUnderstanding
from app.schemas.enums import Jurisdiction

def route(understanding: QueryUnderstanding, query: str) -> Jurisdiction:
    """Heuristically routes the query to INDIA or INTERNATIONAL."""
    query_lower = query.lower()
    
    international_keywords = ["wipo", "international", "uspto", "epo", "foreign", "abroad", "global", "export"]
    india_keywords = ["india", "indian", "ayush", "cdsco", "ipindia", "tkdl", "nba", "biodiversity board"]
    
    # Simple heuristic
    for kw in international_keywords:
        if kw in query_lower:
            # Check if it also mentions India strongly, but default to International if explicit
            return Jurisdiction.INTERNATIONAL
            
    # Default to India as it's an Ayurvedic Indian Legal bot
    return Jurisdiction.INDIA
