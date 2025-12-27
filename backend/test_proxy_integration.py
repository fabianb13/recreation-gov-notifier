"""
Test script to verify SOCKS5 proxy integration with Recreation.gov API
"""

import sys
import time
from recreation_api import recreation_api
from proxy_manager import proxy_manager

def test_proxy_pool():
    """Test that proxy pool is initialized"""
    print("\n" + "="*80)
    print("Testing Proxy Pool Status")
    print("="*80)
    
    if not proxy_manager.initialized:
        print("❌ Proxy manager not initialized!")
        return False
    
    stats = proxy_manager.get_stats()
    print(f"✅ Proxy pool initialized")
    print(f"   Total proxies: {stats['total_proxies']}")
    print(f"   Total requests made: {stats['total_requests']}")
    print(f"   Total capacity: {stats['total_proxies'] * 35} req/min")
    
    print(f"\n📊 Proxy Details:")
    for i, proxy in enumerate(stats['proxies'][:5], 1):  # Show first 5
        print(f"   {i}. {proxy['ip']} (external: {proxy['external_ip']}) - "
              f"{proxy['latency_ms']:.1f}ms - "
              f"Tokens: {proxy['available_tokens']:.1f}")
    
    if len(stats['proxies']) > 5:
        print(f"   ... and {len(stats['proxies']) - 5} more proxies")
    
    return True


def test_recreation_api_with_proxy():
    """Test Recreation.gov API call through SOCKS5 proxy"""
    print("\n" + "="*80)
    print("Testing Recreation.gov API via SOCKS5 Proxy")
    print("="*80)
    
    # Test facility ID: 232447 (Lake Tahoe - D.L. Bliss State Park)
    facility_id = "232447"
    
    try:
        print(f"🔍 Fetching facility info for ID: {facility_id}")
        facility_info = recreation_api.get_facility(facility_id)
        
        if facility_info and "campground" in facility_info:
            facility_name = facility_info["campground"].get("facility_name", "Unknown")
            print(f"✅ Successfully retrieved facility: {facility_name}")
            
            # Show which proxy was used
            stats = proxy_manager.get_stats()
            print(f"📊 Proxy stats after request:")
            print(f"   Total requests across all proxies: {stats['total_requests']}")
            
            return True
        else:
            print(f"❌ Failed to retrieve facility info")
            return False
            
    except Exception as e:
        print(f"❌ Error during API call: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_round_robin_proxy_selection():
    """Test that proxies are selected in round-robin fashion"""
    print("\n" + "="*80)
    print("Testing Round-Robin Proxy Selection")
    print("="*80)
    
    print("Making 5 test requests to verify round-robin selection...")
    
    proxy_ips_used = []
    for i in range(5):
        proxy = proxy_manager.get_next_proxy()
        if proxy:
            proxy_ips_used.append(proxy.ip)
            print(f"   Request {i+1}: Using proxy {proxy.ip}")
        else:
            print(f"   Request {i+1}: ❌ No proxy available")
            return False
    
    # Check if we got different proxies (assuming we have at least 5)
    unique_proxies = len(set(proxy_ips_used))
    print(f"\n✅ Used {unique_proxies} unique proxy/proxies out of 5 requests")
    
    if unique_proxies >= min(5, len(proxy_manager.proxies)):
        print(f"✅ Round-robin working correctly!")
        return True
    else:
        print(f"⚠️ Expected more unique proxies")
        return False


def main():
    """Run all proxy tests"""
    print("\n" + "="*80)
    print("SOCKS5 Proxy Integration Test Suite")
    print("="*80)
    
    # Initialize proxy manager if not already done
    if not proxy_manager.initialized:
        print("\n🚀 Initializing proxy manager...")
        if not proxy_manager.initialize():
            print("❌ Failed to initialize proxy manager")
            sys.exit(1)
    
    # Run tests
    tests = [
        ("Proxy Pool Status", test_proxy_pool),
        ("Round-Robin Selection", test_round_robin_proxy_selection),
        ("Recreation.gov API Call", test_recreation_api_with_proxy),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
        
        # Brief pause between tests
        time.sleep(1)
    
    # Summary
    print("\n" + "="*80)
    print("Test Results Summary")
    print("="*80)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    print("\n" + "="*80)
    if all_passed:
        print("✅ All tests passed!")
        print("="*80)
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        print("="*80)
        sys.exit(1)


if __name__ == "__main__":
    main()
