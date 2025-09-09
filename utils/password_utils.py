import re
from typing import List, Tuple


def validate_password(password: str) -> Tuple[bool, List[str], int]:
    """
    Validate password and return validation status, missing requirements, and strength score.

    Returns:
        Tuple[bool, List[str], int]: (is_valid, missing_requirements, strength_score)
    """
    if not password:
        return False, ["Password is required"], 0

    missing = []
    strength_score = 0

    # Basic requirements
    if len(password) < 8:
        missing.append("At least 8 characters")
    else:
        strength_score += 20

    if len(password) > 128:
        missing.append("Maximum 128 characters")
    else:
        strength_score += 10

    if not re.search(r"[A-Z]", password):
        missing.append("At least one uppercase letter")
    else:
        strength_score += 15

    if not re.search(r"[a-z]", password):
        missing.append("At least one lowercase letter")
    else:
        strength_score += 15

    if not re.search(r"[0-9]", password):
        missing.append("At least one number")
    else:
        strength_score += 15

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
        missing.append("At least one special character")
    else:
        strength_score += 15

    # Check for malicious characters - only allow safe characters
    if not re.match(
        r'^[a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`\s]+$', password
    ):
        missing.append("Contains invalid characters")
    else:
        strength_score += 10

    # Additional strength bonuses
    if len(password) >= 12:
        strength_score += 5
    if len(password) >= 16:
        strength_score += 5

    # Check for common weak patterns
    if re.search(r"(.)\1{2,}", password):  # 3+ repeated characters
        strength_score -= 10

    if re.search(
        r"(012|123|234|345|456|567|678|789|890|abc|bcd|cde|def)", password.lower()
    ):
        strength_score -= 15

    # Common weak passwords
    weak_patterns = [r"password", r"123456", r"qwerty", r"admin", r"login", r"welcome"]

    for pattern in weak_patterns:
        if re.search(pattern, password.lower()):
            strength_score -= 20
            break

    is_valid = len(missing) == 0

    return is_valid, missing


def get_password_requirements() -> List[str]:
    """Get list of all password requirements."""
    return [
        "At least 8 characters",
        "Maximum 128 characters",
        "At least one uppercase letter",
        "At least one lowercase letter",
        "At least one number",
        "At least one special character",
        "Only safe characters allowed",
    ]
