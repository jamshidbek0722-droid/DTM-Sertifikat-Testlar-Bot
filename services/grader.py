async def grade_submission(
    parsed_answers: dict[str, str],
    answer_key: dict[str, str],
    total_questions: int
) -> tuple[int, float, list[dict]]:
    """
    Grades the submission against the answer key.
    
    Returns: (score, percentage, detailed_breakdown)
    detailed_breakdown: [{"q": 1, "user": "a", "correct": "b", "is_correct": False}, ...]
    """
    score = 0
    detailed_breakdown = []
    
    for i in range(1, total_questions + 1):
        q_str = str(i)
        user_ans = parsed_answers.get(q_str)
        correct_ans = answer_key.get(q_str)
        
        is_correct = (user_ans == correct_ans) if user_ans and correct_ans else False
        if is_correct:
            score += 1
            
        detailed_breakdown.append({
            "q": i,
            "user": user_ans,
            "correct": correct_ans,
            "is_correct": is_correct
        })
        
    percentage = (score / total_questions) * 100 if total_questions > 0 else 0.0
    return score, round(percentage, 1), detailed_breakdown
