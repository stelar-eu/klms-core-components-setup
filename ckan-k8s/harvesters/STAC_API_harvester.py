import os
import pandas as pd
import geopandas as gpd
import math
import numpy as np
import collections
from iso639 import Lang, iter_langs

import json
import re
import requests
import shapely
from shapely.geometry import shape, Polygon
from stelar.client import Client

##############################################################################
# Applicable to harvest these EO data sources:

# Microsoft Planetary Computer STAC API (microsoft-pc) [PUBLIC]
# STAC_API='https://planetarycomputer.microsoft.com/api/stac/v1/collections'

# Earth Search by Element 84 STAC API (earth-search-aws) [PUBLIC]
# STAC_API='https://earth-search.aws.element84.com/v1/collections'

# Sentinel Hub [PROTECTED]
# STAC_API='https://services.sentinel-hub.com/api/v1/catalog/1.0.0/collections'

# USGS Landsat Collection 2 API [PUBLIC]
# STAC_API='https://landsatlook.usgs.gov/stac-server/collections'
    
# Terrascope [PROTECTED]
# STAC_API = 'https://services.terrascope.be/stac/collections'

# EODC API (openEO) [PROTECTED]
STAC_API='https://openeo.eodc.eu/openeo/1.1.0/collections'
##############################################################################

# List of STAC themes
STAC_themes = ['Air Quality','Biodiversity','Biomass','Vegetation','Climate','DEM','Demographics','Fire','Imagery','Infrastructure','Land Use','Land Cover','SAR','Snow','Soils','Solar','Temperature','Water','Weather']


def get_timespan(temporalCoverage):
    """ Extract the start and end of the given temporal coverage.
    
    Args:
        temporalCoverage (list): The temporal coverage given as a list of intervals.
        
    Returns:
        A pair or values (one or both may be None).
    """    
    temporal_start = None
    temporal_end = None
    if temporalCoverage['interval']:
        timespan = temporalCoverage['interval'][0]
        temporal_start = timespan[0]
        temporal_end = timespan[1]

    return temporal_start, temporal_end


def getLanguageCodes(language_en):
    """ Find the language code of the given language.
    
    Args:
        language_en (string): Language name (in English).
        
    Returns:
        A list with corresponding 2-digit language code(s) ( ISO-639-1).
    """
    lang = []
        
    if language_en == None:
        return lang

    for lg in iter_langs():
        if language_en.capitalize() in lg.name and lg.pt1 != '':
            lang.append(lg.pt1)
        
    return lang


def bbox(left, bottom, right, top):
    """ Create a Polygon geometry representing a bounding box from two pairs of (lon, lat) coordinates in WGS84 (EPSG:4326).
    
    Args:
        left (float): Minimum longitude (left side of the rectangle).
        bottom (float): Minimum latitude (bottom side of the rectangle).
        right (float): Maximum longitude (right side of the rectangle).
        top (float): Maximum latitude (top side of the rectangle).
        
    Returns:
        A GeoJson representing the given bounding box in WGS84.
    """
    # Create a shapely geometry from the given coordinates    
    poly = Polygon([[left, bottom], [left, top], [right, top], [right, bottom]]) 

    # Covert it to GeoJSON as required by CKAN
    return json.dumps(shapely.geometry.mapping(poly))


def slugify_title(title: str) -> str:
    """
    Convert a string into a URL-friendly “slug”:
    - lowercase
    - trim leading/trailing whitespace
    - remove non-alphanumeric characters (except spaces)
    - replace runs of whitespace with single hyphens
    """
    slug = title.lower().strip()
    # Remove any character that is not a letter, number, or space
    slug = re.sub(r'[^a-z0-9\s]', '', slug)
    # Replace one or more spaces with a single hyphen
    slug = re.sub(r'\s+', '-', slug)
    return slug


