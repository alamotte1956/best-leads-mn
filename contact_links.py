"""Encode email addresses as recipients, never as mailto query/header parameters."""
from urllib.parse import quote


def mailto_address(value):
    if (not isinstance(value,str) or not value or len(value)>254 or '@' not in value
            or any(char.isspace() or ord(char)<32 or ord(char)==127 for char in value)):
        return None
    return 'mailto:'+quote(value,safe='@.')
