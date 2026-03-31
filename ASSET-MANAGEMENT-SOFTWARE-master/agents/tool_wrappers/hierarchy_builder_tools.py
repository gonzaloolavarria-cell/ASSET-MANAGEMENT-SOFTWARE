"""MCP tool wrappers for hierarchy builder — build equipment hierarchy from vendor data."""

import json
from agents.tool_wrappers.registry import tool
from tools.engines.hierarchy_builder_engine import (
    build_from_vendor,
    auto_assign_criticality as _auto_crit,
    _load_equipment_library,
)


@tool(
    "build_hierarchy_from_vendor",
    'Build a complete 6-level equipment hierarchy from the equipment library. Returns {"hierarchy_nodes": [...], "failure_modes": [...], "task_templates": [...]}. '
    'Input: JSON string with REQUIRED fields: plant_id (str, e.g. "OCP-JFC"), area_code (str, e.g. "GRD"), equipment_type (str — use get_equipment_types to list valid types, e.g. "SAG_MILL"). '
    'Optional: model, manufacturer, power_kw, weight_kg, serial_number, installation_date, sequence. '
    'Example: {"plant_id": "OCP-JFC", "area_code": "GRD", "equipment_type": "SAG_MILL", "manufacturer": "Metso", "power_kw": 8000}',
    {
        "type": "object",
        "properties": {"input_json": {"type": "string"}},
        "required": ["input_json"],
    },
)
def build_hierarchy_from_vendor_tool(input_json: str) -> str:
    data = json.loads(input_json)
    result = build_from_vendor(
        plant_id=data["plant_id"],
        area_code=data["area_code"],
        equipment_type=data["equipment_type"],
        model=data.get("model", ""),
        manufacturer=data.get("manufacturer", ""),
        power_kw=data.get("power_kw", 0),
        weight_kg=data.get("weight_kg", 0),
        serial_number=data.get("serial_number", ""),
        installation_date=data.get("installation_date", ""),
        sequence=data.get("sequence", 1),
    )
    return json.dumps(result, default=str)


@tool(
    "get_equipment_types",
    "List all available equipment types from the equipment library with default criticality and sub-assembly count.",
    {"type": "object", "properties": {}},
)
def get_equipment_types_tool() -> str:
    library = _load_equipment_library()
    types = []
    for et in library.get("equipment_types", []):
        types.append({
            "equipment_type": et.get("equipment_type_id", et.get("name", "")),
            "default_criticality": et.get("default_criticality", "A"),
            "sub_assemblies": len(et.get("sub_assemblies", [])),
            "manufacturers": et.get("manufacturers", []),
        })
    return json.dumps({"total_types": len(types), "equipment_types": types})


@tool(
    "auto_assign_criticality",
    "Auto-assign criticality class based on equipment type and power rating. Input: JSON with equipment_type and power_kw.",
    {
        "type": "object",
        "properties": {
            "equipment_type": {"type": "string"},
            "power_kw": {"type": "number"},
        },
        "required": ["equipment_type"],
    },
)
def auto_assign_criticality_tool(equipment_type: str, power_kw: float = 0) -> str:
    crit = _auto_crit(equipment_type, power_kw)
    return json.dumps({"equipment_type": equipment_type, "power_kw": power_kw, "criticality": crit})
