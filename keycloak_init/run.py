from keycloak import KeycloakAdmin, KeycloakPostError
from kubernetes import client, config  # need to pip install
import base64
import yaml
import os
import subprocess

config.load_incluster_config()

# Keycloak admin credentials
KEYCLOAK_ADMIN_USERNAME = os.getenv("KEYCLOAK_ADMIN")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
KEYCLOAK_URL = "http://keycloak:" + os.getenv("KEYCLOAK_PORT")

KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE")

# CLIENT_NAMES
API_CLIENT = os.getenv("KC_API_CLIENT_NAME")
MINIO_CLIENT = os.getenv("KC_MINIO_CLIENT_NAME")
CKAN_CLIENT = os.getenv("KC_CKAN_CLIENT_NAME")  # ????????????

# CLIENTS REDIRECT
API_CLIENT_REDIRECT = os.getenv("KC_API_CLIENT_REDIRECT")
MINIO_CLIENT_REDIRECT = os.getenv("KC_MINIO_CLIENT_REDIRECT")
CKAN_CLIENT_REDIRECT = os.getenv("KC_CKAN_CLIENT_REDIRECT")

# HOME URLS
API_CLIENT_HOME_URL = os.getenv("KC_API_CLIENT_HOME_URL")
MINIO_CLIENT_HOME_URL = os.getenv("KC_MINIO_CLIENT_HOME_URL")
CKAN_CLIENT_HOME_URL = os.getenv("KC_CKAN_CLIENT_HOME_URL")

# ROOT_URL

API_CLIENT_ROOT_URL = os.getenv("KC_API_CLIENT_ROOT_URL", API_CLIENT_HOME_URL)
MINIO_CLIENT_ROOT_URL = os.getenv("KC_MINIO_CLIENT_ROOT_URL", MINIO_CLIENT_HOME_URL)
CKAN_CLIENT_ROOT_URL = os.getenv("KC_CKAN_CLIENT_ROOT_URL", CKAN_CLIENT_HOME_URL)

# QUAY REGISTRY ROLES
QUAY_PUSHERS_ROLE = os.getenv("KC_QUAY_PUSHERS")
QUAY_PULLERS_ROLE = os.getenv("KC_QUAY_PULLERS")
QUAY_CLAIM_NAME = os.getenv("KC_QUAY_GROUP_CLAIM")

################### Keycloak Section ############################


# Function to initialize Keycloak Admin client
def initialize_keycloak_admin():
    return KeycloakAdmin(
        server_url=KEYCLOAK_URL,
        username=KEYCLOAK_ADMIN_USERNAME,
        password=KEYCLOAK_ADMIN_PASSWORD,
        realm_name=KEYCLOAK_REALM,
        verify=False,
    )


def create_realm_role(keycloak_admin, role_name):
    realm_role = {
        "name": role_name,
        "composite": True,
        "clientRole": False,
        "containerId": KEYCLOAK_REALM,
    }
    keycloak_admin.create_realm_role(realm_role, skip_exists=True)

    return role_name


# Function to create a client
def create_client(keycloak_admin, client_name, home_url, root_url):
    client_representation = {
        "clientId": client_name,
        "enabled": True,
        "rootUrl": root_url,
        "baseUrl": home_url,
        "redirectUris": ["*"],
        "attributes": {"post.logout.redirect.uris": "+"},
        "directAccessGrantsEnabled": True,
    }

    client_id = keycloak_admin.create_client(client_representation, skip_exists=True)
    print(f'Client "{client_name}" created successfully with ID: {client_id}')
    return client_id


# Function creating a keycloak client scope
def create_client_scope(
    keycloak_admin,
    client_id,
    name,
    claim_name,
    mapper_name,
    mapper_type="oidc-usermodel-client-role-mapper",
):
    protocol_mapper = {
        "name": mapper_name,
        "protocol": "openid-connect",
        "protocolMapper": mapper_type,
        "consentRequired": False,
        "config": {
            "claim.name": claim_name,
            "jsonType.label": "String",
            "id.token.claim": "true",
            "access.token.claim": "true",
            "multivalued": "true",
        },
    }

    scope = {
        "name": name,
        "protocol": "openid-connect",
    }

    client_scope_id = keycloak_admin.create_client_scope(scope, skip_exists=True)
    keycloak_admin.add_mapper_to_client_scope(client_scope_id, protocol_mapper)

    keycloak_admin.add_client_default_client_scope(
        client_id,
        client_scope_id,
        {
            "realm": "master",
            "client": MINIO_CLIENT,
            "clientScopeId": "minio_auth_scope",
        },
    )


