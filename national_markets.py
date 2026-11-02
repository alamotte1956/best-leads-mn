"""Approved market catalog. New markets deliberately fail closed."""
STATES = {
    'minnesota': ('MN', 'Minnesota', ('Twin Cities',)),
    'texas': ('TX', 'Texas', ('Dallas–Fort Worth', 'Houston')),
    'florida': ('FL', 'Florida', ('Tampa–St. Petersburg', 'Orlando', 'Jacksonville')),
    'north-carolina': ('NC', 'North Carolina', ('Charlotte', 'Raleigh–Durham')),
    'georgia': ('GA', 'Georgia', ('Atlanta suburbs',)),
    'wisconsin': ('WI', 'Wisconsin', ('Western Wisconsin', 'Milwaukee', 'Madison')),
    'indiana': ('IN', 'Indiana', ('Indianapolis', 'Fort Wayne', 'Northwest Indiana')),
}

def city_slug(name):
    return name.lower().replace('–', '-').replace(' ', '-').replace('.', '')

def enabled(slug):
    # Release policy: enabling additional states requires a reviewed code change.
    return slug == 'minnesota'


def slug_for_code(code):
    return next((slug for slug, row in STATES.items() if row[0] == code), None)


def code_enabled(code):
    slug = slug_for_code(code)
    return bool(slug and enabled(slug))


def usa_hostname(host):
    # Never use suffix matching or forwarded headers to select a brand.
    return host.split(':', 1)[0].lower() in (
        'restorationcontractorsusa.com', 'www.restorationcontractorsusa.com')
