
-- Auxiliary function to check is the given JSON is valid:

CREATE OR REPLACE FUNCTION is_valid_json(p_json text) 
    RETURNS boolean
    AS $function$
        BEGIN
        RETURN (p_json::json IS NOT NULL);
        EXCEPTION
            WHEN OTHERS THEN
            RETURN false; 
        END; 
    $function$
    IMMUTABLE 
    LANGUAGE plpgsql;


-- Custom function to estimate Jaccard similarity between two arrays of strings (keywords):

CREATE OR REPLACE FUNCTION jaccard_similarity(text[], text[]) 
    RETURNS double precision
    AS 'SELECT (SELECT CAST(COUNT(*) AS double precision) FROM (SELECT unnest($1) INTERSECT SELECT unnest($2)) AS intersect_elements)/(SELECT COUNT(*) FROM (SELECT unnest($1) UNION SELECT unnest($2)) AS union_elements);'
    LANGUAGE SQL
    IMMUTABLE
    RETURNS NULL ON NULL INPUT;


-- Auxiliary function to extract values for a specific key stored in CKAN extras:

CREATE OR REPLACE FUNCTION facet_single_values(varchar) 
    RETURNS TABLE (value VARCHAR, cnt BIGINT)
    AS 'SELECT value, count(*) AS cnt FROM public.package_extra WHERE key=$1 GROUP BY value;'
    LANGUAGE SQL
    IMMUTABLE
    RETURNS NULL ON NULL INPUT;


-- Auxiliary function to extract values from arrays concerning a specific key stored in CKAN extras:

CREATE OR REPLACE FUNCTION facet_array_values(varchar) 
    RETURNS TABLE (value VARCHAR, cnt BIGINT)
    AS 'WITH facet_values AS (SELECT (jsonb_array_elements(value::jsonb) ->> 0) AS value FROM public.package_extra WHERE key=$1) SELECT value, count(*) AS cnt FROM facet_values GROUP BY value;'
    LANGUAGE SQL
    IMMUTABLE
    RETURNS NULL ON NULL INPUT;

