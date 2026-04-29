"""服務層封裝（對齊 Credolab 架構）。"""

__all__ = ["DataflowService", "GoogleMapsAPIService", "GeocodingFlowService"]


def __getattr__(name):
    if name == "DataflowService":
        from .dataflow_service import DataflowService
        return DataflowService
    if name == "GoogleMapsAPIService":
        from .google_maps_api_service import GoogleMapsAPIService
        return GoogleMapsAPIService
    if name == "GeocodingFlowService":
        from .geocoding_flow_service import GeocodingFlowService
        return GeocodingFlowService
    raise AttributeError(f"module 'services' has no attribute {name}")