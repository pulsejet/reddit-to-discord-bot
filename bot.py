#!/usr/bin/env python3

# Reddit bot to post the comments from reddit to a Discord channel that
# match a given search term.

import os
import praw
import praw.models
import requests
import json
import pickle
import asyncio
import logging
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Starting reddit-to-discord bot")

# Reddit API credentials
reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')

# Discord API credentials
discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

# Subreddits to search for comments
subreddits = os.getenv('SUBREDDITS', '').split(',')

# Search term to look for in comments
search_term = os.getenv('SEARCH_TERM')

# Pickle file to store seen comments in
pickle_file = os.getenv('DATABASE_FILE', 'seen_comments.pkl')

# Interval between checks in seconds
check_interval = int(os.getenv('CHECK_INTERVAL_SECONDS', '300'))
if check_interval < 10:
    logger.fatal("CHECK_INTERVAL_SECONDS must be at least 10 seconds")
    exit(1)

# Gemini API credentials
gemini_api_key = os.getenv('GEMINI_API_KEY')
gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite')
ai_validate_prompt = os.getenv('AI_VALIDATE_PROMPT')

# Check if all required environment variables are set
if not all([
        reddit_client_id,
        reddit_client_secret,
        discord_webhook_url,
        subreddits,
        search_term,
        pickle_file,
        gemini_api_key,
        ai_validate_prompt,
    ]):
    logger.fatal("One or more required environment variables are missing or empty")
    exit(1)
else:
    logger.info("")
    logger.info("Loaded configuration:")
    logger.info(f"  Subreddits: {', '.join(subreddits)}")
    logger.info(f"  Search term: {search_term}")
    logger.info(f"  Database file: {pickle_file}")
    logger.info(f"  Check interval: {check_interval} seconds")
    logger.info("")

# Initialize Reddit and Discord clients
reddit = praw.Reddit(client_id=reddit_client_id,
                     client_secret=reddit_client_secret,
                     user_agent='bot/0.0.1',
                     check_for_async=False,
                     read_only=True)

# Load seen comments from file
database: set[str] = set()
dirty: bool = False
try:
    with open(pickle_file, 'rb') as f:
        database = pickle.load(f)
        logger.info(f"Loaded {len(database)} objects from database file")
except FileNotFoundError:
    logger.warning("Database file not found, starting with empty database")
    with open(pickle_file, 'wb') as f:
        pickle.dump(database, f)


async def filter_gemini(content: str) -> bool:
    logger.info("Validating content with Gemini AI")
    try:
        prompt = f"{ai_validate_prompt}\n\n{content}"
        logger.info(f"Prompt to Gemini: {prompt}\n")

        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
        )

        # Play safe - discard only if AI explicitly says "no"
        response_text = response.text or ""
        logger.info(f"Gemini response: {response_text}")
        return not ('no' in response_text.lower())
    except Exception as e:
        logger.error(f"Error validating content with Gemini AI: {e}")
        return True

async def handle_object(
        typename: str,
        obj: praw.models.Comment | praw.models.Submission,
        body: str):
    if search_term.lower() not in body.lower():
        return
    if obj.id in database:
        return

    # Mark comment as seen
    global dirty
    database.add(obj.id)
    dirty = True

    # Validate comment with Gemini AI
    if not await filter_gemini(body[:2000]):
        logger.info(f"Object {obj.id} filtered out by Gemini AI")
        return

    # Trim comment body to 500 characters
    if len(body) > 500:
        body = body[:500] + ' ...'

    # Send comment to Discord
    await send_discord(typename, obj.subreddit, body, obj.permalink, obj.author)

async def send_discord(
        typename: str,
        subreddit: praw.models.Subreddit,
        body: str,
        permalink: str,
        author: praw.models.Redditor):
    # Get logo of subreddit
    logo = subreddit.icon_img
    if not logo:
        logo = subreddit.community_icon
    if not logo:
        logo = 'https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png'

    # Format comment data for Discord webhook
    data = {
        'username': f'r/{subreddit.display_name}',
        'avatar_url': logo,
        'embeds': [{
            'title': f'New {typename} in r/{subreddit.display_name}',
            'description': body,
            'url': f'https://reddit.com{permalink}',
            'author': {
                'name': f'u/{author.name}',
                'url': f'https://reddit.com/u/{author.name}',
                'icon_url': author.icon_img,
            },
        }],
    }

    # Send comment to Discord webhook
    headers = {'Content-Type': 'application/json'}
    response = requests.post(discord_webhook_url, data=json.dumps(data), headers=headers)
    logger.info("Discord POST status: %s (%d)", response.reason, response.status_code)

# Define function to start bot
async def start_bot():
    subreddit = reddit.subreddit('+'.join(subreddits))

    # Get 10 comments from the subreddit
    for comment in subreddit.comments(limit=20):
        await handle_object('comment', comment, comment.body)

    # Get 10 posts from the subreddit
    for submission in subreddit.new(limit=20):
        await handle_object('post', submission, submission.selftext)

    # Save seen comments to file
    global dirty
    if dirty:
        dirty = False
        logger.info(f"Saving {len(database)} objects to database file")
        with open(pickle_file, 'wb') as f:
            pickle.dump(database, f)
    else:
        logger.info("No new objects detected, skipping database update")

async def bot_loop():
    while True:
        logger.info("Checking for new comments and posts")
        await start_bot()
        logger.info(f"Sleeping for {check_interval} seconds")
        await asyncio.sleep(check_interval)

# Start bot
if __name__ == '__main__':
    asyncio.run(bot_loop())
