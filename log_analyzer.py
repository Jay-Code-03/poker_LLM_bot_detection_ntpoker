# log_analyzer.py
import os
import json
import argparse
from tabulate import tabulate

def list_sessions(log_dir="logs"):
    """List all available sessions"""
    if not os.path.exists(log_dir):
        print(f"Log directory '{log_dir}' not found.")
        return []
        
    sessions = [d for d in os.listdir(log_dir) if d.startswith("session_")]
    sessions.sort(reverse=True)  # Most recent first
    return sessions

def load_session(session_name, log_dir="logs"):
    """Load a session's JSON data"""
    json_path = os.path.join(log_dir, session_name, "session.json")
    
    if not os.path.exists(json_path):
        print(f"Session file not found: {json_path}")
        return None
        
    with open(json_path, 'r') as f:
        return json.load(f)

def summarize_session(session_data):
    """Generate a summary of the session"""
    if not session_data:
        return
        
    # Extract hand summaries
    hand_summaries = [entry for entry in session_data if entry['type'] == 'hand_summary']
    
    # Count actions by type
    action_counts = {}
    for entry in session_data:
        if entry['type'] == 'action':
            action = entry['data']['action']
            action_counts[action] = action_counts.get(action, 0) + 1
    
    print(f"Session Summary:")
    print(f"Total hands played: {len(hand_summaries)}")
    print(f"Action breakdown:")
    for action, count in action_counts.items():
        print(f"  - {action}: {count}")
        
    # Print hand details in a table
    hands_data = []
    for hand in hand_summaries:
        hero_cards = ', '.join(hand['data']['hero_cards'])
        community_cards = ', '.join(hand['data']['community_cards'])
        pot_type = hand['data']['preflop_pot_type']
        
        # Count hero actions
        hero_actions = [a for a in hand['data']['actions'] if a['player'] == 'hero']
        action_summary = ', '.join([a['action_type'] for a in hero_actions])
        
        hands_data.append([
            hand['hand_id'],
            hero_cards,
            community_cards,
            pot_type,
            action_summary
        ])
    
    if hands_data:
        print("\nHand Summary:")
        print(tabulate(hands_data, headers=["Hand #", "Hero Cards", "Community Cards", "Pot Type", "Hero Actions"]))

def main():
    parser = argparse.ArgumentParser(description='Analyze poker bot logs')
    parser.add_argument('--list', action='store_true', help='List available sessions')
    parser.add_argument('--session', type=str, help='Analyze a specific session')
    
    args = parser.parse_args()
    
    if args.list:
        sessions = list_sessions()
        if sessions:
            print("Available sessions:")
            for i, session in enumerate(sessions):
                print(f"{i+1}. {session}")
        else:
            print("No sessions found.")
            
    elif args.session:
        data = load_session(args.session)
        if data:
            summarize_session(data)
    else:
        # Default: show most recent session
        sessions = list_sessions()
        if sessions:
            print(f"Analyzing most recent session: {sessions[0]}")
            data = load_session(sessions[0])
            if data:
                summarize_session(data)
        else:
            print("No sessions found.")

if __name__ == "__main__":
    main()