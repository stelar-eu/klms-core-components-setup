import os
import subprocess
import logging
from kubernetes import config, client
import yaml 
import base64

config.load_incluster_config()

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE",'default')


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
def issue_api_token():

    try:
        command = (
            "ckan user token add ckan_admin api_token | grep -A 1 \"API Token created:\" | tail -n 1 | tr -d '\t '"
        )
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stdout.strip()

        # If the token is correctly generated, then create a secret in the cluster containing it. 
        token_secret = create_k8s_secret("ckan-admin-token-secret", {'token':output})
        apply_secret_to_cluster(token_secret)    

    except subprocess.CalledProcessError as e:
        print("Error Output:", e.stderr)


@logger.wrap
def setup_spatial():
    log = logging.getLogger('setup_spatial')

    add_option('ckan.spatial.use_postgis', 'true')
    #
    # There are two backends for spatial search: solr-bbxor and solr-spatial-field
    # We are currently committed to the first.
    # The settings of search backend and solr query parsers go hand in hand.
    #  solr-bbox  <-> frange
    #  solr-spatial-field <-> field
    #
    add_option('ckanext.spatial.search_backend', 'solr-bbox')
    add_option('ckan.search.solr_allowed_query_parsers', 'frange')

    # Now initialize the postgis database
    # TODO: vsam-: maybe 4326 (the srid) should be provided by environment!!
    srid = '4326'
    ckan_exec(['ckan', f'--config={ckan_ini}', 'spatial', 'initdb', srid])

    # Conditionally rebuild index (solr) to include spatial data
    if os.environ.get('CKAN__SPATIAL_REBUILD_INDEX', None):
        ckan_exec(['ckan', f'--config={ckan_ini}', 'search-index', 'rebuild'])

    # Copy the env-based configuration for common_map to ckan.ini
    SCM_PREFIX = "CKANEXT__SPATIAL__COMMON_MAP__"
    if SCM_PREFIX+'TYPE' in os.environ:
        opts = [opt for opt in os.environ if opt.startswith(SCM_PREFIX)]
        for opt in opts:
            add_option_from_env(opt, os.environ[opt])


@logger.wrap
def create_ckanini_configmap():
    ckan_ini_path = ckan_ini

    if KUBE_NAMESPACE:
        # Read the content of the CKAN INI file
        try:
            with open(ckan_ini_path, 'r') as f:
                ckan_ini_content = f.read()
        except FileNotFoundError:
            raise Exception(f"[FATAL] CKAN INI file not found at {ckan_ini_path}.")
        except Exception as e:
            raise Exception(f"[FATAL] Error reading CKAN INI file: {str(e)}")

        # Generate the ConfigMap with the content of the CKAN INI file
        cmap = generate_k8s_configmap('ckan-config', KUBE_NAMESPACE, {'ckan.ini': ckan_ini_content})

        try:
            apply_configmap_to_k8s_cluster(cmap)            
        except:
            logger.error("[FATAL] Could not apply ConfigMap to Cluster!")

    else:
        raise Exception("[FATAL] NAMESPACE NOT DEFINED IN ENV VARS.")
    

#### COMMAND TO GREP TOKEN TO PASS IT TO API POD
#ckan user token add ckan_admin api_token | grep -A 1 "API Token created:" | tail -n 1 | tr -d '\t '


@logger.wrap
def generate_k8s_configmap(configmap_name, namespace, data_dict):
    """
    Generates a Kubernetes ConfigMap YAML structure.
    
    Args:
        configmap_name (str): Name of the ConfigMap.
        namespace (str): Namespace in which the ConfigMap will reside.
        data_dict (dict): Dictionary containing key-value pairs for the ConfigMap.
        
    Returns:
        dict: ConfigMap structure.
    """
    # Define the ConfigMap structure
    configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": configmap_name,
            "namespace": namespace,
        },
        "data": data_dict,
    }

    # Output YAML for verification
    # print("Generated Kubernetes ConfigMap YAML:")
    # print(yaml.dump(configmap))
    return configmap

@logger.wrap
def create_k8s_secret(secret_name, data_dict):
    # Encode data to base64 as required by Kubernetes secrets
    encoded_data = {k: base64.b64encode(v.encode("utf-8")).decode("utf-8") for k, v in data_dict.items()}

    # Define the secret structure
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": KUBE_NAMESPACE,
        },
        "type": "Opaque",
        "data": encoded_data,
    }

    logger.info("Generated Kubernetes Secret YAML for CKAN Admin Token")
    
    return secret

@logger.wrap
def apply_secret_to_cluster(secret):
    v1 = client.CoreV1Api()

    # Create the secret in the specified namespace
    try:
        v1.create_namespaced_secret(
            namespace=KUBE_NAMESPACE,
            body=secret
        )
        logger.info(f"Secret created in namespace ''.")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            logger.error(f"Secret 'CKAN_ADMIN_TOKEN' already exists.")
        else:
            logger.error(f"Failed to create secret: {e}")

@logger.wrap
def apply_configmap_to_k8s_cluster(configmap):
    """
    Applies a Kubernetes ConfigMap to the specified namespace.
    
    Args:
        configmap (dict): ConfigMap structure to apply.
        
    Logs:
        Success or failure message for ConfigMap creation.
    """
    # Initialize Kubernetes client
    v1 = client.CoreV1Api()
    # Create the ConfigMap in the specified namespace
    try:
        v1.create_namespaced_config_map(
            namespace=configmap["metadata"]["namespace"],
            body=configmap
        )
        logger.info(f"ConfigMap '{configmap['metadata']['name']}' created in namespace '{configmap['metadata']['namespace']}'.")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            logger.info(f"ConfigMap '{configmap['metadata']['name']}' already exists.")
        else:
            logger.error(f"Failed to create ConfigMap: {e}")


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    logging.info(f"Configuring {ckan_ini} for STELAR extensions.")
    logger.logger = logging.getLogger("stelar")

    setup_root_path()
    setup_keycloak()
    setup_spatial()
    create_ckanini_configmap()
    issue_api_token()