# Function to create a keycloak client role
def create_client_role(keycloak_admin, client_name, client_id, role_name):
    print(client_id)
    keycloak_admin.create_client_role(client_id, {"name": role_name}, skip_exists=True)
    print(f'Role "{role_name}" created successfully for client "{client_name}".')
    return role_name


# Enables service account to a client in keycloak
def enable_service_account(keycloak_admin, client_id):
    try:
        # Retrieve the client configuration
        client_representation = keycloak_admin.get_client(client_id)

        # Update the configuration to enable service accounts
        client_representation["serviceAccountsEnabled"] = True
        client_representation["authorizationServicesEnabled"] = True

        # Update the client with the modified configuration
        keycloak_admin.update_client(client_id, client_representation)
        print(f"Service account enabled for client with ID: {client_id}")

        role = keycloak_admin.get_realm_role("admin")
        print(f"Retrieved existing role: {role}")

        service_account_user = keycloak_admin.get_client_service_account_user(client_id)
        service_account_user_id = service_account_user["id"]

        # Assign the admin role to the service account user
        keycloak_admin.assign_realm_roles(service_account_user_id, [role])
        print(f"Admin role assigned to service account for client ID: {client_id}")

    except KeycloakPostError as e:
        print(f"Failed to enable service account: {e}")
        raise


# creates an open id configuration between keycloak and minIO
def minio_openID_config(keycloak_admin, client_id):
    # Base command for setting the alias
    alias_command = (
        "mc alias set myminio "
        + os.getenv("MINIO_API_DOMAIN")
        + " "
        + os.getenv("MINIO_ROOT_USER")
        + " "
        + os.getenv("MINIO_ROOT_PASSWORD")
    )

    # Check if MINIO_INSECURE_MC is set to True and append --insecure. Used for minikube deployment
    if os.getenv("MINIO_INSECURE_MC", "False").lower() == "true":
        alias_command += " --insecure"

    subprocess.run(alias_command, shell=True, check=True)

    client_secret = keycloak_admin.get_client_secrets(client_id)
    client_secr_value = client_secret.get("value")

    command = (
        "mc idp openid add myminio stelar-sso "
        "client_id="
        + MINIO_CLIENT
        + " client_secret="
        + client_secr_value
        + " config_url="
        + KEYCLOAK_URL
        + "/realms/master/.well-known/openid-configuration "
        'claim_name=policy display_name="STELAR SSO" scopes=openid '
        "redirect_uri=" + os.getenv("KC_MINIO_CLIENT_REDIRECT")
    )

    # Check if MINIO_INSECURE_MC is set to True and append --insecure. Used for minikube deployment
    if os.getenv("MINIO_INSECURE_MC", "False").lower() == "true":
        print("Entering insecure mode...")
        command += " --insecure"

    print("Executing IDP setup command...")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    print("Output:", result.stdout)
    if result.stderr:
        print("Error:", result.stderr)

    # Restart MinIO service and capture output
    print("Attempting to restart MinIO service...")
    restart_command = "mc admin service restart myminio"
    # Check if MINIO_INSECURE_MC is set to True and append --insecure
    if os.getenv("MINIO_INSECURE_MC", "False").lower() == "true":
        print("Entering insecure mode...")
        restart_command += " --insecure"

    restart_result = subprocess.run(
        f'script -q -c "{restart_command}"', shell=True, check=True
    )

    print("Restart Command Output:", restart_result.stdout)
    if restart_result.stderr:
        print("Restart Command Error:", restart_result.stderr)


################### Secret Creation ############################


def create_k8s_secret(secret_name, namespace, data_dict):
    # Encode data to base64 as required by Kubernetes secrets
    encoded_data = {
        k: base64.b64encode(v.encode("utf-8")).decode("utf-8")
        for k, v in data_dict.items()
    }

    # Define the secret structure
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
        },
        "type": "Opaque",
        "data": encoded_data,
    }

    # Output YAML for verification
    print("Generated Kubernetes Secret YAML:")
    print(yaml.dump(secret))

    return secret


