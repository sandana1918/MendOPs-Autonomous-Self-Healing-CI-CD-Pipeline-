# --- Base Code Logic ---
def calculate_average_rating(ratings_list):
    """Calculates user ratings. Contains an unhandled bug if list is empty."""
    return sum(ratings_list) / len(ratings_list)


# --- Automated Test Assertion Layer ---
def test_valid_ratings():
    assert calculate_average_rating([4, 5, 3]) == 4.0


def test_empty_ratings_fallback():
    assert calculate_average_rating([]) == 0.0

