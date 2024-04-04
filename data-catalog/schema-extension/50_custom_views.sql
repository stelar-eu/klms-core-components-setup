
-- Create a view for temporal extents of published datasets (based on their extras):
-- IMPORTANT! Special handling for open intervals (i.e., missing start or end dates).

CREATE OR REPLACE VIEW package_temporal_extent AS
WITH A AS (SELECT e.package_id AS id, e.value::timestamp AS temporal_start FROM package p, package_extra e WHERE e.package_id=p.id AND e.key IN ('temporal_start','startDate') AND p.state='active'),
     B AS (SELECT e.package_id AS id, e.value::timestamp AS temporal_end FROM package p, package_extra e WHERE e.package_id=p.id AND e.key IN ('temporal_end','endDate') AND p.state='active')
SELECT A.id AS id, temporal_start, temporal_end
FROM A LEFT OUTER JOIN B ON A.id=B.id
UNION
SELECT B.id AS id, temporal_start, temporal_end
FROM A RIGHT OUTER JOIN B ON A.id=B.id;


-- View of keywords (TAGS) associated with each dataset (CKAN package):
-- IMPORTANT: Includes both tags (from CKAN table 'package_tag') and custom tags (from CKAN table 'package_extra').

CREATE OR REPLACE VIEW package_tag_array AS 
SELECT id, array_agg(tags) AS arr_values FROM (
(SELECT p.id, t.name AS tags 
  FROM package p, package_tag r, tag t
  WHERE r.tag_id = t.id
  AND r.package_id = p.id
  AND p.state='active')
UNION
( SELECT p.id, trim(json_array_elements(e.value::json)::text, '"') AS tags 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='custom_tags' 
       AND is_valid_json(e.value) 
       AND p.state='active')
) all_tags
GROUP BY id;


-- View of THEMES characterizing each dataset (CKAN package):

CREATE OR REPLACE VIEW package_theme_array AS 
  SELECT id, array_agg(trim(theme::text, '"')) AS arr_values 
  FROM ( SELECT p.id, json_array_elements(e.value::json) AS theme 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='theme' 
       AND is_valid_json(e.value) 
       AND p.state='active') t 
 GROUP BY id;


-- View of LANGUAGES characterizing each dataset (CKAN package):

CREATE OR REPLACE VIEW package_language_array AS 
  SELECT id, array_agg(trim(language::text, '"')) AS arr_values 
  FROM ( SELECT p.id, json_array_elements(e.value::json) AS language 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='language' 
       AND is_valid_json(e.value) 
       AND p.state='active') t 
  GROUP BY id;



-- LICENSE (from extras)
-- FIXME: Include license spec from table 'package'

CREATE OR REPLACE VIEW package_license_array AS 
  SELECT id, array_agg(trim(license::text, '"')) AS arr_values 
  FROM ( SELECT p.id, e.value AS license 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='license'  
       AND p.state='active') t 
  GROUP BY id;


-- DATASET TYPE (from extras)
-- FIXME: Include dataset type from profiling information (if available)

CREATE OR REPLACE VIEW package_dataset_type_array AS 
  SELECT id, array_agg(trim(dataset_type::text, '"')) AS arr_values 
  FROM ( SELECT p.id, e.value AS dataset_type 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='dataset_type'  
       AND p.state='active') t 
  GROUP BY id;



-- FORMAT (from extras)
-- FIXME: Include format from profiling information (if available)

CREATE OR REPLACE VIEW package_format_array AS 
  SELECT id, array_agg(trim(format::text, '"')) AS arr_values 
  FROM ( SELECT p.id, e.value AS format 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='format'  
       AND p.state='active') t 
  GROUP BY id;


-- PROVIDER NAMES (from extras)
-- FIXME: Include information from table 'package'.

