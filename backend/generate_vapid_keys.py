#!/usr/bin/env python3
"""
Generate VAPID keys for Web Push Notifications
Run this once and add the keys to your .env file
"""
from pywebpush import webpush
import base64
import os

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    # Generate private key
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize private key
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    # Base64 URL-safe encode
    private_key_b64 = base64.urlsafe_b64encode(private_key_bytes).decode('utf-8').rstrip('=')
    public_key_b64 = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
    
    print("=" * 80)
    print("VAPID Keys Generated Successfully!")
    print("=" * 80)
    print("\nAdd these to your .env file:\n")
    print(f"VAPID_PRIVATE_KEY={private_key_b64}")
    print(f"VAPID_PUBLIC_KEY={public_key_b64}")
    print(f'VAPID_CLAIMS={{"sub": "mailto:your-email@example.com"}}')
    print("\n" + "=" * 80)
    print("IMPORTANT: Replace 'your-email@example.com' with your actual email")
    print("=" * 80)
    
except ImportError as e:
    print("Error: Required libraries not installed")
    print("Run: pip install pywebpush cryptography")
    print(f"Details: {e}")
