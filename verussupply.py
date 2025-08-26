#!/usr/bin/env python3
"""
VRSC Supply Endpoint
Provides VRSC total supply, converter reserves, and circulating supply information
"""

import json
import os
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for complete VRSC supply response (10-minute TTL)
_supply_response_cache = {
    'response': None,
    'timestamp': 0,
    'ttl': 600  # 10 minutes in seconds
}

def get_vrsc_reserves_from_converters():
    """
    Extract total VRSC reserves from all converters in converter_discovery.json
    
    Returns:
        tuple: (total_vrsc_reserves, converter_details_list)
    """
    total_vrsc_reserves = 0.0
    converter_details = []
    
    try:
        converter_discovery_file = '/home/dev/Desktop/F0rked/API/API_v2/API_v8/converter_discovery.json'
        
        if not os.path.exists(converter_discovery_file):
            logger.warning(f"Converter discovery file not found: {converter_discovery_file}")
            return total_vrsc_reserves, converter_details
        
        with open(converter_discovery_file, 'r') as f:
            data = json.load(f)
        
        # Extract VRSC reserves from all active converters
        for converter in data.get('active_converters', []):
            converter_name = converter.get('name', 'Unknown')
            
            # Look through reserve currencies for VRSC
            for reserve_currency in converter.get('reserve_currencies', []):
                if reserve_currency.get('ticker') == 'VRSC':
                    vrsc_amount = float(reserve_currency.get('reserves', 0))
                    if vrsc_amount > 0:
                        total_vrsc_reserves += vrsc_amount
                        converter_details.append({
                            'converter': converter_name,
                            'vrsc_reserve': vrsc_amount,
                            'currency_id': reserve_currency.get('currency_id', ''),
                            'chain': converter.get('chain', 'Unknown')
                        })
                        logger.info(f"Found {vrsc_amount} VRSC in {converter_name} converter")
                    break
        
        logger.info(f"Total VRSC in converters: {total_vrsc_reserves} from {len(converter_details)} converters")
        return total_vrsc_reserves, converter_details
        
    except Exception as e:
        logger.error(f"Error reading converter discovery file: {e}")
        return total_vrsc_reserves, converter_details

# Custom JSON response for pretty formatting
class PrettyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            jsonable_encoder(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(',', ': ')
        ).encode('utf-8')

def _is_supply_response_cache_valid():
    """Check if the cached supply response is still valid"""
    current_time = time.time()
    return (_supply_response_cache['response'] is not None and 
            current_time - _supply_response_cache['timestamp'] < _supply_response_cache['ttl'])

def _update_supply_response_cache(response):
    """Update the supply response cache with complete response"""
    _supply_response_cache['response'] = response
    _supply_response_cache['timestamp'] = time.time()
    logger.info(f" VRSC supply response cached for {_supply_response_cache['ttl']} seconds")

