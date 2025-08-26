#!/usr/bin/env python3

"""
Verus RPC connection module

Handles RPC setup and communication with multiple chain daemons.
Supports VRSC, CHIPS, VARRR, and VDEX chains.
"""

import os
import sys
import json
import requests
import time
import urllib.parse
from dotenv import load_dotenv

# Import currency mapping from the official dict.py
from dict import normalize_currency_name, get_ticker_by_id

# Default RPC connection settings
VERUS_RPC_HOST = "127.0.0.1"
VERUS_RPC_PORT = 27486
VERUS_RPC_USER = "user"
VERUS_RPC_PASSWORD = "password"

def load_rpc_settings(env_file=".env"):
    """Load RPC connection settings from environment variables"""
    global VERUS_RPC_HOST, VERUS_RPC_PORT, VERUS_RPC_USER, VERUS_RPC_PASSWORD
    
    try:
        # Try to load .env file if it exists
        if os.path.exists(env_file):
            load_dotenv(env_file)
            
        # Parse URL from environment if available
        # Use only VERUS_RPC_* environment variables for consistency
        VERUS_RPC_HOST = os.getenv("VERUS_RPC_HOST", VERUS_RPC_HOST)
        VERUS_RPC_PORT = int(os.getenv("VERUS_RPC_PORT", VERUS_RPC_PORT))
        VERUS_RPC_USER = os.getenv("VERUS_RPC_USER", VERUS_RPC_USER)
        VERUS_RPC_PASSWORD = os.getenv("VERUS_RPC_PASSWORD", VERUS_RPC_PASSWORD)
        
        print(f"Using RPC connection: {VERUS_RPC_HOST}:{VERUS_RPC_PORT} with user {VERUS_RPC_USER}")
        return True
    except Exception as e:
        print(f"Error loading RPC settings: {str(e)}")
        return False

def make_verus_rpc(method, params=None):
    """Make an RPC call to the Verus daemon"""
    return make_rpc_call("VRSC", method, params)

def make_rpc_call(chain, method, params=None, config=None):
    """Make an RPC call to the specified chain daemon"""
    if params is None:
        params = []
    
    # Force reload environment variables for each call
    load_dotenv(".env", override=True)
    
    # Get chain-specific RPC settings
    if chain == "VRSC":
        host = os.getenv("VERUS_RPC_HOST", "127.0.0.1")
        port = int(os.getenv("VERUS_RPC_PORT", "27486"))
        user = os.getenv("VERUS_RPC_USER", "user")
        password = os.getenv("VERUS_RPC_PASSWORD", "password")
    elif chain == "CHIPS":
        host = os.getenv("CHIPS_RPC_HOST", "127.0.0.1")
        port = int(os.getenv("CHIPS_RPC_PORT", "22778"))
        user = os.getenv("CHIPS_RPC_USER", "user")
        password = os.getenv("CHIPS_RPC_PASSWORD", "password")
    elif chain == "VARRR":
        host = os.getenv("VARRR_RPC_HOST", "127.0.0.1")
        port = int(os.getenv("VARRR_RPC_PORT", "20778"))
        user = os.getenv("VARRR_RPC_USER", "user")
        password = os.getenv("VARRR_RPC_PASSWORD", "password")
    elif chain == "VDEX":
        host = os.getenv("VDEX_RPC_HOST", "127.0.0.1")
        port = int(os.getenv("VDEX_RPC_PORT", "21778"))
        user = os.getenv("VDEX_RPC_USER", "user")
        password = os.getenv("VDEX_RPC_PASSWORD", "password")
    else:
        print(f"Warning: Unsupported chain {chain}. Using VRSC settings.")
        host = os.getenv("VERUS_RPC_HOST", "127.0.0.1")
        port = int(os.getenv("VERUS_RPC_PORT", "27486"))
        user = os.getenv("VERUS_RPC_USER", "user")
        password = os.getenv("VERUS_RPC_PASSWORD", "password")
    
    print(f"Using RPC connection: {host}:{port} with user {user} for {chain}")
    
    # Prepare request
    url = f"http://{host}:{port}"
    headers = {"content-type": "application/json"}
    payload = {
        "method": method,
        "params": params,
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
    }
    
    try:
        # Make request with basic auth
        response = requests.post(
            url,
            auth=(user, password),
            headers=headers,
            json=payload,
            timeout=30,
        )
        
        # Check for HTTP errors
        if response.status_code != 200:
            print(f"Error: HTTP status {response.status_code}, {response.text}")
            return None
            
        # Parse JSON response
        result = response.json()
        
        # Check for RPC errors
        if "error" in result and result["error"] is not None:
            error = result["error"]
            print(f"RPC Error: {error}")
            return None
            
        return result.get("result")
        
    except Exception as e:
        print(f"Exception making RPC call: {str(e)}")
        return None

def get_latest_block():
    """Get the latest block height for the chain"""
    try:
        response = make_rpc_call("VRSC", "getinfo", [])
        if response and "blocks" in response:
            return response["blocks"]
        else:
            print("Error getting latest block: Invalid response")
            return None
    except Exception as e:
        print(f"Error getting latest block: {str(e)}")
        return None

def get_currency_name(currency_id):
    """Get currency name from ID using getcurrency RPC and normalize it"""
    try:
        # First try the mapping for a direct match
        ticker = get_ticker_by_id(currency_id)
        if ticker:
            return ticker
            
        # If no direct match, try to get currency info from RPC
        currency_info = make_rpc_call("VRSC", "getcurrency", [currency_id])
        
        if currency_info and "fullyqualifiedname" in currency_info:
            name = currency_info["fullyqualifiedname"]
            # Try to normalize the RPC-returned name
            normalized = normalize_currency_name(name)
            return normalized
            
        elif currency_info and "name" in currency_info:
            name = currency_info["name"]
            # Try to normalize the RPC-returned name
            normalized = normalize_currency_name(name)
            return normalized
            
        else:
            # If all else fails, return the original ID
            return currency_id
            
    except Exception as e:
        print(f"Error getting currency name for {currency_id}: {str(e)}")
        return currency_id

# Initialize RPC settings when the module is imported
load_rpc_settings()

# Basic module test
if __name__ == "__main__":
    print("Testing RPC connection...")
    block = get_latest_block()
    if block:
        print(f"Current block height: {block}")
    else:
        print("Failed to get block height")
