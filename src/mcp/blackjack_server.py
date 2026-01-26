#!/usr/bin/env python3
"""Blackjack MCP server for testing multi-round tool interactions."""
import random

from fastmcp import FastMCP

mcp = FastMCP("blackjack-server")


class BlackjackGame:
    """Game state manager for a single blackjack session."""

    def __init__(self):
        self.dealer_hand: list[str] = []
        self.player_hand: list[str] = []
        self.dealer_hidden_card: str | None = None
        self.hand_in_play: bool = False

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
                value += 11
            else:
                value += int(card)

        while value > 21 and aces > 0:
            value -= 10
            aces -= 1

        return value

    def format_dealer_cards(self, reveal: bool) -> str:
        """Format dealer cards, hiding first card unless revealed."""
        if reveal or not self.dealer_hidden_card:
            return ' '.join(self.dealer_hand)
        return 'X ' + ' '.join(self.dealer_hand[1:])

    def format_state(self, reveal_dealer: bool = False) -> str:
        """Format the current game state as a string."""
        dealer_cards = self.format_dealer_cards(reveal_dealer)
        player_cards = ' '.join(self.player_hand)
        return f"Dealer: {dealer_cards}\nPlayer: {player_cards}"

    def check_immediate_win(self) -> str | None:
        """Check for immediate wins on initial deal."""
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)

        if player_value == 21:
            return "\nPlayer wins!"
        if dealer_value == 21:
            return "\nDealer wins!"
        return None

    def determine_winner(self, dealer_value: int, player_value: int) -> str:
        """Determine the winner based on final hand values."""
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
        self.dealer_hand = []
        self.player_hand = []
        self.dealer_hidden_card = None
        self.hand_in_play = True

        self.dealer_hand = [self.draw_card(), self.draw_card()]
        self.dealer_hidden_card = self.dealer_hand[0]
        self.player_hand = [self.draw_card(), self.draw_card()]

        win_message = self.check_immediate_win()
        if win_message:
            self.hand_in_play = False
            return self.format_state(reveal_dealer=True) + win_message

        return self.format_state() + "\nCall blackjack_hit or blackjack_stand to continue."

    def hit(self) -> str:
        """Deal one additional card to the player."""
        if not self.hand_in_play:
            return "No hand in progress. Call blackjack_deal to start a new hand."

        self.player_hand.append(self.draw_card())
        player_value = self.calculate_hand_value(self.player_hand)

        if player_value > 21:
            self.hand_in_play = False
            return self.format_state(reveal_dealer=True) + "\nBust! Dealer wins!"

        return self.format_state() + "\nCall blackjack_hit or blackjack_stand to continue."

    def stand(self) -> str:
        """Reveal dealer's hand and play out dealer's turn."""
        if not self.hand_in_play:
            return "No hand in progress. Call blackjack_deal to start a new hand."

        self.hand_in_play = False

        while self.calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw_card())

        dealer_value = self.calculate_hand_value(self.dealer_hand)
        player_value = self.calculate_hand_value(self.player_hand)

        return self.format_state(reveal_dealer=True) + self.determine_winner(dealer_value, player_value)


# Global game state
game = BlackjackGame()


@mcp.tool()
def blackjack_deal() -> str:
    """YOU are the player. Start new hand - MUST call this tool to get cards."""
    return game.deal()


@mcp.tool()
def blackjack_hit() -> str:
    """Request another card. MUST call this tool - don't just say 'hit'."""
    return game.hit()


@mcp.tool()
def blackjack_stand() -> str:
    """Keep current hand. MUST call this tool - don't just say 'stand'."""
    return game.stand()


if __name__ == "__main__":
    mcp.run()
