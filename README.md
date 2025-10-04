# reddit-to-discord-bot

Bot to monitor Reddit comments and posts, filter them using AI and send them to a discord channel.

Useful for finding user feedback on a product, service or topic.

## Usage

1. Create a `.env` file with the configuration variables.
    ```env
    REDDIT_CLIENT_ID=your_reddit_client_id
    REDDIT_CLIENT_SECRET=your_reddit_client_secret
    DISCORD_WEBHOOK_URL=webhook_url_for_your_discord_channel

    SUBREDDITS=comma,separated,list,of,subreddits
    SEARCH_TERM=word_or_phrase_to_search_for
    CHECK_INTERVAL_SECONDS=300

    GEMINI_API_KEY=your_gemini_api_key
    AI_VALIDATE_PROMPT=Does the following text have a relation with MY_PRODUCT app?
    ```

1. Build and start using Docker compose
    ```bash
    docker-compose up -d
    ```

## License

Permissive MIT License. See `LICENSE` file for details.
