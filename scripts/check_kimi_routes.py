import httpx
from purposebench.v3.openrouter_metadata import CATALOG_URL, ZDR_ENDPOINTS_URL, parse_metadata_response, select_route

# Fetch catalog and routes
with httpx.Client(timeout=30, follow_redirects=False) as client:
    catalog_response = client.get(CATALOG_URL, headers={"accept": "application/json"})
    route_response = client.get(ZDR_ENDPOINTS_URL, headers={"accept": "application/json"})

catalog_rows = parse_metadata_response(catalog_response.content, source="catalog")
route_rows = parse_metadata_response(route_response.content, source="endpoints")

# Try to find kimi-k3 routes
model_id = "moonshotai/kimi-k3"
print(f"Finding routes for {model_id}...")
try:
    route, route_info, all_routes = select_route(model_id, catalog_rows, route_rows)
    print(f"Selected route: {route['tag']}")
    print(f"Route info: {route_info}")
except Exception as e:
    print(f"Error: {e}")
    # Try to find all available routes
    print("\nAll available routes for kimi-k3:")
    for r in route_rows:
        if "kimi" in str(r).lower():
            print(f"  {r}")
