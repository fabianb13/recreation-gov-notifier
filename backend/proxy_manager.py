"""
SOCKS5 Proxy Manager for Recreation.gov API requests

This module handles:
- DNS resolution of proxy server address
- Latency testing to select fastest proxies
- Proxy verification via test requests
- Round-robin proxy selection for load distribution
- Per-proxy rate limiting (35 req/min per proxy)
"""

import socket
import time
import requests
from typing import List, Dict, Optional, Tuple
from threading import Lock
import itertools
from rate_limiter import TokenBucketRateLimiter
from config import settings

# Proxy configuration
PROXY_HOSTNAME = "proxy-nl.privateinternetaccess.com"
PROXY_PORT = 1080
PROXY_USERNAME = settings.PROXY_USERNAME
PROXY_PASSWORD = settings.PROXY_PASSWORD
PROXY_VERIFY_URL = "https://api.ipify.org"

# Rate limiting per proxy (35 req/min = 0.583 req/sec)
RATE_LIMIT_PER_PROXY = 35.0  # requests per minute
RATE_LIMIT_CAPACITY = 35  # token bucket capacity


class ProxyInfo:
    """Information about a single proxy"""
    def __init__(self, ip: str, port: int, username: str, password: str):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.latency_ms: Optional[float] = None
        self.verified: bool = False
        self.external_ip: Optional[str] = None
        
        # Per-proxy rate limiter (35 requests per minute)
        self.rate_limiter = TokenBucketRateLimiter(rate=RATE_LIMIT_PER_PROXY / 60.0, capacity=RATE_LIMIT_CAPACITY)
    
    def get_proxy_url(self) -> str:
        """Get the SOCKS5 proxy URL for requests library"""
        return f"socks5://{self.username}:{self.password}@{self.ip}:{self.port}"
    
    def get_proxies_dict(self) -> Dict[str, str]:
        """Get proxies dictionary for requests library"""
        proxy_url = self.get_proxy_url()
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    def __repr__(self) -> str:
        status = "✓" if self.verified else "✗"
        latency_str = f"{self.latency_ms:.1f}ms" if self.latency_ms else "N/A"
        ip_str = f"→ {self.external_ip}" if self.external_ip else ""
        return f"Proxy({status} {self.ip}:{self.port}, latency: {latency_str} {ip_str})"


