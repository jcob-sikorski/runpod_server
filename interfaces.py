from datetime import datetime

from pydantic import BaseModel, Field

from typing import List, Optional

class Message(BaseModel):
    user_id: Optional[str] = None, 
    status: Optional[str] = None
    facefusion_source_uris: Optional[List[str]] = None
    facefusion_target_uri: Optional[str] = None
    akool_source_uri: Optional[str] = None
    akool_target_uri: Optional[str] = None
    job_id: Optional[str] = None
    output_url: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))