async def get_vrsc_supply():
    """
    Get VRSC supply information including total supply, VRSC in converters, and circulating supply
    Caches complete response for 10 minutes to reduce external API calls and file I/O
    """
    # Check cache first
    if _is_supply_response_cache_valid():
        cache_age = time.time() - _supply_response_cache['timestamp']
        logger.info(f" Serving cached VRSC supply data (age: {cache_age:.1f}s)")
        return _supply_response_cache['response']
    
    logger.info(" Cache expired, generating fresh VRSC supply data...")
    
    try:
        from verus_rpc import make_rpc_call
        from cache_manager import get_cache_manager
        
        # Method 1: Try external Verus API for total supply
        total_supply = None
        try:
            logger.info("Attempting external Verus API...")
            import requests
            
            api_url = "https://api.verus.services/verus/getcurrency/VRSC"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'supply' in data['result']:
                    total_supply = float(data['result']['supply'])
                    logger.info(f"✅ Got total supply from external API: {total_supply:,.2f} VRSC")
                else:
                    logger.warning("External API response missing supply field")
            else:
                logger.warning(f"External API returned status {response.status_code}")
                
        except Exception as e:
            logger.warning(f"External API failed: {e}")
        
        # Method 2: Try getblockchaininfo for moneysupply
        if total_supply is None:
            try:
                logger.info("Attempting getblockchaininfo RPC call...")
                result = make_rpc_call('VRSC', 'getblockchaininfo', [])
                logger.info(f"getblockchaininfo result keys: {list(result.keys()) if result else 'None'}")
                if result and 'moneysupply' in result:
                    total_supply = float(result['moneysupply'])
                    logger.info(f"Found moneysupply: {total_supply}")
                elif result and 'valuepools' in result:
                    logger.info(f"Found valuepools: {result['valuepools']}")
                else:
                    logger.warning(f"No moneysupply field in getblockchaininfo")
            except Exception as e:
                logger.warning(f"Failed to get moneysupply from getblockchaininfo: {e}")
        
        # Method 2: Try getcurrency for VRSC
        if total_supply is None:
            try:
                logger.info("Attempting getcurrency VRSC RPC call...")
                result = make_rpc_call('VRSC', 'getcurrency', ['VRSC'])
                logger.info(f"getcurrency VRSC result: {result}")
                if result and 'supply' in result:
                    total_supply = float(result['supply'])
                    logger.info(f"Found supply: {total_supply}")
                else:
                    logger.warning(f"No supply field in getcurrency result: {result}")
            except Exception as e:
                logger.warning(f"Failed to get supply from getcurrency: {e}")
        
        # Method 3: Try coinsupply RPC call (correct format from docs)
        if total_supply is None:
            try:
                logger.info("Attempting coinsupply RPC call without height...")
                result = make_rpc_call('VRSC', 'coinsupply', [])
                print(f"DEBUG: coinsupply result: {result}")
                logger.info(f"coinsupply result keys: {list(result.keys()) if result else 'None'}")
                if result and 'total' in result:
                    total_supply = float(result['total'])
                    logger.info(f"Found total supply: {total_supply}")
                    print(f"DEBUG: Found total supply: {total_supply}")
                elif result and 'supply' in result:
                    total_supply = float(result['supply'])
                    logger.info(f"Found transparent supply: {total_supply}")
                    print(f"DEBUG: Found transparent supply: {total_supply}")
                else:
                    logger.warning(f"Unexpected coinsupply result format: {result}")
            except Exception as e:
                print(f"DEBUG: coinsupply failed: {e}")
                logger.warning(f"Failed to get supply from coinsupply: {e}")
        
        # Method 3b: Try coinsupply with explicit current height
        if total_supply is None:
            try:
                logger.info("Getting current block height for coinsupply...")
                block_result = make_rpc_call('VRSC', 'getblockcount', [])
                print(f"DEBUG: getblockcount result: {block_result}")
                if block_result and isinstance(block_result, int):
                    current_height = block_result
                    logger.info(f"Attempting coinsupply with height {current_height}...")
                    result = make_rpc_call('VRSC', 'coinsupply', [current_height])
                    print(f"DEBUG: coinsupply with height result: {result}")
                    if result and 'total' in result:
                        total_supply = float(result['total'])
                        logger.info(f"Found total supply with height: {total_supply}")
                        print(f"DEBUG: Found total supply with height: {total_supply}")
                    elif result and 'supply' in result:
                        total_supply = float(result['supply'])
                        logger.info(f"Found transparent supply with height: {total_supply}")
                        print(f"DEBUG: Found transparent supply with height: {total_supply}")
            except Exception as e:
                print(f"DEBUG: coinsupply with height failed: {e}")
                logger.warning(f"Failed to get supply from coinsupply with height: {e}")
        
        # Method 4: Try gettxoutsetinfo RPC call
        if total_supply is None:
            try:
                logger.info("Attempting gettxoutsetinfo RPC call...")
                result = make_rpc_call('VRSC', 'gettxoutsetinfo', [])
                logger.info(f"gettxoutsetinfo result: {result}")
                if result and 'total_amount' in result:
                    total_supply = float(result['total_amount'])
                    logger.info(f"Found total_amount: {total_supply}")
                else:
                    logger.warning(f"No total_amount field in gettxoutsetinfo result: {result}")
            except Exception as e:
                logger.warning(f"Failed to get supply from gettxoutsetinfo: {e}")
        
        # Method 6: Try getting VRSC currency state from converter data
        if total_supply is None:
            try:
                logger.info("Attempting to get VRSC supply from getcurrencystate...")
                result = make_rpc_call('VRSC', 'getcurrencystate', ['VRSC'])
                logger.info(f"getcurrencystate VRSC result keys: {list(result.keys()) if result else 'None'}")
                if result and 'supply' in result:
                    total_supply = float(result['supply'])
                    logger.info(f"Found supply in currencystate: {total_supply}")
                elif result and 'currencystate' in result and 'supply' in result['currencystate']:
                    total_supply = float(result['currencystate']['supply'])
                    logger.info(f"Found supply in nested currencystate: {total_supply}")
            except Exception as e:
                logger.warning(f"Failed to get supply from getcurrencystate: {e}")
        
        # Method 7: Try listcurrencies to see available methods
        if total_supply is None:
            try:
                logger.info("Attempting listcurrencies to debug available data...")
                result = make_rpc_call('VRSC', 'listcurrencies', [])
                if result and isinstance(result, list):
                    for currency in result:
                        if currency.get('currencyid') == 'i5w5MuNik5NtLcYmNzcvaoixooEebB6MGV' or currency.get('name') == 'VRSC':
                            logger.info(f"Found VRSC currency data: {currency}")
                            if 'supply' in currency:
                                total_supply = float(currency['supply'])
                                logger.info(f"Found supply in listcurrencies: {total_supply}")
                                break
            except Exception as e:
                logger.warning(f"Failed to get supply from listcurrencies: {e}")
        
        # Method 8: Fail if RPC doesn't work - NO ESTIMATES
        if total_supply is None:
            # Log what RPC methods we tried for debugging
            logger.error("All RPC methods failed to retrieve VRSC total supply:")
            logger.error("- getinfo (moneysupply)")
            logger.error("- getblockchaininfo (moneysupply)")
            logger.error("- getcurrency VRSC (supply)")
            logger.error("- coinsupply")
            logger.error("- gettxoutsetinfo (total_amount)")
            logger.error("- getcurrencystate VRSC (supply)")
            logger.error("- listcurrencies (supply)")
            
            raise HTTPException(
                status_code=503,
                detail="Unable to retrieve VRSC total supply from RPC. All methods failed. No fallback estimates allowed."
            )
        
        # Get VRSC reserves from converters using dedicated function
        vrsc_in_converters, converter_details = get_vrsc_reserves_from_converters()
        data_source = "converter_discovery_file"
        
        # Calculate circulating supply
        circulating_supply = total_supply - vrsc_in_converters
        
        # Prepare response with CMC-compliant structure
        response_data = {
            "total_supply": total_supply,
            "circulating_supply": circulating_supply,
            "locked_supply": {
                "vrsc_in_converters": vrsc_in_converters,
                "converter_count": len(converter_details),
                "converter_details": converter_details
            },
            "supply_methodology": {
                "total_supply_source": "External Verus API (api.verus.services)",
                "locked_supply_source": "Converter smart contracts",
                "calculation": "Circulating = Total - Locked in Converters",
                "cmc_compliance": "Excludes smart contract locked tokens per CMC standards",
                "update_frequency": "60 seconds (cache refresh cycle)"
            },
            "timestamp": datetime.now().isoformat(),
            "data_source": data_source
        }
        
        response = PrettyJSONResponse(content=response_data)
        
        # Cache the complete response for future requests
        _update_supply_response_cache(response)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in verussupply endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get VRSC supply information: {str(e)}"
        )
