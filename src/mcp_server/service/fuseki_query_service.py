"""Service for executing SPARQL queries against Apache Fuseki."""

import requests
from typing import Dict, Any
from src.mcp_server.config import Config


class FusekiQueryService:
    """Service for executing SPARQL queries against Apache Fuseki."""

    def __init__(self):
        self.query_url = Config.FUSEKI_QUERY_URL
        self.auth = Config.FUSEKI_AUTH

    def query_sparql(self, sparql_query: str) -> Dict[str, Any]:
        """Execute a SPARQL query and return the JSON result."""
        headers = {'Accept': 'application/sparql-results+json'}
        # POST request with data={"query": ...} is the standard way
        data = {'query': sparql_query}

        try:
            response = requests.post(
                self.query_url,
                data=data,
                headers=headers,
                auth=self.auth
            )
            response.raise_for_status()  # Raise HTTPError for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying Fuseki: {e}")
            print(f"Failed query:\n{sparql_query}")
            raise Exception(f"Fuseki query failed: {e}")
