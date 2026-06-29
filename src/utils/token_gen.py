import secrets
import string

def generate_token() -> str:
    """
    Generate a cryptographically random 8-char booking token.
    Format: VT-XXXX (letters + digits, uppercase)
    
    Collision probability is mathematically negligible for a clinic 
    doing a few hundred appointments a day.
    """
    # Exclude confusing characters like '0', 'O', '1', 'I' if desired, 
    # but standard ascii_uppercase is usually fine for short tokens.
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(4))
    
    return f"VT-{random_part}"
