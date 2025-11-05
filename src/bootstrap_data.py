"""Bootstrap script for initializing graph and vector databases with ontology and data."""

import requests
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.namespace import XSD
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from litellm import embedding
from typing import List, Dict, Tuple


class Config:
    """Configuration constants."""
    FUSEKI_URL = "http://localhost:3030"
    DATASET_NAME = "ontology"
    FUSEKI_AUTH = ("admin", "admin")
    QDRANT_HOST = "localhost"
    QDRANT_PORT = 6333
    COLLECTION_NAME = "ontology_entities"
    EMBEDDING_MODEL = "ollama/nomic-embed-text"
    EMBEDDING_API_BASE = "http://localhost:11434"
    VOC = Namespace("http://bvdheiden.nl/data/#voc/")
    DATA = Namespace("http://bvdheiden.nl/data/#")


class EmbeddingService:
    """Service for generating embeddings."""

    @staticmethod
    def generate(text: str) -> List[float]:
        """Generate embedding vector for text."""
        response = embedding(
            model=Config.EMBEDDING_MODEL,
            input=[text],
            api_base=Config.EMBEDDING_API_BASE
        )
        return response.data[0]['embedding']


class FusekiService:
    """Service for interacting with Apache Fuseki graph database."""

    def __init__(self):
        self.base_url = Config.FUSEKI_URL
        self.dataset_name = Config.DATASET_NAME
        self.auth = Config.FUSEKI_AUTH

    def delete_dataset(self) -> None:
        """Delete dataset if it exists."""
        delete_url = f"{self.base_url}/$/datasets/{self.dataset_name}"
        try:
            response = requests.delete(delete_url, auth=self.auth)
            if response.status_code == 200:
                print(f"Dataset '{self.dataset_name}' deleted")
            elif response.status_code == 404:
                print(f"Dataset '{self.dataset_name}' does not exist")
            else:
                print(f"Delete response: {response.status_code}")
        except Exception as e:
            print(f"Error deleting dataset: {e}")

    def create_dataset(self) -> None:
        """Create dataset if it doesn't exist."""
        create_url = f"{self.base_url}/$/datasets"
        payload = {"dbName": self.dataset_name, "dbType": "tdb2"}

        try:
            response = requests.post(create_url, data=payload, auth=self.auth)
            if response.status_code == 200:
                print(f"Dataset '{self.dataset_name}' created")
            elif response.status_code == 409:
                print(f"Dataset '{self.dataset_name}' already exists")
            else:
                print(f"Unexpected response: {response.status_code}")
        except Exception as e:
            print(f"Error creating dataset: {e}")

    def upload_graph(self, graph: Graph) -> None:
        """Upload RDF graph to Fuseki."""
        upload_url = f"{self.base_url}/{self.dataset_name}/data"
        headers = {'Content-Type': 'text/turtle'}
        ttl_data = graph.serialize(format='turtle')

        try:
            response = requests.post(upload_url, data=ttl_data, headers=headers, auth=self.auth)
            if response.status_code in [200, 201, 204]:
                print("Graph uploaded to Fuseki")
            else:
                print(f"Upload error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error uploading graph: {e}")


class QdrantService:
    """Service for interacting with Qdrant vector database."""

    def __init__(self):
        self.client = QdrantClient(host=Config.QDRANT_HOST, port=Config.QDRANT_PORT)
        self.collection_name = Config.COLLECTION_NAME

    def delete_collection(self) -> None:
        """Delete collection if it exists."""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            print(f"Collection '{self.collection_name}' deleted")
        except Exception as e:
            print(f"Collection does not exist or error: {e}")

    def create_collection(self, vector_size: int) -> None:
        """Create collection if it doesn't exist."""
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            print(f"Collection '{self.collection_name}' created")
        except Exception as e:
            print(f"Collection may already exist: {e}")

    def upsert_points(self, points: List[PointStruct]) -> None:
        """Upload points to Qdrant."""
        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
            print(f"Uploaded {len(points)} points to Qdrant")
        except Exception as e:
            print(f"Error uploading to Qdrant: {e}")


class OntologyBuilder:
    """Builder for creating RDF ontology."""

    def __init__(self):
        self.graph = Graph()
        self._bind_namespaces()

    def _bind_namespaces(self) -> None:
        """Bind namespaces to graph."""
        self.graph.bind("voc", Config.VOC)
        self.graph.bind("data", Config.DATA)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)

    def define_classes(self) -> 'OntologyBuilder':
        """Define ontology classes."""
        self.graph.add((Config.VOC.Resource, RDF.type, OWL.Class))
        self.graph.add((Config.VOC.Resource, RDFS.label, Literal("Resource")))
        self.graph.add((Config.VOC.Team, RDF.type, OWL.Class))
        self.graph.add((Config.VOC.Team, RDFS.label, Literal("Team")))
        return self

    def define_properties(self) -> 'OntologyBuilder':
        """Define ontology properties."""
        self.graph.add((Config.VOC.containedIn, RDF.type, OWL.ObjectProperty))
        self.graph.add((Config.VOC.containedIn, RDFS.label, Literal("contained in")))
        self.graph.add((Config.VOC.containedIn, RDFS.domain, Config.VOC.Resource))
        self.graph.add((Config.VOC.containedIn, RDFS.range, Config.VOC.Resource))

        self.graph.add((Config.VOC.ownedBy, RDF.type, OWL.ObjectProperty))
        self.graph.add((Config.VOC.ownedBy, RDFS.label, Literal("owned by")))
        self.graph.add((Config.VOC.ownedBy, RDFS.domain, Config.VOC.Resource))
        self.graph.add((Config.VOC.ownedBy, RDFS.range, Config.VOC.Team))
        return self

    def build(self) -> Graph:
        """Return the built graph."""
        return self.graph


