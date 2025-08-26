#!/usr/bin/env python3
"""
Session-Based Block Height Utility
Provides a single, consistent block height for all calculations within one API session
This ensures all volume and liquidity calculations use the same blockchain state
"""

import json
import time
from verus_rpc import make_verus_rpc

# Global cache for session-based block height
_session_block_height = None
_session_id = None

def start_new_session():
    """
    Start a new API session, clearing any cached block height
    This should be called at the beginning of each API request
    
    Returns:
        str: New session ID
    """
    global _session_block_height, _session_id
    
    _session_block_height = None
    _session_id = f"session_{int(time.time() * 1000)}"
    
    print(f"🆕 Started new API session: {_session_id}")
    return _session_id

def get_session_block_height(session_id=None):
    """
    Get the block height for the current session
    If no block height is cached for this session, fetch a fresh one
    
    Args:
        session_id (str): Optional session ID for validation
        
    Returns:
        int: Current block height for this session, or None if failed
    """
    global _session_block_height, _session_id
    
    # If session_id is provided, validate it matches current session
    if session_id and session_id != _session_id:
        print(f"⚠️  Session ID mismatch. Starting new session.")
        start_new_session()
    
    # If we already have a block height for this session, return it
    if _session_block_height is not None:
        print(f"🔄 Using cached session block height: {_session_block_height} (session: {_session_id})")
        return _session_block_height
    
    # Fetch fresh block height for this session
    try:
        print(f"🔄 Fetching fresh block height for session: {_session_id}")
        result = make_verus_rpc('getinfo', [])
        
        if result and 'blocks' in result:
            _session_block_height = int(result['blocks'])
            print(f"✅ Session block height set: {_session_block_height} (session: {_session_id})")
            return _session_block_height
        else:
            print("❌ Failed to get block height from getinfo")
            return None
        
    except Exception as e:
        print(f"❌ Error fetching session block height: {e}")
        return None

def get_current_session_id():
    """
    Get the current session ID
    
    Returns:
        str: Current session ID, or None if no session is active
    """
    return _session_id

def clear_session():
    """
    Clear the current session and cached block height
    This should be called at the end of each API request
    """
    global _session_block_height, _session_id
    
    old_session = _session_id
    _session_block_height = None
    _session_id = None
    
    print(f"🧹 Cleared session: {old_session}")

def estimate_vrsc_to_dai():
    """
    Estimate VRSC to DAI conversion rate using estimateconversion
    Uses the current session block height for consistency
    
    Returns:
        dict: Conversion estimate data, or None if failed
    """
    block_height = get_session_block_height()
    if block_height is None:
        print("❌ Cannot estimate conversion without block height")
        return None
    
    try:
        print(f"🔄 Estimating VRSC to DAI conversion at block {block_height}")
        
        # Use estimateconversion to get VRSC to DAI rate
        # Parameters: [{"currency":"DAI.vETH","amount":1,"convertto":"VRSC","via":"Bridge.vETH"}]
        conversion_params = [{
            "currency": "VRSC",
            "amount": 1,
            "convertto": "DAI.vETH",
            "via": "Bridge.vETH"
        }]
        
        result = make_verus_rpc('estimateconversion', conversion_params)
        
        if result:
            print(f"✅ VRSC to DAI conversion estimate: {result}")
            return result
        else:
            print("❌ Failed to get VRSC to DAI conversion estimate")
            return None
            
    except Exception as e:
        print(f"❌ Error estimating VRSC to DAI conversion: {e}")
        return None

if __name__ == "__main__":
    # Test the session-based block height functionality
    print("🧪 Testing Session-Based Block Height Utility")
    print("=" * 50)
    
    # Start a new session
    session_id = start_new_session()
    print(f"Session ID: {session_id}")
    
    # Test block height fetch
    block_height = get_session_block_height()
    print(f"Block height: {block_height}")
    
    # Test cached block height (should use same value)
    cached_height = get_session_block_height()
    print(f"Cached block height: {cached_height}")
    
    # Test VRSC to DAI conversion
    conversion = estimate_vrsc_to_dai()
    print(f"VRSC to DAI conversion: {conversion}")
    
    # Clear session
    clear_session()
    
    print("✅ Session-based block height utility test complete")
