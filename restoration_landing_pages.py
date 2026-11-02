LANDING_PAGES = {
    "water-damage": {
        "title": "Water Damage Restoration",
        "service": "Flood Damage Restoration",
        "headline": "Water Damage Restoration in the Twin Cities",
        "description": "Find help for flooding, leaks, water extraction, and structural drying."
    },
    "storm-hail-damage": {
        "title": "Storm and Hail Damage Repair",
        "service": "Storm Damage Restoration",
        "headline": "Storm and Hail Damage Repair in Minnesota",
        "description": "Request help with wind, hail, and storm-related property damage."
    },
    "roof-repair": {
        "title": "Roof Repair and Replacement",
        "service": "Roof Leak Repair",
        "headline": "Roof Repair and Replacement in the Twin Cities",
        "description": "Find roofing contractors for leaks, missing shingles, and roof damage."
    },
    "basement-flooding": {
        "title": "Basement Flood Cleanup",
        "service": "Basement Flood Cleanup",
        "headline": "Basement Flood Cleanup in the Twin Cities",
        "description": "Request assistance for flooded basements and sump pump failures."
    },
    "mold-remediation": {
        "title": "Mold Remediation",
        "service": "Mold Remediation",
        "headline": "Mold Remediation in the Twin Cities",
        "description": "Connect with contractors for mold assessment and remediation."
    },
    "fire-smoke-damage": {
        "title": "Fire and Smoke Restoration",
        "service": "Fire Damage Restoration",
        "headline": "Fire and Smoke Damage Restoration",
        "description": "Find help for fire damage, smoke residue, and property restoration."
    },
    "sewer-backup": {
        "title": "Sewer Backup Cleanup",
        "service": "Sewer Backup Cleanup",
        "headline": "Sewer Backup Cleanup in the Twin Cities",
        "description": "Request professional cleanup after a sewer backup."
    },
    "frozen-pipes": {
        "title": "Frozen and Burst Pipe Damage",
        "service": "Frozen Pipe Damage",
        "headline": "Frozen and Burst Pipe Damage Restoration",
        "description": "Find help with winter pipe damage and resulting water cleanup."
    },
    "siding-repair": {
        "title": "Siding and Exterior Repairs",
        "service": "Siding Repair",
        "headline": "Siding and Exterior Storm Damage Repair",
        "description": "Request estimates for damaged siding and exterior repairs."
    },
    "emergency-tarping": {
        "title": "Emergency Roof Tarping",
        "service": "Emergency Tarping",
        "headline": "Emergency Roof Tarping and Storm Protection",
        "description": "Find assistance protecting storm-damaged property."
    }
}

restoration_landing_pages = LANDING_PAGES

# Describes possible contractor work, not promises about marketplace availability.
SERVICE_DETAILS = {
    "water-damage": (
        "Water damage can follow appliance leaks, plumbing failures or heavy rain. A contractor may assess affected materials, remove standing water and plan drying before repairs begin.",
        ["Water extraction and moisture assessment", "Drying plans for affected walls, floors and structural materials", "Repair planning after the source of water is addressed"],
        "Describe the water source if known, the rooms affected and when you first noticed the damage."),
    "storm-hail-damage": (
        "Minnesota wind and hail can affect roofing, siding and other exterior materials. Request an assessment of visible damage and a written repair scope based on the property's condition.",
        ["Assessment of wind and hail damage", "Roofing, siding and exterior repair planning", "Documentation of affected areas for your own records"],
        "Include the storm date if known and describe visible damage from a safe location. Coverage decisions belong to your insurer."),
    "roof-repair": (
        "Roofing repair starts with identifying the source of a leak or damaged roofing materials. A contractor can discuss localized repairs and whether broader replacement should be evaluated.",
        ["Leak investigation and repair planning", "Assessment of missing shingles, flashing and storm damage", "Written repair or replacement scope for the affected roof"],
        "Describe ceiling stains, known leaks or missing shingles. Include the approximate roof age if you know it; a site assessment determines the appropriate work."),
    "basement-flooding": (
        "Heavy rain, seepage and sump pump failures can leave basements wet. Cleanup and repair planning depend on where the water came from, what materials were affected and whether the source has been addressed.",
        ["Assessment of water entry and affected rooms", "Water removal and drying plans", "Cleanup and repair scope for damaged basement materials"],
        "Tell us whether water is still entering, which rooms are affected and whether a sump pump or drain problem is known."),
    "mold-remediation": (
        "Mold concerns often involve an underlying moisture problem. A qualified contractor may evaluate affected materials, discuss containment and removal, and explain how the moisture source will be addressed.",
        ["Assessment of visible growth and moisture concerns", "Containment and removal planning where appropriate", "Repair recommendations tied to the moisture source"],
        "Describe visible growth, odors, known leaks and the rooms involved. A request or photograph alone cannot establish the extent of a mold problem."),
    "fire-smoke-damage": (
        "After a property is cleared for entry by the appropriate authorities, restoration planning may include fire-damaged materials, smoke residue, odors and water used during firefighting.",
        ["Assessment of fire, smoke and related water damage", "Cleaning and affected-material repair planning", "Coordination of a written restoration scope"],
        "Describe the rooms affected and whether authorities have cleared the property for entry. This request service does not dispatch emergency responders."),
    "sewer-backup": (
        "A sewer backup can affect flooring, walls and belongings. Professional cleanup planning depends on the source, affected materials and the extent of contamination; plumbing repairs may require separate work.",
        ["Assessment of affected areas and cleanup needs", "Removal and cleaning scope for affected materials", "Drying and restoration planning after the backup is addressed"],
        "Tell us where the backup appeared, whether it is ongoing and which areas of the property were affected."),
    "frozen-pipes": (
        "Minnesota winter conditions can lead to frozen or burst pipes and water damage. Plumbing work to address the source and restoration of wet building materials may involve different contractors.",
        ["Assessment of water-damaged rooms and materials", "Water extraction and structural drying plans", "Repair planning after the plumbing issue is addressed"],
        "Describe the suspected pipe location, when the leak was discovered and whether water is still entering the affected area."),
    "siding-repair": (
        "Wind, hail and moisture can damage siding and exterior trim. An assessment can help determine the affected area, material options and the scope of repairs needed around openings and adjoining surfaces.",
        ["Assessment of cracked, loose or missing siding", "Exterior trim and moisture-related repair planning", "Material and repair-scope discussion"],
        "Describe the damaged sides of the property, the siding material if known and any related interior water damage."),
    "emergency-tarping": (
        "Temporary roof protection may be part of a contractor's response to storm damage. Whether tarping is suitable depends on weather, safe access and roof condition; permanent repairs require a separate assessment.",
        ["Assessment of temporary roof protection options", "Planning for exposed areas and related water entry", "Follow-up scope for permanent roofing repairs"],
        "Explain where the roof is exposed and whether water is entering. Availability and arrival times must be confirmed directly with a contractor."),
}

for _slug, (_overview, _scope, _request_tip) in SERVICE_DETAILS.items():
    LANDING_PAGES[_slug].update(overview=_overview, scope=_scope, request_tip=_request_tip)