class DataPopulator:
    """Populator for adding instances to the ontology."""

    RESOURCES = [
        "user-authentication-service", "customer-profile-service",
        "product-catalog-service", "product-search-service",
        "product-recommendation-service", "pricing-and-promotions-service",
        "shopping-cart-service", "checkout-service",
        "order-management-service", "payment-gateway-service",
        "shipping-and-tracking-service", "inventory-management-service",
        "warehouse-fulfillment-service", "notification-service",
        "review-and-ratings-service", "analytics-and-reporting-service",
        "fraud-detection-service", "loyalty-and-rewards-service",
        "cms-content-service", "api-gateway-service"
    ]

    TEAMS = ["alpha", "beta", "charlie", "delta"]

    SERVICE_ENDPOINTS = {
        "user-authentication-service": [
            "/api/v1/auth/login", "/api/v1/auth/logout",
            "/api/v1/auth/refresh-token", "/api/v1/auth/validate-session"
        ],
        "customer-profile-service": [
            "/api/v1/profile/get", "/api/v1/profile/update", "/api/v1/profile/delete"
        ],
        "product-catalog-service": [
            "/api/v1/products/list", "/api/v1/products/{id}", "/api/v1/categories/list"
        ],
        "product-search-service": [
            "/api/v1/search/products", "/api/v1/search/filters", "/api/v1/search/suggestions"
        ],
        "product-recommendation-service": [
            "/api/v1/recommendations/personalized", "/api/v1/recommendations/trending",
            "/api/v1/recommendations/similar"
        ],
        "pricing-and-promotions-service": [
            "/api/v1/pricing/calculate", "/api/v1/promotions/active",
            "/api/v1/promotions/validate-coupon"
        ],
        "shopping-cart-service": [
            "/api/v1/cart/add", "/api/v1/cart/remove", "/api/v1/cart/get", "/api/v1/cart/clear"
        ],
        "checkout-service": [
            "/api/v1/checkout/initiate", "/api/v1/checkout/validate", "/api/v1/checkout/complete"
        ],
        "order-management-service": [
            "/api/v1/orders/create", "/api/v1/orders/{id}", "/api/v1/orders/list",
            "/api/v1/orders/cancel"
        ],
        "payment-gateway-service": [
            "/api/v1/payment/process", "/api/v1/payment/refund", "/api/v1/payment/status"
        ],
        "shipping-and-tracking-service": [
            "/api/v1/shipping/calculate-cost", "/api/v1/shipping/create-label",
            "/api/v1/tracking/status", "/api/v1/tracking/history"
        ],
        "inventory-management-service": [
            "/api/v1/inventory/check-availability", "/api/v1/inventory/reserve",
            "/api/v1/inventory/release"
        ],
        "warehouse-fulfillment-service": [
            "/api/v1/fulfillment/create-pick-list", "/api/v1/fulfillment/pack-order",
            "/api/v1/fulfillment/ship-order"
        ],
        "notification-service": [
            "/api/v1/notifications/send-email", "/api/v1/notifications/send-sms",
            "/api/v1/notifications/push"
        ],
        "review-and-ratings-service": [
            "/api/v1/reviews/create", "/api/v1/reviews/list", "/api/v1/ratings/calculate-average"
        ],
        "analytics-and-reporting-service": [
            "/api/v1/analytics/track-event", "/api/v1/reports/sales",
            "/api/v1/reports/customer-behavior", "/api/v1/reports/inventory"
        ],
        "fraud-detection-service": [
            "/api/v1/fraud/analyze-transaction", "/api/v1/fraud/check-risk-score"
        ],
        "loyalty-and-rewards-service": [
            "/api/v1/loyalty/points-balance", "/api/v1/loyalty/earn-points",
            "/api/v1/loyalty/redeem-points"
        ],
        "cms-content-service": [
            "/api/v1/content/pages/{slug}", "/api/v1/content/banners", "/api/v1/content/articles"
        ],
        "api-gateway-service": [
            "/api/v1/gateway/route", "/api/v1/gateway/health"
        ]
    }

    def __init__(self):
        self.graph = Graph()
        self._bind_namespaces()

    def _bind_namespaces(self) -> None:
        """Bind namespaces to graph."""
        self.graph.bind("voc", Config.VOC)
        self.graph.bind("data", Config.DATA)
        self.graph.bind("rdfs", RDFS)

    def add_teams(self) -> 'DataPopulator':
        """Add teams to graph."""
        for team in self.TEAMS:
            team_uri = Config.DATA[f"team-{team}"]
            self.graph.add((team_uri, RDF.type, Config.VOC.Team))
            self.graph.add((team_uri, RDFS.label, Literal(f"Team {team}")))
        print(f"Added {len(self.TEAMS)} teams")
        return self

    def add_resources(self) -> 'DataPopulator':
        """Add resources with ownership to graph."""
        for idx, resource in enumerate(self.RESOURCES):
            resource_uri = Config.DATA[resource]
            self.graph.add((resource_uri, RDF.type, Config.VOC.Resource))
            self.graph.add((resource_uri, RDFS.label, Literal(resource)))

            team_idx = idx % len(self.TEAMS)
            team_uri = Config.DATA[f"team-{self.TEAMS[team_idx]}"]
            self.graph.add((resource_uri, Config.VOC.ownedBy, team_uri))
        print(f"Added {len(self.RESOURCES)} resources")
        return self

    def add_endpoints(self) -> 'DataPopulator':
        """Add endpoints with containedIn relationships to graph."""
        endpoint_count = 0
        for service, endpoints in self.SERVICE_ENDPOINTS.items():
            service_uri = Config.DATA[service]
            for endpoint_path in endpoints:
                endpoint_id = f"{service}-{endpoint_path.replace('/', '-').replace('{', '').replace('}', '')}"
                endpoint_uri = Config.DATA[endpoint_id]
                self.graph.add((endpoint_uri, RDF.type, Config.VOC.Resource))
                self.graph.add((endpoint_uri, RDFS.label, Literal(endpoint_path)))
                self.graph.add((endpoint_uri, Config.VOC.containedIn, service_uri))
                endpoint_count += 1
        print(f"Added {endpoint_count} endpoints")
        return self

    def build(self) -> Graph:
        """Return the built graph."""
        return self.graph

    def build_vector_points(self, start_id: int = 1) -> List[PointStruct]:
        """Build vector database points."""
        points = []
        point_id = start_id

        for team in self.TEAMS:
            team_name = f"Team {team}"
            team_uri = str(Config.DATA[f"team-{team}"])
            embedding_vec = EmbeddingService.generate(team_name)
            points.append(PointStruct(
                id=point_id,
                vector=embedding_vec,
                payload={
                    "uri": team_uri,
                    "label": team_name,
                    "type": "Team",
                    "rdf_type": str(Config.VOC.Team)
                }
            ))
            point_id += 1

        for resource in self.RESOURCES:
            resource_uri = str(Config.DATA[resource])
            embedding_vec = EmbeddingService.generate(resource)
            points.append(PointStruct(
                id=point_id,
                vector=embedding_vec,
                payload={
                    "uri": resource_uri,
                    "label": resource,
                    "type": "Resource",
                    "rdf_type": str(Config.VOC.Resource)
                }
            ))
            point_id += 1

        for service, endpoints in self.SERVICE_ENDPOINTS.items():
            for endpoint_path in endpoints:
                endpoint_id = f"{service}-{endpoint_path.replace('/', '-').replace('{', '').replace('}', '')}"
                endpoint_uri = str(Config.DATA[endpoint_id])
                embedding_text = f"{service} {endpoint_path}"
                embedding_vec = EmbeddingService.generate(embedding_text)
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding_vec,
                    payload={
                        "uri": endpoint_uri,
                        "label": endpoint_path,
                        "type": "Resource",
                        "rdf_type": str(Config.VOC.Resource),
                        "service": service
                    }
                ))
                point_id += 1

        return points


