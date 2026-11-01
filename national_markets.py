"""Approved market catalog. New markets deliberately fail closed."""
STATES = {
    'minnesota': ('MN', 'Minnesota', ('Twin Cities',)),
    'texas': ('TX', 'Texas', ('Dallas–Fort Worth', 'Houston')),
    'florida': ('FL', 'Florida', ('Tampa–St. Petersburg', 'Orlando', 'Jacksonville')),
    'north-carolina': ('NC', 'North Carolina', ('Charlotte', 'Raleigh–Durham')),
    'georgia': ('GA', 'Georgia', ('Atlanta suburbs',)),
    'wisconsin': ('WI', 'Wisconsin', ('Western Wisconsin', 'Milwaukee', 'Madison')),
}

def city_slug(name):
    return name.lower().replace('–', '-').replace(' ', '-').replace('.', '')

def enabled(slug):
    # Release policy: enabling additional states requires a reviewed code change.
    return slug == 'minnesota'
