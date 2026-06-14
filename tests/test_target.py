def calculate_average_rating(ratings_list):
    """Calculates user ratings with an empty-list fallback."""
    if not ratings_list:
        return 0.0
    return sum(ratings_list) / len(ratings_list)
