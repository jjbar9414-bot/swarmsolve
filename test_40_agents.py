#!/usr/bin/env python3
"""
SwarmSolve Mass Test — 40 Agents competing via Groq (free)
Run: python test_40_agents.py
"""

import requests
import time
import re
import random

# ==========================================================
# CONFIGURATION
# ==========================================================

SWARMSOLVE_URL = "https://web-production-ed55.up.railway.app"
GROQ_API_KEY = "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"
GROQ_MODEL = "llama-3.3-70b-versatile"
CHALLENGE_ID = "sort-speed"
NUM_AGENTS = 40
ROUNDS_PER_AGENT = 2  # each agent tries 2 times
WAIT_BETWEEN = 3  # seconds between requests (Groq rate limit)


def ask_groq(prompt):
    """Send prompt to Groq and get response"""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 2048,
            },
            timeout=60,
        )
        if r.status_code == 429:
            print("    Rate limited, waiting 30s...")
            time.sleep(30)
            return None
        if r.status_code != 200:
            print(f"    Groq error {r.status_code}: {r.text[:100]}")
            return None
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    Groq error: {e}")
        return None


def extract_code(response):
    """Extract Python code from LLM response"""
    if not response:
        return None

    # Try ```python ... ```
    matches = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
    if matches:
        return matches[0].strip()

    # Try ``` ... ```
    matches = re.findall(r"```\n(.*?)```", response, re.DOTALL)
    if matches:
        return matches[0].strip()

    # If has def, extract code lines
    if "def " in response:
        lines = response.split("\n")
        code_lines = []
        in_code = False
        for line in lines:
            if line.strip().startswith("def ") or in_code:
                in_code = True
                code_lines.append(line)
        if code_lines:
            return "\n".join(code_lines)

    return None


def run_test():
    print()
    print("=" * 60)
    print("  SwarmSolve Mass Test — 40 Agents via Groq")
    print("=" * 60)
    print(f"  Platform:  {SWARMSOLVE_URL}")
    print(f"  Challenge: {CHALLENGE_ID}")
    print(f"  Model:     {GROQ_MODEL}")
    print(f"  Agents:    {NUM_AGENTS}")
    print("=" * 60)
    print()

    # Step 1: Check platform is alive
    print("[1] Checking platform...")
    try:
        r = requests.get(f"{SWARMSOLVE_URL}/api/challenges", timeout=10)
        if r.status_code != 200:
            print(f"  Platform error: {r.status_code}")
            return
        print("  Platform is online!")
    except Exception as e:
        print(f"  Cannot reach platform: {e}")
        return

    # Step 2: Get initial challenge state
    print("\n[2] Getting challenge info...")
    r = requests.get(f"{SWARMSOLVE_URL}/api/challenge/{CHALLENGE_ID}", timeout=10)
    data = r.json()
    print(f"  Title: {data['title']}")
    print(f"  Initial score: {data['initial_score']}")
    print(f"  Current best: {data['best_score']}")
    print()

    # Step 3: Run agents
    agent_names = [f"Agent_{i:02d}" for i in range(NUM_AGENTS)]
    total_submissions = 0
    successful = 0
    best_score = 0

    for round_num in range(1, ROUNDS_PER_AGENT + 1):
        print(f"{'=' * 60}")
        print(f"  ROUND {round_num}/{ROUNDS_PER_AGENT}")
        print(f"{'=' * 60}")

        for i, agent_name in enumerate(agent_names):
            print(f"\n  [{total_submissions + 1}] {agent_name} (round {round_num})...")

            # Get challenge (agent sees their island's best)
            try:
                r = requests.get(
                    f"{SWARMSOLVE_URL}/api/challenge/{CHALLENGE_ID}",
                    params={"agent_name": agent_name},
                    timeout=15,
                )
                challenge = r.json()
            except Exception as e:
                print(f"    Failed to get challenge: {e}")
                continue

            if challenge.get("is_stopped"):
                print(f"    Challenge stopped! Best: {challenge.get('global_best_score')}")
                break

            current_code = challenge["best_solution"]
            current_score = challenge["best_score"]
            island = challenge.get("your_island", "?")

            print(f"    Island {island} | Best: {current_score}")

            # Ask Groq to improve
            prompt = f"""You are an expert Python programmer. Improve this sorting function to be FASTER.

Current code (score: {current_score} — higher is better, measures elements sorted per second):
```python
{current_code}
```
Rules:
- Function must be named `solve` and take a list parameter
- Must return the sorted list (ascending order)
- Must be correct — wrong results get score 0
- Make it FASTER — use better algorithms, avoid copies, use built-in optimizations
- You CAN use numpy (import numpy as np)
- Try: numpy argsort, radix sort, counting sort, or hybrid approaches
- Do NOT use external libraries other than numpy

Return ONLY the improved code in a ```python``` block."""

            response = ask_groq(prompt)
            improved = extract_code(response)

            if not improved:
                print("    Could not extract code, skipping...")
                time.sleep(WAIT_BETWEEN)
                continue

            # Submit solution
            try:
                result = requests.post(
                    f"{SWARMSOLVE_URL}/api/submit",
                    json={
                        "challenge_id": CHALLENGE_ID,
                        "code": improved,
                        "agent_name": agent_name,
                    },
                    timeout=60,
                )
                r_data = result.json()
            except Exception as e:
                print(f"    Submit failed: {e}")
                time.sleep(WAIT_BETWEEN)
                continue

            total_submissions += 1

            if r_data.get("ok"):
                score = r_data["score"]
                successful += 1
                if score > best_score:
                    best_score = score

                marker = ""
                if r_data.get("is_new_global_best"):
                    marker = " *** GLOBAL BEST! ***"
                elif r_data.get("is_new_island_best"):
                    marker = " * Island best!"

                print(f"    Score: {score:,.0f}{marker}")
            else:
                print(f"    Rejected: {r_data.get('error', '?')[:60]}")

            time.sleep(WAIT_BETWEEN)

    # Step 4: Show final results
    print()
    print("=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)
    print(f"  Total submissions: {total_submissions}")
    print(f"  Successful: {successful}")
    print(f"  Best score: {best_score:,.0f}")
    print()

    # Show leaderboard
    print("  LEADERBOARD:")
    r = requests.get(f"{SWARMSOLVE_URL}/api/leaderboard/{CHALLENGE_ID}", timeout=10)
    lb = r.json()
    for entry in lb.get("leaderboard", [])[:10]:
        print(f"    #{entry['rank']}: {entry['agent_name']} — {entry['score']:,.0f} (island {entry.get('island_id', '?')})")

    # Show island status
    print()
    print("  ISLAND STATUS:")
    r = requests.get(f"{SWARMSOLVE_URL}/api/islands/{CHALLENGE_ID}", timeout=10)
    status = r.json()
    print(f"    Islands: {status['num_islands']}")
    print(f"    Total agents: {status['total_agents']}")
    print(f"    Migrations: {status['migrations_completed']}")
    for s in status.get("island_stats", []):
        print(f"    Island {s['island_id']}: {s['num_agents']} agents, {s['num_solutions']} solutions, best={s['best_score']:,.0f}")

    print()
    print("  Done! Check the platform:")
    print(f"  {SWARMSOLVE_URL}/leaderboard")
    print()


if __name__ == "__main__":
    run_test()