"""Public restoration information pages. No database or matching side effects."""
from flask import Blueprint, render_template
from urllib.parse import urlencode

restoration_landing_pages = Blueprint('restoration_landing_pages', __name__)
PAGES = {
    'water-damage-restoration': {
        'name': 'Water damage', 'service': 'Flood Damage Restoration', 'theme': 'water',
        'title': 'Water Damage Restoration in the Twin Cities | Restoration Contractors MN',
        'description': 'Request a connection with a water damage restoration contractor in Minneapolis, St. Paul and the Twin Cities. Describe your cleanup and drying needs.',
        'eyebrow': 'WATER DAMAGE RESTORATION · TWIN CITIES',
        'headline': 'Water where it', 'highlight': 'doesn’t belong?',
        'intro': 'A wet basement. A burst pipe. A leak that became a bigger problem. Tell us what happened and request a connection with a contractor serving your area.',
        'cta': 'Find water damage help',
        'panel_title': 'Start with what you can see.',
        'panel_intro': 'You don’t need to know the full extent of the damage to describe your project.',
        'symptoms': ['Standing water or a flooded basement', 'Wet walls, ceilings or flooring', 'Damage after a pipe or appliance leak'],
        'scope_heading': 'Cleanup is only part of the project.',
        'scope_intro': 'Describe both the visible water and the areas it affected. Your contractor can discuss the assessment and work appropriate for your property.',
        'scopes': [('Water removal', 'Extraction and cleanup needs after flooding, leaks or an overflow.'), ('Drying and moisture assessment', 'Assessment of affected materials and discussion of drying equipment and follow-up.'), ('Repairs after the damage', 'Damaged walls, floors or finishes that may need repair after the source is addressed.')],
        'details': 'Include the source if known, when you noticed it, whether water is still entering, and which rooms or materials are affected.',
        'faqs': [('Can I request help for a basement flood?', 'Yes. Describe the flooding and select the most appropriate service on the request form. Availability depends on your ZIP code and participating contractors.'), ('Does submitting a request mean a contractor is dispatched?', 'No. A submission records your request. A match, response time, visit and price are not guaranteed.'), ('Can I request repairs as well as cleanup?', 'Yes. Include the repairs you think may be needed. Discuss the final scope and any separate trades directly with the contractor.')],
    },
    'fire-smoke-damage-restoration': {
        'name': 'Fire & smoke damage', 'service': 'Fire Damage Restoration', 'theme': 'fire',
        'title': 'Fire & Smoke Damage Restoration in the Twin Cities | Restoration Contractors MN',
        'description': 'Find your next step after fire or smoke damage. Request a connection with a Twin Cities contractor for cleanup, contents and property repair needs.',
        'eyebrow': 'FIRE & SMOKE RESTORATION · TWIN CITIES',
        'headline': 'After the fire,', 'highlight': 'a way forward.',
        'intro': 'Soot, smoke odors and damaged rooms can leave you unsure where to begin. Describe the property and the work you need so we can review your contractor request.',
        'cta': 'Find fire & smoke help',
        'panel_title': 'Make the next step clearer.',
        'panel_intro': 'Tell us about the damage once the immediate emergency has been handled.',
        'symptoms': ['Soot or smoke damage in living spaces', 'Contents affected by smoke or fire', 'Cleanup and repairs after a fire'],
        'scope_heading': 'Look beyond the burned area.',
        'scope_intro': 'A restoration project may involve several kinds of work. Share what you know, then ask a contractor to explain the proposed assessment and scope.',
        'scopes': [('Smoke and soot cleanup', 'Cleaning needs for affected surfaces and rooms.'), ('Contents and odor concerns', 'Questions about affected belongings, cleaning options and persistent odors.'), ('Property restoration', 'Discussion of damaged finishes, structural repairs and the trades needed for the work.')],
        'details': 'Include the rooms affected, the approximate date of the fire, and whether you need cleanup, contents help, repairs or all three.',
        'faqs': [('Can I request help with smoke damage only?', 'Yes. Explain whether you have visible soot, an odor concern or damage to belongings. You can select Smoke Damage Cleanup on the request form.'), ('Will you handle my insurance claim?', 'We provide contractor connections, not insurance claim decisions. Ask the contractor about documentation, estimates and any help they offer. Coverage is determined by your insurer and policy.'), ('Who performs the restoration work?', 'Independent contractors perform the work. Review their qualifications, estimate, agreement and insurance before hiring.')],
    },
    'mold-remediation': {
        'name': 'Mold remediation', 'service': 'Mold Remediation', 'theme': 'mold',
        'title': 'Mold Remediation Contractors in the Twin Cities | Restoration Contractors MN',
        'description': 'Describe a mold or moisture concern and request a connection with a Twin Cities contractor. Explore inspection, remediation and moisture-related project needs.',
        'eyebrow': 'MOLD & MOISTURE · TWIN CITIES',
        'headline': 'A mold concern?', 'highlight': 'Start with clarity.',
        'intro': 'Visible growth, a recurring moisture problem or an affected attic or basement: explain what you’re seeing and request a contractor connection for your property.',
        'cta': 'Find mold remediation help',
        'panel_title': 'Describe the space, not a diagnosis.',
        'panel_intro': 'Share what you’ve noticed. A website request cannot identify mold or determine its extent.',
        'symptoms': ['Visible growth on building materials', 'A damp attic, basement or crawl space', 'A recurring moisture or musty-odor concern'],
        'scope_heading': 'Ask about the moisture, too.',
        'scope_intro': 'Use the first conversation to understand what assessment is proposed, what remediation may involve and how the underlying moisture concern will be addressed.',
        'scopes': [('Inspection questions', 'Discuss the affected area and whether an on-site assessment or testing is appropriate.'), ('Remediation planning', 'Ask for a written scope covering affected materials and the proposed work.'), ('Moisture-related repairs', 'Discuss leaks, ventilation or other building issues that may need a separate trade.')],
        'details': 'Include where the concern is, the approximate area affected, any known leak or moisture history, and whether it has happened before.',
        'faqs': [('Can you identify mold from my request?', 'No. This website does not identify mold, diagnose health concerns or determine remediation needs. Discuss the property with a qualified professional.'), ('Do I need testing before requesting help?', 'You can submit a request without test results. Ask the contractor what assessment is appropriate and why, including any separate testing costs.'), ('Can I request help for an attic or basement?', 'Yes. Select the relevant service and describe the location, moisture history and visible conditions. Matching depends on service and geographic availability.')],
    },
    'storm-damage-restoration': {
        'name': 'Storm damage', 'service': 'Storm Damage Restoration', 'theme': 'storm',
        'title': 'Storm Damage Repair in the Twin Cities | Restoration Contractors MN',
        'description': 'Request a Twin Cities contractor connection for storm, wind or hail damage. Describe roof, siding, water intrusion and exterior repair needs.',
        'eyebrow': 'STORM DAMAGE RESTORATION · TWIN CITIES',
        'headline': 'The storm passed.', 'highlight': 'What needs repair?',
        'intro': 'Wind, hail and fallen branches can leave more than one part of your home affected. Tell us about the damage and request a contractor serving your Minnesota area.',
        'cta': 'Find storm damage help',
        'panel_title': 'One project. The details that matter.',
        'panel_intro': 'Describe the areas affected so your request reflects the work you need.',
        'symptoms': ['Roof, siding or gutter damage', 'Water entering after wind or hail', 'Exterior damage after fallen branches'],
        'scope_heading': 'Connect the outside damage to the inside.',
        'scope_intro': 'Storm projects can involve exterior repairs and interior restoration. Include both in your request so you can discuss a coordinated scope with a contractor.',
        'scopes': [('Roof and exterior concerns', 'Damaged shingles, siding, gutters or other exterior materials.'), ('Water intrusion and cleanup', 'Leaks and interior damage noticed during or after the storm.'), ('Repair planning', 'Discuss assessment, estimates, material options and the trades your project needs.')],
        'details': 'Include when the storm occurred, the parts of the property affected, any active leaks, and whether you need an inspection, cleanup or repairs.',
        'faqs': [('Can I request a roof inspection after hail?', 'Yes. Select Roof Inspection or Hail Damage Repair and describe your concern. An inspection and estimate are arranged directly with a contractor.'), ('Are emergency tarping services guaranteed?', 'No. You may request Emergency Tarping, but availability and response time depend on the contractor. This website is not an emergency dispatch service.'), ('Can one request include interior and exterior damage?', 'Yes. Explain both in the project description. The contractor can discuss which work they provide and whether additional trades are needed.')],
    },
}

def service_page(slug):
    from flask import abort
    page = PAGES.get(slug)
    if page is None:
        abort(404)
    request_url = '/?' + urlencode({'service': page['service']}) + '#homeowner-request-form'
    return render_template('restoration_landing.html', page=page, pages=PAGES,
                           slug=slug, request_url=request_url,
                           canonical='https://www.restorationcontractorsmn.com/' + slug)


for _slug in PAGES:
    restoration_landing_pages.add_url_rule(
        "/" + _slug, endpoint=_slug.replace("-", "_"),
        view_func=service_page, defaults={"slug": _slug}, methods=["GET"],
    )
