import time

from google import genai

from app.config import Config

_gemini = genai.Client(api_key=Config.GEMINI_API_KEY)


def get_ai_summary(ticker: str, price_data: dict, articles: list[dict], is_fresh: bool) -> str:
    direction = "up" if price_data["pct_change"] >= 0 else "down"

    article_blocks = []
    for a in articles:
        if a["text"]:
            article_blocks.append(f"Headline: {a['title']}\n{a['text']}")
        else:
            article_blocks.append(f"Headline: {a['title']}")
    articles_text = "\n\n---\n\n".join(article_blocks)

    if is_fresh:
        context_note = "Here is today's news coverage:"
        instruction = (
            f"In 2-3 sentences, explain why {ticker} moved the way it did today "
            f"based on this coverage. Be direct and specific."
        )
    else:
        context_note = "There was no major news published today. Here is the most recent coverage:"
        instruction = (
            f"In 2-3 sentences, note that there wasn't much news today for {ticker} "
            f"and briefly summarize the recent context that may be influencing the move."
        )

    prompt = (
        f"{ticker} moved {direction} {abs(price_data['pct_change']):.2f}% today, "
        f"closing at ${price_data['price']:.2f}.\n\n"
        f"{context_note}\n\n{articles_text}\n\n{instruction} No filler phrases."
    )

    for attempt in range(4):
        try:
            response = _gemini.models.generate_content(
                model="gemini-2.5-flash", contents=prompt
            )
            return response.text
        except Exception:
            if attempt == 3:
                raise
            wait = 15 * (2 ** attempt)
            time.sleep(wait)
