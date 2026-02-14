import httpx


class ShopifyClient:
    def __init__(self, store_domain: str, storefront_token: str, admin_token: str):
        self.storefront_url = f"https://{store_domain}/api/2025-01/graphql.json"
        self.admin_url = f"https://{store_domain}/admin/api/2025-01/graphql.json"
        self._client = httpx.AsyncClient(timeout=15.0)

        self.storefront_headers = {
            "X-Shopify-Storefront-Access-Token": storefront_token,
            "Content-Type": "application/json",
        }
        self.admin_headers = {
            "X-Shopify-Access-Token": admin_token,
            "Content-Type": "application/json",
        }

    # -- Low-level helpers --

    async def _storefront_query(self, query: str, variables: dict | None = None) -> dict:
        """Send a GraphQL query to the Storefront API."""
        response = await self._client.post(
            self.storefront_url,
            headers=self.storefront_headers,
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise Exception(f"Shopify Storefront API error: {data['errors']}")
        return data["data"]

    # -- Product methods --

    async def search_products(self, query: str, limit: int = 5) -> list[dict]:
        """Search the store catalog by keyword. Returns simplified product list."""
        gql = """
        query SearchProducts($query: String!, $first: Int!) {
            products(query: $query, first: $first, sortKey: RELEVANCE) {
                edges {
                    node {
                        id
                        title
                        description
                        handle
                        productType
                        vendor
                        priceRange {
                            minVariantPrice { amount currencyCode }
                            maxVariantPrice { amount currencyCode }
                        }
                        images(first: 1) {
                            edges { node { url altText } }
                        }
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    availableForSale
                                    price { amount currencyCode }
                                    selectedOptions { name value }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        data = await self._storefront_query(gql, {"query": query, "first": limit})
        return [self._parse_product(edge["node"]) for edge in data["products"]["edges"]]

    async def get_product(self, product_id: str) -> dict | None:
        """Get full details for a single product by its Shopify GID."""
        gql = """
        query GetProduct($id: ID!) {
            product(id: $id) {
                id
                title
                description
                handle
                productType
                vendor
                priceRange {
                    minVariantPrice { amount currencyCode }
                    maxVariantPrice { amount currencyCode }
                }
                images(first: 5) {
                    edges { node { url altText } }
                }
                variants(first: 20) {
                    edges {
                        node {
                            id
                            title
                            availableForSale
                            price { amount currencyCode }
                            selectedOptions { name value }
                        }
                    }
                }
            }
        }
        """
        data = await self._storefront_query(gql, {"id": product_id})
        if data["product"] is None:
            return None
        return self._parse_product(data["product"])

    # -- Helper to clean up raw GraphQL into simple dicts --

    def _parse_product(self, node: dict) -> dict:
        """Turn a raw GraphQL product node into a clean dictionary."""
        images = [edge["node"]["url"] for edge in node.get("images", {}).get("edges", [])]
        variants = [
            {
                "id": v["node"]["id"],
                "title": v["node"]["title"],
                "available": v["node"]["availableForSale"],
                "price": v["node"]["price"]["amount"],
                "currency": v["node"]["price"]["currencyCode"],
                "options": {
                    opt["name"]: opt["value"]
                    for opt in v["node"].get("selectedOptions", [])
                },
            }
            for v in node.get("variants", {}).get("edges", [])
        ]
        return {
            "id": node["id"],
            "title": node["title"],
            "description": node.get("description", ""),
            "handle": node.get("handle", ""),
            "product_type": node.get("productType", ""),
            "vendor": node.get("vendor", ""),
            "price": node["priceRange"]["minVariantPrice"]["amount"],
            "currency": node["priceRange"]["minVariantPrice"]["currencyCode"],
            "image_url": images[0] if images else None,
            "images": images,
            "variants": variants,
        }

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
