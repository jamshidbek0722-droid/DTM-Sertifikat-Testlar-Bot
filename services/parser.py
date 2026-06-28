import re
from dataclasses import dataclass

@dataclass
class ParseResult:
    parsed: dict[str, str]   # {"1": "a", "2": "b", ...}
    missing: list[int]        # question numbers not found in input
    duplicates: list[int]     # question numbers submitted more than once
    invalid_options: list[str] # options not in (a, b, c, d, e)
    is_valid: bool            # True only if no missing, no duplicates, all options valid

def parse_answer_string(raw: str, total_questions: int) -> ParseResult:
    """
    Parses any supported answer string format into a structured dict.
    
    The regex must handle ALL format variations:
    Continuous, space-separated, comma-dash, newlines, mixed styles.
    Case-insensitive. Strips all irrelevant characters.
    """
    # Pattern: digit(s) followed by optional non-alphanumeric chars, followed by a single letter
    pattern = r"(\d+)[^0-9a-zA-Z]*([a-zA-Z])"
    matches = re.findall(pattern, raw)
    
    parsed = {}
    duplicates = set()
    invalid_options = set()
    
    valid_choices = {'a', 'b', 'c', 'd', 'e'}
    
    for num_str, letter_str in matches:
        num = int(num_str)
        letter = letter_str.lower()
        
        # We only care about questions up to total_questions.
        # If user provides answers beyond total_questions, we ignore them.
        if num > total_questions or num <= 0:
            continue
            
        if str(num) in parsed:
            duplicates.add(num)
        
        if letter not in valid_choices:
            invalid_options.add(f"{num}-{letter}")
            
        parsed[str(num)] = letter

    missing = []
    for i in range(1, total_questions + 1):
        if str(i) not in parsed:
            missing.append(i)
            
    is_valid = len(missing) == 0 and len(duplicates) == 0 and len(invalid_options) == 0
    
    return ParseResult(
        parsed=parsed,
        missing=sorted(list(missing)),
        duplicates=sorted(list(duplicates)),
        invalid_options=sorted(list(invalid_options)),
        is_valid=is_valid
    )
