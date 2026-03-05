"""
Security middleware for Miso Gallery

Provides:
- Rate limiting
- Security headers
- Input validation
"""

import os
from flask import request, jsonify
from functools import wraps
import time

# Rate limiting storage (simple in-memory for now)
rate_limit_storage = {}

def rate_limit(max_requests=100, window=60):
    """Simple rate limiter decorator"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Skip if no auth (public endpoints)
            if not is_auth_enabled():
                return f(*args, **kwargs)
            
            # Get client IP
            client_ip = request.headers.get('X-Forwarded-For', 
                            request.headers.get('CF-Connecting-IP',
                            request.remote_addr))
            
            key = f"{client_ip}:{request.endpoint or 'unknown'}"
            now = time.time()
            
            # Clean old entries
            rate_limit_storage[key] = [t for t in rate_limit_storage.get(key, []) if now - t < window]
            
            # Check limit
            if len(rate_limit_storage.get(key, [])) >= max_requests:
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            # Add this request
            rate_limit_storage.setdefault(key, []).append(now)
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def sanitize_path(path):
    """Prevent path traversal attacks"""
    # Remove any null bytes
    path = path.replace('\x00', '')
    
    # Block path traversal
    if '..' in path or path.startswith('/'):
        return False
    
    return True

# Security headers for Flask
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'"
}

def add_security_headers(response):
    """Add security headers to all responses"""
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
