from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re
import csv
import time

def get_ratings_and_reviews(url):
    # Set up headless Chrome options
    options = Options()
    options.headless = True  # Run in headless mode (no GUI)
    
    # Initialize the WebDriver with the headless option
    driver = webdriver.Chrome(options=options)
    
    # Open the webpage
    driver.get(url)
    
    # Get the page source after all JavaScript has loaded
    page_source = driver.page_source
    
    # Parse the page with BeautifulSoup
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Find the specific span with class="Wphh3N"
    span_tag = soup.find('span', class_="Wphh3N")
    
    # Extract text if the span tag was found, otherwise set to None
    if span_tag:
        text = span_tag.get_text()
        
        # Use regular expressions to extract ratings and reviews separately
        ratings_match = re.search(r'(\d+,\d+|\d+) ratings', text)
        reviews_match = re.search(r'(\d+,\d+|\d+) reviews', text)
        
        ratings = ratings_match.group(1) if ratings_match else None
        reviews = reviews_match.group(1) if reviews_match else None
    else:
        ratings, reviews = None, None
    
    # Close the browser
    driver.quit()
    
    return ratings, reviews

def scrape_reviews(url, num_reviews=100):
    # Modify URL to go to the reviews page
    reviews_url = url.replace("/p/", "/product-reviews/")
    
    # Set up headless Chrome options
    options = Options()
    options.headless = True
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(options=options)
    
    reviews_data = []
    page_number = 1
    
    while len(reviews_data) < num_reviews:
        # Open the reviews page with the updated page number
        driver.get(f"{reviews_url}&page={page_number}")
        
        # Get the page source after JavaScript loads
        page_source = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find all divs containing individual reviews
        review_divs = soup.find_all('div', class_="_11pzQk")
        
        # Extract text from each review div and add to the list
        for review_div in review_divs:
            review_text = review_div.get_text(strip=True)
            reviews_data.append(review_text)
            if len(reviews_data) >= num_reviews:
                break  # Stop if we've collected enough reviews
        
        # Increment the page number to move to the next page of reviews
        page_number += 1
        time.sleep(2)  # Sleep to avoid hitting rate limits
    
    # Close the browser
    driver.quit()
    
    # Save the reviews to a CSV file
    with open('reviews.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Review'])
        for review in reviews_data:
            writer.writerow([review])
    
    print(f"Saved {len(reviews_data)} reviews to 'reviews.csv'.")

# Example usage
flipkart_url = "https://www.flipkart.com/titan-karishma-analog-watch-women/p/itmf7gdx6usedpun?pid=WATF7GCFGUUP3DKX&lid=LSTWATF7GCFGUUP3DKXZYAUJR&marketplace=FLIPKART&q=titan&store=r18%2Ff13&srno=s_1_8&otracker=AS_QueryStore_OrganicAutoSuggest_2_2_na_na_na&otracker1=AS_QueryStore_OrganicAutoSuggest_2_2_na_na_na&fm=search-autosuggest&iid=01e3cff2-3f3f-4dbb-a43f-2e26724f7afe.WATF7GCFGUUP3DKX.SEARCH&ppt=sp&ppn=sp&qH=3250320dcaf3b60f"
ratings, reviews = get_ratings_and_reviews(flipkart_url)

# Print total ratings and reviews if found
if ratings and reviews:
    print("Total Ratings:", ratings)
    print("Total Reviews:", reviews)
else:
    print("Ratings and reviews not found.")

# Scrape individual reviews and save them to CSV
scrape_reviews(flipkart_url)
