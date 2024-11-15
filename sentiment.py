import streamlit as st
import pandas as pd
import pickle
import re
import csv
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from sklearn.ensemble import RandomForestClassifier
from nltk.stem.porter import PorterStemmer
from nltk.corpus import stopwords
import plotly.graph_objects as go
import nltk

nltk.download('stopwords')
STOPWORDS = set(stopwords.words('english'))

def get_ratings_and_reviews(url):
    """
    Scrapes the total number of ratings and reviews from a Flipkart product page.
    """
    options = Options()
    options.headless = True  
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    span_tag = soup.find('span', class_="Wphh3N")
    if span_tag:
        text = span_tag.get_text()
        ratings_match = re.search(r'(\d+,\d+|\d+) ratings', text)
        reviews_match = re.search(r'(\d+,\d+|\d+) reviews', text)
        ratings = ratings_match.group(1) if ratings_match else None
        reviews = reviews_match.group(1) if reviews_match else None
    else:
        ratings, reviews = None, None
    
    driver.quit()
    return ratings, reviews

def scrape_reviews(url, num_reviews=100):
    """
    Scrapes product reviews from Flipkart, handling multiple possible review div classes.
    """
    reviews_url = url.replace("/p/", "/product-reviews/")
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)
    
    reviews_data = []
    page_number = 1
    max_pages = 10  # Limit to prevent infinite loops
    
    while len(reviews_data) < num_reviews and page_number <= max_pages:
        try:
            driver.get(f"{reviews_url}&page={page_number}")
            time.sleep(2)  # Wait for page to load
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Try multiple review div classes
            review_divs = soup.find_all('div', class_="ZmyHeo")
            if not review_divs:
                review_divs = soup.find_all('div', class_="_11pzQk")
            if not review_divs:
                review_divs = soup.find_all('div', class_="t-ZTKy")
                
            if not review_divs:  # If no reviews found on the page
                break
                
            for review_div in review_divs:
                # Look for the review text in different possible locations
                review_text = None
                
                # Try to find the main review text
                text_div = review_div.find('div', class_="")
                if text_div:
                    review_text = text_div.get_text(strip=True)
                
                # Try to find and include "READ MORE" content
                read_more = review_div.find('span', class_="wTYmpv")
                if read_more:
                    expanded_text = read_more.get_text(strip=True)
                    if review_text:
                        review_text += " " + expanded_text
                
                if not review_text:  # If still no text found, try getting all text
                    review_text = review_div.get_text(strip=True)
                
                if review_text and review_text != "READ MORE":  # Only add non-empty reviews
                    reviews_data.append(review_text)
                if len(reviews_data) >= num_reviews:
                    break
            
            page_number += 1
            
        except Exception as e:
            st.error(f"Error scraping reviews: {str(e)}")
            break
    
    driver.quit()
    
    if not reviews_data:
        return None
        
    with open('reviews.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Review'])
        for review in reviews_data:
            writer.writerow([review])
    
    return reviews_data

def preprocess_reviews(reviews):
    """
    Preprocesses reviews by removing stopwords, stemming, and cleaning text.
    """
    if not reviews:
        return None
        
    stemmer = PorterStemmer()
    processed_reviews = []
    
    for review in reviews:
        # Remove non-alphabetic characters
        review = re.sub('[^a-zA-Z]', ' ', review)
        # Convert to lowercase
        review = review.lower()
        # Stem words and remove stopwords
        review = [stemmer.stem(word) for word in review.split() if word not in STOPWORDS]
        processed_reviews.append(' '.join(review))
    
    return processed_reviews

def load_model():
    """
    Loads the pre-trained model and associated transformers.
    """
    with open("countVectorizer.pkl", "rb") as cvf:
        count_vectorizer = pickle.load(cvf)
    with open("scaler.pkl", "rb") as sc:
        scaler = pickle.load(sc)
    with open("rn.pkl", "rb") as fr:
        model_rf = pickle.load(fr)
    return count_vectorizer, scaler, model_rf

