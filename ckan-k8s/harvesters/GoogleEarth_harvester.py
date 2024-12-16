 
import os
import pandas as pd
import geopandas as gpd
import math
import numpy as np
import collections
from iso639 import Lang, iter_langs

import urllib.request
import json
import re
import requests
import shapely
from shapely.geometry import shape, Polygon

#####################################################
# Applicable to harvest these EO data sources:

# Collect sources of satellite images
# https://developers.google.com/earth-engine/datasets/catalog

# Catalog in JSON available at 
# https://github.com/opengeos/Earth-Engine-Catalog/tree/master

#####################################################

# List of STAC themes
STAC_themes = ['Air Quality','Biodiversity','Biomass','Vegetation','Climate','DEM','Demographics','Fire','Imagery','Infrastructure','Land Use','Land Cover','SAR','Snow','Soils','Solar','Temperature','Water','Weather']

# Mapping of most common GEE tags to STAC themes
GEE_mappings = { 
    'biodiversity':'Biodiversity',
    'cloud':'Weather',
    'climate':'Climate',
    'air_quality':'Air Quality',
    'radiation':'Weather',
    'reflectance':'Weather',
    'landcover':'Land Cover',
    'agriculture':'Vegetation',
    'fishing':'Biodiversity',
    'forest':'Vegetation',
    'elevation':'DEM',
    'dem':'DEM',
    'soil':'Soils',
    'fire':'Fire',
    'coastal':'Water',
    'crop':'Vegetation',
    'built':'Land Use',
    'built_up':'Land Use',
    'building':'Land Use',
    'atmosphere':'Climate',
    'ocean':'Climate',
    'air_temperature':'Temperature',
    'orthophoto':'Imagery',
    'landsat':'Imagery',
    'modis':'Imagery',
    'sentinel':'Imagery',
    'multispectral':'Imagery',
    'climate_change':'Climate',
    'ice':'Climate',
    'hydrology':'Water',
    'biomass':'Biomass',
    'demography':'Demographics',
    'census':'Demographics',
    'bathymetry':'Water',
    'water':'Water',
    'borders':'Borders',
    'population':'Statistics',
    'protected_areas':'Protected sites',
    'surface_temperature':'Temperature',
    'sar':'SAR'
}

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


