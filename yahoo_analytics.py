#!/usr/bin/env python3
"""
Yahoo Fantasy Analytics Engine:
- Manager Tendencies & Historical Scouting
- Real-Time Waiver Wire Arbitrage & VORP Calculation
- FAAB Bid Optimization & Game Theory Calibrator
- Drop/Add Roster Optimizer
"""

import os
import math
import logging
from typing import Dict, List, Any, Optional
import duckdb
import pandas as pd

logger = logging.getLogger("YahooAnalytics")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(PROJECT_DIR, "draft_vault.duckdb")

def get_duckdb_connection():
    """Connects to the local DuckDB database."""
    if not os.path.exists(DB_FILE):
        return None
    return duckdb.connect(DB_FILE, read_only=True)

def analyze_manager_tendencies(teams_data: List[Dict[str, Any]], custom_profiles: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Analyzes historical habits, spending rates, and behavior for all managers in the league.
    """
    scouted_managers = []
    
    for t in teams_data:
        mgr_name = t.get("manager_name", t.get("team_name", "Unknown"))
        faab_balance = t.get("faab_balance", 100)
        initial_budget = 100
        faab_spent = max(0, initial_budget - faab_balance)
        spend_pct = round((faab_spent / initial_budget) * 100, 1)

        # Baseline heuristic traits
        if custom_profiles and mgr_name in custom_profiles:
            profile = custom_profiles[mgr_name]
            archetype = profile.get("draft_archetype", "Balanced Strategist")
            draft_tendency = profile.get("draft_tendency", "Standard consensus drafter.")
            reach_tendency = profile.get("reach_tendency", "Follows ADP closely.")
            faab_style = profile.get("faab_style", f"Spent ${faab_spent} of ${initial_budget}.")
            faab_score = profile.get("faab_aggressiveness_score", int(spend_pct))
            trade_freq = profile.get("trade_frequency", "Moderate")
            vulnerabilities = profile.get("vulnerabilities", "Standard roster balance.")
        else:
            # Dynamic calculation from metrics
            if spend_pct >= 70:
                archetype = "🔥 Splash Spender / Waiver Addict"
                faab_score = 90
                faab_style = f"Aggressive Churner (${faab_spent} spent already). Constantly attacks waiver wire."
                vulnerabilities = f"Extremely low remaining FAAB (${faab_balance}). Cannot contest medium-to-large bids."
            elif spend_pct <= 15:
                archetype = "⏳ FAAB Bank Fortress / Hoarder"
                faab_score = 20
                faab_style = f"Ultra-Conservative (${faab_spent} spent). Holds budget for late-season crises."
                vulnerabilities = "Reluctant to submit bids over $15; easy to out-maneuver on high-upside breakouts."
            else:
                archetype = "⚖️ Balanced Value Manager"
                faab_score = 50
                faab_style = f"Calculated Bidder (${faab_spent} spent, ${faab_balance} remaining)."
                vulnerabilities = "Disciplined budget management; requires tactical bid sizing."
            
            draft_tendency = "Follows standard draft ADP with occasional positional runs."
            reach_tendency = "Average draft variance."
            trade_freq = "Moderate"

        scouted_managers.append({
            "team_id": t.get("team_id"),
            "team_name": t.get("team_name"),
            "manager_name": mgr_name,
            "rank": t.get("rank", 1),
            "record": f"{t.get('wins', 0)}-{t.get('losses', 0)}",
            "points_for": t.get("points_for", 0.0),
            "points_against": t.get("points_against", 0.0),
            "faab_balance": faab_balance,
            "faab_spent": faab_spent,
            "spend_pct": spend_pct,
            "archetype": archetype,
            "faab_score": faab_score,
            "draft_tendency": draft_tendency,
            "reach_tendency": reach_tendency,
            "faab_style": faab_style,
            "trade_frequency": trade_freq,
            "vulnerabilities": vulnerabilities
        })

    # Sort by standings rank
    scouted_managers.sort(key=lambda x: x["rank"])
    return scouted_managers

def calculate_faab_recommendations(
    free_agents: List[Dict[str, Any]], 
    league_teams: List[Dict[str, Any]],
    user_team_name: str = "Kareem's Contenders (You)"
) -> List[Dict[str, Any]]:
    """
    Computes game-theory calibrated FAAB bidding recommendations for every available waiver target.
    Accounts for remaining budgets of rival managers.
    """
    # Find user FAAB and rival maximum FAAB
    user_faab = 100
    rival_max_faab = 0
    faab_distribution = []
    
    for t in league_teams:
        bal = t.get("faab_balance", 100)
        t_name = t.get("team_name", "")
        if user_team_name.lower() in t_name.lower():
            user_faab = bal
        else:
            faab_distribution.append(bal)
            if bal > rival_max_faab:
                rival_max_faab = bal

    processed_waivers = []
    
    for p in free_agents:
        ecr = p.get("ecr_rank", 150)
        vorp = p.get("vorp", 10.0)
        pos = p.get("pos", "FLEX")
        pct_owned = p.get("percent_rostered", 20.0)
        
        # Base bid percent based on ECR & VORP
        if ecr <= 90 or vorp >= 35.0:
            urgency = "CRITICAL 🚨"
            cat = "🚨 High-Priority Bellcow Breakout"
            base_pct = 30
            bid_low_pct = 22
            bid_high_pct = 40
        elif ecr <= 120 or vorp >= 25.0:
            urgency = "HIGH 🔥"
            cat = "⚡ High-Target / High-Ceiling Starter"
            base_pct = 16
            bid_low_pct = 12
            bid_high_pct = 22
        elif ecr <= 150 or vorp >= 15.0:
            urgency = "MEDIUM 💎"
            cat = "💎 Premium Handcuff / Spot Starter"
            base_pct = 8
            bid_low_pct = 5
            bid_high_pct = 12
        else:
            urgency = "SPECULATIVE 📈"
            cat = "📈 Speculative Stash / Matchup Streamer"
            base_pct = 3
            bid_low_pct = 1
            bid_high_pct = 5

        # Dynamic Dollar Bids ($100 budget standard)
        target_bid = max(1, round(100 * (base_pct / 100)))
        bid_low = max(0, round(100 * (bid_low_pct / 100)))
        bid_high = max(1, round(100 * (bid_high_pct / 100)))
        
        # Cap high bid at user's available balance
        target_bid = min(target_bid, user_faab)
        bid_high = min(bid_high, user_faab)

        # Game Theory Lockout note if opponent max budget is lower
        game_theory_note = ""
        if rival_max_faab < target_bid and rival_max_faab < user_faab:
            lockout_bid = rival_max_faab + 1
            game_theory_note = f"🎯 100% Lockout Guarantee: Bid ${lockout_bid} to mathematically outbid the entire league!"

        processed_waivers.append({
            "player_id": p.get("player_id"),
            "player_name": p.get("player_name"),
            "pos": pos,
            "team": p.get("team"),
            "status": p.get("status", "Available"),
            "percent_rostered": pct_owned,
            "ecr_rank": ecr,
            "pos_rank": p.get("pos_rank", f"{pos}{ecr}"),
            "proj_pts": p.get("proj_pts", 150.0),
            "vorp": vorp,
            "urgency": p.get("urgency", urgency),
            "category": p.get("category", cat),
            "target_bid": p.get("recommended_faab_bid", target_bid),
            "bid_low": bid_low,
            "bid_high": bid_high,
            "bid_range": p.get("faab_bid_range", f"${bid_low} - ${bid_high}"),
            "rationale": p.get("rationale", f"Top available {pos} on waivers with {vorp} VORP."),
            "target_drop": p.get("target_drop", "Lowest Bench Asset"),
            "net_vorp_gain": p.get("net_vorp_gain", f"+{round(max(5.0, vorp - 5.0), 1)} VORP"),
            "game_theory_note": game_theory_note
        })

    # Sort by urgency and VORP
    processed_waivers.sort(key=lambda x: (x["ecr_rank"], -x["vorp"]))
    return processed_waivers

def evaluate_drop_add_pairs(user_roster: List[Dict[str, Any]], waiver_targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifies the best drop candidates on user's bench and matches them with top waiver additions.
    """
    # Filter bench players
    bench_players = [p for p in user_roster if p.get("slot") in ["BN", "IR"] or p.get("droppable", False)]
    # Sort bench players by droppability (lowest VORP first, IR/injured priority)
    bench_players.sort(key=lambda x: (0 if x.get("status") in ["IR", "Out"] else 1, x.get("vorp", 0.0)))

    recommendations = []
    
    for w in waiver_targets[:6]: # Top 6 waiver targets
        if not bench_players:
            break
            
        best_drop = bench_players[0] # Prime drop candidate
        w_vorp = w.get("vorp", 0.0)
        d_vorp = best_drop.get("vorp", 0.0)
        net_gain = round(w_vorp - d_vorp, 1)

        recommendations.append({
            "add_player": w.get("player_name"),
            "add_pos": w.get("pos"),
            "add_team": w.get("team"),
            "add_vorp": w_vorp,
            "add_urgency": w.get("urgency"),
            "drop_player": best_drop.get("player_name"),
            "drop_pos": best_drop.get("pos"),
            "drop_team": best_drop.get("team"),
            "drop_status": best_drop.get("status"),
            "drop_vorp": d_vorp,
            "drop_reason": best_drop.get("role", "Bench depth"),
            "net_vorp_upgrade": f"+{net_gain} VORP" if net_gain > 0 else f"{net_gain} VORP",
            "recommended_bid": w.get("bid_range", "$5 - $15"),
            "action_priority": "🔥 Immediate Action" if net_gain >= 20 else "✅ Solid Upgrade"
        })

    return recommendations

if __name__ == "__main__":
    from yahoo_service import get_demo_league_data
    demo = get_demo_league_data()
    scouted = analyze_manager_tendencies(demo["teams"], demo["manager_profiles"])
    print(f"Scouted {len(scouted)} managers.")
    waivers = calculate_faab_recommendations(demo["free_agents"], demo["teams"])
    print(f"Processed {len(waivers)} waiver targets.")
    pairs = evaluate_drop_add_pairs(demo["user_roster"], waivers)
    print(f"Generated {len(pairs)} Drop/Add recommendations.")