def ingest_stac_metadata(input_dict, c: Client):
    """ Ingest a data source conforming to STAC into the Data Catalog (CKAN) according to the given metadata (JSON).
    
    Args:
        input_dict (dict): JSON dictionary containing the metadata as obtained from STAC API.
        owner_org (string): The organization account name as used by CKAN (to allow dataset names from different providers).
        headers (dict): Headers for connecting to the CKAN API (including the CKAN token).
        
    Returns:
        The identifier of the published item in the Data Catalog; None, if publishing failed.
    """
    pid = None
    
    # # Include provider in the title to avoid conflicts with existing CKAN resources
    # # CKAN supports up to 100 characters in title; trim exceeding characters
    # if len(input_dict['title']) + len(' (' + owner_org + ')')> 200:
    #     title = input_dict['title'][:(197-len(' (' + owner_org + ')'))] + '...' + ' (' + owner_org + ')'
    # else:
    #     title = input_dict['title'] + ' (' + owner_org + ')'
    
    # CKAN supports up to 1000 characters in abstract; trim exceeding characters
    if len(input_dict['description']) > 10000:
        notes = input_dict['description'][:9997] + '...'
    else:
        notes = input_dict['description']
        
    # Check if tags conform to CKAN rules
    # CKAN tags can only contain alphanumeric characters, spaces ( ), hyphens (-), underscores (_) or dots (.)
    if 'keywords' in input_dict:
        tags = [t.strip() for t in input_dict['keywords']]
        # Keep all remaining tags in the extras
        custom_tags = []
        for t in tags:
            if not re.match('[a-zA-Z\-\_\.\s]+$', t):
                custom_tags.append(t)
        # Remove not-conforming tags        
        tags = [t for t in tags if t not in custom_tags]
        if not custom_tags:
            custom_tags = None
    else:
        tags = ['Remote Sensing']  # Assign ad-hoc tags; at least one must be specified
        custom_tags = None

    # Assign theme(s) according to tags; also handle special cases not directly associated to STAC themes
    themes = []
    for t in tags:
        if t in STAC_themes:
            themes.append(t)
        elif t.title() in STAC_themes:
            themes.append(t)
        elif t == 'Satellite' or t=='landsat' or t=='sentinel' or t=='COG' or t=='HREA' or t=='Remote Sensing':
            themes.append('Imagery')
        elif t == 'Precipitation':
            themes.append('Imagery')
        elif t == 'Wetlands':
            themes.append('Water')
            themes.append('Biodiversity')
        elif t.lower().startswith('air'):
            themes.append('Air Quality')
        elif t.lower().startswith('building'):
            themes.append('Land Use')
    # Remove duplicates
    themes = list(dict.fromkeys(themes))
    if not themes:  # Assign ad-hoc theme
        themes.append('Remote Sensing')
            
    # Extract alternate identifiers (e.g., DOI), documentation, license, ...
    url = None
    alt_href = None
    doc = None
    license = None
    json_href = None
    for link in input_dict['links']:
        if link['rel'] == 'cite-as' or link['rel'] == 'about':
            alt_href = link['href']
            url = link['href']
        elif link['rel'] == 'describedby':
            doc = link['href']
        elif link['rel'] == 'license':
            license = link['href']
        elif link['rel'] == 'self':
            json_href = link['href']
     
    # Extract temporal coverage
    temporal_start, temporal_end = get_timespan(input_dict['extent']['temporal'])

    # Extract spatial coverage
    geom = input_dict['extent']['spatial']
    if geom['bbox']:
        bounds = geom['bbox'][0]   # Considering the first bounding box only
        spatial = bbox(bounds[0], bounds[1], bounds[2], bounds[3])

    # Extract info about the providers
    if 'providers' in input_dict:
        for provider in input_dict['providers']:
            if 'url' in provider:
                if 'producer' in provider['roles']:
                    owner_url = provider['url']
                    if url == None:
                        url = owner_url
                if 'processor' in provider['roles']:
                    publisher_url = provider['url']
        
    # Extract the first author (if applicable)
    author_name = None
    if 'author' in input_dict.keys():
        author = input_dict['author']
        if isinstance(author, list) and len(author)>0 and author[0]['@type'] == 'Person':
            author_name = author[0]['name']

    # Construct a JSON for each data source (CKAN package)
    # IMPORTANT! NO CKAN resources will be associated with each package
    # pub_metadata = {
    #     'basic_metadata': {
    #         'title': title,
    #         'notes': notes,  # CKAN supports up to 1000 characters
    #         'url': url,
    # #        'license_id': 'other-closed',         # No generic CKAN license for STAC
    #         'private' : False,  # Dataset metadata will be publicly accessible/searchable
    #         'tags': tags  # Original keywords conforming to CKAN rules
    #     },
    #     'extra_metadata': {
    #         'alternate_identifier': alt_href,
    #         'documentation': doc,
    #         'license': license,  # Specify here the license (may be a URL, link to a PDF, etc.)
    #         'theme': themes,
    #         'language': ['en'],   # Ad-hoc language assigned for metadata
    #         'spatial': spatial,
    #         'temporal_start': temporal_start,
    #         'temporal_end': temporal_end,
    #         'contact_name': author_name,
    #         'contact_email': next((value for key,value in input_dict.items() if key == 'contact'), None),
    #         'custom_tags': custom_tags   # Any original keywords NOT conforming to CKAN rules
    #         }
    #     }
    
    max_length = 100
    base_title = input_dict['title'] + ' by STAC'
    if len(base_title) > max_length:
        truncated_title = base_title[:max_length - 3] + '...'
    else:
        truncated_title = base_title

    spec = {
        "title": truncated_title,
        "name": slugify_title(truncated_title),
        "notes": notes,
        "url": url,
        "private": False,  # Dataset metadata will be publicly accessible/searchable
        "tags": tags,  # Original keywords conforming to CKAN rules
        "license": license,
        "alternate_identifier": alt_href,
        "documentation": doc,
        "theme": themes,
        "language": ['en'],   # Ad-hoc language assigned for metadata
        "spatial": spatial,
        "temporal_start": temporal_start,
        "temporal_end": temporal_end,
        "contact_name": author_name,
        "contact_email": next((value for key,value in input_dict.items() if key == 'contact'), None),
        "custom_tags": custom_tags,   # Any original keywords NOT conforming to CKAN rules
    }
    

    try:
        spec["organization"] = c.organizations["stelar-klms"]
        d = c.datasets.create(**spec)
        print('Created new dataset with ID:', d.id)
        pid = str(d.id)
    except Exception as e:
        print('Error while preparing metadata for STAC item:', input_dict['title'], 'Error:', str(e))
        return None, None


    # STAGE #2: Also publish the original JSON metadata as a resource
    rid = None
    if pid != None and json_href:
        # Put the details regarding the resource into a dictionary:
        try:
            r = d.add_resource(
                title=input_dict['title'] + ' specifications',
                description='Specifications about ' + input_dict['title'] + ' data in JSON format',
                format='JSON',
                license=license,
                resource_type='other',
                url=json_href
            )
            rid = str(r.id)
        except Exception as e:
            print('Error while creating resource for STAC item:', input_dict['title'], 'Error:', str(e))
            return pid, None
    
    return pid, rid


def main():
    # Initialize the STELAR client, using context file. Credentials can be also hardcoded here like
    # c = Client(base_url="https://klms.stelar.gr", username='your_username', password='your_password')
    c = Client(context='staging')
    # Path to the JSON file containing DLR metadata
    json_file = 'path/to/dlr_metadata.json'

    ingest_stac_metadata(
        input_dict=json.load(open(json_file, 'r')),
        c=c
    )

if __name__ == "__main__":
    main()
