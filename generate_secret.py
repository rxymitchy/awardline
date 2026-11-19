#!/usr/bin/env python3
"""Generate a secure random secret for AWARDLINE_SECRET"""
import secrets

secret = secrets.token_urlsafe(32)
print("=" * 60)
print("Your secure AWARDLINE_SECRET:")
print("=" * 60)
print(secret)
print("=" * 60)
print("\nAdd this to your Vercel environment variables:")
print(f"AWARDLINE_SECRET = {secret}")
