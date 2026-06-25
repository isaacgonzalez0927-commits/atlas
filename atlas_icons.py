"""Shared adaptive home-screen icon link tags for Atlas."""

ATLAS_ICON_LINKS = """
<link rel="apple-touch-icon" href="/static/apple-touch-icon-light.png" media="(prefers-color-scheme: light)">
<link rel="apple-touch-icon" href="/static/apple-touch-icon-dark.png" media="(prefers-color-scheme: dark)">
<link rel="apple-touch-icon" href="/static/apple-touch-icon-light.png">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icon-192-light.png" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icon-192-dark.png" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icon-192-light.png">
<link rel="icon" type="image/png" sizes="512x512" href="/static/icon-512-light.png" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/png" sizes="512x512" href="/static/icon-512-dark.png" media="(prefers-color-scheme: dark)">
"""

ATLAS_MANIFEST_ICONS = [
    {"src": "/static/icon-192-light.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "/static/icon-512-light.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "/static/icon-192-dark.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "/static/icon-512-dark.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "/static/icon-512-light.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
]