def sentiment_analysis(reviews):
    """
    Performs sentiment analysis on the preprocessed reviews.
    """
    if not reviews:
        return None
        
    count_vectorizer, scaler, model_rf = load_model()
    x_new_count = count_vectorizer.transform(reviews)
    x_new_scaled = scaler.transform(x_new_count.toarray())
    return model_rf.predict(x_new_scaled)

def analyze_single_product(url):
    """
    Analyzes sentiment for a single product and displays results.
    """
    with st.spinner("Fetching data..."):
        try:
            ratings, reviews_count = get_ratings_and_reviews(url)
            reviews = scrape_reviews(url, num_reviews=100)
            
            if not reviews:
                st.warning("No reviews found for this product.")
                return
                
            processed_reviews = preprocess_reviews(reviews)
            sentiments = sentiment_analysis(processed_reviews)
            
            df_reviews = pd.DataFrame({"Review Body": reviews, "Sentiment": sentiments})
            
            sentiment_counts = df_reviews['Sentiment'].value_counts()
            st.subheader("Sentiment Analysis Results")
            
            # Create sentiment distribution chart
            fig_sentiment = go.Figure(go.Bar(
                y=sentiment_counts.index.map({1: 'Positive', 0: 'Negative'}),
                x=sentiment_counts.values,
                text=sentiment_counts.values,
                textposition='auto',
                marker_color=['green', 'red'],
                orientation='h'
            ))
            fig_sentiment.update_layout(
                xaxis_title='Number of Reviews',
                yaxis_title='Sentiment',
                showlegend=False,
                height=400
            )
            st.plotly_chart(fig_sentiment, use_container_width=True)
            
            if ratings and reviews_count:
                st.subheader("Product Metrics")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Ratings", ratings)
                with col2:
                    st.metric("Total Reviews", reviews_count)
                with col3:
                    positive_percentage = (sentiment_counts.get(1, 0) / len(reviews) * 100)
                    st.metric("Positive Sentiment", f"{positive_percentage:.1f}%")
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("Positive Reviews")
                positive_reviews = df_reviews[df_reviews['Sentiment'] == 1]['Review Body']
                for review in positive_reviews:
                    st.success(review)

            with col2:
                st.subheader("Negative Reviews")
                negative_reviews = df_reviews[df_reviews['Sentiment'] == 0]['Review Body']
                for review in negative_reviews:
                    st.warning(review)
                    
        except Exception as e:
            st.error("Error analyzing product.")
            st.write(e)

