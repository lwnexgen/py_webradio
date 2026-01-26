#!pysched/bin/python
import argparse
import base64
import fnmatch
import json
import os
import pdb  # noqa: F401
import sys
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import arrow
import requests
import torch
from bs4 import BeautifulSoup as Soup
from flask import Flask, Response, stream_with_context
from openai import OpenAI
from PIL import Image
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoProcessor

from mdparse import convert_to_json, print_boxscore, split_attempts
from screenshotter import NBA_TEAMS, screenshot_url
from vllm import LLM, SamplingParams
from vllm.model_executor.models.deepseek_ocr import NGramPerReqLogitsProcessor

# Create model instance
llm = LLM(
    model="deepseek-ai/DeepSeek-OCR",
    enable_prefix_caching=False,
    mm_processor_cache_gb=0,
    logits_processors=[NGramPerReqLogitsProcessor],
)

app = Flask(__name__)

# "mlb": ["MIL", "Milwaukee", "Brewers", "Milwaukee Brewers"],
# "nfl": ["GB", "Green Bay", "Packers", "Green Bay Packers"],
# "ncaaf": ["WIS", "Wisconsin", "Badgers", "Wisconsin Badgers"],
# "ncaab": ["WIS", "Wisconsin", "Badgers", "Wisconsin Badgers"],

favorites = {
    "nba": ["MIL", "Milwaukee", "Bucks", "Milwaukee Bucks"],
}


def scrape_links_by_pattern(base_url, pattern):
    matching_links = set()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    try:
        html_content = ""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.goto(base_url, timeout=10000, wait_until="domcontentloaded")
            html_content = page.content()
            browser.close()

        soup = Soup(html_content, "html.parser")
        for link in soup.find_all("a"):
            href = link.get("href")
            if not href:
                continue
            absolute_url = urljoin(base_url, href)
            if fnmatch.fnmatch(absolute_url, pattern):
                matching_links.add(absolute_url)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return []

    return list(matching_links)


def image_to_base64_data_uri(file_path):
    print(f"Encoding image {file_path} to base64 data URI...")
    with open(file_path, "rb") as img_file:
        base64_data = base64.b64encode(img_file.read()).decode("utf-8")
        return f"data:image/png;base64,{base64_data}"


def parse_screenshot_with_ollama(image_path, metadata={}):
    print(f"Parsing screenshot at {image_path} with metadata: {metadata}")

    # Prepare batched input with your image file
    image_1 = Image.open(image_path).convert("RGB")
    # prompt = "<image>\nFree OCR"
    prompt = "<image>\nExtract the basketball box score table in markdown format."
    model_input = [
        {"prompt": prompt, "multi_modal_data": {"image": image_1}},
    ]

    sampling_param = SamplingParams(
        temperature=0.0,
        max_tokens=8192,
        # ngram logit processor args
        extra_args=dict(
            ngram_size=30,
            window_size=90,
            whitelist_token_ids={128821, 128822},  # whitelist: <td>, </td>
        ),
        skip_special_tokens=False,
    )

    # Generate output
    model_outputs = llm.generate(model_input, sampling_param)

    for output in model_outputs:
        output_path = image_path.replace(".png", "_ocr_output.md")
        with open(output_path, "w") as f:
            f.write(output.outputs[0].text)
        try:
            parsed, headers = split_attempts(convert_to_json(output.outputs[0].text))
        except Exception as e:
            print(f"Error parsing OCR output: {e} - see {output_path}")
            parsed, headers = {}, []
        return (parsed, output_path)


@app.route("/stream")
def home():
    def event_stream():
        while True:
            screenshot_paths = screenshot_url(
                GAME_URL.replace("matchup", "matchup"),
                obj_filter={"selector": "div.Boxscore"},
            )
            data = []
            for i, screenshot_path in enumerate(screenshot_paths):
                boxdata, boxmd = parse_screenshot_with_ollama(
                    screenshot_path, metadata=GAME_INFO
                )
                data.append(print_boxscore(boxdata))

            datastr = "\n\n".join(data)

            # Format as an SSE message: "data: ...\n\n"
            yield f"data:\n{datastr}\n\n"

            # Wait for 1 second before sending the next update
            time.sleep(10)

    global GAME_URL
    global GAME_INFO

    GAME_URL, GAME_INFO = find_game_url()
    print(f"Monitoring game at URL: {GAME_URL}")

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # Best practice: tell Nginx not to buffer this response
        "X-Accel-Buffering": "no",
    }

    # stream_with_context is important for long-running responses
    return Response(stream_with_context(event_stream()), headers=headers)


def cmd():
    parser = argparse.ArgumentParser(
        description="emit events at specified intervals when a given ESPN score changes"
    )
    parser.add_argument("game_url", help="The ESPN game URL to monitor")
    return parser.parse_args()


def load_scoreboard(sport):
    print(f"Loading scoreboard for {sport}...")
    base_url = f"https://www.espn.com/{sport}/scoreboard"
    pattern = f"https://www.espn.com/{sport}/boxscore/_/gameId/*"
    game_links = scrape_links_by_pattern(base_url, pattern)
    return game_links


def find_game_url():
    user_agent_str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    # for league, favs in favorites.items():
    #     print(f"Scraping current scores for {league}...")
    #     for link in load_scoreboard(league):
    #         resp = Soup(
    #             requests.get(link, headers={"User-Agent": user_agent_str}).text,
    #             "html.parser",
    #         )
    #         title = resp.find("title").text
    #         if any(fav in title for fav in favs):
    #             print(f"Found favorite game: {title}")
    #             print(f"URL: {link}")
    #             return link
    # link = "https://www.espn.com/nba/boxscore/_/gameId/401809962"
    link = "https://www.espn.com/nba/boxscore/_/gameId/401810068"
    # link = "https://www.espn.com/womens-college-basketball/boxscore/_/gameId/401812567"
    resp = Soup(
        requests.get(link, headers={"User-Agent": user_agent_str}).text,
        "html.parser",
    )
    title = resp.find("title").text
    _description = resp.find("meta", {"name": "description"})
    if _description:
        description = _description.get("content", "")
    metadata = {"sport": "nba", "page_title": title}
    return link, metadata


if __name__ == "__main__":
    app.run(host="192.168.0.197", port=5001)
