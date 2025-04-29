from kubernetes import client, config
from keycloak import KeycloakOpenID
import yaml
import os
import subprocess
import re
import time
import requests

config.load_incluster_config()
KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE")
# Keycloak Configuration Params
KC_ISSUER = os.getenv("KC_ISSUER")
KC_ROLES_FIELD = os.getenv("KC_QUAY_GROUP_CLAIM")
KC_QUAY_CLIENT_NAME = os.getenv("KC_QUAY_CLIENT_NAME")
KC_QUAY_CLIENT_SECRET = os.getenv("KC_QUAY_CLIENT_SECRET")
KC_PUSHERS_ROLE_NAME = os.getenv("KC_QUAY_PUSHERS")
KC_PULLERS_ROLE_NAME = os.getenv("KC_QUAY_PULLERS")
KC_ADMIN_USER = os.getenv("KC_ADMIN_USER")
KC_ADMIN_PASSWORD = os.getenv("KC_ADMIN_PASSWORD")
KC_REALM = os.getenv("KC_REALM")

# Database Configuration Params
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Storage Config Parameters
MINIO_HOST = os.getenv("MINIO_HOST")
MINIO_SANITIZED_HOST = MINIO_HOST.replace("http://", "").replace("https://", "")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER")
MINIO_ROOT_PASS = os.getenv("MINIO_ROOT_PASSWORD")
MINIO_INSECURE = os.getenv("MC_INSECURE") == "true"
MINIO_BUCKET = os.getenv("MINIO_REGISTRY_BUCKET")

# Generic Params
QUAY_SERVER_HOSTNAME = os.getenv("QUAY_SERVER_HOSTNAME")
QUAY_REDIS_HOSTNAME = os.getenv("QUAY_REDIS_HOSTNAME")
QUAY_REDIS_PORT = os.getenv("QUAY_REDIS_PORT")


#----------------- KEYCLOAK -----------------
def mc_setup():
    subprocess.run(
        [
            "mc",
            "alias",
            "set",
            "myminio",
            MINIO_HOST,
            MINIO_ROOT_USER,
            MINIO_ROOT_PASS,
        ],
        capture_output=True,
        text=True,
        check=True,
    )


