import json
import re
from shapely.geometry import Polygon, mapping
from stelar.client import Client
import pycountry
from difflib import get_close_matches

##############################################################################
# Applicable to harvest EO data assets available from German Aerospace Center (DLR):
# https://geoservice.dlr.de/data-assets/
##############################################################################

def get_timespan(temporalCoverage):
    """ Extract the start and end of the given temporal coverage.
    Args:
        temporalCoverage (str): Temporal coverage string like 'YYYY-MM-DD/YYYY-MM-DD' or 'YYYY-MM-DD/..'.
    Returns:
        Tuple[str|None, str|None]: start and end dates (None if missing).
    """
    temporal_start = None
    temporal_end = None
    if temporalCoverage:
        parts = temporalCoverage.split('/')
        if parts[0] != '..':
            temporal_start = parts[0]
        if len(parts) > 1 and parts[1] != '..':
            temporal_end = parts[1]
    return temporal_start, temporal_end


def get_language_codes(language):
    """Find ISO-639-1 2-letter code(s) for the given language name."""
    if not language or not isinstance(language, str):
        return []
    name = language.strip()
    codes = set()
    # exact
    try:
        lang = pycountry.languages.lookup(name)
        if hasattr(lang, 'alpha_2'):
            codes.add(lang.alpha_2)
    except LookupError:
        pass
    # partial
    lower = name.lower()
    for lang in pycountry.languages:
        lname = getattr(lang, 'name', '') or ''
        if lower in lname.lower() and hasattr(lang, 'alpha_2'):
            codes.add(lang.alpha_2)
    # fuzzy
    names = [getattr(lang, 'name', '') for lang in pycountry.languages if getattr(lang, 'name', '')]
    for match in get_close_matches(name, names, cutoff=0.8):
        flang = pycountry.languages.get(name=match)
        if flang and hasattr(flang, 'alpha_2'):
            codes.add(flang.alpha_2)
    return sorted(codes)


def slugify_title(title: str) -> str:
    """Convert string to URL-friendly slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s]', '', slug)
    return re.sub(r'\s+', '-', slug)


def bbox(left, bottom, right, top):
    """Return GeoJSON dict for bounding box in EPSG:4326."""
    poly = Polygon([[left, bottom], [left, top], [right, top], [right, bottom]])
    return mapping(poly)


def ingest_dlr_metadata(json_file: str, c: Client):
    """Ingest DLR metadata JSON into CKAN via STELAR client."""
    data = json.load(open(json_file))

    # Truncate notes
    notes = data.get('description') or ''
    if len(notes) > 1000:
        notes = notes[:997] + '...'

    # Tags
    raw_tags = [t.strip() for t in (data.get('keywords') or '').split(',') if t]
    conforming, custom = [], []
    for t in raw_tags:
        if re.match(r'^[A-Za-z0-9 _\-.]+$', t):
            conforming.append(t)
        else:
            custom.append(t)

    # DOI
    ident = data.get('identifier') or {}
    doi = ident.get('value') if ident.get('propertyID') == 'doi' else None

    # Temporal
    start, end = get_timespan(data.get('temporalCoverage') or '')

    # Spatial
    spatial = None
    geo = (data.get('spatialCoverage') or {}).get('geo') or {}
    box = geo.get('box')
    if box:
        coords = list(map(float, box.split()))
        spatial = bbox(*coords)

    # Author
    author = data.get('author') or []
    contact_name = None
    if isinstance(author, list) and author and author[0].get('@type') == 'Person':
        contact_name = author[0].get('name')

    # Build spec and remove None values
    spec = {
        'title': data.get('name') or '',
        'name': slugify_title(data.get('name') or ''),
        'notes': notes,
        'url': data.get('url') or '',
        'private': False,
        'tags': conforming,
        'doi': doi,
        'documentation': data.get('documentation'),
        'license': data.get('license'),
        'theme': [data.get('additionalType')] if data.get('additionalType') else [],
        'language': get_language_codes(data.get('inLanguage') or ''),
        'spatial': spatial,
        'temporal_start': start,
        'temporal_end': end,
        'contact_name': contact_name,
        'contact_email': data.get('contact'),
        'custom_tags': custom
    }
    # drop None
    spec = {k: v for k, v in spec.items() if v is not None}
    spec['organization'] = c.organizations.get('stelar-klms')
    c.datasets.create(**spec)


def main():
    c = Client(context='default')

    # Scan the directory for JSON files
    import os
    json_dir = './dlr'

    for filename in os.listdir(json_dir):
        if filename.endswith('.json'):
            json_file = os.path.join(json_dir, filename)
            print(f'Ingesting {json_file}...')
            try:
                ingest_dlr_metadata(json_file, c)
                print('Done.')
            except Exception as e:
                print(f'Error ingesting {json_file}: {e}')

if __name__ == '__main__':
    main()