# Function to apply the secret to the Kubernetes cluster
def apply_secret_to_cluster(secret):
    # Initialize Kubernetes client
    v1 = client.CoreV1Api()

    # Create the secret in the specified namespace
    try:
        v1.create_namespaced_secret(
            namespace=secret["metadata"]["namespace"], body=secret
        )
        print(
            f"Secret '{secret['metadata']['name']}' created in namespace '{secret['metadata']['namespace']}'."
        )
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"Secret '{secret['metadata']['name']}' already exists.")
        else:
            print(f"Failed to create secret: {e}")


############################## MAIN ################################


def main():

    keycloak_admin = initialize_keycloak_admin()

    clients_name_list = [
        {
            "name": API_CLIENT,
            "home_url": API_CLIENT_HOME_URL,
            "root_url": API_CLIENT_ROOT_URL,
        },
        {
            "name": MINIO_CLIENT,
            "home_url": MINIO_CLIENT_HOME_URL,
            "root_url": MINIO_CLIENT_ROOT_URL,
        },
        {
            "name": CKAN_CLIENT,
            "home_url": CKAN_CLIENT_HOME_URL,
            "root_url": CKAN_CLIENT_ROOT_URL,
        },
    ]
    for client in clients_name_list:
        print(client)

        client_id = create_client(
            keycloak_admin, client["name"], client["home_url"], client["root_url"]
        )

        # keycloak API client initializations
        if client["name"] == API_CLIENT:
            enable_service_account(keycloak_admin, client_id)

        # keycloak MinIO client initializations
        if client["name"] == MINIO_CLIENT:
            enable_service_account(keycloak_admin, client_id)

            try:
                create_client_scope(
                    keycloak_admin,
                    client_id,
                    "minio_auth_scope",
                    "policy",
                    "client_role_mapper",
                )

            except KeycloakPostError as err:
                print("This client scope already Exists")

            try:
                scopeData = keycloak_admin.get_client_scope_by_name("minio_auth_scope")
                api_client_id = keycloak_admin.get_client_id(API_CLIENT)
                keycloak_admin.add_client_default_client_scope(
                    api_client_id,
                    scopeData["id"],
                    {
                        "realm": "master",
                        "client": API_CLIENT,
                        "clientScopeId": "minio_auth_scope",
                    },
                )
            except:
                print("Scope already assigned")

            create_client_role(keycloak_admin, MINIO_CLIENT, client_id, "consoleAdmin")
            keycloak_admin.assign_client_role(
                keycloak_admin.get_user_id("admin"),
                client_id,
                keycloak_admin.get_client_role(client_id, "consoleAdmin"),
            )

        client_secret_info = keycloak_admin.get_client_secrets(client_id)
        client_secret = client_secret_info["value"]

        print(client["name"] + " Secret:", client_secret)

        secret_name = client["name"] + "-client-secret"
        secret = create_k8s_secret(
            secret_name, KUBE_NAMESPACE, {"secret": client_secret}
        )
        apply_secret_to_cluster(secret)

    minio_client_id = keycloak_admin.get_client_id(MINIO_CLIENT)
    client_role = keycloak_admin.get_client_role(minio_client_id, "consoleAdmin")
    print(f"Retrieved existing role: {client_role}")

    api_client_id = keycloak_admin.get_client_id(API_CLIENT)
    service_account_user = keycloak_admin.get_client_service_account_user(api_client_id)
    service_account_user_id = service_account_user["id"]

    # Assign the admin role to the service account user
    keycloak_admin.assign_client_role(
        service_account_user_id, minio_client_id, [client_role]
    )
    print(
        f"ConsoleAdmin role assigned to service account for client ID: {api_client_id}"
    )

    # minio_client_id = keycloak_admin.get_client_id(MINIO_CLIENT)
    minio_openID_config(keycloak_admin, minio_client_id)

    # Create the realm roles for registry access and the scope for mapping them in the token
    create_realm_role(keycloak_admin, QUAY_PUSHERS_ROLE)
    create_realm_role(keycloak_admin, QUAY_PULLERS_ROLE)
    create_client_scope(
        keycloak_admin,
        api_client_id,
        "registry_scope",
        QUAY_CLAIM_NAME,
        "registry_mapper",
        "oidc-usermodel-realm-role-mapper",
    )


if __name__ == "__main__":
    main()
