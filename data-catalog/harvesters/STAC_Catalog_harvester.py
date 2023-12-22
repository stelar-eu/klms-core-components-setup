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

###################################################
# Applicable to harvest these EO data sources:

# Collections from Open Environmental Data Cube Europe (odse)
# https://stacindex.org/catalogs/eco-datacube#/

# Collections from OpenLandMap STAC
# https://stacindex.org/catalogs/openlandmap

##################################################

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


def ingest_stac_metadata(input_dict, base_url, stac_url, owner_org, headers):
    """ Ingest a data source conforming to STAC into the Data Catalog (CKAN) according to the given metadata (JSON).
    
    Args:
        input_dict (dict): JSON dictionary containing the metadata as obtained from the STAC Catalog.
        base_url (string): The URL of the organization.
        stac_url (string): The publicly accessile STAC URL of the organization.
        owner_org (string): The organization account name as used by CKAN (to allow dataset names from different providers).
        headers (dict): Headers for connecting to the CKAN API (including the CKAN token).
        
    Returns:
        The identifier of the published item in the Data Catalog; None, if publishing failed.
    """
    pid = None
    
    # Include provider in the title to avoid conflicts with existing CKAN resources
    # CKAN supports up to 200 characters in title; trim exceeding characters
    if len(input_dict['title']) + len(' (' + owner_org + ')')> 200:
        title = input_dict['title'][:(197-len(' (' + owner_org + ')'))] + '...' + ' (' + owner_org + ')'
    else:
        title = input_dict['title'] + ' (' + owner_org + ')'
    
    # CKAN supports up to 10000 characters in abstract; trim exceeding characters
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
            themes.append(t.title())
        elif t == 'Satellite' or t=='sentinel' or t=='landsat' or t=='ard' or t=='COG' or t=='HREA' or t=='Remote Sensing':
            themes.append('Imagery')
        elif t == 'land':
            themes.append('Land Use')
        elif 'landcover' in t:
            themes.append('Land Cover')
        elif 'fire' in t:
            themes.append('Fire')
        elif 'flood' in t:
            themes.append('Climate')
        elif 'soil' in t:
            themes.append('Soils')
        elif 'boundar' in t:
            themes.append('Boundaries')
        elif 'terrain' in t or 'dtm' in t:
            themes.append('DEM')
        elif 'administrative' in t and 'protected' in title.lower():
            themes.append('Protected Zones')
        elif 'tropomi' in t:
            themes.append('Air Quality')
            themes.append('Climate')
        elif 'temperature' in t:
            themes.append('Temperature')
        elif 'vegetation' in t:
            themes.append('Vegetation')
        elif t.lower().startswith('air'):
            themes.append('Air Quality')
        elif t.lower().startswith('building'):
            themes.append('Land Use')
     
    # Remove duplicates
    themes = list(dict.fromkeys(themes))
    if not themes:  # Assign ad-hoc theme
        themes.append('Remote Sensing')
        
    # Construct the URL of this dataset using the publicly accessible STAC UTL
    url = base_url + input_dict['id'] + '/collection.json'
    doc = stac_url + input_dict['id'] + '/collection.json'
        
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

    # Construct a JSON for each data source (CKAN package)
    # IMPORTANT! NO CKAN resources will be associated with each package
    pub_metadata = {
        'basic_metadata': {
            'title': title,
            'notes': notes,  # CKAN supports up to 10000 characters
            'url': url,
            'version': next((value for key,value in input_dict.items() if key == 'version'), None),
    #        'license_id': 'other-closed',         # No generic CKAN license for STAC
            'private' : False,  # Dataset metadata will be publicly accessible/searchable
            'tags': tags  # Original keywords conforming to CKAN rules
        },
        'extra_metadata': {
#            'alternate_identifier': alt_href,
            'documentation': doc,
            'license': next((value for key,value in input_dict.items() if key == 'license'), None),  # Specify here the license (may be a URL, link to a PDF, etc.)
            'theme': themes,
            'language': ['en'],   # Ad-hoc language assigned for metadata
            'spatial': spatial,
            'temporal_start': temporal_start,
            'temporal_end': temporal_end,
            'contact_name': next((value for key,value in input_dict.items() if key == 'contact_name'), None),
            'contact_email': next((value for key,value in input_dict.items() if key == 'contact_email'), None),
            'custom_tags': custom_tags   # Any original keywords NOT conforming to CKAN rules
            }
        }

    # Publish this collection as a CKAN package
    # Make a POST request to the KLMS API with the package metadata
    pub_response = requests.post(KLMS_API+'catalog/publish', json=pub_metadata, headers=headers)

    response_dict = pub_response.json()
    if ('success' in response_dict) and (response_dict['success'] is True):
        # Extract the ID of the newly created package
        pid = response_dict['result'][0]['result']['id']
        print('Status Code:', pub_response.status_code,'. New data source', title, 'published in CKAN with ID:' + pid)
    else:
        print('Status Code:', pub_response.text,'. Data source ', title, 'not published in CKAN.')
    
    return pid
