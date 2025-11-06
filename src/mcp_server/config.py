"""Configuration constants for MCP Server."""

from rdflib import Namespace


class Config:
    """Configuration constants (mirrored from bootstrap.py)."""
    FUSEKI_URL = "http://localhost:3031"
    DATASET_NAME = "ontology"
    FUSEKI_AUTH = ("admin", "admin")
    QDRANT_HOST = "localhost"
    QDRANT_PORT = 6333
    COLLECTION_NAME = "ontology_entities"
    EMBEDDING_MODEL = "ollama/nomic-embed-text"
    EMBEDDING_API_BASE = "http://localhost:11434"
    VOC = Namespace("http://bvdheiden.nl/data/#voc/")
    DATA = Namespace("http://bvdheiden.nl/data/#")
    RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

    # Computed after other attributes are defined
    FUSEKI_QUERY_URL = f"{FUSEKI_URL}/{DATASET_NAME}/query"