CREATE OR REPLACE VIEW package_provider_array AS
  SELECT id, array_agg(trim(provider_name::text, '"')) AS arr_values 
  FROM ( SELECT p.id, e.value AS provider_name 
       FROM package p, package_extra e 
       WHERE e.package_id=p.id 
       AND e.key='provider_name'  
       AND p.state='active') t 
  GROUP BY id;


-- ORGANIZATION (from CKAN table "group")

CREATE OR REPLACE VIEW package_organization_array AS
  SELECT id, array_agg(trim(organization_name::text, '"')) AS arr_values 
  FROM ( SELECT p.id, g.title AS organization_name 
       FROM package p, "group" g 
       WHERE p.owner_org = g.id
       AND p.state='active'
       AND g.is_organization = true 
       AND g.state = 'active') t
  GROUP BY id;


-----------------------------------------------------
-- Custom views for specific extra metadata 
-----------------------------------------------------

-- NUM_ROWS as specified in the extras of the PACKAGE:

CREATE OR REPLACE VIEW package_num_rows AS 
  SELECT p.id, e.value
  FROM public.package p, public.package_extra e
  WHERE p.id = e.package_id
  AND p.state = 'active'
  AND e.key = 'num_rows';


-- DAYS_ACTIVE as specified in the extras of the PACKAGE:

CREATE OR REPLACE VIEW package_days_active AS 
  SELECT p.id, e.value
  FROM public.package p, public.package_extra e
  WHERE p.id = e.package_id
  AND p.state = 'active'
  AND e.key = 'days_active';


-- VELOCITY as specified in the extras of the PACKAGE:

CREATE OR REPLACE VIEW package_velocity AS 
  SELECT p.id, e.value
  FROM public.package p, public.package_extra e
  WHERE p.id = e.package_id
  AND p.state = 'active'
  AND e.key = 'velocity';


-----------------------------------------------------
-- Custom views for specific profiling metadata 
-----------------------------------------------------

-- CLOUD COVERAGE in RASTER data as specified in the PROFILING information
-- CAUTION! A package may contain multiple raster images -> multiple profiles -> taking the min percentage

CREATE OR REPLACE VIEW profile_vista_min_cloud_coverage AS 
  SELECT PR.id, min(N.percentage) AS value
  FROM public.resource PR, klms.raster R, klms.attribute A, klms.band_attribute B, klms.categorical_distribution N
  WHERE PR.id = R.resource_id
  AND PR.state = 'active'
  AND R.name = B.raster_name
  AND A.attr_id = B.attr_id
  AND B.no_data_distribution = N.distr_id
  AND A.type ='Band'
  AND N.type='clouds'
  GROUP BY PR.id;


-- MISSING values in RASTER data as specified in the PROFILING information
-- CAUTION! A package may contain multiple raster images -> multiple profiles -> taking the min percentage

CREATE OR REPLACE VIEW profile_vista_min_missing AS 
  SELECT PR.id, min(N.percentage) AS value
  FROM public.resource PR, klms.raster R, klms.attribute A, klms.band_attribute B, klms.categorical_distribution N
  WHERE PR.id = R.resource_id
  AND PR.state = 'active'
  AND R.name = B.raster_name
  AND A.attr_id = B.attr_id
  AND B.no_data_distribution = N.distr_id
  AND A.type ='Band'
  AND N.type='missing'
  GROUP BY PR.id;


-- LAI values in RASTER data as specified in the PROFILING information
-- CAUTION! A package may contain multiple raster images -> multiple profiles -> taking the max percentage

CREATE OR REPLACE VIEW profile_vista_max_lai AS 
  SELECT PR.id, max(N.percentage) AS value
  FROM public.resource PR, klms.raster R, klms.attribute A, klms.band_attribute B, klms.categorical_distribution N
  WHERE PR.id = R.resource_id
  AND PR.state = 'active'
  AND R.name = B.raster_name
  AND A.attr_id = B.attr_id
  AND B.no_data_distribution = N.distr_id
  AND A.type ='Band'
  AND N.type='LAI'
  GROUP BY PR.id;

