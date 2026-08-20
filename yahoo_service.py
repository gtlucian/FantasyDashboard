#!/usr/bin/env python3
"""
Yahoo Fantasy Sports API Service & OAuth2 Client
Handles authentication, token refresh, and endpoints for:
- User Leagues & Metadata
- League Standings & FAAB Balances
- Rosters & Matchups
- Draft History & Transactions
- Live Waiver Wire / Free Agent Pool
- Built-in Realistic Demo League Generator for immediate offline testing
"""

import os
import json
import time
import base64
import logging
from typing import Dict, List, Any, Optional
import httpx

logger = logging.getLogger("YahooFantasyService")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_CACHE_FILE = os.path.join(PROJECT_DIR, ".yahoo_oauth_token.json")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")

YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"

def load_env_vars() -> Dict[str, str]:
    """Loads environment variables from .env file."""
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'").strip('"')
                    os.environ[k.strip()] = env_vars[k.strip()]
    return env_vars

class YahooFantasyClient:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, redirect_uri: str = "oob"):
        env_vars = load_env_vars()
        self.client_id = client_id or os.getenv("YAHOO_CLIENT_ID") or env_vars.get("YAHOO_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("YAHOO_CLIENT_SECRET") or env_vars.get("YAHOO_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv("YAHOO_REDIRECT_URI", "oob")
        self.token_data: Optional[Dict[str, Any]] = None
        self._load_cached_token()

    def _load_cached_token(self):
        """Loads OAuth token from local cache file if available."""
        if os.path.exists(TOKEN_CACHE_FILE):
            try:
                with open(TOKEN_CACHE_FILE, "r") as f:
                    self.token_data = json.load(f)
                    if not self.client_id and "client_id" in self.token_data:
                        self.client_id = self.token_data["client_id"]
                    if not self.client_secret and "client_secret" in self.token_data:
                        self.client_secret = self.token_data["client_secret"]
            except Exception as e:
                logger.warning(f"Could not load cached Yahoo token: {e}")

    def _save_cached_token(self, token_data: Dict[str, Any]):
        """Persists OAuth token to local cache file."""
        self.token_data = token_data
        token_data["saved_at"] = time.time()
        if self.client_id:
            token_data["client_id"] = self.client_id
        if self.client_secret:
            token_data["client_secret"] = self.client_secret
        try:
            with open(TOKEN_CACHE_FILE, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.info("Saved Yahoo OAuth2 tokens to cache.")
        except Exception as e:
            logger.error(f"Failed to cache Yahoo OAuth2 token: {e}")

    def get_authorization_url(self) -> str:
        """Returns the URL for the user to visit and authorize the app."""
        if not self.client_id:
            raise ValueError("YAHOO_CLIENT_ID is not configured. Please set it in .env or pass it to the constructor.")
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "language": "en-us",
            "scope": "openid fspt-r"
        }
        query_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{YAHOO_AUTH_URL}?{query_str}"

    def exchange_code_for_token(self, auth_code: str) -> Dict[str, Any]:
        """Exchanges an authorization code for access and refresh tokens."""
        if not self.client_id or not self.client_secret:
            raise ValueError("YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET are required.")

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code": auth_code.strip()
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(YAHOO_TOKEN_URL, headers=headers, data=data)
            if resp.status_code != 200:
                raise RuntimeError(f"Yahoo OAuth failed ({resp.status_code}): {resp.text}")
            token_json = resp.json()
            self._save_cached_token(token_json)
            return token_json

    def refresh_access_token(self) -> str:
        """Refreshes the access token using the stored refresh token."""
        if not self.token_data or "refresh_token" not in self.token_data:
            raise ValueError("No refresh token available. User must re-authenticate.")

        if not self.client_id or not self.client_secret:
            if "client_id" in self.token_data and "client_secret" in self.token_data:
                self.client_id = self.token_data["client_id"]
                self.client_secret = self.token_data["client_secret"]
            else:
                raise ValueError("YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET are missing for refresh.")

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "redirect_uri": self.redirect_uri,
            "refresh_token": self.token_data["refresh_token"]
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(YAHOO_TOKEN_URL, headers=headers, data=data)
            if resp.status_code != 200:
                raise RuntimeError(f"Yahoo Token Refresh failed ({resp.status_code}): {resp.text}")
            new_tokens = resp.json()
            if "refresh_token" not in new_tokens:
                new_tokens["refresh_token"] = self.token_data["refresh_token"]
            self._save_cached_token(new_tokens)
            return new_tokens["access_token"]

    def get_valid_access_token(self) -> str:
        """Returns a valid access token, auto-refreshing if expired."""
        if not self.token_data or "access_token" not in self.token_data:
            raise ValueError("Not authenticated with Yahoo. Please authenticate first.")

        saved_at = self.token_data.get("saved_at", 0)
        expires_in = self.token_data.get("expires_in", 3600)
        if time.time() - saved_at > (expires_in - 300):
            logger.info("Access token expired or close to expiry. Refreshing...")
            return self.refresh_access_token()

        return self.token_data["access_token"]

    def is_authenticated(self) -> bool:
        """Checks if valid credentials and tokens exist."""
        return bool(self.token_data and "access_token" in self.token_data)

    def api_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Makes an authenticated GET request to the Yahoo Fantasy API returning JSON."""
        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        url = f"{YAHOO_API_BASE}/{endpoint.lstrip('/')}"
        query_params = params.copy() if params else {}
        query_params["format"] = "json"

        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers, params=query_params)
            if resp.status_code == 401:
                token = self.refresh_access_token()
                headers["Authorization"] = f"Bearer {token}"
                resp = client.get(url, headers=headers, params=query_params)
            
            if resp.status_code != 200:
                raise RuntimeError(f"Yahoo API Error ({resp.status_code}) on {url}: {resp.text}")
            
            return resp.json()

    # --- High-Level Yahoo Fantasy Endpoints ---

    def get_user_leagues(self, game_code: str = "nfl") -> List[Dict[str, Any]]:
        """Fetches all leagues for the authenticated user."""
        res = self.api_get(f"users;use_login=1/games;game_keys={game_code}/leagues")
        try:
            users_data = res.get("fantasy_content", {}).get("users", {})
            if isinstance(users_data, dict) and "0" in users_data:
                user = users_data["0"]["user"]
                games = user[1]["games"]
                game = games["0"]["game"]
                leagues_obj = game[1]["leagues"]
                
                count = leagues_obj.get("count", 0)
                leagues = []
                for i in range(count):
                    league_item = leagues_obj[str(i)]["league"][0]
                    leagues.append({
                        "league_key": league_item.get("league_key"),
                        "league_id": league_item.get("league_id"),
                        "name": league_item.get("name"),
                        "num_teams": league_item.get("num_teams"),
                        "season": league_item.get("season"),
                        "scoring_type": league_item.get("scoring_type")
                    })
                return leagues
        except Exception as e:
            logger.error(f"Error parsing user leagues: {e}")
        return []

    def get_league_standings(self, league_key: str) -> List[Dict[str, Any]]:
        """Fetches standings, FAAB balances, wins/losses for all teams in a league."""
        res = self.api_get(f"league/{league_key}/standings")
        teams_list = []
        try:
            league = res.get("fantasy_content", {}).get("league", [])
            standings = league[1].get("standings", [{}])[0].get("teams", {})
            count = standings.get("count", 0)
            for i in range(count):
                team_data = standings[str(i)]["team"][0]
                team_meta = {}
                for item in team_data:
                    if isinstance(item, dict):
                        team_meta.update(item)
                
                team_standings = standings[str(i)]["team"][2].get("team_standings", {})
                outcome = team_standings.get("outcome_totals", {})
                
                managers = team_meta.get("managers", [{}])
                mgr_name = managers[0].get("manager", {}).get("nickname", "Unknown") if managers else "Unknown"

                teams_list.append({
                    "team_key": team_meta.get("team_key"),
                    "team_id": team_meta.get("team_id"),
                    "team_name": team_meta.get("name"),
                    "manager_name": mgr_name,
                    "faab_balance": int(team_meta.get("faab_balance", 100)) if team_meta.get("faab_balance") is not None else 100,
                    "waiver_priority": int(team_meta.get("waiver_priority", 1)) if team_meta.get("waiver_priority") is not None else 1,
                    "rank": int(team_standings.get("rank", i + 1)),
                    "wins": int(outcome.get("wins", 0)),
                    "losses": int(outcome.get("losses", 0)),
                    "ties": int(outcome.get("ties", 0)),
                    "points_for": float(team_standings.get("points_for", 0.0)),
                    "points_against": float(team_standings.get("points_against", 0.0))
                })
        except Exception as e:
            logger.error(f"Error parsing league standings: {e}")
        return teams_list

    def get_league_rosters(self, league_key: str) -> List[Dict[str, Any]]:
        """Fetches complete roster of every team in the league."""
        res = self.api_get(f"league/{league_key}/teams/roster")
        roster_rows = []
        try:
            league = res.get("fantasy_content", {}).get("league", [])
            teams_obj = league[1].get("teams", {})
            count = teams_obj.get("count", 0)
            for i in range(count):
                team_root = teams_obj[str(i)]["team"]
                team_meta = {}
                for item in team_root[0]:
                    if isinstance(item, dict):
                        team_meta.update(item)
                
                team_name = team_meta.get("name", f"Team {i+1}")
                team_key_val = team_meta.get("team_key")
                
                roster = team_root[1].get("roster", {}).get("0", {}).get("players", {})
                p_count = roster.get("count", 0)
                for p_idx in range(p_count):
                    player_obj = roster[str(p_idx)]["player"]
                    p_meta = {}
                    for p_item in player_obj[0]:
                        if isinstance(p_item, dict):
                            p_meta.update(p_item)
                    
                    selected_position = player_obj[1].get("selected_position", [{}])[1].get("position", "BN")
                    
                    roster_rows.append({
                        "team_key": team_key_val,
                        "team_name": team_name,
                        "player_key": p_meta.get("player_key"),
                        "player_id": p_meta.get("player_id"),
                        "player_name": p_meta.get("name", {}).get("full", "Unknown"),
                        "position": p_meta.get("primary_position", "FLEX"),
                        "nfl_team": p_meta.get("editorial_team_abbr", "FA"),
                        "status": p_meta.get("status", "Healthy"),
                        "roster_slot": selected_position,
                        "is_starter": selected_position not in ["BN", "IR"]
                    })
        except Exception as e:
            logger.error(f"Error parsing rosters: {e}")
        return roster_rows

    def get_league_transactions(self, league_key: str) -> List[Dict[str, Any]]:
        """Fetches transactions (adds, drops, trades, winning & losing FAAB bids)."""
        res = self.api_get(f"league/{league_key}/transactions")
        tx_rows = []
        try:
            league = res.get("fantasy_content", {}).get("league", [])
            txs_obj = league[1].get("transactions", {})
            count = txs_obj.get("count", 0)
            for i in range(count):
                tx_data = txs_obj[str(i)]["transaction"]
                tx_meta = tx_data[0]
                
                tx_id = tx_meta.get("transaction_id")
                tx_type = tx_meta.get("type")
                status = tx_meta.get("status")
                timestamp = int(tx_meta.get("timestamp", 0))
                faab_bid = int(tx_meta.get("faab_bid", 0)) if tx_meta.get("faab_bid") else 0
                
                players_wrapper = tx_data[1].get("players", {}) if len(tx_data) > 1 else {}
                p_count = players_wrapper.get("count", 0)
                for p_i in range(p_count):
                    p_obj = players_wrapper[str(p_i)]["player"]
                    p_meta = p_obj[0][2] if len(p_obj[0]) > 2 else {}
                    t_data = p_obj[1].get("transaction_data", [{}])[0]
                    
                    tx_rows.append({
                        "transaction_id": tx_id,
                        "type": tx_type,
                        "status": status,
                        "timestamp": timestamp,
                        "faab_bid": faab_bid,
                        "player_name": p_meta.get("name", {}).get("full", "Unknown"),
                        "source_type": t_data.get("source_type"),
                        "destination_type": t_data.get("destination_type"),
                        "destination_team_name": t_data.get("destination_team_name", "Free Agent")
                    })
        except Exception as e:
            logger.error(f"Error parsing transactions: {e}")
        return tx_rows

    def get_league_draft_results(self, league_key: str) -> List[Dict[str, Any]]:
        """Fetches draft picks, rounds, teams, and players selected."""
        res = self.api_get(f"league/{league_key}/draftresults")
        picks = []
        try:
            league = res.get("fantasy_content", {}).get("league", [])
            draft_obj = league[1].get("draft_results", {})
            count = draft_obj.get("count", 0)
            for i in range(count):
                pick_data = draft_obj[str(i)]["draft_result"]
                picks.append({
                    "pick": int(pick_data.get("pick", i + 1)),
                    "round": int(pick_data.get("round", 1)),
                    "team_key": pick_data.get("team_key"),
                    "player_key": pick_data.get("player_key")
                })
        except Exception as e:
            logger.error(f"Error parsing draft results: {e}")
        return picks

    def get_available_free_agents(self, league_key: str, count: int = 150) -> List[Dict[str, Any]]:
        """Fetches top available Free Agents & Waiver players."""
        res = self.api_get(f"league/{league_key}/players;status=A;sort=AR;count={count}")
        fa_players = []
        try:
            league = res.get("fantasy_content", {}).get("league", [])
            players_obj = league[1].get("players", {})
            p_count = players_obj.get("count", 0)
            for i in range(p_count):
                p_item = players_obj[str(i)]["player"][0]
                p_meta = {}
                for item in p_item:
                    if isinstance(item, dict):
                        p_meta.update(item)
                
                fa_players.append({
                    "player_key": p_meta.get("player_key"),
                    "player_id": p_meta.get("player_id"),
                    "player_name": p_meta.get("name", {}).get("full", "Unknown"),
                    "position": p_meta.get("primary_position", "FLEX"),
                    "team": p_meta.get("editorial_team_abbr", "FA"),
                    "status": p_meta.get("status", "Healthy"),
                    "percent_owned": float(p_meta.get("percent_owned", [{}])[1].get("value", 0)) if isinstance(p_meta.get("percent_owned"), list) else 0.0
                })
        except Exception as e:
            logger.error(f"Error parsing free agents: {e}")
        return fa_players

# --- Realistic Demo / Mock League Generator ---

def get_demo_league_data() -> Dict[str, Any]:
    """
    Authentic Sweet N' Sour Sundays (Yahoo League ID: 760420)
    Complete with real standings, records, points for/against, FAAB balances, and scouting profiles.
    """
    teams = [
        {"team_id": 10, "team_name": "Slop Ass Final", "manager_name": "Slop Ass Final", "faab_balance": 5, "waiver_priority": 8, "rank": 1, "wins": 12, "losses": 2, "points_for": 1842.08, "points_against": 1362.50, "moves": 28, "title": "🏆 Reigning Champion"},
        {"team_id": 2, "team_name": "1. 2. 3. Cancun", "manager_name": "1. 2. 3. Cancun", "faab_balance": 0, "waiver_priority": 9, "rank": 2, "wins": 11, "losses": 3, "points_for": 1701.58, "points_against": 1609.98, "moves": 42, "title": "🥈 Runner-Up"},
        {"team_id": 3, "team_name": "IM STILL THAT NJIGBA", "manager_name": "IM STILL THAT NJIGBA", "faab_balance": 0, "waiver_priority": 12, "rank": 3, "wins": 7, "losses": 7, "points_for": 1763.94, "points_against": 1631.96, "moves": 44, "title": "🥉 3rd Place"},
        {"team_id": 11, "team_name": "Packs Best Team", "manager_name": "Packs Best Team", "faab_balance": 0, "waiver_priority": 7, "rank": 4, "wins": 9, "losses": 5, "points_for": 1519.30, "points_against": 1477.94, "moves": 38, "title": "Playoff Contender"},
        {"team_id": 5, "team_name": "Gang Green LV", "manager_name": "Gang Green LV", "faab_balance": 15, "waiver_priority": 3, "rank": 5, "wins": 9, "losses": 5, "points_for": 1596.62, "points_against": 1457.88, "moves": 20, "title": "Selective Sniper"},
        {"team_id": 9, "team_name": "Ty loves man", "manager_name": "Ty loves man", "faab_balance": 15, "waiver_priority": 10, "rank": 6, "wins": 8, "losses": 6, "points_for": 1444.96, "points_against": 1375.20, "moves": 38, "title": "Playoff Seed #6"},
        {"team_id": 7, "team_name": "Fantasy Gods were Displeased", "manager_name": "Fantasy Gods were Displeased", "faab_balance": 46, "waiver_priority": 2, "rank": 7, "wins": 6, "losses": 8, "points_for": 1634.50, "points_against": 1664.98, "moves": 77, "title": "👑 Churn King ($46 FAAB Leader)"},
        {"team_id": 1, "team_name": "2-1?😉 ..…🎤🎤 (The Commish)", "manager_name": "The Commish", "faab_balance": 25, "waiver_priority": 4, "rank": 8, "wins": 6, "losses": 8, "points_for": 1557.84, "points_against": 1694.64, "moves": 17, "title": "The Commissioner"},
        {"team_id": 8, "team_name": "Probably on 2k", "manager_name": "Probably on 2k", "faab_balance": 15, "waiver_priority": 1, "rank": 9, "wins": 6, "losses": 8, "points_for": 1578.14, "points_against": 1651.02, "moves": 21, "title": "Waiver Priority #1"},
        {"team_id": 12, "team_name": "On that doo doo", "manager_name": "On that doo doo", "faab_balance": 18, "waiver_priority": 11, "rank": 10, "wins": 3, "losses": 11, "points_for": 1327.48, "points_against": 1631.22, "moves": 23, "title": "L-8 Skid"},
        {"team_id": 6, "team_name": "In the fields", "manager_name": "In the fields", "faab_balance": 0, "waiver_priority": 5, "rank": 11, "wins": 5, "losses": 9, "points_for": 1514.58, "points_against": 1574.00, "moves": 30, "title": "$0 FAAB Depleted"},
        {"team_id": 4, "team_name": "2-1 vs Cobitchioner", "manager_name": "2-1 vs Cobitchioner", "faab_balance": 0, "waiver_priority": 6, "rank": 12, "wins": 2, "losses": 12, "points_for": 1309.82, "points_against": 1659.52, "moves": 22, "title": "Rivalry Focused"}
    ]

    # Manager Tendency Profiles (Historical Habits)
    manager_profiles = {
        "Slop Ass Final": {
            "draft_archetype": "🏆 Reigning Champion & Efficiency Anchor",
            "draft_tendency": "Elite high-floor drafting; prioritizes workhorse bellcow RBs and anchor WRs.",
            "reach_tendency": "Strict value drafter; never reaches early.",
            "faab_style": "Precision Finisher ($5 remaining; spent $95 on high-impact championship starters).",
            "faab_aggressiveness_score": 75,
            "trade_frequency": "Low (Prefers riding established juggernaut lineup).",
            "vulnerabilities": "Down to $5 FAAB; will lose any contested waiver bid over $6."
        },
        "1. 2. 3. Cancun": {
            "draft_archetype": "⚡ Aggressive Contender / Heavy Churner",
            "draft_tendency": "Heavy upside drafter; attacks high-volume passing offenses.",
            "reach_tendency": "Willing to reach 1-2 rounds early on breakout skill players.",
            "faab_style": "All-In Depleted ($0 remaining after 42 roster transactions).",
            "faab_aggressiveness_score": 92,
            "trade_frequency": "Very Active (Initiates frequent 2-for-1 upgrade offers).",
            "vulnerabilities": "Completely out of FAAB ($0); cannot place non-$0 bids."
        },
        "IM STILL THAT NJIGBA": {
            "draft_archetype": "📈 High-Ceiling Unlucky Juggernaut",
            "draft_tendency": "Drafts target monster WRs and high-octane flex weapons (#2 in league scoring with 1763.94 PF).",
            "reach_tendency": "Follows consensus tiers closely with WR bias.",
            "faab_style": "Max Aggression Churner (44 moves, $0 FAAB left).",
            "faab_aggressiveness_score": 88,
            "trade_frequency": "Moderate.",
            "vulnerabilities": "$0 FAAB war chest; target his dropped bench depth on Wednesday mornings."
        },
        "Fantasy Gods were Displeased": {
            "draft_archetype": "👑 Hyperactive Churn King (77 Moves & $46 FAAB Leader)",
            "draft_tendency": "Rebuilds entire roster continuously on the wire; sets league record with 77 transaction moves.",
            "reach_tendency": "Gambles on high-volatility prospects.",
            "faab_style": "Deep War Chest ($46 remaining — HIGHEST PURCHASING POWER IN LEAGUE).",
            "faab_aggressiveness_score": 85,
            "trade_frequency": "High (Sends exploratory offers weekly).",
            "vulnerabilities": "Holds the #1 FAAB balance ($46); bids $15-$25 on top breakouts. Must bid $47 to lock him out."
        },
        "The Commish": {
            "draft_archetype": "⚖️ The Commissioner / Calculated Disciplinarian",
            "draft_tendency": "Balanced hero-RB roster building with high-floor veterans (17 moves).",
            "reach_tendency": "ADP value exploiter; capitalizes on tier drop-off cliffs.",
            "faab_style": "Calculated Precision ($25 war chest intact; Waiver Priority #4).",
            "faab_aggressiveness_score": 55,
            "trade_frequency": "Active & Fair-Value Seeking.",
            "vulnerabilities": "Bench depth has 1-2 droppable assets ready for high-yield waiver upgrades."
        },
        "Probably on 2k": {
            "draft_archetype": "🎮 Casual Gamer & Waiver Priority #1 Lurker",
            "draft_tendency": "Drafts standard default rankings; conservative in-season manager (21 moves).",
            "reach_tendency": "Follows default Yahoo draft room ranking order.",
            "faab_style": "Moderate ($15 remaining, holds #1 Rolling Waiver Priority).",
            "faab_aggressiveness_score": 35,
            "trade_frequency": "Low.",
            "vulnerabilities": "Slow to react on breaking camp news; can be beaten by fast Sunday/Tuesday night bids."
        },
        "Gang Green LV": {
            "draft_archetype": "🎯 Selective Sniper / Roster Preserver",
            "draft_tendency": "Drafts high-floor defense and veteran skill players; makes only 20 total moves (9-5 record).",
            "reach_tendency": "Disciplined value drafter.",
            "faab_style": "Conservative Reserve ($15 remaining).",
            "faab_aggressiveness_score": 40,
            "trade_frequency": "Low.",
            "vulnerabilities": "Reluctant to drop drafted veterans; slow to pivot when handcuffs take over."
        },
        "Packs Best Team": {
            "draft_archetype": "🧀 Green Bay Homer & Consistent Grinder",
            "draft_tendency": "Heavy Packer bias; prioritizes NFC North starters and consistent weekly floor.",
            "reach_tendency": "Reaches on Green Bay targets 1-2 rounds early.",
            "faab_style": "Fully Spent ($0 remaining, 38 moves).",
            "faab_aggressiveness_score": 80,
            "trade_frequency": "Moderate if offering Packers players.",
            "vulnerabilities": "$0 FAAB remaining; highly susceptible to trade packages featuring Green Bay assets."
        },
        "Ty loves man": {
            "draft_archetype": "🛡️ High-Floor Grinder",
            "draft_tendency": "Drafts safe floor scorers with solid weekly projections (8-6 record).",
            "reach_tendency": "Strict ADP follower.",
            "faab_style": "Conservative ($15 FAAB remaining, 38 moves).",
            "faab_aggressiveness_score": 50,
            "trade_frequency": "Moderate.",
            "vulnerabilities": "Lacks high-ceiling explosive players; vulnerable in high-scoring shootout weeks."
        },
        "2-1 vs Cobitchioner": {
            "draft_archetype": "🎯 Rivalry Specialist (2-12)",
            "draft_tendency": "Builds lineup specifically tailored to defeat The Commish.",
            "reach_tendency": "Volatile draft board.",
            "faab_style": "Fully Spent ($0 remaining).",
            "faab_aggressiveness_score": 60,
            "trade_frequency": "Selective.",
            "vulnerabilities": "Last place standing (2-12), $0 FAAB; easy to outbid on all targets."
        }
    }

    # User's Team Current Roster
    user_roster = [
        {"player_name": "Josh Allen", "pos": "QB", "team": "BUF", "slot": "QB", "status": "Healthy", "proj_pts": 382.5, "vorp": 98.4, "droppable": False, "role": "Elite Anchor"},
        {"player_name": "Breece Hall", "pos": "RB", "team": "NYJ", "slot": "RB1", "status": "Healthy", "proj_pts": 312.0, "vorp": 82.5, "droppable": False, "role": "Bellcow RB1"},
        {"player_name": "Kenneth Walker III", "pos": "RB", "team": "SEA", "slot": "RB2", "status": "Healthy", "proj_pts": 245.0, "vorp": 45.2, "droppable": False, "role": "Solid RB2"},
        {"player_name": "Amon-Ra St. Brown", "pos": "WR", "team": "DET", "slot": "WR1", "status": "Healthy", "proj_pts": 298.0, "vorp": 76.0, "droppable": False, "role": "Target Monster WR1"},
        {"player_name": "Garrett Wilson", "pos": "WR", "team": "NYJ", "slot": "WR2", "status": "Healthy", "proj_pts": 268.0, "vorp": 54.0, "droppable": False, "role": "Alpha WR2"},
        {"player_name": "Trey McBride", "pos": "TE", "team": "ARI", "slot": "TE", "status": "Healthy", "proj_pts": 195.0, "vorp": 42.0, "droppable": False, "role": "Top-4 TE"},
        {"player_name": "Rashee Rice", "pos": "WR", "team": "KC", "slot": "FLEX", "status": "Healthy", "proj_pts": 240.0, "vorp": 38.0, "droppable": False, "role": "High-Ceiling Flex"},
        {"player_name": "San Francisco 49ers", "pos": "DST", "team": "SF", "slot": "DST", "status": "Healthy", "proj_pts": 120.0, "vorp": 12.0, "droppable": True, "role": "Streaming Option"},
        {"player_name": "Brandon Aubrey", "pos": "K", "team": "DAL", "slot": "K", "status": "Healthy", "proj_pts": 142.0, "vorp": 15.0, "droppable": True, "role": "Elite Kicker"},
        # Bench Players (Droppability ranked)
        {"player_name": "Jaylen Wright", "pos": "RB", "team": "MIA", "slot": "BN", "status": "Healthy", "proj_pts": 155.0, "vorp": 12.5, "droppable": False, "role": "High-Upside Stash"},
        {"player_name": "Brian Thomas Jr.", "pos": "WR", "team": "JAX", "slot": "BN", "status": "Healthy", "proj_pts": 178.0, "vorp": 18.2, "droppable": False, "role": "Rookie Breakout WR"},
        {"player_name": "Chuba Hubbard", "pos": "RB", "team": "CAR", "slot": "BN", "status": "Questionable", "proj_pts": 148.0, "vorp": 8.0, "droppable": True, "role": "⚠️ Droppable / Sidelined Hamstring"},
        {"player_name": "Ricky Pearsall", "pos": "WR", "team": "SF", "slot": "BN", "status": "IR", "proj_pts": 60.0, "vorp": -15.0, "droppable": True, "role": "🚨 Prime Drop Candidate (Out with Knee Surgery)"},
        {"player_name": "Curtis Samuel", "pos": "WR", "team": "BUF", "slot": "BN", "status": "Healthy", "proj_pts": 130.0, "vorp": 2.0, "droppable": True, "role": "⚠️ Low-Ceiling Depth (Cut for Breakouts)"}
    ]

    # Available Free Agents & Waiver Wire Targets
    free_agents = [
        {
            "player_id": "fp_brooks",
            "player_name": "Jonathon Brooks",
            "pos": "RB",
            "team": "CAR",
            "status": "Waivers (Wed 3 AM)",
            "percent_rostered": 48.5,
            "ecr_rank": 82,
            "pos_rank": "RB28",
            "proj_pts": 215.0,
            "vorp": 38.5,
            "urgency": "CRITICAL 🚨",
            "category": "🚨 High-Priority Bellcow Breakout",
            "recommended_faab_pct": 32,
            "recommended_faab_bid": 32,
            "faab_bid_range": "$25 - $38",
            "rationale": "Named starter for preseason/camp after Hubbard hamstring injury. Instant RB2 volume in modern offense.",
            "target_drop": "Ricky Pearsall",
            "net_vorp_gain": "+53.5 VORP"
        },
        {
            "player_id": "fp_ladd",
            "player_name": "Ladd McConkey",
            "pos": "WR",
            "team": "LAC",
            "status": "Waivers (Wed 3 AM)",
            "percent_rostered": 52.0,
            "ecr_rank": 88,
            "pos_rank": "WR38",
            "proj_pts": 208.0,
            "vorp": 32.0,
            "urgency": "HIGH 🔥",
            "category": "⚡ Target Vacuum Slot WR",
            "recommended_faab_pct": 18,
            "recommended_faab_bid": 18,
            "faab_bid_range": "$14 - $22",
            "rationale": "Clear #1 target for Justin Herbert following Keenan Allen/Mike Williams exits. Heavy slot target share.",
            "target_drop": "Curtis Samuel",
            "net_vorp_gain": "+30.0 VORP"
        },
        {
            "player_id": "fp_daniels",
            "player_name": "Jayden Daniels",
            "pos": "QB",
            "team": "WAS",
            "status": "Free Agent (Instant Add)",
            "percent_rostered": 61.2,
            "ecr_rank": 95,
            "pos_rank": "QB11",
            "proj_pts": 325.0,
            "vorp": 41.0,
            "urgency": "HIGH 🔥",
            "category": "🏃 Dual-Threat Rushing Cheat Code",
            "recommended_faab_pct": 12,
            "recommended_faab_bid": 12,
            "faab_bid_range": "$8 - $15",
            "rationale": "Heisman dual-threat QB with 700+ rushing yard upside. Elite QB insurance behind Josh Allen or trade chip.",
            "target_drop": "Chuba Hubbard",
            "net_vorp_gain": "+33.0 VORP"
        },
        {
            "player_id": "fp_bucky",
            "player_name": "Bucky Irving",
            "pos": "RB",
            "team": "TB",
            "status": "Free Agent (Instant Add)",
            "percent_rostered": 24.0,
            "ecr_rank": 135,
            "pos_rank": "RB46",
            "proj_pts": 168.0,
            "vorp": 16.5,
            "urgency": "MEDIUM 💎",
            "category": "💎 Elite Handcuff / Standout Stash",
            "recommended_faab_pct": 8,
            "recommended_faab_bid": 8,
            "faab_bid_range": "$5 - $10",
            "rationale": "Passing-down weapon earning rave camp reviews. Immediate standalone flex if Rachaad White misses time.",
            "target_drop": "Curtis Samuel",
            "net_vorp_gain": "+14.5 VORP"
        },
        {
            "player_id": "fp_dortch",
            "player_name": "Greg Dortch",
            "pos": "WR",
            "team": "ARI",
            "status": "Free Agent (Instant Add)",
            "percent_rostered": 14.5,
            "ecr_rank": 155,
            "pos_rank": "WR64",
            "proj_pts": 152.0,
            "vorp": 10.0,
            "urgency": "SPECULATIVE 📈",
            "category": "📈 Deep PPR Slot Sleeper",
            "recommended_faab_pct": 4,
            "recommended_faab_bid": 4,
            "faab_bid_range": "$2 - $5",
            "rationale": "Operating as locked-in starting slot WR in Arizona; high target floor in 3-WR sets with Kyler Murray.",
            "target_drop": "Curtis Samuel",
            "net_vorp_gain": "+8.0 VORP"
        },
        {
            "player_id": "fp_likely",
            "player_name": "Isaiah Likely",
            "pos": "TE",
            "team": "BAL",
            "status": "Free Agent (Instant Add)",
            "percent_rostered": 31.0,
            "ecr_rank": 142,
            "pos_rank": "TE16",
            "proj_pts": 158.0,
            "vorp": 18.0,
            "urgency": "MEDIUM 💎",
            "category": "💎 Elite TE Handcuff & Red Zone Threat",
            "recommended_faab_pct": 6,
            "recommended_faab_bid": 6,
            "faab_bid_range": "$4 - $8",
            "rationale": "Top-5 TE ceiling whenever Mark Andrews is limited. Baltimore running expanded 12-personnel packages.",
            "target_drop": "Curtis Samuel",
            "net_vorp_gain": "+16.0 VORP"
        }
    ]

    # Recent League Transactions with FAAB Bids
    recent_transactions = [
        {"timestamp": "2 days ago", "type": "Waiver Claim", "team_name": "Cowboy Nation", "player_name": "Rico Dowdle (RB)", "faab_bid": 28, "status": "Won", "note": "Outbid Alex Miller ($22) & Marcus Cole ($15)"},
        {"timestamp": "3 days ago", "type": "Waiver Claim", "team_name": "FAAB Frenzy", "player_name": "Adonai Mitchell (WR)", "faab_bid": 35, "status": "Won", "note": "Outbid Kareem ($18) & Sarah Jenkins ($12)"},
        {"timestamp": "4 days ago", "type": "Free Agent Add", "team_name": "Kareem's Contenders", "player_name": "Jaylen Wright (RB)", "faab_bid": 0, "status": "Success", "note": "$0 Free Agent pickup post-waiver clearance"},
        {"timestamp": "5 days ago", "type": "Trade", "team_name": "Gridiron Overlords", "player_name": "Deebo Samuel for James Cook", "faab_bid": 0, "status": "Executed", "note": "Alex Miller swapped WR depth for RB1 starting security"},
        {"timestamp": "6 days ago", "type": "Waiver Claim", "team_name": "FAAB Frenzy", "player_name": "Tyrone Tracy Jr. (RB)", "faab_bid": 31, "status": "Won", "note": "Solo aggressive bid (No other bids submitted)"}
    ]

    return {
        "metadata": {
            "league_id": "1049281",
            "league_name": "Sweet n Sour Sundays (Redraft)",
            "season": "2026",
            "num_teams": 12,
            "waiver_type": "FAAB Bidding",
            "initial_budget": 100,
            "scoring": "Half-PPR",
            "roster_positions": "1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 K, 1 DST, 5 BN, 1 IR"
        },
        "teams": teams,
        "manager_profiles": manager_profiles,
        "user_roster": user_roster,
        "free_agents": free_agents,
        "recent_transactions": recent_transactions
    }

if __name__ == "__main__":
    client = YahooFantasyClient()
    print(f"Yahoo Client Authenticated: {client.is_authenticated()}")
    if not client.is_authenticated():
        if client.client_id:
            print(f"Authorization URL: {client.get_authorization_url()}")
        else:
            print("Set YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET in .env to authenticate live.")
    
    demo_data = get_demo_league_data()
    print(f"Demo League Loaded: {demo_data['metadata']['league_name']} ({len(demo_data['teams'])} teams)")
