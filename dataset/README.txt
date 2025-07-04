Overview
This dataset contains synthetic Amazon movie reviews designed for machine learning research, natural language processing tasks, and educational purposes. The dataset mimics the structure and characteristics of real Amazon product reviews for movies, providing a safe and ethically sound alternative for research and development.

The dataset includes the following fields:

Movie Title: The title of the movie being reviewed
Reviewer Name: Synthetic reviewer usernames
Rating: Star rating (1-5 scale)
Review Text: Detailed review content
Helpful Votes: Number of users who found the review helpful
Verified Purchase: Boolean indicating if the reviewer purchased the product
Review Date: Date when the review was posted


File Format

Format: CSV (Comma-Separated Values)
Encoding: UTF-8
Headers: Included in first row

Common Analysis Tasks
python# Rating distribution
rating_dist = df['Rating'].value_counts().sort_index()

# Average rating by verified purchase status
avg_rating_verified = df.groupby('Verified Purchase')['Rating'].mean()

# Review length analysis
df['Review Length'] = df['Review Text'].str.len()
print(f"Average review length: {df['Review Length'].mean():.2f} characters")

# Most helpful reviews
top_helpful = df.nlargest(5, 'Helpful Votes')

Sources
Synthetic Amazon Movie Reviews Dataset (2024)
Generated for Machine Learning Research and Education





