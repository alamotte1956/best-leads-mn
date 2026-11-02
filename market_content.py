"""Editorial landing-page copy. No contractor availability or response-time claims."""
STATE_COPY = {
    'minnesota': ('Restoration support, close to home.',
        'From frozen-pipe damage to basement flooding, Minnesota property owners need a clear next step. Describe the damage and the location so a contractor can assess the work.'),
    'texas': ('A clearer path after property damage.',
        'Water leaks, smoke damage and severe weather can leave Texas homes and businesses with several repairs to coordinate. Start with the type of damage, your ZIP code and the help you need.'),
    'florida': ('Help your property recover with confidence.',
        'Water intrusion, storm damage and moisture concerns call for a careful restoration plan. Tell a contractor what happened, which areas are affected and whether the property is safe to enter.'),
    'north-carolina': ('Local restoration starts with a clear request.',
        'Whether the problem is a plumbing leak, smoke damage or a storm-related repair, a useful request helps a restoration professional understand your North Carolina property.'),
    'georgia': ('Take the next step toward restoring your property.',
        'Atlanta-area property damage can involve cleanup, drying and repair. Describe the affected rooms, the source of damage if known and the restoration service you are looking for.'),
    'indiana': ('A clear next step for Indiana properties.',
        'From basement water intrusion to fire cleanup and storm-related roof damage, Indiana property owners need a plan based on the location and scope of work. This future market is not open for requests.'),
    'wisconsin': ('Restore your space, one clear step at a time.',
        'Wisconsin property owners may need help with frozen pipes, water intrusion, fire cleanup or storm repairs. Share the location and type of damage so the scope can be reviewed.'),
}

SERVICE_GROUPS = (
    ('Water damage', 'Leaks, flooding, water extraction and structural drying.'),
    ('Fire and smoke', 'Cleanup, soot and odor removal, and repair planning.'),
    ('Mold and moisture', 'Inspection, remediation and moisture-related repair requests.'),
    ('Storm and exterior damage', 'Roof leaks, wind damage, temporary protection and exterior repairs.'),
)


def landing_content(state, label, city=False):
    headline, introduction = STATE_COPY[state]
    return {
        'headline': headline,
        'introduction': introduction,
        'description': f'Restoration service information for {label}: water, fire, smoke, mold and storm damage. Check current availability and understand the next steps.',
        'location_note': (f'For properties in {label}, the exact property ZIP code and the requested service determine coverage. A nearby city name alone does not establish contractor availability.'
                          if city else 'Service areas are checked by property ZIP code and restoration service. Statewide information does not mean every ZIP code is covered.'),
        'faqs': (
            (f'How do I request restoration help in {label}?', 'When requests are available, describe the damage, choose the service and enter the property ZIP code. Contractor availability depends on coverage and approval status.'),
            ('Does submitting a request guarantee a contractor or an estimate?', 'No. A request does not guarantee a match, response time, price or completed work. Confirm the scope, credentials, insurance and written estimate directly with the contractor.'),
            ('What should I do if there is immediate danger?', 'Move to a safe location and contact emergency services for immediate danger. Do not enter an unsafe structure or approach standing water near electrical equipment.'),
        ),
    }
