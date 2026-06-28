import asyncio
from services.parser import parse_answer_string
from services.grader import grade_submission

def test_parser():
    formats = [
        "1a2b3c4d",
        "1-a 2-b 3-c 4-d",
        "1-a, 2-b, 3-c, 4-d",
        "1a, 2b, 3c, 4d",
        "1-a\n2-b\n3-c\n4-d",
        "1 - a, 2 - b, 3 - c, 4 - d",
        "1-a 2b 3 - c, 4 d",
        "1-A 2-B 3-C 4-D"
    ]
    total_q = 4
    for i, raw in enumerate(formats):
        result = parse_answer_string(raw, total_q)
        print(f"Format {i+1}: {result.is_valid}, {result.parsed}")
        assert result.is_valid, f"Failed on format: {raw}"
        assert result.parsed == {'1': 'a', '2': 'b', '3': 'c', '4': 'd'}, f"Wrong parse: {result.parsed}"
    
    print("All parser format tests passed!")
    
    # Test duplicates and missing
    raw_invalid = "1-a 1-b 3-x 5-a"
    res = parse_answer_string(raw_invalid, 4)
    print(f"Invalid parse test: valid={res.is_valid}, missing={res.missing}, dup={res.duplicates}, invalid_opts={res.invalid_options}")

async def test_grader():
    parsed = {'1': 'a', '2': 'b', '3': 'c'}
    answer_key = {'1': 'a', '2': 'b', '3': 'd', '4': 'a'}
    score, pct, breakdown = await grade_submission(parsed, answer_key, 4)
    print(f"Grader test: score={score}, pct={pct}%")
    for b in breakdown:
        print(b)
    assert score == 2
    assert pct == 50.0

if __name__ == "__main__":
    test_parser()
    asyncio.run(test_grader())