def ingest_earthengine_metadata(input_dict, owner_org, headers):
    """ Ingest a data source from Google Earth Engine into the Data Catalog (CKAN) according to the given metadata (JSON).
    
    Args:
        input_dict (dict): JSON dictionary containing the metadata as obtained from Google Earth Engine.
        owner_org (string): The organization account name as used by CKAN (to allow dataset names from different providers).
        headers (dict): Headers for connecting to the CKAN API (including the CKAN token).
        
    Returns:
        The identifier of the published item in the Data Catalog; None, if publishing failed.
    """
    pid = None
    
    # Description about this data source
    notes = input_dict['title'] # Initially set to the title
    # Fetch all details in order to get a full description
    json_href = next((value for key,value in input_dict.items() if key == 'catalog'), None)
    if json_href:
        with urllib.request.urlopen(json_href) as f:
            json_url = json.load(f)
            notes = json_url['description']
            # CKAN supports up to 1000 characters in abstract; trim exceeding characters
            if len(notes) > 1000:
                notes = notes[:997] + '...'       

    # Include provider in the title to avoid conflicts with existing CKAN resources
    # CKAN supports up to 100 characters in title; trim exceeding characters
    if len(input_dict['title']) + len(' (' + owner_org + ')')> 100:
        title = input_dict['title'][:(97-len(' (' + owner_org + ')'))] + '...' + ' (' + owner_org + ')'
    else:
        title = input_dict['title'] + ' (' + owner_org + ')'
    
    # Check if tags conform to CKAN rules
    # CKAN tags can only contain alphanumeric characters, spaces ( ), hyphens (-), underscores (_) or dots (.)
    if 'keywords' in input_dict:
        themes = []  # Assign theme(s) according to tags; also handle special cases not directly associated to STAC themes
        tags = [t.strip() for t in input_dict['keywords'].split(',')]
        for tag in tags:
            if tag in GEE_mappings:
                themes.append(GEE_mappings[tag])
            elif tag.title() in STAC_themes:
                themes.append(tag.title())
    else:
        tags = ['Imagery']  # Assign ad-hoc tags; at least one must be specified

    # Remove duplicates
    themes = list(dict.fromkeys(themes))   

    # Extract spatial coverage
    if 'bbox' in input_dict:
        bounds = list(map(float, input_dict['bbox'].split(',')))   
        spatial = bbox(bounds[0], bounds[1], bounds[2], bounds[3])

    # Construct a JSON for each data source (CKAN package)
    # IMPORTANT! NO CKAN resources will be associated with each package
    pub_metadata = {
        'basic_metadata': {
            'title': title,
            'notes': notes,  # CKAN supports up to 1000 characters
            'url': next((value for key,value in input_dict.items() if key == 'url'), None),
    #        'license_id': 'other-closed',         # No generic CKAN license for STAC
            'private' : False,  # Dataset metadata will be publicly accessible/searchable
            'tags': tags  # Original keywords conforming to CKAN rules
        },
        'extra_metadata': {
            'alternate_identifier': next((value for key,value in input_dict.items() if key == 'id'), None),
            'license': next((value for key,value in input_dict.items() if key == 'license'), None),
            'theme': themes,
            'language': ['en'],   # Ad-hoc language assigned for metadata
            'spatial': spatial,
            'temporal_start': next((value for key,value in input_dict.items() if key == 'state_date'), None),
            'temporal_end': next((value for key,value in input_dict.items() if key == 'end_date'), None),
            # Also include some extra metadata provided by this catalog
            'provider_name': next((value for key,value in input_dict.items() if key == 'provider'), None),
            'access_rights': next((value for key,value in input_dict.items() if key == 'terms_of_use'), None),
            'thumbnail': next((value for key,value in input_dict.items() if key == 'thumbnail'), None),
            'deprecated': next((value for key,value in input_dict.items() if key == 'deprecated'), None),
            'dataset_type': next((value for key,value in input_dict.items() if key == 'type'), None)
            }
        }
            
    # STAGE #1: Publish this collection as a CKAN package
    # Make a POST request to the KLMS API with the package metadata
    pub_response = requests.post(KLMS_API+'catalog/publish', json=pub_metadata, headers=headers)

    response_dict = pub_response.json()
    if ('success' in response_dict) and (response_dict['success'] is True):
        # Extract the ID of the newly created package
        pid = response_dict['result'][0]['result']['id']
        print('Status Code:', pub_response.status_code,'. New data source', title, 'published in CKAN with ID:' + pid)
    else:
        print('Status Code:', pub_response.text,'. Data source ', title, 'not published in CKAN.')
        
    # STAGE #2: Also publish the original JSON metadata as a resource
    rid = None
    if pid != None and json_href:
        # Put the details regarding the resource into a dictionary:
        resource_metadata = {'resource_metadata' : {
            'package_id': pid,  # MUST specify the id of the package (data source) assigned by CKAN
            'name': title + ' specifications',
            'description': 'Specifications about ' + title + ' data in JSON format',
            'format': 'JSON',
            'license': next((value for key,value in input_dict.items() if key == 'license'), None),
            'resource_type': 'other',
            'url': json_href
        }}

        # Make a POST request to the KLMS API with the resource metadata
        res_response = requests.post(KLMS_API+'resource/link', json=resource_metadata, headers=headers)

        response_dict = json.loads(res_response.text)
        if (response_dict['success'] is True):
            # Extract the ID of the newly created resource
            rid = response_dict['result']['id']
            print('Created new resource with ID:' + rid)
    
    return pid, rid