class Bootstrap:
    """Main bootstrap orchestrator."""

    def __init__(self):
        self.fuseki = FusekiService()
        self.qdrant = QdrantService()

    def run(self) -> None:
        """Execute bootstrap process."""
        print("=" * 80)
        print("Starting bootstrap process")
        print("=" * 80)

        print("\n1. Clearing existing data...")
        print("  - Deleting Fuseki dataset...")
        self.fuseki.delete_dataset()
        print("  - Deleting Qdrant collection...")
        self.qdrant.delete_collection()

        print("\n2. Creating Fuseki dataset...")
        self.fuseki.create_dataset()

        print("\n3. Building and uploading ontology...")
        ontology = OntologyBuilder().define_classes().define_properties().build()
        self.fuseki.upload_graph(ontology)

        print("\n4. Building and uploading data...")
        data_populator = DataPopulator()
        data_graph = data_populator.add_teams().add_resources().add_endpoints().build()
        self.fuseki.upload_graph(data_graph)

        print("\n5. Creating Qdrant collection...")
        sample_embedding = EmbeddingService.generate("test")
        self.qdrant.create_collection(len(sample_embedding))

        print("\n6. Generating and uploading vector embeddings...")
        points = data_populator.build_vector_points()
        self.qdrant.upsert_points(points)

        print("\n" + "=" * 80)
        print("Bootstrap completed successfully")
        print("=" * 80)


def main():
    """Main entry point."""
    bootstrap = Bootstrap()
    bootstrap.run()


if __name__ == "__main__":
    main()
