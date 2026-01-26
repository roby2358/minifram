#!/usr/bin/env python3
"""
Blackjack MCP server for testing multi-round tool interactions.
Implements simplified blackjack over the Model Context Protocol via stdio.
"""
import json
import random
import sys
from typing import Any


class BlackjackGame:
    """Game state manager for a single blackjack session."""

    def __init__(self):
        self.dealer_hand: list[str] = []
        self.player_hand: list[str] = []
        self.dealer_hidden_card: str | None = None

    def draw_card(self) -> str:
        """Draw a random card from the deck."""
        cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        return random.choice(cards)

    def calculate_hand_value(self, hand: list[str]) -> int:
        """Calculate the best value for a hand, handling aces optimally."""
        value = 0
        aces = 0

        for card in hand:
            if card in ['J', 'Q', 'K']:
                value += 10
            elif card == 'A':
                aces += 1
                value += 11  # Start with 11
            else:
                value += int(card)

        # Adjust aces from 11 to 1 if needed to avoid bust
        while value > 21 and aces > 0:
            value -= 10  # Convert one ace from 11 to 1
            aces -= 1

        return value

    def format_dealer_cards(self, reveal: bool) -> str:
        """Format dealer cards, hiding first card unless revealed."""
        if reveal or not self.dealer_hidden_card:
            return ' '.join(self.dealer_hand)

        # Show X for hidden first card, then only the face-up cards
        return 'X ' + ' '.join(self.dealer_hand[1:])

    def format_state(self, reveal_dealer: bool = False) -> str:
        """Format the current game state as a string."""
        dealer_cards = self.format_dealer_cards(reveal_dealer)
        player_cards = ' '.join(self.player_hand)
        return f"Dealer: {dealer_cards}\nPlayer: {player_cards}"

    def check_immediate_win(self) -> str | None:
        """Check for immediate wins on initial deal.

        Returns:
            Win message if someone has 21, None otherwise
        """
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)

        if player_value == 21:
            return "\nPlayer wins!"
        if dealer_value == 21:
            return "\nDealer wins!"

        return None

    def determine_winner(self, dealer_value: int, player_value: int) -> str:
        """Determine the winner based on final hand values.

        Returns:
            Win message describing the outcome
        """
        if dealer_value > 21:
            return "\nPlayer wins!"
        elif dealer_value == player_value:
            return "\nPush! Dealer wins!"
        elif dealer_value > player_value:
            return "\nDealer wins!"
        else:
            return "\nPlayer wins!"

    def deal(self) -> str:
        """Start a new hand."""
        # Reset state
        self.dealer_hand = []
        self.player_hand = []
        self.dealer_hidden_card = None

        # Deal two cards to dealer
        self.dealer_hand.append(self.draw_card())
        self.dealer_hand.append(self.draw_card())
        self.dealer_hidden_card = self.dealer_hand[0]  # First card is hidden

        # Deal two cards to player
        self.player_hand.append(self.draw_card())
        self.player_hand.append(self.draw_card())

        # Check for immediate wins
        win_message = self.check_immediate_win()
        if win_message:
            return self.format_state(reveal_dealer=True) + win_message

        return self.format_state()

    def hit(self) -> str:
        """Deal one additional card to the player."""
        self.player_hand.append(self.draw_card())
        player_value = self.calculate_hand_value(self.player_hand)

        if player_value > 21:
            return self.format_state(reveal_dealer=True) + "\nBust! Dealer wins!"

        return self.format_state()

    def stay(self) -> str:
        """Reveal dealer's hand and play out dealer's turn."""
        # Dealer draws until reaching 17 or higher
        while self.calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw_card())

        dealer_value = self.calculate_hand_value(self.dealer_hand)
        player_value = self.calculate_hand_value(self.player_hand)

        win_message = self.determine_winner(dealer_value, player_value)
        return self.format_state(reveal_dealer=True) + win_message


# Global game state
game = BlackjackGame()


def send_message(msg: dict[str, Any]):
    """Send JSON-RPC message to stdout."""
    output = json.dumps(msg) + "\n"
    sys.stdout.write(output)
    sys.stdout.flush()


def build_success_response(request_id: Any, text: str) -> dict[str, Any]:
    """Build a successful tool call response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
    }


def build_error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """Build an error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }


def get_tool_definitions() -> list[dict]:
    """Get the list of available blackjack tools."""
    return [
        {
            "name": "blackjack_deal",
            "description": "Server is dealer. Start new hand: deals 2 cards each, first dealer card hidden.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "blackjack_hit",
            "description": "Server deals one card to player. Call this tool for each hit - don't simulate.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "blackjack_stay",
            "description": "Player stands. Server reveals and plays dealer hand to 17+, determines winner.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]


def build_initialize_response(request_id: Any) -> dict[str, Any]:
    """Build the MCP initialize response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "blackjack-server",
                "version": "0.1.0"
            }
        }
    }


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Handle incoming JSON-RPC request."""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Initialize
    if method == "initialize":
        return build_initialize_response(request_id)

    # List available tools
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": get_tool_definitions()
            }
        }

    # Call a tool
    elif method == "tools/call":
        tool_name = params.get("name")

        try:
            if tool_name == "blackjack_deal":
                result_text = game.deal()
            elif tool_name == "blackjack_hit":
                result_text = game.hit()
            elif tool_name == "blackjack_stay":
                result_text = game.stay()
            else:
                return build_error_response(
                    request_id, -32601, f"Unknown tool: {tool_name}"
                )

            return build_success_response(request_id, result_text)

        except Exception as e:
            return build_error_response(
                request_id, -32603, f"Tool execution error: {str(e)}"
            )

    # Unknown method
    else:
        return build_error_response(
            request_id, -32601, f"Method not found: {method}"
        )


def main():
    """Main server loop - read from stdin, write to stdout."""
    sys.stderr.write("Blackjack MCP server started\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)
            send_message(response)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"JSON decode error: {e}\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
