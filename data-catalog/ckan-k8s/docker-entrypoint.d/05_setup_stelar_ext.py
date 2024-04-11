import os
import subprocess
import logging


# A convenient wrapper for logging
class StackLogger(logging.LoggerAdapter):
    def __init__(self, logger, extra={}):
        super().__init__(logger, extra)
        self.stack = ['__main__']
    def process(self, msg, kwargs):
        return f"[{self.stack[-1]}] {msg}", kwargs
    def wrap(self, c):
        cname = getattr(c, '__qualname__', c)
        if cname is not c and callable(c):
            from functools import wraps

            @wraps(c)
            def wrapped_callable(*args, **kwargs):
                try:
                    self.stack.append(cname)
                    return c(*args, **kwargs)
                finally:
                    self.stack.pop()
            return wrapped_callable
        else:
            return c


# The logger object
logger = StackLogger(None)

# Global variable, used for convenience
ckan_ini = os.environ.get("CKAN_INI", "/srv/app/ckan.ini")


#
# Some utilities
#

def ckan_exec(cmd: list[str]):
    """Execute a 'ckan' command

    Args:
        cmd (list[str]): The list of arguments to pass
    """
    subprocess.check_output(cmd, stderr=subprocess.STDOUT)


def add_option(opname:str, opvalue: str, opsection: str|None = None):
    """Add ckan config option.

    The option is added by executing the command
    > ckan config-tool ckan_ini  <optname> = <optvalue>

    Args:
        opname (str): The option name
        opval (str): The option value
    """
    cmd = ["ckan", "config-tool", ckan_ini]
    if opsection is not None:
        cmd += ['--section', opsection]
    cmd += [f"{opname} = {opvalue}"]
    ckan_exec(cmd)


def add_option_from_env(envvar: str, dflt:str ="", opsection: str|None = None):
    """Add a ckan config option from an environment variable.

    The option name is extracted from the environment var name, after applying two
    transformations:
    - converting the envvar to lower case, and
    - substituting '__' (two underscores) by '.'

    For example,
    CKAN__INI ->  ckan.ini
    CKAN__FOO_BAR -> ckan.foo_bar

    Args:
        envvar (str): The environment variable
        dflt (str, optional): The default value. Defaults to "".
        opsection (str | None, optional): The section name. Defaults to None.
    """
    opname = envvar.lower().replace('__', '.')
    opvalue = os.environ.get(envvar, dflt)
    add_option(opname, opvalue, opsection)

@logger.wrap
def setup_root_path():
    add_option_from_env("CKAN__ROOT_PATH")

@logger.wrap
def setup_keycloak():
    add_option_from_env("CKANEXT__KEYCLOAK__SERVER_URL")
    add_option_from_env("CKANEXT__KEYCLOAK__CLIENT_ID")

    add_option_from_env("CKANEXT__KEYCLOAK__REALM_NAME")
    add_option_from_env("CKANEXT__KEYCLOAK__REDIRECT_URI")
    add_option_from_env("CKANEXT__KEYCLOAK__CLIENT_SECRET_KEY")
    add_option_from_env("CKANEXT__KEYCLOAK__BUTTON_STYLE")
    add_option_from_env("CKANEXT__KEYCLOAK__ENABLE_CKAN_INTERNAL_LOGIN")


@logger.wrap
def setup_spatial():
    log = logging.getLogger('setup_spatial')

    add_option('ckan.spatial.use_postgis', 'true')
    add_option('ckanext.spatial.search_backend', 'solr-bbox')

    # Now initialize the postgis database
    # TODO: vsam-: maybe 4326 (the srid) should be provided by environment!!
    srid = '4326'
    ckan_exec(['ckan', f'--config={ckan_ini}', 'spatial', 'initdb', srid])

    # Conditionally rebuild index (solr) to include spatial data
    if os.environ.get('CKAN__SPATIAL_REBUILD_INDEX', None):
        ckan_exec(['ckan', f'--config={ckan_ini}', 'search-index', 'rebuild'])

    map_type = os.environ.get('CKANEXT__SPATIAL__COMMON_MAP__TYPE', None)
    match map_type:
        case 'mapbox':
            add_option_from_env('CKANEXT__SPATIAL__COMMON_MAP__TYPE')
            add_option_from_env('CKANEXT__SPATIAL__COMMON_MAP__MAPBOX__MAP_ID', 'mapbox.satellite')
            add_option_from_env('CKANEXT__SPATIAL__COMMON_MAP__ACCESS_TOKEN', 'DANGER:notgiven')

        case _:
            pass


@logger.wrap
def setup_klms_schema():
    #
    # Set up the custom SQL schemas for execution metadata
    # This is currently done here, but it is possible that we will
    # eventually move this to another container.
    #

    psql = '/usr/bin/psql'                                  # psql executable
    URL = os.environ.get('CKAN_SQLALCHEMY_URL', None)       # db URI
    custom_schemata = '/srv/app/etc/custom_schemata.sql'    # sql source file

    if not os.access(psql, os.X_OK):
        logger.error(f"{psql} cannot be executed, skipping custom schema init")
    elif URL is None:
        logger.error("CKAN_SQLALCHEMY_URL is not set, skipping custom schema init")
    elif not os.access(custom_schemata, os.R_OK):
        logger.error("Custom schemata file does not exist, skipping custom schema init")
    else:
        cmd = [psql, URL, '-v', 'ON_ERROR_STOP=on', '-f', custom_schemata]
        rcode = subprocess.call(cmd)
        match rcode:
            case 0:
                logger.info("Custom schemas created successfully")
            case _:
                logger.fatal(f"Custom schema creation failed ({rcode=})")


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    logging.info(f"Configuring {ckan_ini} for STELAR extensions.")
    logger.logger = logging.getLogger("stelar")

    setup_root_path()
    setup_keycloak()
    setup_spatial()
    setup_klms_schema()