class ProxyManager:
    """
    Manages a pool of SOCKS5 proxies with automatic discovery and round-robin selection
    """
    
    def __init__(self):
        self.proxies: List[ProxyInfo] = []
        self.proxy_cycle = None
        self.lock = Lock()
        self.initialized = False
        self.total_requests = 0
    
    def _resolve_proxy_ips(self, hostname: str) -> List[str]:
        """
        Resolve proxy hostname to list of IP addresses using DNS
        
        Args:
            hostname: DNS hostname to resolve
            
        Returns:
            List of IP addresses
        """
        print(f"🔍 Resolving DNS for {hostname}...")
        try:
            # getaddrinfo returns list of (family, type, proto, canonname, sockaddr) tuples
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
            # Extract unique IP addresses from sockaddr tuples
            ips = list(set([addr[4][0] for addr in addr_info]))
            print(f"✅ Found {len(ips)} IP address(es): {', '.join(ips)}")
            return ips
        except socket.gaierror as e:
            print(f"❌ DNS resolution failed for {hostname}: {e}")
            return []
    
    def _test_latency(self, ip: str, port: int, timeout: float = 2.0) -> Optional[float]:
        """
        Test latency to proxy server via TCP connection
        
        Args:
            ip: Proxy IP address
            port: Proxy port
            timeout: Connection timeout in seconds
            
        Returns:
            Latency in milliseconds, or None if connection failed
        """
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.close()
            latency_ms = (time.time() - start_time) * 1000
            return latency_ms
        except (socket.timeout, socket.error) as e:
            print(f"⚠️ Latency test failed for {ip}:{port} - {e}")
            return None
    
    def _verify_proxy(self, proxy: ProxyInfo, timeout: int = 10) -> bool:
        """
        Verify proxy works by making test request to ipify.org
        
        Args:
            proxy: ProxyInfo object to verify
            timeout: Request timeout in seconds
            
        Returns:
            True if proxy works, False otherwise
        """
        try:
            print(f"🔐 Verifying proxy {proxy.ip}:{proxy.port}...")
            
            # Make request through SOCKS5 proxy
            response = requests.get(
                PROXY_VERIFY_URL,
                proxies=proxy.get_proxies_dict(),
                timeout=timeout
            )
            
            if response.status_code == 200:
                external_ip = response.text.strip()
                proxy.external_ip = external_ip
                proxy.verified = True
                print(f"✅ Proxy {proxy.ip} verified - External IP: {external_ip}")
                return True
            else:
                print(f"❌ Proxy {proxy.ip} verification failed - Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Proxy {proxy.ip} verification failed - {e}")
            return False
    
    def initialize(self) -> bool:
        """
        Initialize proxy pool:
        1. Resolve DNS to get proxy IPs
        2. Test latency to each IP
        3. Verify each proxy works
        4. Sort by latency (fastest first)
        
        Returns:
            True if at least one proxy was initialized successfully
        """
        print(f"\n{'='*80}")
        print(f"🚀 Initializing SOCKS5 Proxy Pool")
        print(f"{'='*80}")
        
        # Step 1: Resolve DNS
        proxy_ips = self._resolve_proxy_ips(PROXY_HOSTNAME)
        if not proxy_ips:
            print(f"❌ No proxy IPs found for {PROXY_HOSTNAME}")
            return False
        
        # Step 2: Test latency for each IP
        print(f"\n📊 Testing latency to {len(proxy_ips)} proxy server(s)...")
        proxy_candidates = []
        
        for ip in proxy_ips:
            latency = self._test_latency(ip, PROXY_PORT, timeout=3.0)
            if latency is not None:
                proxy = ProxyInfo(ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
                proxy.latency_ms = latency
                proxy_candidates.append(proxy)
                print(f"  ✓ {ip}: {latency:.1f}ms")
            else:
                print(f"  ✗ {ip}: Connection failed")
        
        if not proxy_candidates:
            print(f"❌ No reachable proxies found")
            return False
        
        # Filter out high-latency proxies (>500ms)
        proxy_candidates = [p for p in proxy_candidates if p.latency_ms <= 500.0]
        if not proxy_candidates:
            print(f"❌ No proxies with acceptable latency (≤500ms) found")
            return False
        
        print(f"\n✅ {len(proxy_candidates)} proxy/proxies with acceptable latency (≤500ms)")
        
        # Sort by latency (fastest first)
        proxy_candidates.sort(key=lambda p: p.latency_ms)
        print(f"🏆 Fastest proxy: {proxy_candidates[0].ip} ({proxy_candidates[0].latency_ms:.1f}ms)")
        
        # Step 3: Verify each proxy works (test with ipify.org)
        print(f"\n🔐 Verifying proxy connectivity...")
        verified_proxies = []
        
        for proxy in proxy_candidates:
            if self._verify_proxy(proxy, timeout=2):
                verified_proxies.append(proxy)
        
        if not verified_proxies:
            print(f"❌ No working proxies found (verification failed)")
            return False
        
        # Store verified proxies and create round-robin cycle
        with self.lock:
            self.proxies = verified_proxies
            self.proxy_cycle = itertools.cycle(self.proxies)
            self.initialized = True
        
        print(f"\n{'='*80}")
        print(f"✅ Proxy pool initialized with {len(self.proxies)} working proxy/proxies")
        print(f"{'='*80}")
        
        for i, proxy in enumerate(self.proxies, 1):
            print(f"  {i}. {proxy}")
        
        print(f"\n💡 Rate limit: {RATE_LIMIT_PER_PROXY} req/min per proxy")
        print(f"💡 Total capacity: {RATE_LIMIT_PER_PROXY * len(self.proxies)} req/min across all proxies\n")
        
        return True
    
    def get_next_proxy(self) -> Optional[ProxyInfo]:
        """
        Get next proxy using round-robin selection
        
        Returns:
            ProxyInfo object, or None if no proxies available
        """
        if not self.initialized or not self.proxies:
            print(f"⚠️ Proxy manager not initialized or no proxies available")
            return None
        
        with self.lock:
            proxy = next(self.proxy_cycle)
            self.total_requests += 1
            return proxy
    
    def acquire_with_proxy(self) -> Optional[Tuple[ProxyInfo, float]]:
        """
        Get next proxy and acquire rate limit token
        
        Returns:
            Tuple of (ProxyInfo, wait_time) or None if no proxies available
        """
        proxy = self.get_next_proxy()
        if not proxy:
            return None
        
        # Acquire token from this proxy's rate limiter (blocks until available)
        wait_time = proxy.rate_limiter.acquire_with_wait(tokens=1)
        
        return proxy, wait_time
    
    def get_stats(self) -> Dict:
        """Get statistics about proxy usage"""
        if not self.initialized:
            return {"initialized": False}
        
        stats = {
            "initialized": True,
            "total_proxies": len(self.proxies),
            "total_requests": self.total_requests,
            "proxies": []
        }
        
        for proxy in self.proxies:
            stats["proxies"].append({
                "ip": proxy.ip,
                "external_ip": proxy.external_ip,
                "latency_ms": proxy.latency_ms,
                "available_tokens": proxy.rate_limiter.get_available_tokens()
            })
        
        return stats


# Global singleton instance
proxy_manager = ProxyManager()
