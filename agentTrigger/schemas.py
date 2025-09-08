from pydantic import BaseModel
from typing import Any, Dict, Optional

class Essentials(BaseModel):
    resourceName: Optional[str] = None
    alertRule: Optional[str] = ""
    monitorCondition: Optional[str] = ""
    timeGenerated: Optional[str] = ""

class Condition(BaseModel):
    metricName: Optional[str] = None

class AlertContext(BaseModel):
    condition: Optional[Condition] = Condition()
    value: Optional[Any] = None
    context: Optional[Dict[str, Any]] = {}

class Data(BaseModel):
    essentials: Optional[Essentials] = Essentials()
    alertContext: Optional[AlertContext] = AlertContext()

class Alert(BaseModel):
    data: Optional[Data] = Data()