def analyze_comparison(url1, url2):
    """
    Compares sentiment analysis results between two products.
    """
    with st.spinner("Fetching data for comparison..."):
        try:
            # Analyze first product
            ratings1, reviews_count1 = get_ratings_and_reviews(url1)
            reviews1 = scrape_reviews(url1, num_reviews=100)
            
            # Analyze second product
            ratings2, reviews_count2 = get_ratings_and_reviews(url2)
            reviews2 = scrape_reviews(url2, num_reviews=100)
            
            if not reviews1 or not reviews2:
                st.warning("One or both products have no reviews available.")
                return
                
            # Process both products
            processed_reviews1 = preprocess_reviews(reviews1)
            processed_reviews2 = preprocess_reviews(reviews2)
            
            sentiments1 = sentiment_analysis(processed_reviews1)
            sentiments2 = sentiment_analysis(processed_reviews2)
            
            # Create comparison chart
            df1 = pd.DataFrame({"Review Body": reviews1, "Sentiment": sentiments1})
            df2 = pd.DataFrame({"Review Body": reviews2, "Sentiment": sentiments2})
            
            sentiment_counts1 = df1['Sentiment'].value_counts(normalize=True) * 100
            sentiment_counts2 = df2['Sentiment'].value_counts(normalize=True) * 100
            
            fig = go.Figure(data=[
                go.Bar(name='Product 1', x=['Positive', 'Negative'], 
                      y=[sentiment_counts1.get(1, 0), sentiment_counts1.get(0, 0)],
                      marker_color='green'),
                go.Bar(name='Product 2', x=['Positive', 'Negative'], 
                      y=[sentiment_counts2.get(1, 0), sentiment_counts2.get(0, 0)],
                      marker_color='blue')
            ])
            
            fig.update_layout(
                title='Sentiment Comparison',
                yaxis_title='Percentage of Reviews',
                barmode='group',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Display metrics
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Product 1 Metrics")
                st.metric("Total Ratings", ratings1 if ratings1 else "N/A")
                st.metric("Total Reviews", reviews_count1 if reviews_count1 else "N/A")
                st.metric("Positive Reviews", f"{sentiment_counts1.get(1, 0):.1f}%")
                
                st.subheader("Product 1 Reviews Sample")
                positive_reviews1 = df1[df1['Sentiment'] == 1]['Review Body'].head(5)
                negative_reviews1 = df1[df1['Sentiment'] == 0]['Review Body'].head(5)
                
                st.write("Positive Reviews:")
                for review in positive_reviews1:
                    st.success(review)
                    
                st.write("Negative Reviews:")
                for review in negative_reviews1:
                    st.warning(review)
                
            with col2:
                st.subheader("Product 2 Metrics")
                st.metric("Total Ratings", ratings2 if ratings2 else "N/A")
                st.metric("Total Reviews", reviews_count2 if reviews_count2 else "N/A")
                st.metric("Positive Reviews", f"{sentiment_counts2.get(1, 0):.1f}%")
                
                st.subheader("Product 2 Reviews Sample")
                positive_reviews2 = df2[df2['Sentiment'] == 1]['Review Body'].head(5)
                negative_reviews2 = df2[df2['Sentiment'] == 0]['Review Body'].head(5)
                
                st.write("Positive Reviews:")
                for review in positive_reviews2:
                    st.success(review)
                    
                st.write("Negative Reviews:")
                for review in negative_reviews2:
                    st.warning(review)
                
        except Exception as e:
            st.error("Error comparing products.")
            st.write(e)

def main():
    """
    Main application function that handles the UI and user interaction.
    """
    st.set_page_config(
        page_title="Flipkart Product Sentiment Analysis",
        page_icon="📊",
        layout="wide"
    )
    
    # Sidebar
    with st.sidebar:
        st.title("Navigation")
        selected_mode = st.radio(
            "Choose Analysis Mode",
            ["Single Product Analysis", "Compare Products"],
            key="sidebar_mode"
        )
        
        st.markdown("---")
        st.markdown("### How to Use")
        st.markdown("""
        1. Select analysis mode
        2. Paste Flipkart product URL(s)
        3. Click analyze/compare button
        """)
        
        st.markdown("---")
        st.markdown("### About")
        st.info(
            "This tool analyzes customer sentiments from Flipkart product reviews "
            "using machine learning."
        )
    
    # Main content
    st.title("🛍️ Sentiment Analysis of Flipkart Products")
    st.markdown("Analyze and compare customer sentiments for Flipkart products based on their reviews.")
    
    st.markdown("---")
    
    if selected_mode == "Single Product Analysis":
        st.subheader("Single Product Analysis")
        url = st.text_input("Enter Product URL", placeholder="Paste Flipkart product URL here")
        
        if st.button("Analyze", 
                     type="primary",
                     use_container_width=True):
            if url:
                analyze_single_product(url)
            else:
                st.warning("Please enter a product URL")
                
    else:  # Comparison mode
        st.subheader("Product Comparison")
        url1 = st.text_input("Product 1 URL", placeholder="Paste first product URL here")
        url2 = st.text_input("Product 2 URL", placeholder="Paste second product URL here")
            
        if st.button("Compare", 
                     type="primary",
                     use_container_width=True):
            if url1 and url2:
                analyze_comparison(url1, url2)
            else:
                st.warning("Please enter both product URLs")

if __name__ == "__main__":
    main()