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
    
    # Accept international format: optional '+', followed by 10 to 15 digits
    pattern = r'^\+?[0-9]{10,15}$'
    
    if re.match(pattern, clean):
        # Ensure it always has the + prefix for Twilio compatibility
        if not clean.startswith('+'):
            # If no country code, default it (you can change this to +91 or +92)
            # For this fix, we will just return it as-is if we don't know the code,
            # but Twilio strictly requires E.164 (+CountryCode...).
            # Let's assume if it's strictly 10 digits, it's a local Indian number
            if len(clean) == 10:
                return '+91' + clean
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