#----------------- Tool Registry Configuration -----------------
def generate_tool_registry_configuration():
    registry_config_yaml = "config.yaml"
    if KUBE_NAMESPACE:
        try:
            with open(registry_config_yaml, "r") as f:
                registry_file = f.read()
            registry_yaml = yaml.safe_load(registry_file)
        except FileNotFoundError:
            raise Exception(
                f"[FATAL] Registry config file not found at {registry_file}."
            )
        except Exception as e:
            raise Exception(f"[FATAL] Error reading registry config file: {str(e)}")

        print("[SETUP] Configuring the YAML with provided params")

        # Acquire MinIO set of permanent keys to provide quay with.
        s3_creds = get_minio_keys()

        # Configure REDIS
        registry_yaml["BUILDLOGS_REDIS"]["host"] = QUAY_REDIS_HOSTNAME
        registry_yaml["BUILDLOGS_REDIS"]["port"] = int(QUAY_REDIS_PORT)
        registry_yaml["USER_EVENTS_REDIS"]["host"] = QUAY_REDIS_HOSTNAME
        registry_yaml["USER_EVENTS_REDIS"]["port"] = int(QUAY_REDIS_PORT)

        # Configure DB_URL
        registry_yaml["DB_URI"] = (
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        )

        # Configure DISTRIBUTED_STORAGE_CONFIG
        registry_yaml["DISTRIBUTED_STORAGE_CONFIG"]["default"][1][
            "hostname"
        ] = MINIO_SANITIZED_HOST
        registry_yaml["DISTRIBUTED_STORAGE_CONFIG"]["default"][1]["access_key"] = (
            s3_creds["access_key"]
        )
        registry_yaml["DISTRIBUTED_STORAGE_CONFIG"]["default"][1]["secret_key"] = (
            s3_creds["secret_key"]
        )
        registry_yaml["DISTRIBUTED_STORAGE_CONFIG"]["default"][1][
            "bucket_name"
        ] = MINIO_BUCKET
        registry_yaml["DISTRIBUTED_STORAGE_CONFIG"]["default"][1]["is_secure"] = not MINIO_INSECURE
    

        # Configure server hostname
        registry_yaml["SERVER_HOSTNAME"] = QUAY_SERVER_HOSTNAME
        registry_yaml["PREFERRED_URL_SCHEME"] = "http" if MINIO_INSECURE else "https"

        # Configure OIDC params
        registry_yaml["OIDC_LOGIN_CONFIG"]["CLIENT_ID"] = KC_QUAY_CLIENT_NAME
        registry_yaml["OIDC_LOGIN_CONFIG"]["CLIENT_SECRET"] = KC_QUAY_CLIENT_SECRET
        registry_yaml["OIDC_LOGIN_CONFIG"]["OIDC_SERVER"] = KC_ISSUER
        registry_yaml["OIDC_LOGIN_CONFIG"]["PREFERRED_GROUP_CLAIM_NAME"] = KC_ROLES_FIELD
        registry_yaml["OIDC_LOGIN_CONFIG"]["DEBUGGING"] = MINIO_INSECURE

        cmap = generate_k8s_configmap(
            "registry-config", KUBE_NAMESPACE, {"config.yaml": yaml.dump(registry_yaml)}
        )
        print(
            f"[SETUP] Generated YAML succesfully, will apply it to the K8s namespace '{KUBE_NAMESPACE}'"
        )

        try:
            apply_configmap_to_k8s_cluster(cmap)
            print("[SETUP] Applied ConfigMap To K8s namespace '{KUBE_NAMESPACE}'")
        except Exception as e:
            print(f"[FATAL] Failed to apply ConfigMap to Kubernetes cluster: {str(e)}")

        print("[SETUP] Will wait for QUAY to come up, to configure orgs and teams...")

        timeout = 300  # 5 minutes
        interval = 10
        elapsed = 0
        quay_url = "http://quay:8080/api/v1/discovery"
        print(f"[SETUP] Checking QUAY status at {quay_url}")

        while elapsed < timeout:
            try:
                response = requests.get(quay_url)
                if response.status_code == 200:
                    print("[SETUP] QUAY is up and running.")
                    break
                else:
                    print(f"[SETUP] QUAY returned status code {response.status_code}")
            except requests.exceptions.RequestException:
                print("[SETUP] Waiting for QUAY to come up...")

            time.sleep(interval)
            elapsed += interval
        else:
            raise Exception(
                "[FATAL] QUAY did not come up within 3 minutes. Aborting configuration, good luck!"
            )

        # Issue a token for the administrator account to create orgs and teams
        try:
            kopenid = KeycloakOpenID(
                server_url="http://keycloak:8080",
                realm_name=KC_REALM,
                client_id=KC_QUAY_CLIENT_NAME,
                client_secret_key=KC_QUAY_CLIENT_SECRET,
                verify=False,
            )

            token = kopenid.token(
                username=KC_ADMIN_USER,
                password=KC_ADMIN_PASSWORD,
                grant_type="password",
            )
        except Exception as e:
            print(
                f"[FATAL] Could not acquire OAuth2.0 due to unexpected error: {str(e)}"
            )

        tkn = token.get("access_token", None)
        if tkn:
            
            #----------------- ORGANIZATION CREATION -----------------
            # Create organization STELAR
            org_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {tkn}",
            }
            data = {"name": "stelar"}
            try:
                response = requests.post(org_url, headers=headers, json=data, allow_redirects=True, verify=False)
                if response.status_code == 201:
                    print("[SETUP] Organization 'stelar' created successfully.")
                else:
                    print(
                        f"[FATAL] Failed to create organization. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to create organization failed: {str(e)}")
                return

            #----------------- TEAM CREATION -----------------
            # Create pullers team
            team_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization/stelar/team/{KC_PULLERS_ROLE_NAME}"
            team_data = {"name": KC_PULLERS_ROLE_NAME, "role": "member"}
            try:
                response = requests.put(team_url, headers=headers, json=team_data, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    print(f"[SETUP] Team {KC_PULLERS_ROLE_NAME} created successfully.")
                else:
                    print(
                        f"[FATAL] Failed to create team. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to create team failed: {str(e)}")
                return

            # Create pushers team
            team_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization/stelar/team/{KC_PUSHERS_ROLE_NAME}"
            team_data = {"name": KC_PUSHERS_ROLE_NAME, "role": "creator"}
            try:
                response = requests.put(team_url, headers=headers, json=team_data, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    print(f"[SETUP] Team {KC_PUSHERS_ROLE_NAME} created successfully.")
                else:
                    print(
                        f"[FATAL] Failed to create team. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to create team failed: {str(e)}")
                return
            
            #----------------- TEAM SYNCING -----------------

            # Enable team syncing with OIDC for pushers
            sync_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization/stelar/team/{KC_PUSHERS_ROLE_NAME}/syncing"
            sync_data = {"group_name": KC_PUSHERS_ROLE_NAME}
            try:
                response = requests.post(sync_url, headers=headers, json=sync_data, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    print(
                        f"[SETUP] Team syncing enabled successfully for {KC_PUSHERS_ROLE_NAME}."
                    )
                else:
                    print(
                        f"[FATAL] Failed to enable team syncing. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to enable team syncing failed: {str(e)}")
                return

            # Enable team syncing with OIDC for pullers
            sync_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization/stelar/team/{KC_PULLERS_ROLE_NAME}/syncing"
            sync_data = {"group_name": KC_PULLERS_ROLE_NAME}
            try:
                response = requests.post(sync_url, headers=headers, json=sync_data, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    print(
                        f"[SETUP] Team syncing enabled successfully for {KC_PULLERS_ROLE_NAME}."
                    )
                else:
                    print(
                        f"[FATAL] Failed to enable team syncing. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to enable team syncing failed: {str(e)}")
                return
                      
            #----------------- REPOSITORY DELEGATION -----------------

            # Enable org repository default delegation permissions for pushers
            delegation_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization/stelar/prototypes"
            delegation_data = {
                "delegate": {
                    "name": KC_PUSHERS_ROLE_NAME,
                    "kind": "team",
                    "is_robot": False,
                    "is_org_member": True,
                },
                "role": "write",
            }
            try:
                response = requests.post(delegation_url, headers=headers, json=delegation_data, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    print(f"[SETUP] Default delegation permissions set successfully for {KC_PUSHERS_ROLE_NAME}.")
                else:
                    print(
                        f"[FATAL] Failed to set default delegation permissions. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to set default delegation permissions failed: {str(e)}")
                return

            # Enable org repository default delegation permissions for pullers
            delegation_url = f"http://{QUAY_SERVER_HOSTNAME}/api/v1/organization/stelar/prototypes"
            delegation_data = {
                "delegate": {
                    "name": KC_PULLERS_ROLE_NAME,
                    "kind": "team",
                    "is_robot": False,
                    "is_org_member": True,
                },
                "role": "read",
            }
            try:
                response = requests.post(delegation_url, headers=headers, json=delegation_data, allow_redirects=True, verify=False)
                if response.status_code == 200:
                    print(f"[SETUP] Default delegation permissions set succesfully for {KC_PULLERS_ROLE_NAME}.")
                else:
                    print(
                        f"[FATAL] Failed to set default delegation permissions. Status code: {response.status_code}, Response: {response.text}"
                    )
                    return
            except requests.exceptions.RequestException as e:
                print(f"[FATAL] Request to set default delegation permissions failed: {str(e)}")
                return
            
            print(f"[SETUP] Configuration Completed")

        else:
            print(f"[FATAL] Could not find OAuth2.0 in the KC response")

    else:
        raise Exception("[FATAL] NAMESPACE NOT DEFINED IN ENV VARS.")


def get_minio_keys():
    try:
        result = subprocess.run(
            ["mc", "admin", "accesskey", "create", "myminio/"],
            capture_output=True,
            text=True,
            check=True,
        )

        access_key_match = re.search(r"Access Key:\s*(\S+)", result.stdout)
        secret_key_match = re.search(r"Secret Key:\s*(\S+)", result.stdout)

        if access_key_match and secret_key_match:
            return {
                "access_key": access_key_match.group(1),
                "secret_key": secret_key_match.group(1),
            }
        else:
            print("[FATAL] Failed to generate S3 credentials set")
    except Exception as e:
        print(f"[FATAL] Failed to generate S3 credentials set: {str(e)}")

    return None


#----------------- ConfigMap Generation -----------------
def apply_configmap_to_k8s_cluster(configmap):
    """
    Applies a Kubernetes ConfigMap to the specified namespace.

    Args:
        configmap (dict): ConfigMap structure to apply.
    """
    v1 = client.CoreV1Api()
    try:
        v1.create_namespaced_config_map(
            namespace=configmap["metadata"]["namespace"], body=configmap
        )
    except Exception:
        raise


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
    configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": configmap_name,
            "namespace": namespace,
        },
        "data": data_dict,
    }

    return configmap


#----------------- MAIN -----------------
if __name__ == "__main__":
    mc_setup()
    generate_tool_registry_configuration()
