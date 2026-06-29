import re
from typing import Optional

def validate_phone(phone: str) -> Optional[str]:
    """
    Normalize and validate phone numbers. 
    Returns a clean E.164 formatted string (e.g. +923001234567) or None if invalid.
    """
    if not phone:
        return None
        
    # Remove all spaces, dashes, and parentheses
    clean = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Pakistan format example: +92, 03, or 923 followed by 9 digits
    # (You can adjust this regex for other countries like US: ^\+1[0-9]{10}$)
    pattern = r'^(\+92|0|92)[3][0-9]{9}$'
    
    if re.match(pattern, clean):
        # Normalize to standard +92 format
        if clean.startswith('0'):
            return '+92' + clean[1:]
        if clean.startswith('92'):
            return '+' + clean
        return clean
        
    return None

def validate_name(name: str) -> bool:
    """
    Name must be 2-50 chars, letters and spaces only.
    Prevents people from using emojis, numbers, or symbols.
    """
    if not name:
        return False
    return bool(re.match(r'^[A-Za-z\s]{2,50}$', name.strip()))

def sanitize_input(text: str) -> str:
    """
    Basic sanitization to strip HTML/SQL special chars from free text fields
    (like doctor's notes or patient symptoms).
    """
    if not text:
        return ""
    # Strip dangerous characters to prevent basic XSS or weird formatting
    clean = re.sub(r'[<>"\'%;()&+]', '', text)
    # Limit length to prevent buffer bloat
    return clean[:500].strip()
