from keycloak import KeycloakAdmin,KeycloakPostError
from kubernetes import client, config #need to pip install 
import base64
import yaml
import os

config.load_kube_config()

# Keycloak admin credentials
KEYCLOAK_ADMIN_USERNAME = os.getenv("KEYCLOAK_ADMIN")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD")
# KEYCLOAK_ADMIN_USERNAME = 'admin'
# KEYCLOAK_ADMIN_PASSWORD = 'stelartuc'
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
KEYCLOAK_URL = 'http://keycloak:'+ os.getenv("KEYCLOAK_PORT")

#CLIENT_NAMES
API_CLIENT = os.getenv("KC_API_CLIENT_NAME")
MINIO_CLIENT = os.getenv("KC_MINIO_CLIENT_NAME")
CKAN_CLIENT = os.getenv("KC_CKAN_CLIENT_NAME") #????????????
# KEYCLOAK_URL = 'https://kc.stelar.gr/'

#CLIENTS REDIRECT
API_CLIENT_REDIRECT = os.getenv("KC_API_CLIENT_REDIRECT")
MINIO_CLIENT_REDIRECT = os.getenv("KC_MINIO_CLIENT_REDIRECT")
CKAN_CLIENT_REDIRECT = os.getenv("KC_CKAN_CLIENT_REDIRECT")

#HOME URLS
API_CLIENT_HOME_URL = os.getenv("KC_API_CLIENT_HOME_URL")
MINIO_CLIENT_HOME_URL = os.getenv("KC_MINIO_CLIENT_HOME_URL")
CKAN_CLIENT_HOME_URL = os.getenv("KC_CKAN_CLIENT_HOME_URL")

#ROOT_URL

API_CLIENT_ROOT_URL = os.getenv("KC_API_CLIENT_ROOT_URL",API_CLIENT_HOME_URL)
MINIO_CLIENT_ROOT_URL = os.getenv("KC_MINIO_CLIENT_ROOT_URL",MINIO_CLIENT_HOME_URL)
CKAN_CLIENT_ROOT_URL = os.getenv("KC_CKAN_CLIENT_ROOT_URL",CKAN_CLIENT_HOME_URL)



# Function to initialize Keycloak Admin client
def initialize_keycloak_admin():
    return KeycloakAdmin(server_url=KEYCLOAK_URL,
                         username=KEYCLOAK_ADMIN_USERNAME,
                         password=KEYCLOAK_ADMIN_PASSWORD,
                         realm_name=KEYCLOAK_REALM,
                         verify=True)

# Function to create a client
def create_client(keycloak_admin, client_name, home_url, root_url):
    client_representation = {
            "clientId": client_name,
            "enabled": True,
            "rootUrl": root_url,
            "baseUrl": home_url,
            "redirectUris": ["*"],
            "attributes": {
                "post.logout.redirect.uris": "+"
            },
            "directAccessGrantsEnabled": True
            
        }
    
    client_id = keycloak_admin.create_client(client_representation,skip_exists=True)
    print(f'Client "{client_name}" created successfully with ID: {client_id}')
    return client_id

################### Secret Creation ############################

def create_k8s_secret(secret_name, namespace, data_dict):
    # Encode data to base64 as required by Kubernetes secrets
    encoded_data = {k: base64.b64encode(v.encode("utf-8")).decode("utf-8") for k, v in data_dict.items()}

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
            namespace=secret["metadata"]["namespace"],
            body=secret
        )
        print(f"Secret '{secret['metadata']['name']}' created in namespace '{secret['metadata']['namespace']}'.")
    except client.exceptions.ApiException as e:
        if e.status == 409:
            print(f"Secret '{secret['metadata']['name']}' already exists.")
        else:
            print(f"Failed to create secret: {e}")


############################## MAIN ################################


def main():
    # print("Hello there")

    keycloak_admin = initialize_keycloak_admin()

    clients_name_list = [{"name":MINIO_CLIENT,"home_url":MINIO_CLIENT_HOME_URL,"root_url":MINIO_CLIENT_ROOT_URL},
                         {"name":API_CLIENT,"home_url":API_CLIENT_HOME_URL,"root_url":API_CLIENT_ROOT_URL},
                         {"name":CKAN_CLIENT,"home_url":CKAN_CLIENT_HOME_URL,"root_url":CKAN_CLIENT_ROOT_URL}]
    for client in clients_name_list:
        print(client)

        client_id = create_client(keycloak_admin,client["name"],client["home_url"],client["root_url"])

        client_secret_info = keycloak_admin.get_client_secrets(client_id)
        client_secret = client_secret_info['value']

        print(client["name"]+" Secret:", client_secret)

        secret_name = client["name"]+"-client-secret"
        secret = create_k8s_secret(secret_name,'default',{"secret":client_secret})
        apply_secret_to_cluster(secret)



if __name__ == "__main__":
    main()