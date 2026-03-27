from pydantic import BaseModel


class VisionRequest(BaseModel):
    image_uri: str


class CameraDeviceInfoRequest(BaseModel):
    device_name: str = ""
    user_agent: str = ""
    os: str = ""
    browser_language: str = ""
    viewport: str = ""
    screen: str = ""
    timezone: str = ""
    platform: str = ""
    cpu_cores: int = 0
    memory_gb: float = 0.0
    network_type: str = ""
    network_downlink_mbps: float = 0.0
    local_ip_hint: str = ""


class OnpremHandshakeRequest(BaseModel):
    site_id: str = ""
    agent_version: str = ""
    camera_id: str = ""
    device_name: str = ""
    os: str = ""
    platform: str = ""
    user_agent: str = ""
    browser_language: str = ""
    viewport: str = ""
    screen: str = ""
    timezone: str = ""
    cpu_cores: int = 0
    memory_gb: float = 0.0
    network_type: str = ""
    network_downlink_mbps: float = 0.0
    local_ip_hint: str = ""


class OverlayTodayCountsResponse(BaseModel):
    date: str
    ok_count: int
    ng_count: int
