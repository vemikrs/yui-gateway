#!/usr/bin/env python3
import os
import sys
import httpx
import re
from azure.identity import ClientSecretCredential

# Load from .env
from dotenv import load_dotenv
load_dotenv()

def extract_resource_info(endpoint_url):
    """Extract subscription, resource group, and account name from Azure OpenAI endpoint"""
    # Example: https://s-8400-resource.cognitiveservices.azure.com/
    # Need to call management API to get resource details

    # Extract account name from domain
    match = re.match(r'https://([^.]+)\.cognitiveservices\.azure\.com/?', endpoint_url)
    if not match:
        raise ValueError(f"Cannot parse account name from endpoint: {endpoint_url}")

    account_name = match.group(1)
    return account_name

def list_deployments_via_management_api():
    """Use Azure Resource Management API to list deployments"""
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    if not all([tenant_id, client_id, client_secret, endpoint]):
        print("Missing required environment variables")
        return False

    try:
        credential = ClientSecretCredential(tenant_id, client_id, client_secret)
        # Use management API token scope
        token = credential.get_token("https://management.azure.com/.default").token

        account_name = extract_resource_info(endpoint)

        # First, find the subscription and resource group by searching for the account
        search_url = "https://management.azure.com/subscriptions?api-version=2022-12-01"

        with httpx.Client(timeout=30) as client:
            # Get subscriptions
            resp = client.get(search_url, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            subscriptions = resp.json().get("value", [])

            # Search for the cognitive services account across subscriptions
            for subscription in subscriptions:
                sub_id = subscription["subscriptionId"]

                # List all cognitive services accounts in this subscription
                accounts_url = f"https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.CognitiveServices/accounts?api-version=2024-10-01"

                try:
                    accounts_resp = client.get(accounts_url, headers={"Authorization": f"Bearer {token}"})
                    accounts_resp.raise_for_status()
                    accounts = accounts_resp.json().get("value", [])

                    # Find our account
                    for account in accounts:
                        if account["name"] == account_name:
                            # Extract resource group from resource ID
                            resource_id = account["id"]
                            resource_group = resource_id.split("/")[4]  # /subscriptions/{sub}/resourceGroups/{rg}/...

                            # Now get deployments for this account
                            deployments_url = f"https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{account_name}/deployments?api-version=2024-10-01"

                            deployments_resp = client.get(deployments_url, headers={"Authorization": f"Bearer {token}"})
                            deployments_resp.raise_for_status()
                            deployments_data = deployments_resp.json()

                            deployments = deployments_data.get("value", [])
                            if deployments:
                                print(f"Available deployments for {account_name}:")
                                for deployment in deployments:
                                    name = deployment["name"]
                                    properties = deployment.get("properties", {})
                                    model = properties.get("model", {})
                                    model_name = model.get("name", "Unknown")
                                    model_version = model.get("version", "Unknown")
                                    sku = deployment.get("sku", {})
                                    capacity = sku.get("capacity", "Unknown")
                                    state = properties.get("provisioningState", "Unknown")

                                    print(f"  - {name}")
                                    print(f"    Model: {model_name} (version: {model_version})")
                                    print(f"    Capacity: {capacity}")
                                    print(f"    State: {state}")
                                    print()
                                return True
                            else:
                                print(f"No deployments found for account: {account_name}")
                                return True

                except Exception as e:
                    # Skip subscriptions we can't access
                    continue

            print(f"Could not find cognitive services account: {account_name}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = list_deployments_via_management_api()
    sys.exit(0 if success else 1)
