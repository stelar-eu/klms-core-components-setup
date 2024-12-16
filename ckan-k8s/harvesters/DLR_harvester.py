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

##############################################################################
# Applicable to harvest EO data assets available from German Aerospace Center (DLR):

# https://geoservice.dlr.de/data-assets/
 
##############################################################################


def get_timespan(temporalCoverage):
    """ Extract the start and end of the given temporal coverage.
    
    Args:
        temporalCoverage (string): The temporal coverage given as a string like '2015-04-24/2020-07-12' or '2018-08-30/..'.
        
    Returns:
        A pair or values (one or both may be None).
    """    
    temporal_start = None
    temporal_end = None
    if temporalCoverage:
        timespan = temporalCoverage.split('/')   # character / is used by DLR as delimeter
        if timespan[0] != '..':   # substring '..' denotes NULL
            temporal_start = timespan[0]
        if timespan[1] != '..':
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
    return poly
    # Covert it to GeoJSON as required by CKAN
    # return json.dumps(shapely.geometry.mapping(poly))

def ingest_dlr_metadata(json_file):
    """ Ingest a data source from DLR into the Data Catalog (CKAN) according to the given metadata (JSON).
    
    Args:
        json_file (string): Path to the JSON file containing the metadata as obtained from DLR.
        
    Returns:
        The identifier of the published item in the Data Catalog; None, if publishing failed.
    """
    pid = None
    
    # Open JSON file and read its contents into a dict
    f = open(json_file)
    input_dict = json.load(f)
    f.close()
    
    # CKAN supports up to 1000 characters in abstract
    if len(input_dict['description']) > 1000:
        notes = input_dict['description'][:997] + '...'
    else:
        notes = input_dict['description']
        
    # Check if tags conform to CKAN rules
    # CKAN tags can only contain alphanumeric characters, spaces ( ), hyphens (-), underscores (_) or dots (.)
    tags = [t.strip() for t in input_dict['keywords'].split(',')]
    # Keep all remaining tags in the extras
    custom_tags = []
    for t in tags:
        if not re.match('[a-zA-Z\-\_\.\s]+$', t):
            custom_tags.append(t)
    # Remove any not-conforming tags        
    tags = [t for t in tags if t not in custom_tags]

    # Extract DOI
    doi = None
    if input_dict['identifier']:
        if input_dict['identifier']['propertyID'] == 'doi':
            doi = input_dict['identifier']['value']
     
    # Extract temporal coverage
    temporal_start, temporal_end = get_timespan(input_dict['temporalCoverage'])

    # Extract spatial coverage
    geom = input_dict['spatialCoverage']['geo']
    if geom['box']:
        bounds = list(map(float, geom['box'].split(' ')))   
        spatial = bbox(bounds[0], bounds[1], bounds[2], bounds[3])
    
    # Extract the first author (if applicable)
    author_name = None
    if input_dict['author']:
        author = input_dict['author']
        if isinstance(author, list) and len(author)>0 and author[0]['@type'] == 'Person':
            author_name = author[0]['name']
    
    # Construct a JSON for each data source (CKAN package)
    # IMPORTANT! NO CKAN resources will be associated with each package
    pub_metadata = {
        'basic_metadata': {
            'title': input_dict['name'],
            'notes': notes,  
            'url': input_dict['url'],
    #        'license_id': 'other-closed',         # No CKAN license suitable for DLR
            'private' : False,  # Dataset will be publicly accessible
            'tags': tags  # Original keywords conforming to CKAN rules
        },
        'extra_metadata': {
            'alternate_identifier': doi,
            'documentation': input_dict['documentation'],
            'license': next((value for key,value in input_dict.items() if key == 'license'), None),
            'theme':[input_dict['additionalType']],
            'language': [input_dict['inLanguage']],
            'spatial': spatial.wkt,
            'temporal_start': temporal_start,
            'temporal_end': temporal_end,
            'contact_name': author_name,
            'contact_email': next((value for key,value in input_dict.items() if key == 'contact'), None),
            'custom_tags': custom_tags   # Any original keywords NOT conforming to CKAN rules
            }
        }
    
    # Make a POST request to the KLMS API with the metadata
    pub_response = requests.post(KLMS_API+'catalog/publish', json=pub_metadata, headers=headers)

    response_dict = pub_response.json()
    if (response_dict['success'] is True):
        # Extract the ID of the newly created package
        pid = response_dict['result'][0]['result']['id']
        print('Status Code', pub_response.status_code, '. Published new data source in CKAN with ID:' + pid)
    else:
        print('Status Code', pub_response.status_code, '. Data source not published in CKAN.')
        
    return pid


