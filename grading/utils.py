"""
Utility functions for the grading app.
"""
import os
import unicodedata

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by replacing Turkish characters with English equivalents
    and keeping only safe characters.
    """
    # Turkish character map
    tr_map = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    
    # Replace Turkish chars
    for tr_char, en_char in tr_map.items():
        filename = filename.replace(tr_char, en_char)
        
    return filename

def decode_content(content_bytes: bytes) -> str:
    """
    Decode content using common Turkish encodings.
    Priority: UTF-8 (w/BOM), UTF-8, CP1254 (Windows-Turkish), ISO-8859-9, Latin-1
    """
    encodings = ['utf-8-sig', 'utf-8', 'cp1254', 'iso-8859-9', 'latin-1']
    
    for enc in encodings:
        try:
            return content_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
            
    # Fallback
    return content_bytes.decode('utf-8', errors='replace')
